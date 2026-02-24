# Examples: Intelligent Multi-Metric Routing

## Overview

Concrete examples that define expected behavior through Input-Output pairs, Edge Cases, and State Transitions.

> **EDD Note**: These examples serve as the "training data" for understanding the feature. Make them specific, executable, and comprehensive enough that an AI can learn the pattern and generate correct behavior.

---

## Input-Output Examples

### Example 1: Speed-Optimized Routing (Highest TPS Wins)
**ID**: EX-001

**Context**: User wants fastest throughput - prioritize TPS metric

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 28.85,
      "quality": 0.88,
      "utilization": 0.55
    },
    {
      "id": "Qwen/Qwen3.5-397B-A17B-TEE",
      "model": "qwen3.5-397b-a17b-tee",
      "tps": 29.45,
      "ttft": 9.41,
      "quality": 0.90,
      "utilization": 0.63
    }
  ],
  "strategy": "speed",
  "weights": {
    "tps": 0.5,
    "ttft": 0.3,
    "quality": 0.1,
    "utilization": 0.1
  }
}
```

**Expected Output**:
```json
{
  "selected_chute": "Qwen/Qwen3.5-397B-A17B-TEE",
  "scores": {
    "moonshotai/kimi-k2.5-tee": {
      "tps_normalized": 0.96,
      "ttft_normalized": 1.00,
      "quality_normalized": 1.00,
      "utilization_normalized": 1.00,
      "total_score": 0.986
    },
    "zai-org/glm-5-tee": {
      "tps_normalized": 0.77,
      "ttft_normalized": 0.22,
      "quality_normalized": 0.96,
      "utilization_normalized": 0.75,
      "total_score": 0.562
    },
    "Qwen/Qwen3.5-397B-A17B-TEE": {
      "tps_normalized": 1.00,
      "ttft_normalized": 0.69,
      "quality_normalized": 0.98,
      "utilization_normalized": 0.65,
      "total_score": 0.853
    }
  },
  "decision_reason": "Qwen selected: highest TPS (29.45) with acceptable TTFT (9.41s)"
}
```

**Verification**: Qwen should be selected due to highest TPS (29.45), with Kimi as second choice

---

### Example 2: Latency-Optimized Routing (Lowest TTFT Wins)
**ID**: EX-002

**Context**: User wants fastest time-to-first-token - prioritize TTFT metric

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 28.85,
      "quality": 0.88,
      "utilization": 0.55
    },
    {
      "id": "Qwen/Qwen3.5-397B-A17B-TEE",
      "model": "qwen3.5-397b-a17b-tee",
      "tps": 29.45,
      "ttft": 9.41,
      "quality": 0.90,
      "utilization": 0.63
    }
  ],
  "strategy": "latency",
  "weights": {
    "tps": 0.1,
    "ttft": 0.6,
    "quality": 0.15,
    "utilization": 0.15
  }
}
```

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "scores": {
    "moonshotai/kimi-k2.5-tee": {
      "tps_normalized": 0.96,
      "ttft_normalized": 1.00,
      "quality_normalized": 1.00,
      "utilization_normalized": 1.00,
      "total_score": 1.00
    },
    "zai-org/glm-5-tee": {
      "tps_normalized": 0.77,
      "ttft_normalized": 0.22,
      "quality_normalized": 0.96,
      "utilization_normalized": 0.75,
      "total_score": 0.50
    },
    "Qwen/Qwen3.5-397B-A17B-TEE": {
      "tps_normalized": 1.00,
      "ttft_normalized": 0.69,
      "quality_normalized": 0.98,
      "utilization_normalized": 0.65,
      "total_score": 0.74
    }
  },
  "decision_reason": "Kimi selected: lowest TTFT (6.45s) - 4.5x faster than Qwen, 4x faster than GLM"
}
```

**Verification**: Kimi should be selected due to lowest TTFT (6.45s) - avoiding the 28.85s from GLM

---

### Example 3: Balanced Strategy (Equal Weights)
**ID**: EX-003

**Context**: User wants balanced performance across all metrics

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 28.85,
      "quality": 0.88,
      "utilization": 0.55
    },
    {
      "id": "Qwen/Qwen3.5-397B-A17B-TEE",
      "model": "qwen3.5-397b-a17b-tee",
      "tps": 29.45,
      "ttft": 9.41,
      "quality": 0.90,
      "utilization": 0.63
    }
  ],
  "strategy": "balanced",
  "weights": {
    "tps": 0.25,
    "ttft": 0.25,
    "quality": 0.25,
    "utilization": 0.25
  }
}
```

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "scores": {
    "moonshotai/kimi-k2.5-tee": {
      "tps_normalized": 0.96,
      "ttft_normalized": 1.00,
      "quality_normalized": 1.00,
      "utilization_normalized": 1.00,
      "total_score": 0.99
    },
    "zai-org/glm-5-tee": {
      "tps_normalized": 0.77,
      "ttft_normalized": 0.22,
      "quality_normalized": 0.96,
      "utilization_normalized": 0.75,
      "total_score": 0.675
    },
    "Qwen/Qwen3.5-397B-A17B-TEE": {
      "tps_normalized": 1.00,
      "ttft_normalized": 0.69,
      "quality_normalized": 0.98,
      "utilization_normalized": 0.65,
      "total_score": 0.83
    }
  },
  "decision_reason": "Kimi wins balanced: best TTFT (6.45s), good TPS (28.31), highest quality (0.92), lowest utilization (0.41)"
}
```

**Verification**: Kimi wins balanced due to best combination across all metrics

---

### Example 4: Quality-Optimized Routing
**ID**: EX-004

**Context**: User prioritizes output quality over speed

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 28.85,
      "quality": 0.88,
      "utilization": 0.55
    },
    {
      "id": "Qwen/Qwen3.5-397B-A17B-TEE",
      "model": "qwen3.5-397b-a17b-tee",
      "tps": 29.45,
      "ttft": 9.41,
      "quality": 0.90,
      "utilization": 0.63
    }
  ],
  "strategy": "quality",
  "weights": {
    "tps": 0.15,
    "ttft": 0.15,
    "quality": 0.5,
    "utilization": 0.2
  }
}
```

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "scores": {
    "moonshotai/kimi-k2.5-tee": {
      "tps_normalized": 0.96,
      "ttft_normalized": 1.00,
      "quality_normalized": 1.00,
      "utilization_normalized": 1.00,
      "total_score": 1.00
    },
    "zai-org/glm-5-tee": {
      "tps_normalized": 0.77,
      "ttft_normalized": 0.22,
      "quality_normalized": 0.96,
      "utilization_normalized": 0.75,
      "total_score": 0.75
    },
    "Qwen/Qwen3.5-397B-A17B-TEE": {
      "tps_normalized": 1.00,
      "ttft_normalized": 0.69,
      "quality_normalized": 0.98,
      "utilization_normalized": 0.65,
      "total_score": 0.84
    }
  },
  "decision_reason": "Kimi selected: highest quality score (0.92), also has best TTFT"
}
```

**Verification**: Kimi wins due to highest quality score (0.92)

---

## Edge Cases

### Edge Case 1: Missing TPS/TTFT Metrics (Fallback to Utilization)
**ID**: EC-001

**Context**: API returns partial metrics - TPS/TTFT unavailable

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": null,
      "ttft": null,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": null,
      "ttft": null,
      "quality": 0.88,
      "utilization": 0.85
    }
  ],
  "strategy": "balanced"
}
```

