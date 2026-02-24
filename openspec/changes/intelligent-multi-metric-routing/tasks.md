# Implementation Tasks: intelligent-multi-metric-routing

## Overview

Implementation checklist for the intelligent multi-metric routing system. This feature adds a new routing strategy that considers multiple performance metrics (TPS, TTFT, quality, utilization) for optimal request distribution across AI model deployments.

## Setup

- [ ] **S-001**: Review existing codebase structure
      - Location: Root directory
      - Verify: `chutes_routing.py`, `litellm-config.yaml`, `start_litellm.py` exist

- [ ] **S-002**: Set up development environment
      - Command: `pip install httpx pyyaml pytest pytest-bdd`
      - Verify: Dependencies installed

- [ ] **S-003**: Create routing module directory
      - Command: `mkdir -p routing tests/bdd/steps`
      - Files created: `routing/__init__.py`, `tests/__init__.py`

---

## Phase 1: Data Models & Types

- [ ] **T1-001**: Create `routing/metrics.py` with `ChuteMetrics` dataclass
      - File: `routing/metrics.py`
      - Implements: `ChuteMetrics` with fields: chute_id, model, tps, ttft, utilization, total_invocations, fetched_at
      - Methods: `is_complete()`, `has_utilization()`

- [ ] **T1-002**: Create `ChuteScore` dataclass
      - File: `routing/metrics.py`
      - Implements: `ChuteScore` with normalized scores (0.0-1.0) and raw values
      - Fields: tps_normalized, ttft_normalized, quality_normalized, utilization_normalized, total_score, raw_*

- [ ] **T1-003**: Create `RoutingDecision` dataclass
      - File: `routing/metrics.py`
      - Implements: `RoutingDecision` with selected_chute, scores, decision_reason, fallback_mode, cache_hit, api_calls_made, warning

- [ ] **T1-004**: Create `routing/strategy.py` with `RoutingStrategy` enum
      - File: `routing/strategy.py`
      - Values: SPEED, LATENCY, BALANCED (default), QUALITY, UTILIZATION_ONLY

- [ ] **T1-005**: Create `StrategyWeights` dataclass
      - File: `routing/strategy.py`
      - Implements: Weights for TPS, TTFT, quality, utilization
      - Methods: `from_strategy()`, `validate()`

---

## Phase 2: Metrics Cache

- [ ] **T2-001**: Implement `MetricsCache` class with per-metric TTLs
      - File: `routing/cache.py`
      - Default TTLs: utilization=30s, tps=300s, ttft=300s, quality=300s
      - Methods: `get()`, `set()`, `get_all()`, `is_warm()`, `clear()`

- [ ] **T2-002**: Add cache hit/miss logging
      - File: `routing/cache.py`
      - Implement: Logging for cache operations

- [ ] **T2-003**: Write unit tests for MetricsCache
      - File: `tests/test_metrics_cache.py`
      - Coverage: TTL expiration, multi-metric storage, cache clear

---

## Phase 3: API Client Extension

- [ ] **T3-001**: Implement `ChutesAPIClient` class
      - File: `routing/client.py`
      - Endpoints: `/chutes/utilization`, `/invocations/stats/llm`
      - Methods: `fetch_utilization()`, `fetch_performance_stats()`, `fetch_all_metrics()`

- [ ] **T3-002**: Add response parsing for TPS/TTFT data
      - File: `routing/client.py`
      - Parse: JSON responses from `/invocations/stats/llm`

- [ ] **T3-003**: Add error handling for API failures
      - File: `routing/client.py`
      - Handle: Connection errors, timeouts, non-200 responses

- [ ] **T3-004**: Write integration tests for API client
      - File: `tests/test_api_client.py`
      - Coverage: Successful fetches, error handling (mocked)

---

## Phase 4: Scoring Engine

- [ ] **T4-001**: Implement normalization functions
      - File: `routing/intelligent.py`
      - Higher-is-better: TPS, quality, low utilization
      - Lower-is-better: TTFT (invert after normalization)

