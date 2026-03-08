# Design: API Structured Responses

## Overview

This document details the technical design for implementing structured error responses in the intelligent routing system. The design addresses the problem of returning `None` values from routing methods and implements graceful degradation with circuit breaker protection.

## Architecture Overview

The structured response system integrates into the existing routing architecture with three new components:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LiteLLM Router                                │
│                         (http://localhost:4000)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   IntelligentMultiMetricRouting                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    Circuit Breaker Layer                            │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │ │
│  │   │   CLOSED    │─▶│    OPEN     │─▶│  HALF-OPEN   │                 │ │
│  │   │  Normal ops │  │  Degraded   │  │   Testing   │                 │ │
│  │   └─────────────┘  └─────────────┘  └─────────────┘                 │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                  Degradation Strategy Layer                         │ │
│  │   Level 1: Cached → Level 2: Utilization → Level 3: Random → Ex    │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│      ChutesAPIClient            │   │      Response Builder           │
│  - get_utilization()            │   │  - build_success()              │
│  - get_llm_stats()              │   │  - build_error()                │
│  - get_deployment_metrics()     │   │  - build_problem_details()      │
└─────────────────────────────────┘   └─────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `CircuitBreaker` | Track API failures, implement open/closed state, return degraded responses when open |
| `DegradationStrategy` | Manage 4-tier fallback cascade (cached → utilization → random → exception) |
| `ResponseBuilder` | Construct structured responses (deployment dict, error objects, Problem Details) |
| `IntelligentMultiMetricRouting` | Main routing logic, orchestrates above components |

---

## Component Diagram

### Circuit Breaker State Machine

```
┌──────────────┐     failure threshold     ┌──────────────┐
│              │      (default: 3)          │              │
│    CLOSED    │ ─────────────────────────▶ │     OPEN     │
│              │                            │              │
│  Normal ops  │                            │  Degraded    │
│  API calls   │                            │  responses   │
│  permitted   │                            │  only        │
└──────────────┘                            └──────────────┘
       ▲                                           │
       │              cooldown timer               │
       │            (default: 30s)                  │
       │                                           │
       │                                           ▼
       │                            ┌──────────────────────────────┐
       │                            │                              │
       └────────────────────────────│      HALF-OPEN              │
                                    │                              │
                                    │   Test API recovery         │
                                    │   (single request)          │
                                    │                              │
                                    └──────────────────────────────┘
```

### Error Response Flow

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   RFC 9457      │      │   OpenAI        │      │   HTTP Status  │
│   Problem       │      │   Compatible    │      │   Code         │
│   Details       │      │   Error         │      │                │
├─────────────────┤      ├─────────────────┤      ├─────────────────┤
│ type: URI       │      │ error: {        │      │ 200 = OK       │
│ title: string   │      │   message,      │      │   (degraded    │
│ status: int     │      │   type,         │      │    OK)          │
│ detail: string  │      │   code,         │      │                │
│ instance: URI   │      │   param         │      │ 503 = Service  │
│ extensions?     │      │ }               │      │   Unavailable  │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## Data Flow

### Request Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. ROUTE REQUEST                                                         │
│    Router calls async_get_available_deployment(model_list, ...)          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. CIRCUIT BREAKER CHECK                                                │
│                                                                          │
│    if circuit_breaker.is_open:                                         │
│        logger.warning("Circuit breaker OPEN, returning degraded")       │
│        return degrade_to_fallback()  ──────────────────────────────▶ 4 │
│    else:                                                                 │
│        proceed to fetch metrics                                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 3. FETCH METRICS (with degradation cascade)                            │
│                                                                          │
│    try:                                                                  │
│        metrics = await fetch_all_metrics()                              │
│        if metrics:                   # Level 0: Full data              │
│            return select_optimal_chute(metrics)                         │
│    except TimeoutError:                                                 │
│        logger.warning("Metrics fetch timeout, checking cache...")      │
│                                                                          │
│    # Level 1: Try cached metrics                                        │
│    cached = cache.get_all()                                            │
│    if cached:                                                           │
│        logger.info("Using cached metrics for routing")                  │
│        return select_optimal_chute(cached, source="cache")             │
│                                                                          │
│    # Level 2: Try utilization only                                      │
│    utilization = await fetch_utilization_only()                         │
│    if utilization:                                                      │
│        logger.warning("Using utilization-only routing")                 │
│        return select_by_utilization(utilization)                        │
│                                                                          │
│    # Level 3: Random selection with warning                             │
│    logger.error("No metrics available, random selection")              │
│    return select_random_with_warning(model_list)                        │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 4. RETURN RESPONSE                                                       │
│                                                                          │
│    ResponseBuilder.build_success(deployment, degradation_level)         │
│    or                                                                   │
│    ResponseBuilder.build_error(error_type, message, status_code)       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Circuit Breaker Integration Flow

```
                         ┌─────────────────┐
                         │  API Call Made  │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            ┌───────────────┐           ┌───────────────┐
            │   Success     │           │    Failure    │
            └───────┬───────┘           └───────┬───────┘
                    │                           │
                    ▼                           ▼
            ┌───────────────┐           ┌───────────────┐
            │ reset failure │           │ increment      │
            │ counter       │           │ failure count  │
            └───────┬───────┘           └───────┬───────┘
                    │                           │
                    ▼                           ▼
            ┌───────────────┐           ┌───────────────┐
            │  Circuit      │           │  if failures  │
            │  stays CLOSED │           │  >= threshold │
            └───────────────┘           └───────┬───────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │ circuit.open()│
                                        │ (30s cooldown)│
                                        └───────────────┘
```

---

## Class/Interface Design

### 1. CircuitBreaker

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import threading


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, return degraded
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 3
    cooldown_seconds: int = 30
    half_open_timeout: int = 10


class CircuitBreaker:
    """
    API-level circuit breaker for Chutes API calls.
    
    Prevents cascading failures by stopping API calls when
    the service is experiencing issues.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for cooldown expiration."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.cooldown_seconds:
                        self._state = CircuitState.HALF_OPEN
                        logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    def is_open(self) -> bool:
        """Check if circuit is open (returns degraded responses)."""
        return self.state == CircuitState.OPEN

    def record_success(self) -> None:
        """Record successful API call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker CLOSED after successful recovery")
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed API call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN after half-open failure")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self._failure_count} failures"
                )

    def get_status(self) -> dict:
        """Get circuit breaker status for debugging."""
        with self._lock:
            return {
                "state": self.state.value,
                "failure_count": self._failure_count,
                "last_failure": self._last_failure_time,
            }
