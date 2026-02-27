"""
Structured Response Types for Routing.

This module provides structured response types for RFC 9457 Problem Details
and OpenAI-compatible error formats.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProblemDetails:
    """
    RFC 9457 Problem Details for HTTP APIs.

    Example:
    {
        "type": "https://api.chutes.ai/problems/routing-failure",
        "title": "Routing Failed",
        "status": 503,
        "detail": "All chutes unavailable after degradation cascade",
        "instance": "/v1/chat/completions"
    }
    """

    type: str
    title: str
    status: int
    detail: str
    instance: str
    extensions: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": self.instance,
        }
        if self.extensions:
            result.update(self.extensions)
        return result


@dataclass
class OpenAIError:
    """
    OpenAI-compatible error format.

    Example:
    {
        "error": {
            "message": "All chutes unavailable",
            "type": "server_error",
            "code": "routing_failure",
            "param": None
        }
    }
    """

    message: str
    error_type: str
    code: str
    param: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "code": self.code,
                "param": self.param,
            }
        }


class DegradationLevel:
    """Degradation levels for routing."""

    FULL = 0  # All metrics available
    CACHED = 1  # Using cached metrics
    UTILIZATION = 2  # Utilization only
    RANDOM = 3  # Random selection (fallback)
    FAILED = 4  # Complete failure

    @staticmethod
    def to_string(level: int) -> str:
        """Get human-readable degradation level."""
        reasons = {
            0: "Full metrics available",
            1: "Using cached metrics",
            2: "Using utilization only",
            3: "Random selection (metrics unavailable)",
            4: "Complete failure",
        }
        return reasons.get(level, "Unknown")


class ResponseBuilder:
    """
    Builds structured responses for routing decisions.

    Supports both RFC 9457 Problem Details and OpenAI-compatible
    error formats.
    """

    PROBLEM_BASE_URL = "https://api.chutes.ai/problems"

    def __init__(self, base_path: str = "/v1/chat/completions"):
        self.base_path = base_path
        self.logger = logging.getLogger(__name__)

    def build_success(
        self,
        deployment: Dict[str, Any],
        degradation_level: int = 0,
    ) -> Dict[str, Any]:
        """
        Build successful deployment response.

        Args:
            deployment: Selected deployment dictionary
            degradation_level: 0=full, 1=cached, 2=utilization, 3=random

        Returns:
            Deployment dictionary with metadata
        """
        response = deployment.copy()
        response["_routing_metadata"] = {
            "degradation_level": degradation_level,
            "degradation_reason": DegradationLevel.to_string(degradation_level),
        }
        return response

    def build_error(
        self,
        error_type: str,
        message: str,
        status_code: int = 503,
        code: str = "routing_failure",
        param: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build error response with both formats.

        Args:
            error_type: OpenAI error type (e.g., "server_error")
            message: Human-readable error message
            status_code: HTTP status code
            code: Error code for categorization
            param: Parameter that caused error (if applicable)

        Returns:
            Dict with both problem_details and openai_error
        """
        problem = ProblemDetails(
            type=f"{self.PROBLEM_BASE_URL}/{code}",
            title=error_type.replace("_", " ").title(),
            status=status_code,
            detail=message,
            instance=self.base_path,
            extensions={"code": code},
        )

        openai_error = OpenAIError(
            message=message,
            error_type=error_type,
            code=code,
            param=param,
        )

        return {
            "problem_details": problem.to_dict(),
            "openai_error": openai_error.to_dict(),
            "status_code": status_code,
        }

    def build_problem_details(
        self,
        title: str,
        detail: str,
        status: int = 503,
        code: str = "routing_failure",
    ) -> ProblemDetails:
        """Build standalone RFC 9457 Problem Details."""
        return ProblemDetails(
            type=f"{self.PROBLEM_BASE_URL}/{code}",
            title=title,
            status=status,
            detail=detail,
            instance=self.base_path,
            extensions={"code": code},
        )

    def build_error_response(
        self,
        error_type: str,
        message: str,
        status_code: int = 503,
        code: str = "routing_failure",
        param: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build complete error response with both RFC 9457 and OpenAI formats.

        This is the main entry point for building error responses.
        """
        result = self.build_error(
            error_type=error_type,
            message=message,
            status_code=status_code,
            code=code,
            param=param,
        )
        # Merge both formats at root level for maximum compatibility
        response = result["openai_error"].copy()
        response["problem_details"] = result["problem_details"]
        response["_routing_metadata"] = {
            "degradation_level": DegradationLevel.FAILED,
            "degradation_reason": DegradationLevel.to_string(DegradationLevel.FAILED),
        }
        return response