- [ ] **T4-002**: Implement quality derivation from total_invocations
      - File: `routing/intelligent.py`
      - Formula: `min(1.0, log10(total_invocations + 1) / 6.0)`

- [ ] **T4-003**: Implement weighted score calculation
      - File: `routing/intelligent.py`
      - Formula: `total_score = tps_norm * w_tps + ttft_norm * w_ttft + quality_norm * w_quality + util_norm * w_util`

- [ ] **T4-004**: Add weight validation
      - File: `routing/strategy.py`
      - Validate: Weights sum to 1.0 (±0.001 tolerance)

- [ ] **T4-005**: Write unit tests for scoring engine
      - File: `tests/test_scoring.py`
      - Coverage: Normalization edge cases, weight validation

---

## Phase 5: Main Routing Strategy

- [ ] **T5-001**: Create `IntelligentMultiMetricRouting` class
      - File: `routing/intelligent.py`
      - Inherits: `ChutesRoutingStrategy` (ABC)

- [ ] **T5-002**: Implement `select_chute()` method
      - File: `routing/intelligent.py`
      - Logic: Single chute check, complete metrics check, fallback check, scoring

- [ ] **T5-003**: Implement fallback to utilization-only
      - File: `routing/intelligent.py`
      - Trigger: Missing TPS/TTFT metrics
      - Fallback: Select lowest utilization

- [ ] **T5-004**: Add high utilization warning
      - File: `routing/intelligent.py`
      - Threshold: >80% utilization on all chutes

- [ ] **T5-005**: Add decision reason generation
      - File: `routing/intelligent.py`
      - Format: Human-readable explanation of why chute was selected

- [ ] **T5-006**: Write integration tests for routing
      - File: `tests/test_intelligent_routing.py`
      - Coverage: All routing scenarios

---

## Phase 6: Configuration

- [ ] **T6-001**: Add YAML configuration parsing
      - File: `routing/config.py` (new)
      - Options: routing_strategy, routing_weights, cache_ttls, chutes_api_url

- [ ] **T6-002**: Add environment variable support
      - File: `routing/config.py`
      - Variables: ROUTING_STRATEGY, ROUTING_TPS_WEIGHT, CACHE_TTL_TPS, etc.

- [ ] **T6-003**: Validate configuration on startup
      - File: `routing/config.py`
      - Checks: Weight sum, valid strategy, TTL values

- [ ] **T6-004**: Update `litellm-config.yaml` with new options
      - File: `litellm-config.yaml`
      - Add: router_settings.routing_strategy section

---

## Phase 7: Integration & Testing

### Example Verification

#### Input-Output Examples
- [ ] **EX-001**: Verify speed-optimized routing
      - Test: `test_speed_optimized_routing()` in `tests/test_intelligent_routing.py`
      - Expected: Qwen selected (highest TPS: 29.45)
      - Reference: `examples.md` EX-001

- [ ] **EX-002**: Verify latency-optimized routing
      - Test: `test_latency_optimized_routing()` in `tests/test_intelligent_routing.py`
      - Expected: Kimi selected (lowest TTFT: 6.45s)
      - Reference: `examples.md` EX-002

- [ ] **EX-003**: Verify balanced strategy
      - Test: `test_balanced_routing()` in `tests/test_intelligent_routing.py`
      - Expected: Kimi selected (best overall metrics)
      - Reference: `examples.md` EX-003

- [ ] **EX-004**: Verify quality-optimized routing
      - Test: `test_quality_optimized_routing()` in `tests/test_intelligent_routing.py`
      - Expected: Kimi selected (highest quality: 0.92)
      - Reference: `examples.md` EX-004

#### Edge Cases
- [ ] **EC-001**: Verify missing TPS/TTFT fallback
      - Test: `test_missing_metrics_fallback()` in `tests/test_intelligent_routing.py`
      - Expected: Fallback to utilization-only mode
      - Reference: `examples.md` EC-001