```

### 2. DegradationStrategy

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import logging


class DegradationLevel(Enum):
    """Degradation levels for routing."""
    FULL = 0          # All metrics available
    CACHED = 1        # Using cached metrics
    UTILIZATION = 2   # Utilization only
    RANDOM = 3        # Random selection (fallback)
    FAILED = 4        # Complete failure


@dataclass
class DegradationConfig:
    """Configuration for degradation behavior."""
    enable_cached: bool = True
    enable_utilization: bool = True
    enable_random: bool = True
    random_warning_threshold: float = 0.7


class DegradationStrategy:
    """
    Implements 4-tier graceful degradation cascade.
    
    Falls back through levels when higher-quality data
    is unavailable due to API failures or timeouts.
    """

    def __init__(self, config: Optional[DegradationConfig] = None):
        self.config = config or DegradationConfig()
        self.logger = logging.getLogger(__name__)

    def get_degradation_level(
        self,
        metrics: Optional[Dict[str, Any]],
        cached_metrics: Optional[Dict[str, Any]],
        utilization: Optional[Dict[str, Any]],
    ) -> DegradationLevel:
        """
        Determine the appropriate degradation level.
        
        Args:
            metrics: Full metrics from API
            cached_metrics: Cached metrics from cache
            utilization: Utilization-only data
            
        Returns:
            DegradationLevel indicating which tier to use
        """
        if metrics:
            return DegradationLevel.FULL

        if self.config.enable_cached and cached_metrics:
            self.logger.info("Degradation: Using cached metrics (Level 1)")
            return DegradationLevel.CACHED

        if self.config.enable_utilization and utilization:
            self.logger.warning("Degradation: Using utilization only (Level 2)")
            return DegradationLevel.UTILIZATION

        if self.config.enable_random:
            self.logger.error("Degradation: Random selection (Level 3)")
            return DegradationLevel.RANDOM

        self.logger.critical("Degradation: Complete failure (Level 4)")
        return DegradationLevel.FAILED

    def select_with_degradation(
        self,
        deployments: List[Dict[str, Any]],
        metrics: Optional[Dict[str, Any]] = None,
        cached_metrics: Optional[Dict[str, Any]] = None,
        utilization: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[Dict[str, Any]], DegradationLevel]:
        """
        Select deployment with graceful degradation.
        
        Returns tuple of (deployment, level).
        """
        level = self.get_degradation_level(metrics, cached_metrics, utilization)

        if level == DegradationLevel.FULL:
            return self._select_best(deployments, metrics), DegradationLevel.FULL

        if level == DegradationLevel.CACHED:
            return self._select_best(deployments, cached_metrics), DegradationLevel.CACHED

        if level == DegradationLevel.UTILIZATION:
            return self._select_by_utilization(deployments, utilization), DegradationLevel.UTILIZATION

        if level == DegradationLevel.RANDOM:
            import random
            selected = random.choice(deployments)
            self.logger.warning(
                f"Random selection from {len(deployments)} deployments - "
                "metrics unavailable"
            )
            return selected, DegradationLevel.RANDOM

        # Level FAILED - return None to trigger exception
        return None, DegradationLevel.FAILED
```