**Expected Behavior**:
Routing should fallback to utilization-only mode, selecting the chute with lowest utilization (less loaded)

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "fallback_mode": true,
  "decision_reason": "Metrics unavailable - fallback to utilization-only: Kimi (0.41) < GLM (0.85)"
}
```

**Verification**: System gracefully degrades to utilization-only routing

---

### Edge Case 2: All Chutes at High Utilization
**ID**: EC-002

**Context**: All chutes are heavily loaded (>0.8 utilization)

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.85
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 28.85,
      "quality": 0.88,
      "utilization": 0.82
    },
    {
      "id": "Qwen/Qwen3.5-397B-A17B-TEE",
      "model": "qwen3.5-397b-a17b-tee",
      "tps": 29.45,
      "ttft": 9.41,
      "quality": 0.90,
      "utilization": 0.91
    }
  ],
  "strategy": "balanced"
}
```

**Expected Behavior**:
System should still route but add warning/retry header for client awareness

**Expected Output**:
```json
{
  "selected_chute": "zai-org/glm-5-tee",
  "warning": "All chutes above 80% utilization",
  "decision_reason": "GLM has lowest utilization (0.82) among high-load candidates"
}
```

**Verification**: Routes to least-loaded chute despite all being at high utilization

---

### Edge Case 3: Single Chute Available
**ID**: EC-003