- [ ] **EC-002**: Verify high utilization handling
      - Test: `test_high_utilization_warning()` in `tests/test_intelligent_routing.py`
      - Expected: Warning included, route to least-loaded
      - Reference: `examples.md` EC-002

- [ ] **EC-003**: Verify single chute available
      - Test: `test_single_chute_selection()` in `tests/test_intelligent_routing.py`
      - Expected: Direct return without scoring
      - Reference: `examples.md` EC-003

- [ ] **EC-004**: Verify extreme TTFT variance
      - Test: `test_extreme_ttft_variance()` in `tests/test_intelligent_routing.py`
      - Expected: Normalized score > 0, not zero
      - Reference: `examples.md` EC-004

- [ ] **EC-005**: Verify cache hit behavior
      - Test: `test_cache_hit()` in `tests/test_metrics_cache.py`
      - Expected: No API calls made
      - Reference: `examples.md` EC-005

#### State Transitions
- [ ] **ST-001**: Verify cache lifecycle
      - Test: `test_cache_lifecycle()` in `tests/test_metrics_cache.py`
      - Expected: Cache populated, TTLs set correctly
      - Reference: `examples.md` ST-001

- [ ] **ST-002**: Verify strategy change mid-request
      - Test: `test_strategy_change()` in `tests/test_intelligent_routing.py`
      - Expected: Same cache, different decision
      - Reference: `examples.md` ST-002

- [ ] **ST-003**: Verify fallback mode activation
      - Test: `test_fallback_mode()` in `tests/test_intelligent_routing.py`
      - Expected: Graceful degradation
      - Reference: `examples.md` ST-003

### BDD Scenario Verification

- [ ] **BDD-001**: Speed-optimized (TPS priority)
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Speed optimized routing selects highest TPS"
      - Expected: Pass

- [ ] **BDD-002**: Latency-optimized (TTFT priority)
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Latency optimized routing selects lowest TTFT"
      - Expected: Pass

- [ ] **BDD-003**: Balanced strategy (equal weights)
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Balanced strategy selects best overall"
      - Expected: Pass

- [ ] **BDD-004**: Quality-optimized
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Quality optimized routing selects highest reliability"
      - Expected: Pass

- [ ] **BDD-005**: Missing metrics fallback
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Fallback to utilization when metrics unavailable"
      - Expected: Pass

- [ ] **BDD-006**: High utilization handling
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Warning when all chutes highly utilized"
      - Expected: Pass

- [ ] **BDD-007**: Single chute available
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Direct selection when only one chute available"
      - Expected: Pass

- [ ] **BDD-008**: Extreme TTFT variance
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Handles extreme TTFT differences gracefully"
      - Expected: Pass

- [ ] **BDD-009**: Cache hit
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Uses cached metrics when available"
      - Expected: Pass

- [ ] **BDD-010**: Cache miss (fresh fetch)
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Fetches fresh metrics on cache miss"
      - Expected: Pass

- [ ] **BDD-011**: Strategy change
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Same metrics produce different results with strategy change"
      - Expected: Pass

- [ ] **BDD-012**: Fallback mode
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Graceful degradation to utilization-only"
      - Expected: Pass

- [ ] **BDD-013**: Environment configuration
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Loads configuration from environment variables"
      - Expected: Pass

- [ ] **BDD-014**: Custom weights override
      - Framework: pytest-bdd
      - Feature: `tests/bdd/intelligent_routing.feature`
      - Scenario: "Custom weights override strategy defaults"
      - Expected: Pass

---

## Phase 8: Integration with LiteLLM

- [ ] **T8-001**: Register new strategy in LiteLLM
      - File: `chutes_routing.py`
      - Import: `IntelligentMultiMetricRouting`
      - Logic: Select based on config value

- [ ] **T8-002**: Update config loading in start script
      - File: `start_litellm.py`
      - Pass: New config options to routing

