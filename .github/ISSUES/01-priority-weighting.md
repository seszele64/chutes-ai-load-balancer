# Issue: Implement Priority Weighting for Model Selection

**Priority:** High  
**Type:** Feature Enhancement  
**Component:** Routing Strategy  
**Files Likely Modified:** `chutes_routing.py`, `litellm-config.yaml`

---

## Description

The current routing system treats all three models (Kimi K2.5 TEE, GLM-5 TEE, Qwen3.5) as equals when selecting a deployment. While the `litellm-config.yaml` file contains an `order` field in the `model_info` section that indicates priority (1 = highest, 3 = lowest), this field is completely ignored by the routing logic in `chutes_routing.py`.

## Current Behavior

1. The routing strategy fetches utilization data for all configured models
2. It selects the model with the **lowest utilization percentage** regardless of priority
3. When two models have similar utilization (e.g., 45% vs 47%), the selection is essentially random between them
4. The `order` field in `model_info` is present but never read or used:
   ```yaml
   model_info:
     id: 2ff25e81-4586-5ec8-b892-3a6f342693d7
     order: 1  # This is ignored!
   ```

## Expected Behavior

1. When utilization differences are small (within a configurable threshold, e.g., 10%), the priority `order` should be used as a tiebreaker
2. Primary model (order: 1) should be preferred when utilization is reasonably close to secondary/tertiary options
3. This ensures the primary model is used as the main workhorse while still benefiting from load distribution
4. Configuration should be flexible:
   - Priority weight factor (how much priority affects scoring)
   - Utilization difference threshold for priority activation

## Suggested Implementation Approach

### Option A: Weighted Score Calculation

Add a priority weight factor to the routing score:

```python
# Pseudocode
def calculate_routing_score(utilization, priority_order, weight_factor=0.3):
    # Normalize priority: order 1 gets highest priority score (1.0), order 3 gets lowest (0.0)
    priority_score = 1.0 - ((priority_order - 1) / 2)  # Maps 1->1.0, 2->0.5, 3->0.0
    
    # Combined score: lower is better
    # Utilization is weighted higher (1 - weight_factor), priority lower (weight_factor)
    combined_score = (utilization * (1 - weight_factor)) + (priority_score * weight_factor)
    
    return combined_score
```

### Option B: Threshold-Based Priority

Only apply priority when utilization difference is below threshold:

```python
def select_deployment(utilizations, model_priorities, threshold=0.1):
    sorted_by_util = sorted(utilizations.items(), key=lambda x: x[1])
    
    # If top two are within threshold, use priority
    if len(sorted_by_util) >= 2:
        top_util = sorted_by_util[0][1]
        second_util = sorted_by_util[1][1]
        
        if (second_util - top_util) <= threshold:
            # Use priority to break tie
            return select_by_priority(sorted_by_util, model_priorities)
    
    return sorted_by_util[0][0]
```

### Recommended Approach

**Option A (Weighted Score)** provides smoother behavior and is more intuitive for operators. The weight factor can be made configurable via:
1. Constructor parameter in `ChutesUtilizationRouting`
2. Environment variable
3. YAML configuration

### Implementation Steps

1. Add `priority_weight` parameter to `ChutesUtilizationRouting.__init__()`
2. Add `utilization_threshold` parameter to control when priority is applied
3. Create method to read `order` from model_info in model_list
4. Modify `_find_least_utilized()` to use weighted scoring
5. Update `litellm-config.yaml` with example priority configurations
6. Add tests for priority weighting behavior

### Configuration Example

```python
# In chutes_routing.py
def __init__(
    self,
    chutes_api_key: Optional[str] = None,
    cache_ttl: int = 30,
    chutes_api_base: str = "https://api.chutes.ai",
    priority_weight: float = 0.3,  # NEW: Weight for priority (0-1)
    utilization_threshold: float = 0.1,  # NEW: Max util diff to apply priority
):
```

```yaml
# In litellm-config.yaml (optional - provide guidance)
# model_info:
#   order: 1  # 1 = highest priority, 3 = lowest
```

---

## Verification

- [ ] Verify priority weight parameter is properly read from configuration
- [ ] Test that order:1 model is preferred when util difference < threshold
- [ ] Test that util difference > threshold still routes to lowest util
- [ ] Verify configuration can be set via environment variable
- [ ] Add unit tests for weighted score calculation

---

## Related Issues

- Issue #2: No Load Threshold Protection
- Issue #3: Single Metric Only (can be combined)
- Issue #4: No Health Checks
