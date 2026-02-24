# Change Proposal: Intelligent Multi-Metric Routing

## Problem Statement

Current routing only uses utilization data, ignoring critical performance metrics like TPS (tokens per second), TTFT (time to first token), and quality scores. This leads to suboptimal routing decisions - for example, routing to GLM with 28.85s latency when Kimi has only 6.45s. The existing ChutesUtilizationRouting strategy lacks awareness of latency, throughput, and quality metrics that are available from the chutes API.

## Scope

### In Scope
- [ ] Multi-metric scoring system (TPS, TTFT, quality, utilization)
- [ ] Pluggable routing strategies (speed/latency/quality/balanced)
- [ ] Metrics caching with separate TTLs per metric type
- [ ] Fallback to utilization-only when metrics unavailable
- [ ] Configuration via YAML and environment variables

### Out of Scope
- Machine learning-based routing
- Multi-armed bandit algorithms
- Client-side routing selection
- Historical trend analysis

## Approach

How will we solve this using EDD + BDD?

### EDD Strategy
- Use concrete examples of chute metrics to define scoring behavior
- Define input-output examples for each routing strategy
- Create edge case examples for metric unavailability scenarios
- Map metric combinations to expected routing decisions

### BDD Strategy
- Use Gherkin scenarios for routing decisions under different conditions
- Create Given-When-Then scenarios for:
  - Speed-optimized routing with varying TPS/TTFT
  - Quality-optimized routing with quality scores
  - Balanced routing with multiple metrics
  - Fallback behavior when metrics unavailable
- Map scenarios to automated test verification

## Success Criteria

### Example Verification
- [ ] All input-output examples pass verification
- [ ] All edge case examples handled correctly

### Scenario Verification
- [ ] All BDD scenarios pass
- [ ] Gherkin scenarios map to automated tests

### Performance Targets
- 40-60% improvement in average latency
- Configurable routing strategies
- Graceful fallback when APIs unavailable
- <100ms overhead per routing decision

## Risks

- **API rate limiting**: Aggressive caching with separate TTLs per metric type will mitigate excessive API calls
- **Metric staleness**: Separate TTLs per metric type (utilization: 5s, TPS: 10s, TTFT: 10s, quality: 60s) ensures fresh data without over-fetching
- **Configuration complexity**: Sensible defaults provided for all routing strategies

## Rollback Plan

If issues arise:
1. Revert to ChutesUtilizationRouting strategy (existing implementation)
2. Disable multi-metric features via configuration flag
3. Fall back to utilization-only mode

## Dependencies

### External Dependencies
- Chutes API endpoints:
  - `/chutes/utilization` - Current utilization data
  - `/invocations/stats/llm` - LLM invocation statistics (TPS, TTFT)
  - `/miner/scores` - Quality scores from miners
- LiteLLM proxy integration (http://localhost:4000)

### Internal Dependencies
- Existing ChutesUtilizationRouting strategy (to be extended)
- litellm-config.yaml - Model configuration
- chutes_routing.py - Custom LiteLLM routing strategy