### 3. ResponseBuilder

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
import logging


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
            "degradation_reason": self._get_degradation_reason(degradation_level),
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

    @staticmethod
    def _get_degradation_reason(level: int) -> str:
        """Get human-readable degradation reason."""
        reasons = {
            0: "Full metrics available",
            1: "Using cached metrics",
            2: "Using utilization only",
            3: "Random selection (metrics unavailable)",
            4: "Complete failure",
        }
        return reasons.get(level, "Unknown")
```

---

## Error Handling Strategy

### When to Raise Exceptions vs Return Structured Errors

| Scenario | Before | After | Action |
|----------|--------|-------|--------|
| No model list | `return None` | `raise EmptyModelListError` | Raise - complete failure |
| API timeout | `return None` | Return degraded (cached/util) | Return - graceful degradation |
| No cached data | `return None` | Return degraded (random) | Return - degraded but functional |
| All circuits open | N/A | Return 503 + Problem Details | Return - complete failure |
| Partial metrics | `return None` | Return degraded (partial) | Return - graceful degradation |

### Exception Hierarchy

```python
# Existing exceptions (src/litellm_proxy/exceptions.py)
class ChutesRoutingError(Exception):
    """Base exception for routing errors."""
    pass


class EmptyModelListError(ChutesRoutingError):
    """Raised when no models are configured."""
    pass


class ConfigurationError(ChutesRoutingError):
    """Raised when configuration is invalid."""
    pass


class ModelUnavailableError(ChutesRoutingError):
    """Raised when a model is unavailable."""
    pass


# New exceptions for structured responses
class DegradationExhaustedError(ChutesRoutingError):
    """Raised when all degradation levels have failed."""
    
    def __init__(self, levels_attempted: list, original_error: Optional[Exception] = None):
        self.levels_attempted = levels_attempted
        self.original_error = original_error
        super().__init__(
            f"All degradation levels exhausted: {levels_attempted}. "
            f"Original error: {original_error}"
        )


class CircuitBreakerOpenError(ChutesRoutingError):
    """Raised when circuit breaker is open and degraded response not acceptable."""
    
    def __init__(self, cooldown_remaining: float):
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"Circuit breaker open. Retry after {cooldown_remaining:.1f}s"
        )