- [ ] **T8-003**: Write end-to-end tests
      - File: `tests/test_e2e_routing.py`
      - Coverage: Full request flow through LiteLLM

- [ ] **T8-004**: Performance benchmark routing decisions
      - Tool: `pytest-benchmark` or manual timing
      - Target: <10ms per decision (excluding API calls)

- [ ] **T8-005**: Test fallback behavior with running services
      - Method: Simulate API failures, verify fallback

---

## Phase 9: Documentation

- [ ] **T9-001**: Update README with new routing options
      - File: `README.md`
      - Add: Documentation for balanced, speed, latency, quality strategies

- [ ] **T9-002**: Document configuration options
      - File: `docs/configuration.md` (or README update)
      - Include: YAML config, env variables, TTL explanations

- [ ] **T9-003**: Add troubleshooting guide
      - Topics: High utilization warnings, fallback mode, cache issues

- [ ] **T9-004**: Create migration guide from old routing
      - Content: How to switch from utilization-only to multi-metric

---

## Verification Summary

### Implementation Phases

| Phase | Tasks | Completed |
|-------|-------|-----------|
| Phase 1: Data Models | T1-001 to T1-005 | [ ]/5 |
| Phase 2: Metrics Cache | T2-001 to T2-003 | [ ]/3 |
| Phase 3: API Client | T3-001 to T3-004 | [ ]/4 |
| Phase 4: Scoring Engine | T4-001 to T4-005 | [ ]/5 |
| Phase 5: Main Routing | T5-001 to T5-006 | [ ]/6 |
| Phase 6: Configuration | T6-001 to T6-004 | [ ]/4 |
| Phase 7: Integration | Examples + BDD | [ ]/26 |
| Phase 8: LiteLLM | T8-001 to T8-005 | [ ]/5 |
| Phase 9: Documentation | T9-001 to T9-004 | [ ]/4 |

### Example & Scenario Verification

| Category | Items | Completed |
|----------|-------|-----------|
| Input-Output Examples | 4 (EX-001 to EX-004) | [ ]/4 |
| Edge Cases | 5 (EC-001 to EC-005) | [ ]/5 |
| State Transitions | 3 (ST-001 to ST-003) | [ ]/3 |
| BDD Scenarios | 14 (BDD-001 to BDD-014) | [ ]/14 |
| **Total** | **26** | **[ ]/26** |

---

## Notes

- **User Decisions Incorporated**:
  - Skip `/miner/scores` - use `total_invocations` from `/chutes/utilization`
  - 5-minute refresh for TPS/TTFT (300s TTL)
  - Default strategy: `balanced` (25% each)
  - Fallback: `utilization-only`
  - Coexist with existing `ChutesUtilizationRouting`

- **Test Data** (from `examples.md`):
  - Kimi: TPS=28.31, TTFT=6.45s, Quality=0.92, Util=0.41
  - GLM: TPS=22.68, TTFT=28.85s, Quality=0.88, Util=0.55
  - Qwen: TPS=29.45, TTFT=9.41s, Quality=0.90, Util=0.63

- **Dependencies**:
  - httpx: Async HTTP client
  - PyYAML: Config loading
  - pytest: Testing framework
  - pytest-bdd: BDD scenarios

- **Reference Files**:
  - `design.md`: Technical implementation details
  - `behavior.md`: BDD scenario definitions
  - `examples.md`: Input-output examples with expected values

---

## Dependencies

| Artifact | Status | Path |
|----------|--------|------|
| proposal.md | Done | `openspec/changes/intelligent-multi-metric-routing/proposal.md` |
| examples.md | Done | `openspec/changes/intelligent-multi-metric-routing/examples.md` |
| behavior.md | Done | `openspec/changes/intelligent-multi-metric-routing/behavior.md` |
| design.md | Done | `openspec/changes/intelligent-multi-metric-routing/design.md` |
| tasks.md | Ready | `openspec/changes/intelligent-multi-metric-routing/tasks.md` |

---

*Generated by OpenSpec - BDD-EDD Schema*
