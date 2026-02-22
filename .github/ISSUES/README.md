# Chutes Load Balancer Routing - Implementation Issues

This directory contains detailed GitHub-style issue files documenting the identified implementation gaps in the chutes load balancer routing system.

## Issues Index

| # | Issue | Priority | Description |
|---|-------|----------|-------------|
| 01 | [Priority Weighting](./01-priority-weighting.md) | High | The `order` field in litellm-config.yaml exists but is not used in routing logic |
| 02 | [Load Threshold Protection](./02-load-threshold-protection.md) | High | No mechanism to reject requests when models exceed utilization threshold |
| 03 | [Multi-Factor Scoring](./03-multi-factor-scoring.md) | Medium | Current routing only considers utilization percentage, missing latency, error rate, cost |
| 04 | [Health Checks](./04-health-checks.md | High | No active health checks to verify model availability before routing |

## Quick Summary

### Gap 1: No Priority Weighting
- **Problem:** All three models treated equally despite `order` field in config
- **Impact:** Primary model not preferred when utilization is similar
- **Files:** `chutes_routing.py`, `litellm-config.yaml`

### Gap 2: No Load Threshold Protection
- **Problem:** Models at 99% utilization can still be selected
- **Impact:** Overloaded models continue receiving requests
- **Files:** `chutes_routing.py`

### Gap 3: Single Metric Only
- **Problem:** Only utilization percentage considered
- **Impact:** Ignores latency, error rates, cost efficiency
- **Files:** `chutes_routing.py`, potentially new `metrics/` module

### Gap 4: No Health Checks
- **Problem:** No verification that models actually respond before routing
- **Impact:** Requests fail after timeout when model is down
- **Files:** `chutes_routing.py`, potentially new `health_check.py` module

## Recommended Implementation Order

1. **Issue #4 (Health Checks)** - High priority for reliability
2. **Issue #2 (Load Threshold)** - High priority for reliability  
3. **Issue #1 (Priority Weighting)** - High priority for better utilization
4. **Issue #3 (Multi-Factor)** - Medium priority for optimization

## Related Documentation

- [README-routing.md](../README-routing.md) - Current routing system documentation
- [litellm-config.yaml](../litellm-config.yaml) - Model configuration
- [chutes_routing.py](../chutes_routing.py) - Current routing implementation
- [openspec/specs/routing/](../openspec/specs/routing/) - Routing specifications