**Context**: Only one chute is available (others down/failed)

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    }
  ],
  "strategy": "balanced"
}
```

**Expected Behavior**:
Route to sole available chute without scoring

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "decision_reason": "Only one chute available"
}
```

**Verification**: Returns single available chute

---

### Edge Case 4: Extreme TTFT Variance
**ID**: EC-004

**Context**: One chute has extremely high TTFT compared to others

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41
    },
    {
      "id": "zai-org/glm-5-tee",
      "model": "glm-5-tee",
      "tps": 22.68,
      "ttft": 120.0,
      "quality": 0.88,
      "utilization": 0.30
    }
  ],
  "strategy": "latency"
}
```

**Expected Behavior**:
Normalized TTFT should handle extreme ratios gracefully (avoid near-zero scores)

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "scores": {
    "moonshotai/kimi-k2.5-tee": {
      "ttft_normalized": 1.00,
      "total_score": 1.00
    },
    "zai-org/glm-5-tee": {
      "ttft_normalized": 0.05,
      "total_score": 0.05
    }
  },
  "decision_reason": "Kimi: TTFT 6.45s vs GLM 120s (18.6x faster)"
}
```

**Verification**: GLM TTFT properly penalized but not zero

---

### Edge Case 5: Cache Hit (Skip API Calls)
**ID**: EC-005

**Context**: Metrics recently fetched, should use cached values

**Input**:
```json
{
  "chutes": [
    {
      "id": "moonshotai/kimi-k2.5-tee",
      "model": "kimi-k2.5-tee",
      "tps": 28.31,
      "ttft": 6.45,
      "quality": 0.92,
      "utilization": 0.41,
      "metrics_cached": true,
      "cache_age_ms": 5000
    }
  ],
  "strategy": "balanced",
  "cache_ttl": {
    "utilization": 5000,
    "tps": 10000,
    "ttft": 10000,
    "quality": 60000
  }
}
```

**Expected Behavior**:
Use cached metrics without making API calls

**Expected Output**:
```json
{
  "selected_chute": "moonshotai/kimi-k2.5-tee",
  "cache_hit": true,
  "api_calls_made": 0,
  "decision_reason": "Used cached metrics (age: 5s < TTL)"
}
```

**Verification**: No API calls made, cached values used

---

## State Examples

### State Transition 1: Metrics Cache Lifecycle
**ID**: ST-001

**Context**: Demonstrate how caching works across multiple requests

**Before Action**:
```
Cache state: EMPTY
Last fetch: None
Metrics available: None
```

**Action**:
```
Request 1: Route to /chat/completions
  -> Check cache: MISS
  -> Fetch from Chutes API
  -> Store in cache with TTLs:
     - utilization: 5s
     - tps: 10s  
     - ttft: 10s
     - quality: 60s
  -> Return routed chute
```