```

### HTTP Status Code Strategy

| Status Code | Usage | Response Body |
|-------------|-------|---------------|
| **200 OK** | Successful routing (full or degraded) | Deployment dict + `_routing_metadata` |
| **503 Service Unavailable** | Complete failure, no degraded options | Problem Details + OpenAI error |

```python
# Example: HTTP response handling in client.py
async def handle_routing_response(
    routing_result: Optional[Dict[str, Any]],
    error: Optional[Exception],
) -> Response:
    """Convert routing result to HTTP response."""
    
    if error is None and routing_result is not None:
        # Success (possibly degraded)
        status = 200
        body = routing_result
        
    elif isinstance(error, DegradationExhaustedError):
        # Complete failure
        status = 503
        body = response_builder.build_error(
            error_type="server_error",
            message=str(error),
            status_code=503,
            code="degradation_exhausted",
        )
        
    elif isinstance(error, CircuitBreakerOpenError):
        status = 503
        body = response_builder.build_error(
            error_type="server_error",
            message=str(error),
            status_code=503,
            code="circuit_breaker_open",
        )
        
    else:
        # Unknown error
        status = 503
        body = response_builder.build_error(
            error_type="server_error",
            message="Internal routing error",
            status_code=503,
            code="internal_error",
        )
    
    return Response(status=status, body=body)
```

---

## Integration Points

### Integration with `intelligent.py`

```python
# Modified IntelligentMultiMetricRouting class
from litellm_proxy.routing.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from litellm_proxy.routing.responses import ResponseBuilder, DegradationStrategy


