# Issue: Implement Active Health Checks for Model Availability

**Priority:** High  
**Type:** Reliability / Feature Enhancement  
**Component:** Routing Strategy, Health Monitoring  
**Files Likely Modified:** `chutes_routing.py`, potentially new `health_check.py` module

---

## Description

The current routing system relies solely on utilization data from the Chutes API to determine model availability. However, utilization does not equal availability. A model can show low utilization (e.g., 10%) but be completely unresponsive due to:

- Network connectivity issues
- Model process crashes or hangs
- API endpoint failures
- Authentication/token expiration
- Backend service restarts

Without active health checks, requests are blindly routed to models that appear available by utilization metrics but are actually failing or unresponsive.

## Current Behavior

1. System fetches utilization from Chutes API: `/chutes/utilization`
2. System routes to model with lowest utilization
3. **No verification** that the model actually responds to requests
4. Failed requests only detected after timeout (30-60 seconds)
5. No mechanism to detect "soft" failures (slow responses, high error rates)

### Relevant Code Gap

```python
# From chutes_routing.py - _get_utilization()
def _get_utilization(self, chute_id: str) -> Optional[float]:
    # Only fetches utilization - does NOT verify model is responding
    utilization = self._parse_utilization_response(data, chute_id)
    return utilization  # Returns util even if model is down!
```

## Expected Behavior

1. **Active Health Checks:** Periodically ping/test each model to verify responsiveness
2. **Multi-Level Health Verification:**
   - Level 1: API endpoint reachable (HTTP HEAD/GET)
   - Level 2: Model responds to basic request
   - Level 3: Model produces valid output
3. **Health Status Caching:** Cache health status with shorter TTL than utilization
4. **Graceful Handling:**
   - Exclude unhealthy models from routing
   - Auto-recovery detection when model becomes healthy again
5. **Health Metrics:** Track consecutive failures, recovery time, etc.

## Suggested Implementation Approach

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   ChutesUtilizationRouting                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │ Utilization    │    │ HealthCheck    │                  │
│  │ Fetcher        │    │ Manager        │                  │
│  │                │    │                │                  │
│  │ - /utilization │    │ - /v1/models   │                  │
│  │ - Cache TTL:30s│    │ - Cache TTL:5s │                  │
│  └────────┬────────┘    └────────┬────────┘                  │
│           │                      │                           │
│           └──────────┬───────────┘                          │
│                      ▼                                       │
│           ┌─────────────────────┐                            │
│           │  Routing Decision   │                            │
│           │                     │                            │
│           │  1. Filter unhealthy│                            │
│           │  2. Select by util  │                            │
│           │  3. Return config   │                            │
│           └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### Implementation: HealthCheckManager

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import asyncio
import aiohttp

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Slow but responding
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    chute_id: str
    status: HealthStatus
    latency_ms: float
    error_message: Optional[str]
    timestamp: float
    consecutive_failures: int