**After Action**:
```
Cache state: POPULATED
Last fetch: 2024-01-15T10:00:00Z
Metrics:
  - Kimi: {tps: 28.31, ttft: 6.45, quality: 0.92, util: 0.41}
  - GLM: {tps: 22.68, ttft: 28.85, quality: 0.88, util: 0.55}
  - Qwen: {tps: 29.45, ttft: 9.41, quality: 0.90, util: 0.63}
```

**Verification**: Second request within TTL uses cache

---

### State Transition 2: Strategy Change Mid-Request
**ID**: ST-002

**Context**: Client changes routing strategy between requests

**Before Action**:
```
Current strategy: speed
Cache: {Kimi: TPS=28.31, TTFT=6.45}
Last request used: speed strategy
```

**Action**:
```
Request arrives with strategy: latency
  -> Use cached metrics
  -> Recalculate scores with latency weights
  -> Route based on TTFT instead of TPS
```

**After Action**:
```
Selected: Kimi (was Qwen with speed strategy)
Reason: Now prioritizing TTFT (6.45s) over TPS (28.31)
Cache unchanged: {Kimi: TPS=28.31, TTFT=6.45}
```

**Verification**: Same cached metrics, different routing decision based on strategy

---

### State Transition 3: Fallback from Multi-Metric to Utilization-Only
**ID**: ST-003

**Context**: Metrics API becomes unavailable mid-operation

**Before Action**:
```
Mode: MULTI_METRIC
Cache: {Kimi: {tps: 28.31, ttft: 6.45, quality: 0.92, util: 0.41}}
Metrics API: AVAILABLE
```

**Action**:
```
Request arrives
  -> Check cache: MISS (TTL expired)
  -> Try fetch from metrics API
  -> ERROR: API unavailable (503)
  -> Fallback to utilization-only mode
  -> Use utilization from last successful fetch
```

**After Action**:
```
Mode: FALLBACK_UTILIZATION_ONLY
Selected: Kimi (lowest utilization: 0.41)
Warning: "Metrics API unavailable - using utilization-only fallback"
Cache: Unchanged from last successful fetch
```

**Verification**: Graceful degradation, continues routing

---

## Example Summary

| ID | Type | Description | Verification Method |
|----|------|-------------|---------------------|
| EX-001 | Input-Output | Speed-optimized (TPS priority) | Qwen selected (highest TPS) |
| EX-002 | Input-Output | Latency-optimized (TTFT priority) | Kimi selected (lowest TTFT) |
| EX-003 | Input-Output | Balanced strategy | Kimi selected (best overall) |
| EX-004 | Input-Output | Quality-optimized | Kimi selected (highest quality) |
| EC-001 | Edge Case | Missing TPS/TTFT metrics | Falls back to utilization-only |
| EC-002 | Edge Case | All chutes high utilization | Routes to least-loaded with warning |
| EC-003 | Edge Case | Single chute available | Returns sole available chute |
| EC-004 | Edge Case | Extreme TTFT variance | Handles gracefully, not zero |
| EC-005 | Edge Case | Cache hit | Uses cached values, no API calls |
| ST-001 | State | Cache lifecycle | Cache populated, TTLs set |
| ST-002 | State | Strategy change | Same metrics, different decision |
| ST-003 | State | Fallback mode | Graceful degradation |

---

## Notes

- All examples use real chute data from research:
  - Kimi: TPS=28.31, TTFT=6.45s, Quality=0.92, Util=0.41
  - GLM: TPS=22.68, TTFT=28.85s, Quality=0.88, Util=varies
  - Qwen: TPS=29.45, TTFT=9.41s, Quality=0.90, Util=varies

- Normalization uses min-max scaling: `normalized = (value - min) / (max - min)` for metrics where higher is better (TPS, quality, low utilization)
- For TTFT (lower is better): `normalized = 1 - (value - min) / (max - min)` or invert the ratio

- Default TTLs per metric type:
  - Utilization: 5 seconds
  - TPS: 10 seconds
  - TTFT: 10 seconds  
  - Quality: 60 seconds

- Reference proposal.md for scope details
- These examples should be self-verifying when implemented
