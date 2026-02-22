# Issue: Implement Multi-Factor Routing Scoring

**Priority:** Medium  
**Type:** Feature Enhancement / Performance Optimization  
**Component:** Routing Strategy  
**Files Likely Modified:** `chutes_routing.py`, `litellm-config.yaml`, potentially new `metrics/` module

---

## Description

The current routing system relies on a **single metric**: utilization percentage from the Chutes API. While utilization is an important factor, it doesn't capture the full picture of model performance and suitability. This narrow view can lead to suboptimal routing decisions that don't account for:
- Response latency differences between models
- Error rate variations
- Cost efficiency
- Model capabilities for specific task types

## Current Behavior

1. System fetches only `utilization_current` from the Chutes API
2. Selection is based purely on minimum utilization:
   ```python
   # From chutes_routing.py - _find_least_utilized()
   return min(utilizations.items(), key=lambda x: x[1])[0]
   ```
3. No consideration of:
   - Latency/response time
   - Error rates (failed requests, timeouts)
   - Cost per token
   - Model-specific capabilities
   - Historical performance data

### Current Data Sources

The Chutes API potentially provides more data that is currently unused:
- `utilization_5m` - 5-minute average
- `utilization_15m` - 15-minute average
- Response times (if available in API)
- Error counts (if available in API)

## Expected Behavior

Implement a **multi-factor scoring system** that considers:

1. **Utilization (Primary Factor)**
   - Current utilization percentage
   - Trend (increasing vs decreasing)
   - Historical averages (5m, 15m)

2. **Latency**
   - Average response time
   - P95/P99 response times
   - Latency trend

3. **Error Rate**
   - Failure percentage
   - Timeout rate
   - Error trend

4. **Cost Efficiency** (optional, if data available)
   - Cost per 1K tokens
   - Cost-performance ratio

5. **Model Suitability** (optional, for advanced routing)
   - Task type matching
   - Context length requirements
   - Special capabilities (function calling, vision, etc.)

### Multi-Factor Score Calculation

```python
@dataclass
class ModelMetrics:
    chute_id: str
    utilization: float          # 0.0 - 1.0
    latency_ms: float           # Average latency
    error_rate: float           # 0.0 - 1.0
    cost_per_1k_tokens: float   # If available
    
@dataclass  
class RoutingDecision:
    model_config: Dict
    score: float                # Lower is better
    factors: Dict[str, float]   # Breakdown of score

def calculate_routing_score(
    metrics: ModelMetrics,
    weights: Dict[str, float] = None
) -> RoutingDecision:
    """
    Calculate weighted score from multiple factors.
    
    Each factor is normalized to 0-1 scale where lower = better.
    """
    if weights is None:
        weights = {
            "utilization": 0.50,  # Primary factor
            "latency": 0.25,
            "error_rate": 0.25,
        }
    
    # Normalize each factor
    # Utilization: already 0-1, higher = worse (invert)
    util_score = metrics.utilization
    
    # Latency: normalize (need max_latency reference)
    latency_score = min(metrics.latency_ms / MAX_LATENCY_MS, 1.0)
    
    # Error rate: already 0-1
    error_score = metrics.error_rate
    
    # Calculate weighted sum
    factors = {
        "utilization": util_score,
        "latency": latency_score,
        "error_rate": error_score,
    }
    
    total_score = sum(
        factors[k] * weights[k] 
        for k in weights
    )
    
    return RoutingDecision(
        model_config=...,
        score=total_score,
        factors=factors
    )
```

## Suggested Implementation Approach

### Phase 1: Enhanced Utilization Metrics

1. **Use utilization_5m and utilization_15m** as secondary factors
2. **Detect utilization trends** - if current > 5m average, utilization is increasing
3. **Implement basic scoring**:
   ```python
   def calculate_utilization_score(current, avg_5m, avg_15m):
       # Base score from current utilization
       score = current
       
       # Penalty if current > 5m average (increasing load)
       if current > avg_5m:
           score += 0.1
       
       # Bonus if 15m > 5m (load decreasing over time)
       if avg_15m < avg_5m:
           score -= 0.05
           
       return max(0, min(1, score))
   ```

### Phase 2: Latency Integration

1. Add latency tracking (either from Chutes API or by measuring request times)
2. Cache latency data with similar TTL to utilization
3. Include latency in scoring with configurable weight

### Phase 3: Error Rate Tracking

1. Track request success/failure in routing decisions
2. Calculate rolling error rate
3. Heavily penalize high error rate models in scoring

### Phase 4: Full Multi-Factor Scoring

1. Implement the full `ModelMetrics` dataclass
2. Add configuration for factor weights
3. Expose metrics for observability

### Implementation Structure

```
chutes_routing.py
    ├── ChutesUtilizationRouting (existing)
    │   ├── _get_utilization() [enhance to get multiple metrics]
    │   ├── _find_least_utilized() [rename to _select_best_deployment()]
    │   └── [NEW] _calculate_multi_factor_score()
    │
    └── [NEW] ModelMetrics dataclass
    └── [NEW] MultiFactorScorer class (separate module?)
```

### Configuration Example

```python
# In chutes_routing.py
def __init__(
    self,
    chutes_api_key: Optional[str] = None,
    cache_ttl: int = 30,
    chutes_api_base: str = "https://api.chutes.ai",
    # Multi-factor scoring config
    scoring_weights: Dict[str, float] = None,  # {"utilization": 0.5, "latency": 0.3, "error_rate": 0.2}
    enable_trend_analysis: bool = True,
    latency_threshold_ms: float = 5000,
):
```

```yaml
# In litellm-config.yaml
# Future enhancement - per-model scoring weights
# model_list:
#   - model_name: chutes-models
#     model_info:
#       scoring_weights:
#         utilization: 0.6
#         latency: 0.2  
#         error_rate: 0.2
```

---

## Verification

- [ ] Verify utilization_5m and utilization_15m are now used in scoring
- [ ] Verify trend detection works (increasing vs decreasing load)
- [ ] Verify latency factor can be weighted independently
- [ ] Verify error rate penalizes high-failure models
- [ ] Verify scoring weights are configurable
- [ ] Add unit tests for multi-factor scoring
- [ ] Add integration tests with actual API data

---

## Backward Compatibility

- **Critical:** Maintain default behavior where utilization is the primary (and only) factor if no new configuration is provided
- Add new parameters with sensible defaults that match current behavior
- Log warning when using default weights (single-factor mode)

---

## Related Issues

- Issue #1: No Priority Weighting (priority can be integrated as a scoring factor)
- Issue #2: No Load Threshold Protection (thresholds should apply to all factors)
- Issue #4: No Health Checks (health status should be a gating factor)

---

## Additional Considerations

### Observability

Add metrics for debugging routing decisions:
```python
logger.info(
    f"Routing decision for {chute_id}: "
    f"score={score:.3f} (util={util_score:.2f}, "
    f"latency={lat_score:.2f}, error={err_score:.2f})"
)
```

### Future Enhancements

- **Cost-based routing:** Route to cheaper models for non-critical tasks
- **Task-specific routing:** Match model capabilities to request type
- **A/B testing:** Test different weight configurations in production
- **ML-based scoring:** Use historical data to learn optimal weights
