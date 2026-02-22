# Issue: Implement Load Threshold Protection

**Priority:** High  
**Type:** Feature Enhancement / Reliability  
**Component:** Routing Strategy  
**Files Likely Modified:** `chutes_routing.py`, `start_litellm.py`

---

## Description

The current routing system has no upper limit on utilization. Even when a model is at 99% utilization, it can still be selected as long as it has the lowest utilization among all available models. This creates a critical gap where overloaded models continue receiving requests, leading to:
- Increased latency
- Higher error rates
- Poor user experience
- Potential cascading failures

## Current Behavior

1. System fetches utilization percentages for all models (e.g., Kimi: 99%, GLM: 85%, Qwen: 70%)
2. System selects the model with lowest utilization (Qwen at 70%)
3. If all models are overloaded (e.g., 95%, 92%, 90%), the system still forces a selection
4. No mechanism to reject requests when all models exceed a healthy threshold
5. Default fallback of 0.5 utilization is used when API is unavailable (line 318 in chutes_routing.py)

### Relevant Code

```python
# From chutes_routing.py - _find_least_utilized()
def _find_least_utilized(self, utilizations: Dict[str, float]) -> Optional[str]:
    if not utilizations:
        return None
    # Simply returns the minimum - no threshold check!
    return min(utilizations.items(), key=lambda x: x[1])[0]
```

## Expected Behavior

1. Define a maximum utilization threshold (e.g., 90%) above which models are considered "unavailable"
2. Only consider models below the threshold for routing
3. When ALL models exceed the threshold:
   - Return an error/exception to signal unavailability
   - Or implement request queuing/waiting
   - Log clear warnings about overloaded state
4. Allow threshold to be configurable:
   - Per-model threshold (different limits for different models)
   - Global default threshold
5. Consider implementing a "graceful degradation" mode

## Suggested Implementation Approach

### Option A: Hard Threshold with Error Return

```python
class OverloadedError(Exception):
    """Raised when all models exceed utilization threshold."""
    pass

def select_deployment(self, utilizations, threshold=0.90):
    # Filter out overloaded models
    available = {k: v for k, v in utilizations.items() if v < threshold}
    
    if not available:
        raise OverloadedError(
            f"All models overloaded. Utilizations: {utilizations}"
        )
    
    return min(available.items(), key=lambda x: x[1])[0]
```

### Option B: Soft Threshold with Weighted Avoidance

```python
def calculate_score(self, utilization, threshold=0.90):
    """Higher score = less desirable."""
    if utilization >= threshold:
        # Apply heavy penalty for exceeding threshold
        return 1.0 + (utilization - threshold) * 10
    return utilization

def select_deployment(self, utilizations, threshold=0.90):
    scores = {k: self.calculate_score(v, threshold) for k, v in utilizations.items()}
    return min(scores.items(), key=lambda x: x[1])[0]
```

### Option C: Tiered Threshold with Fallback

```python
TIER_THRESHOLDS = {
    "green": 0.70,   # Preferred - best performance
    "yellow": 0.85,  # Acceptable - degraded performance
    "red": 0.95,     # Last resort - critical degradation
}

def select_with_tiers(self, utilizations):
    # Try green tier first
    green_available = {k: v for k, v in utilizations.items() 
                       if v < TIER_THRESHOLDS["green"]}
    if green_available:
        return min(green_available.items(), key=lambda x: x[1])[0]
    
    # Try yellow tier
    yellow_available = {k: v for k, v in utilizations.items()
                        if v < TIER_THRESHOLDS["yellow"]}
    if yellow_available:
        return min(yellow_available.items(), key=lambda x: x[1])[0]
    
    # Try red tier
    red_available = {k: v for k, v in utilizations.items()
                     if v < TIER_THRESHOLDS["red"]}
    if red_available:
        return min(red_available.items(), key=lambda x: x[1])[0]
    
    # All overloaded - raise error or return lowest
    raise AllModelsOverloadedError(utilizations)
```

### Recommended Approach

**Option C (Tiered Threshold)** provides the best operational visibility and control. It allows:
- Clear alerting on yellow/red tier usage
- Gradual degradation rather than sudden failures
- Easy tuning per model based on capacity

### Implementation Steps

1. Add configuration parameters to `ChutesUtilizationRouting`:
   - `load_threshold` (float): Default 0.90 (90%)
   - `tier_thresholds`: Optional per-tier configuration
   - `fail_on_overload`: Boolean to control error vs fallback behavior

2. Create new exception class `AllModelsOverloadedError`

3. Modify `_find_least_utilized()` to:
   - Filter by threshold before selection
   - Support tier-based selection
   - Raise exception or fallback when no models available

4. Add health check integration (see Issue #4)

5. Add logging for threshold violations:
   ```python
   if utilization >= threshold:
       logger.warning(f"Model {chute_id} exceeded threshold: {utilization:.1%}")
   ```

6. Update `start_litellm.py` to handle/log overload errors

7. Add tests for threshold behavior

### Configuration Example

```python
# In chutes_routing.py
def __init__(
    self,
    chutes_api_key: Optional[str] = None,
    cache_ttl: int = 30,
    chutes_api_base: str = "https://api.chutes.ai",
    load_threshold: float = 0.90,  # NEW: Reject above 90%
    fail_on_overload: bool = True,  # NEW: Raise error if all overloaded
):
```

```yaml
# In litellm-config.yaml
router_settings:
  routing_strategy: simple-shuffle
  # Custom threshold per model (future enhancement)
```

---

## Verification

- [ ] Verify models above threshold are excluded from selection
- [ ] Verify exception/error is raised when all models exceed threshold
- [ ] Verify logging clearly indicates overload condition
- [ ] Verify threshold can be configured via constructor
- [ ] Verify tier-based selection works correctly
- [ ] Add unit tests for threshold logic

---

## Impact Analysis

- **Positive:** Prevents routing to severely overloaded models
- **Positive:** Provides clear signal when capacity is exceeded
- **Negative:** May increase error rates if threshold is too low
- **Mitigation:** Make threshold configurable, start conservative (90%)

---

## Related Issues

- Issue #1: No Priority Weighting (related - priority should consider thresholds)
- Issue #3: Single Metric Only (can include threshold in multi-factor scoring)
- Issue #4: No Health Checks (health checks should respect threshold)
