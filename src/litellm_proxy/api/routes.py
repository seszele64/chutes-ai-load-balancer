"""
FastAPI Routes for Chutes Routing API.

This module provides HTTP endpoints for the intelligent routing system,
including health checks, metrics, and chat completions.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from litellm_proxy.routing.intelligent import IntelligentMultiMetricRouting
from litellm_proxy.routing.responses import DegradationLevel, ResponseBuilder
from litellm_proxy.exceptions import (
    ChutesRoutingError,
    DegradationExhaustedError,
    EmptyModelListError,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)


# Global routing instance - will be set by start_litellm.py
_routing_instance: Optional[IntelligentMultiMetricRouting] = None
_model_list: List[Dict[str, Any]] = []

# Prometheus metrics
_metrics = {
    "requests_total": {"success": 0, "degraded": 0, "failed": 0},
    "degradation_level": 0,
    "circuit_breaker_state": 0,  # 0=closed, 1=open, 2=half-open
    "last_request_time": 0.0,
}


def set_routing_instance(
    routing: IntelligentMultiMetricRouting, model_list: List[Dict[str, Any]]
):
    """Set the global routing instance and model list."""
    global _routing_instance, _model_list
    _routing_instance = routing
    _model_list = model_list
    logger.info("Routing instance and model list set for API routes")


def get_routing_instance() -> IntelligentMultiMetricRouting:
    """Get the current routing instance."""
    if _routing_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing not initialized",
        )
    return _routing_instance


router = APIRouter()

# Response builder instance
_response_builder = ResponseBuilder()


# ============================================================
# Helper Functions
# ============================================================


def _update_metrics(status: str, degradation_level: int):
    """Update internal metrics counters."""
    _metrics["requests_total"][status] += 1
    _metrics["degradation_level"] = degradation_level
    _metrics["last_request_time"] = time.time()


def _get_circuit_breaker_state_value() -> int:
    """Convert circuit breaker state to numeric value for Prometheus."""
    routing = _routing_instance
    if not routing or not routing._circuit_breaker:
        return 0

    state = routing._circuit_breaker.state.value
    if state == "closed":
        return 0
    elif state == "open":
        return 1
    elif state == "half_open":
        return 2
    return 0


def _build_rfc9457_error(
    message: str,
    error_type: str = "server_error",
    code: str = "routing_failed",
    status_code: int = 503,
    instance: str = "/v1/chat/completions",
) -> Dict[str, Any]:
    """Build RFC 9457 compliant error response."""
    problem = _response_builder.build_problem_details(
        title=error_type.replace("_", " ").title(),
        detail=message,
        status=status_code,
        code=code,
    )

    openai_error = {
        "error": {
            "message": message,
            "type": error_type,
            "code": code,
            "param": None,
        }
    }

    # Merge both formats
    response = openai_error.copy()
    response["problem_details"] = problem.to_dict()
    response["_routing_metadata"] = {
        "degradation_level": DegradationLevel.FAILED,
        "degradation_reason": DegradationLevel.to_string(DegradationLevel.FAILED),
    }

    return response


# ============================================================
# Endpoints
# ============================================================


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint with routing subsystem status.

    Returns 200 even if degraded (includes status in body).
    Returns 503 only if completely unhealthy.
    """
    routing = get_routing_instance()
    health_status = routing.get_health_status()

    # Determine HTTP status code based on health
    if health_status["status"] == "unhealthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status,
        )

    # Return 200 for healthy or degraded
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=health_status,
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format:
    - chutes_routing_degradation_level - Current degradation level (0-4)
    - chutes_circuit_breaker_state - Circuit breaker state (0=closed, 1=open, 2=half-open)
    - chutes_routing_requests_total - Total routing requests by status
    """
    cb_state = _get_circuit_breaker_state_value()

    lines = []

    # Degradation level gauge
    lines.append(
        "# HELP chutes_routing_degradation_level Current degradation level (0-4)"
    )
    lines.append("# TYPE chutes_routing_degradation_level gauge")
    lines.append(f"chutes_routing_degradation_level {_metrics['degradation_level']}")
    lines.append("")

    # Circuit breaker state gauge
    lines.append(
        "# HELP chutes_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half-open)"
    )
    lines.append("# TYPE chutes_circuit_breaker_state gauge")
    lines.append(f"chutes_circuit_breaker_state {cb_state}")
    lines.append("")

    # Request counters
    lines.append("# HELP chutes_routing_requests_total Total routing requests")
    lines.append("# TYPE chutes_routing_requests_total counter")
    for status_label, count in _metrics["requests_total"].items():
        lines.append(
            f'chutes_routing_requests_total{{status="{status_label}"}} {count}'
        )
    lines.append("")

    return "\n".join(lines)


@router.get("/v1/models")
async def list_models() -> JSONResponse:
    """
    List available models.

    Returns 200 with model list on success.
    Returns 503 if routing is unavailable.
    """
    routing = get_routing_instance()

    try:
        # Build model list from routing
        models = []
        for model_config in _model_list:
            model_info = model_config.get("model_info", {})
            litellm_params = model_config.get("litellm_params", {})

            model = {
                "id": model_info.get("id", litellm_params.get("model", "")),
                "object": "model",
                "created": 1700000000,  # Placeholder
                "owned_by": "chutes",
                "permission": [],
            }
            models.append(model)

        # Get health status for response headers
        health = routing.get_health_status()

        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "object": "list",
                "data": models,
            },
            headers={
                "X-Degradation-Level": str(health.get("degradation_level", 0)),
            },
        )

        _update_metrics("success", health.get("degradation_level", 0))
        return response

    except ChutesRoutingError as e:
        logger.error(f"Routing error in /v1/models: {e}")
        _update_metrics("failed", DegradationLevel.FAILED)

        error_response = _build_rfc9457_error(
            message=str(e),
            error_type="server_error",
            code="routing_error",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.FAILED)},
        )


@router.post("/v1/chat/completions")
async def chat_completions(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    """
    Chat completions endpoint with intelligent routing.

    Routes requests to the best available model based on
    multi-metric scoring (TPS, TTFT, quality, utilization).

    Returns:
    - 200 OK with deployment info (any degradation level 1-3)
    - 503 Service Unavailable for complete failure (degradation level 4)

    Headers:
    - X-Degradation-Level: 0-4 (which degradation level was used)
    """
    routing = get_routing_instance()

    # Extract model name from request
    model = body.get("model", "")

    try:
        # Get deployment using routing strategy
        # This calls the custom routing strategy
        deployment = routing.get_available_deployment(
            model=model,
            messages=body.get("messages", []),
            request_kwargs={"router": getattr(routing, "router", None)},
        )

        # Extract degradation level from response metadata
        degradation_level = deployment.get("_routing_metadata", {}).get(
            "degradation_level", DegradationLevel.FULL
        )

        # Update metrics
        if degradation_level == DegradationLevel.FAILED:
            _update_metrics("failed", degradation_level)
        elif degradation_level > 0:
            _update_metrics("degraded", degradation_level)
        else:
            _update_metrics("success", degradation_level)

        # Build response
        response_content = {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",  # Actual response would come from the model
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "_routing_metadata": deployment.get("_routing_metadata", {}),
            "_deployment": {
                "model": deployment.get("litellm_params", {}).get("model", ""),
                "api_base": deployment.get("litellm_params", {}).get("api_base", ""),
            },
        }

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_content,
            headers={
                "X-Degradation-Level": str(degradation_level),
                "Content-Type": "application/json",
            },
        )

    except DegradationExhaustedError as e:
        logger.error(f"All degradation levels exhausted: {e}")
        _update_metrics("failed", DegradationLevel.FAILED)

        error_response = _build_rfc9457_error(
            message=f"All degradation levels exhausted: {', '.join(e.levels_attempted)}",
            error_type="server_error",
            code="routing_failed",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.FAILED)},
        )

    except EmptyModelListError as e:
        logger.error(f"No model list available: {e}")
        _update_metrics("failed", DegradationLevel.FAILED)

        error_response = _build_rfc9457_error(
            message=str(e),
            error_type="invalid_request_error",
            code="no_models",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.FAILED)},
        )

    except CircuitBreakerOpenError as e:
        logger.warning(f"Circuit breaker open: {e}")
        _update_metrics("degraded", DegradationLevel.CACHED)

        error_response = _build_rfc9457_error(
            message=str(e),
            error_type="server_error",
            code="circuit_breaker_open",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.CACHED)},
        )

    except ChutesRoutingError as e:
        logger.error(f"Routing error: {e}")
        _update_metrics("failed", DegradationLevel.FAILED)

        error_response = _build_rfc9457_error(
            message=str(e),
            error_type="server_error",
            code="routing_error",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.FAILED)},
        )

    except Exception as e:
        logger.error(f"Unexpected error in chat completions: {e}")
        _update_metrics("failed", DegradationLevel.FAILED)

        error_response = _build_rfc9457_error(
            message=f"Internal server error: {str(e)}",
            error_type="server_error",
            code="internal_error",
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response,
            media_type="application/problem+json",
            headers={"X-Degradation-Level": str(DegradationLevel.FAILED)},
        )


# ============================================================
# Utility Endpoints
# ============================================================


@router.get("/v1")
async def v1_root() -> Dict[str, str]:
    """Root endpoint for v1 API."""
    return {
        "object": "root",
        "api_version": "v1",
    }


@router.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with API info."""
    return {
        "object": "service",
        "provider": "chutes",
        "routing": "intelligent-multi-metric",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
        },
    }