class HealthCheckManager:
    """Manages health checks for all configured models."""
    
    def __init__(
        self,
        api_key: str,
        api_base: str = "https://llm.chutes.ai/v1",
        check_interval: int = 30,  # seconds
        timeout: int = 5,  # seconds
        unhealthy_threshold: int = 3,  # consecutive failures
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.check_interval = check_interval
        self.timeout = timeout
        self.unhealthy_threshold = unhealthy_threshold
        
        # Cache: {chute_id: HealthCheckResult}
        self.health_cache: Dict[str, HealthCheckResult] = {}
        
        # Track consecutive failures: {chute_id: count}
        self.failure_counts: Dict[str, int] = {}
        
        # Start background health check task
        self._check_task = None
        
    async def start(self):
        """Start background health check loop."""
        self._check_task = asyncio.create_task(self._health_check_loop())
        
    async def stop(self):
        """Stop background health checks."""
        if self._check_task:
            self._check_task.cancel()
            
    async def _health_check_loop(self):
        """Background task that periodically checks all models."""
        while True:
            await self.check_all_models()
            await asyncio.sleep(self.check_interval)
            
    async def check_all_models(self, model_list: List[Dict]):
        """Check health of all models in parallel."""
        tasks = []
        for model_config in model_list:
            chute_id = self._get_chute_id(model_config)
            tasks.append(self._check_model_health(chute_id, model_config))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _check_model_health(
        self, 
        chute_id: str, 
        model_config: Dict
    ) -> HealthCheckResult:
        """Perform health check on a single model."""
        api_base = model_config["litellm_params"]["api_base"]
        model = model_config["litellm_params"]["model"]
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                # Try models endpoint first (lightweight)
                url = f"{api_base}/models"
                async with session.get(
                    url, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    latency_ms = (time.time() - start) * 1000
                    
                    if response.status == 200:
                        status = HealthStatus.HEALTHY
                    elif response.status < 500:
                        # Auth error or similar - model exists but can't use
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.UNHEALTHY
                        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                chute_id=chute_id,
                status=HealthStatus.UNHEALTHY,
                latency_ms=self.timeout * 1000,
                error_message="Timeout",
                timestamp=time.time(),
                consecutive_failures=self._increment_failure(chute_id)
            )
        except Exception as e:
            return HealthCheckResult(
                chute_id=chute_id,
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                error_message=str(e),
                timestamp=time.time(),
                consecutive_failures=self._increment_failure(chute_id)
            )
            
        # Update failure count on success
        self.failure_counts[chute_id] = 0
        
        return HealthCheckResult(
            chute_id=chute_id,
            status=status,
            latency_ms=latency_ms,
            error_message=None,
            timestamp=time.time(),
            consecutive_failures=0
        )
        
    def _increment_failure(self, chute_id: str) -> int:
        """Increment and return consecutive failure count."""
        count = self.failure_counts.get(chute_id, 0) + 1
        self.failure_counts[chute_id] = count
        return count
        
    def is_healthy(self, chute_id: str) -> bool:
        """Check if a model is healthy and available for routing."""
        if chute_id not in self.health_cache:
            return True  # Assume healthy if not checked yet
            
        result = self.health_cache[chute_id]
        return (
            result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            and result.consecutive_failures < self.unhealthy_threshold
        )
```

### Integration with Routing

```python
class ChutesUtilizationRouting(CustomRoutingStrategyBase):
    
    def __init__(self, ...):
        # Existing initialization
        ...
        
        # NEW: Health check manager
        self.health_manager = HealthCheckManager(
            api_key=self.chutes_api_key,
            api_base="https://llm.chutes.ai/v1",
            check_interval=30,
            timeout=5,
        )
        
    async def async_get_available_deployment(self, ...):
        # Existing utilization logic...
        utilizations = self._get_all_utilizations(model_list)
        
        # NEW: Filter out unhealthy models
        available_utilizations = {
            chute_id: util 
            for chute_id, util in utilizations.items()
            if self.health_manager.is_healthy(chute_id)
        }
        
        if not available_utilizations:
            # All models unhealthy - log and fallback
            logger.error("All models failed health checks!")
            # Could raise exception or return None to fail request
            
        # Continue with existing selection logic...
```

### Alternative: Simpler Health Check (If Async Too Complex)

For simpler integration, use synchronous requests with threading:

```python
import concurrent.futures

class SimpleHealthChecker:
    """Synchronous health checker using thread pool."""
    
    def __init__(self, api_key: str, timeout: int = 5):
        self.api_key = api_key
        self.timeout = timeout
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
    def check_model(self, model_config: Dict) -> HealthCheckResult:
        """Synchronously check model health."""
        # Use requests library (blocking)
        # Similar logic to async version but synchronous
        pass
        
    def check_all(self, model_list: List[Dict]) -> Dict[str, HealthCheckResult]:
        """Check all models in parallel using thread pool."""
        futures = {
            self._get_chute_id(cfg): self.executor.submit(self.check_model, cfg)
            for cfg in model_list
        }
        return {k: f.result() for k, f in futures.items()}
```

## Configuration

```python
# In chutes_routing.py
def __init__(
    self,
    chutes_api_key: Optional[str] = None,
    cache_ttl: int = 30,
    chutes_api_base: str = "https://api.chutes.ai",
    # NEW: Health check configuration
    enable_health_checks: bool = True,
    health_check_interval: int = 30,
    health_check_timeout: int = 5,
    unhealthy_threshold: int = 3,
):
```

## Implementation Steps

1. **Phase 1: Basic Health Check**
   - Create `HealthCheckManager` class
   - Add synchronous health check method
   - Integrate health filtering into routing

2. **Phase 2: Async Health Checks**
   - Convert to async implementation
   - Add background health check loop
   - Implement failure tracking

3. **Phase 3: Enhanced Health Logic**
   - Add degraded status for slow responses
   - Implement recovery detection
   - Add health metrics/logging

4. **Phase 4: Observability**
   - Expose health status via API endpoint
   - Add health check metrics to logs
   - Create dashboard/health endpoint

---

## Verification

- [ ] Verify unhealthy models are excluded from routing
- [ ] Verify models recover and are re-included after becoming healthy
- [ ] Verify health check timeout doesn't block routing
- [ ] Verify failure counts work correctly
- [ ] Verify logging clearly shows health check results
- [ ] Add unit tests for health check logic
- [ ] Add integration tests with actual endpoints

---

## Edge Cases to Handle

1. **Initial startup:** No health data yet - assume healthy
2. **All models unhealthy:** Fail request or fallback to lowest util
3. **Health check API down:** Use cached health or assume healthy
4. **Network partitions:** Handle gracefully, don't block routing
5. **Rapid state changes:** Debounce health state changes

---

## Related Issues

- Issue #2: No Load Threshold Protection (can use health status as additional threshold)
- Issue #3: Single Metric Only (health can be another factor in scoring)