class IntelligentMultiMetricRouting(ChutesRoutingStrategy, CustomRoutingStrategyBase):
    
    def __init__(self, /* existing params */, 
                 enable_circuit_breaker: bool = True,
                 enable_degradation: bool = True):
        # ... existing initialization ...
        
        # New components
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self.degradation = DegradationStrategy() if enable_degradation else None
        self.response_builder = ResponseBuilder()

    async def async_get_available_deployment(
        self,
        model_list: List[Dict[str, Any]],
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Get available deployment with circuit breaker and degradation."""
        
        # 1. Check circuit breaker
        if self.circuit_breaker and self.circuit_breaker.is_open():
            self.logger.warning("Circuit breaker open, using degraded response")
            deployment, level = self.degradation.select_with_degradation(
                model_list, 
                metrics=None,  # Force degraded
                cached_metrics=None,
                utilization=None,
            )
            return self.response_builder.build_success(deployment, level)
        
        # 2. Try normal routing
        try:
            metrics = await self._fetch_metrics(model_list)
            
            if metrics:
                deployment = self._select_best(model_list, metrics)
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                return self.response_builder.build_success(deployment, 0)
                
        except (ChutesAPITimeoutError, ChutesAPIConnectionError) as e:
            self.logger.warning(f"API error: {e}, attempting degradation")
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
        
        # 3. Try degradation cascade
        try:
            deployment, level = self.degradation.select_with_degradation(
                model_list,
                metrics=None,
                cached_metrics=self._cache.get_all(),
                utilization=await self._fetch_utilization_only(model_list),
            )
            
            if deployment:
                return self.response_builder.build_success(deployment, level)
                
        except Exception as e:
            self.logger.error(f"Degradation failed: {e}")
        
        # 4. Complete failure - raise exception (no more None returns)
        raise DegradationExhaustedError(
            levels_attempted=["full", "cached", "utilization", "random"],
            original_error=e if 'e' in locals() else None
        )
```

### Integration with `client.py`

```python
# Modified ChutesAPIClient class
class ChutesAPIClient:
    
    def __init__(self, /* existing params */,
                 circuit_breaker: Optional[CircuitBreaker] = None):
        # ... existing initialization ...
        self.circuit_breaker = circuit_breaker

    def get_utilization(self, chute_id: str) -> Optional[float]:
        """Fetch utilization with circuit breaker protection."""
        
        if self.circuit_breaker and self.circuit_breaker.is_open():
            self.logger.warning(f"Circuit open, skipping utilization fetch for {chute_id}")
            return None  # Let degradation handle this
            
        try:
            result = self._fetch_utilization_impl(chute_id)
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
            return result
            
        except (requests.Timeout, requests.ConnectionError) as e:
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise ChutesAPITimeoutError(f"Timeout fetching utilization: {e}")
```

### Feature Flags for Rollback

```python
import os
from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """Feature flags for structured responses (for rollback)."""
    
    USE_STRUCTURED_RESPONSES: bool = True
    ENABLE_CIRCUIT_BREAKER: bool = True
    ENABLE_DEGRADATION: bool = True
    
    @classmethod
    def from_env(cls) -> "FeatureFlags":
        """Load feature flags from environment."""
        return cls(
            USE_STRUCTURED_RESPONSES=os.getenv(
                "USE_STRUCTURED_RESPONSES", "true"
            ).lower() == "true",
            ENABLE_CIRCUIT_BREAKER=os.getenv(
                "CIRCUIT_BREAKER_ENABLED", "true"
            ).lower() == "true",
            ENABLE_DEGRADATION=os.getenv(
                "DEGRADATION_ENABLED", "true"
            ).lower() == "true",
        )


# Usage in routing class
flags = FeatureFlags.from_env()

if not flags.USE_STRUCTURED_RESPONSES:
    # Legacy behavior
    return None  # pragma: no cover - fallback path
```

---

## File Structure Summary

```
src/litellm_proxy/
├── exceptions.py                    # MODIFIED: Add new exception types
│   ├── DegradationExhaustedError    # NEW
│   └── CircuitBreakerOpenError     # NEW
│
├── routing/
│   ├── responses.py                 # NEW: ResponseBuilder, structured types
│   │   ├── ProblemDetails           # RFC 9457
│   │   ├── OpenAIError              # OpenAI compatible
│   │   └── ResponseBuilder          # Response construction
│   │
│   ├── circuit_breaker.py           # NEW: Circuit breaker implementation
│   │   ├── CircuitState             # Enum
│   │   ├── CircuitBreakerConfig     # Configuration
│   │   └── CircuitBreaker           # Main class
│   │
│   ├── intelligent.py               # MODIFIED: Integrate new components
│   │   └── IntelligentMultiMetricRouting  # Updated
│   │
│   └── cache.py                     # UNCHANGED
│
└── api/
    └── client.py                    # MODIFIED: Add circuit breaker
        └── ChutesAPIClient          # Updated
```

---

## Testing Strategy

### Unit Tests

| Test | Component | Scenario |
|------|-----------|----------|
| `test_circuit_opens_after_threshold` | CircuitBreaker | 3 failures → open |
| `test_circuit_closes_after_cooldown` | CircuitBreaker | 30s timeout → half-open |
| `test_degradation_cascade` | DegradationStrategy | metrics→cached→util→random |
| `test_response_builder_problem_details` | ResponseBuilder | Valid RFC 9457 format |
| `test_response_builder_openai_error` | ResponseBuilder | Valid OpenAI format |
| `test_degradation_exhausted_error` | Exceptions | All levels failed |

### Integration Tests

| Test | Scenario |
|------|----------|
| `test_timeout_returns_cached` | API timeout → cached data used |
| `test_no_model_list_raises_error` | Empty model list → EmptyModelListError |
| `test_circuit_breaker_integration` | 3 API failures → degraded response |
| `test_partial_metrics_routing` | Some metrics missing → partial routing |

---

## Performance Considerations

| Operation | Target | Implementation |
|-----------|--------|-----------------|
| Circuit breaker state check | <1ms | In-memory boolean + timestamp |
| Degradation level determination | <5ms | Simple enum lookup |
| Error response serialization | <2ms | Pre-built templates |
| Cache lookup | <1ms | In-memory dict with TTL |

---

## Migration Guide

### For Existing Consumers

1. **If catching `None`**: Update to catch specific exceptions:
   ```python
   # Before
   deployment = router.get_deployment(...)
   if deployment is None:
       handle_error()
   
   # After
   try:
       deployment = router.get_deployment(...)
   except DegradationExhaustedError:
       handle_error()
   ```

2. **If depending on HTTP 200 with degraded response**: Check `_routing_metadata`:
   ```python
   response = await proxy.chat_complete(...)
   if response["_routing_metadata"]["degradation_level"] > 0:
       log_warning("Using degraded routing")
   ```

### Rollback Steps

1. Set `USE_STRUCTURED_RESPONSES=false` in environment
2. Set `CIRCUIT_BREAKER_ENABLED=false`
3. Set `DEGRADATION_ENABLED=false`
4. Redeploy (returns to legacy `None`-returning behavior)
