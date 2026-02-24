# Behavior: Intelligent Multi-Metric Routing

## Feature Description

**In order to** optimize request routing across multiple AI model deployments based on real-time performance metrics
**As a** system administrator or developer using the LiteLLM proxy
**I want to** route requests using a configurable multi-metric strategy that considers TPS, TTFT, quality, and utilization

> **Important**: This behavior specification covers **chute-level routing only**. The chutes.ai platform handles internal node/instance selection automatically. We cannot target specific nodes within a chute.

---

## Background

**Given** the system has access to real-time chute metrics from the Chutes API
**And** three model deployments are available: Kimi (moonshotai), GLM (zai-org), and Qwen
**And** the metric data includes: TPS (tokens/second), TTFT (time to first token), quality score (0-1), and utilization (0-1)
**And** the default chute metrics are:
- Kimi: TPS=28.31, TTFT=6.45s, Quality=0.92, Util=0.41
- GLM: TPS=22.68, TTFT=28.85s, Quality=0.88, Util=0.55
- Qwen: TPS=29.45, TTFT=9.41s, Quality=0.90, Util=0.63

---

## Scenarios

### Scenario 1: Speed-Optimized Routing - Highest TPS Wins
**ID**: BDD-001
**Priority**: Must Have
**Maps to**: EX-001

**Given** the routing strategy is set to "speed"
**And** the weight configuration is: TPS=0.5, TTFT=0.3, Quality=0.1, Utilization=0.1
**When** a routing request is received for all three chutes
**Then** the system should calculate normalized scores for each metric
**And** Qwen should be selected as it has the highest TPS (29.45)
**And** the decision reason should mention highest TPS with acceptable TTFT

---

### Scenario 2: Latency-Optimized Routing - Lowest TTFT Wins
**ID**: BDD-002
**Priority**: Must Have
**Maps to**: EX-002

**Given** the routing strategy is set to "latency"
**And** the weight configuration is: TPS=0.1, TTFT=0.6, Quality=0.15, Utilization=0.15
**When** a routing request is received for all three chutes
**Then** the system should prioritize TTFT in score calculation
**And** Kimi should be selected as it has the lowest TTFT (6.45s)
**And** the decision reason should mention Kimi is 4.5x faster than Qwen and 4x faster than GLM

---

### Scenario 3: Balanced Strategy - Equal Weights Across All Metrics
**ID**: BDD-003
**Priority**: Must Have
**Maps to**: EX-003

**Given** the routing strategy is set to "balanced"
**And** the weight configuration is: TPS=0.25, TTFT=0.25, Quality=0.25, Utilization=0.25
**When** a routing request is received for all three chutes
**Then** the system should calculate scores with equal emphasis on all metrics
**And** Kimi should be selected due to best combination: lowest TTFT (6.45s), good TPS (28.31), highest quality (0.92), lowest utilization (0.41)
**And** the total score for Kimi should be approximately 0.99

---

### Scenario 4: Quality-Optimized Routing - Highest Quality Score Wins
**ID**: BDD-004
**Priority**: Must Have
**Maps to**: EX-004

**Given** the routing strategy is set to "quality"
**And** the weight configuration is: TPS=0.15, TTFT=0.15, Quality=0.5, Utilization=0.2
**When** a routing request is received for all three chutes
**Then** the system should prioritize quality score in calculation
**And** Kimi should be selected due to highest quality (0.92)
**And** the total score for Kimi should be 1.00 (highest possible)

---

### Scenario 5: Missing TPS/TTFT Metrics - Fallback to Utilization
**ID**: BDD-005
**Priority**: Must Have
**Maps to**: EC-001

**Given** the Chutes API returns partial metrics with TPS=null and TTFT=null
**And** utilization data is available for all chutes
**When** a routing request is received
**Then** the system should detect the missing metrics
**And** fallback to utilization-only mode
**And** select the chute with lowest utilization (Kimi at 0.41)
**And** include "fallback_mode: true" in the response

---

### Scenario 6: All Chutes at High Utilization
**ID**: BDD-006
**Priority**: Must Have
**Maps to**: EC-002

**Given** all chutes have utilization above 0.8 (Kimi: 0.85, GLM: 0.82, Qwen: 0.91)
**When** a routing request is received with balanced strategy
**Then** the system should still route to a chute
**And** select the chute with lowest utilization (GLM at 0.82)
**And** include a warning about all chutes being above 80% utilization

---

### Scenario 7: Single Chute Available
**ID**: BDD-007
**Priority**: Must Have
**Maps to**: EC-003

**Given** only one chute (Kimi) is available in the system
**When** a routing request is received with any strategy
**Then** the system should route to the sole available chute
**And** the decision reason should indicate only one chute is available

---

### Scenario 8: Extreme TTFT Variance Handled Gracefully
**ID**: BDD-008
**Priority**: Should Have
**Maps to**: EC-004

**Given** Kimi has TTFT=6.45s and GLM has TTFT=120s (18.6x slower)
**When** routing with latency strategy
**Then** the system should normalize TTFT scores appropriately
**And** Kimi should be selected with TTFT normalized to 1.00
**And** GLM should have a normalized TTFT greater than zero (around 0.05)
**And** the decision reason should show the speed ratio

---

### Scenario 9: Cache Hit - Use Cached Metrics
**ID**: BDD-009
**Priority**: Should Have
**Maps to**: EC-005, ST-001

**Given** metrics were previously fetched and cached
**And** the cache age is within TTL (utilization: 5s, TPS: 10s, TTFT: 10s, quality: 60s)
**When** a routing request is received
**Then** the system should use cached values without making API calls
**And** include "cache_hit: true" in the response
**And** set api_calls_made to 0

---

### Scenario 10: Cache Miss - Fetch Fresh Metrics
**ID**: BDD-010
**Priority**: Should Have
**Maps to**: ST-001

**Given** the cache is empty or metrics have exceeded their TTL
**When** a routing request is received
**Then** the system should fetch fresh metrics from the Chutes API
**And** store the results in cache with appropriate TTLs
**And** set api_calls_made to the number of API calls made

---

### Scenario 11: Strategy Change Uses Same Cache
**ID**: BDD-011
**Priority**: Should Have
**Maps to**: ST-002

**Given** metrics are cached from a previous request with "speed" strategy
**When** a new request arrives with "latency" strategy
**Then** the system should reuse the cached metrics
**And** recalculate scores using the new latency weights
**And** select Kimi instead of Qwen (due to TTFT priority)
**And** the cache should remain unchanged

---

### Scenario 12: Fallback from Multi-Metric to Utilization-Only
**ID**: BDD-012
**Priority**: Should Have
**Maps to**: ST-003

**Given** the system is in multi-metric mode with cached metrics
**When** the metrics API becomes unavailable (503 error)
**And** the cached utilization data is still available
**Then** the system should switch to fallback mode
**And** route based on utilization only
**And** include a warning about metrics API unavailability
**And** continue routing without failure

---

### Scenario 13: Configuration via Environment Variables
**ID**: BDD-013
**Priority**: Could Have
**Maps to**: proposal.md (Configuration)

**Given** environment variables are set for routing configuration
**When** the routing system initializes
**Then** the system should load configuration from environment variables
**And** override default values with provided configuration

---

### Scenario 14: Custom Weights Override Strategy Defaults
**ID**: BDD-014
**Priority**: Could Have
**Maps to**: proposal.md (Pluggable strategies)

**Given** a custom weight configuration is provided
**When** scoring is calculated
**Then** the custom weights should override the strategy defaults
**And** the scoring should reflect the custom weight distribution

---

## Scenario Mapping to Examples

| Scenario ID | Description | Maps to Example ID |
|-------------|-------------|-------------------|
| BDD-001 | Speed-optimized (TPS priority) | EX-001 |
| BDD-002 | Latency-optimized (TTFT priority) | EX-002 |
| BDD-003 | Balanced strategy | EX-003 |
| BDD-004 | Quality-optimized | EX-004 |
| BDD-005 | Missing metrics fallback | EC-001 |
| BDD-006 | High utilization handling | EC-002 |
| BDD-007 | Single chute available | EC-003 |
| BDD-008 | Extreme TTFT variance | EC-004 |
| BDD-009 | Cache hit | EC-005 |
| BDD-010 | Cache miss | ST-001 |
| BDD-011 | Strategy change | ST-002 |
| BDD-012 | Fallback mode | ST-003 |
| BDD-013 | Environment config | proposal.md |
| BDD-014 | Custom weights | proposal.md |

---

## Business Rules

1. **Score Normalization**: All metrics must be normalized to 0-1 range before weighted calculation
   - For metrics where higher is better (TPS, quality, low utilization): `normalized = (value - min) / (max - min)`
   - For metrics where lower is better (TTFT): `normalized = 1 - (value - min) / (max - min)`

2. **Weight Validation**: Custom weights must sum to 1.0, otherwise reject with validation error

3. **Cache Invalidation**: Each metric type has its own TTL
   - Utilization: 5 seconds
   - TPS: 10 seconds
   - TTFT: 10 seconds
   - Quality: 60 seconds

4. **Fallback Hierarchy**: When metrics are unavailable, use this priority:
   - Full multi-metric (all metrics available)
   - Utilization-only (TPS/TTFT unavailable)
   - Random selection (no metrics available)

5. **High Utilization Warning**: When all chutes exceed 80% utilization, include warning in response

---

## Notes

- These scenarios are designed to be executable as automated tests (e.g., pytest-bdd)
- All numeric values in scenarios are based on real chute data from the examples
- The scoring algorithm uses weighted sum: `total_score = Σ(normalized_metric * weight)`
- The routing decision should complete in under 100ms (from proposal success criteria)
- Reference examples.md for detailed input/output data used in these scenarios
