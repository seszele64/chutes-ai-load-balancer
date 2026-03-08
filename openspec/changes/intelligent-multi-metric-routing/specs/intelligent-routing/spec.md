# ADDED: Intelligent Multi-Metric Routing Strategy

## Summary

Adds a custom LiteLLM routing strategy that uses intelligent multi-metric scoring including TPS (tokens per second), TTFT (time to first token), quality (derived from total_invocations), and utilization metrics to select the best model chute for each request. This is a chute-level routing solution that coexists with the existing ChutesUtilizationRouting strategy.

---

## ADDED Requirements

### Requirement: Multi-Metric Scoring System

The routing strategy MUST calculate composite scores using weighted normalization for each available chute based on multiple performance metrics.

#### Scenario: Speed-Optimized Routing Selects Highest TPS

**GIVEN** the routing strategy is set to "speed" with weights (TPS=0.5, TTFT=0.3, Quality=0.1, Utilization=0.1)  
**WHEN** a routing request is received for all three chutes  
**THEN** the system SHALL calculate normalized scores for each metric  
**AND** Qwen SHALL be selected as it has the highest TPS (29.45)

#### Scenario: Latency-Optimized Routing Selects Lowest TTFT

**GIVEN** the routing strategy is set to "latency" with weights (TPS=0.1, TTFT=0.6, Quality=0.15, Utilization=0.15)  
**WHEN** a routing request is received for all three chutes  
**THEN** the system SHALL prioritize TTFT in score calculation  
**AND** Kimi SHALL be selected as it has the lowest TTFT (6.45s)

#### Scenario: Balanced Strategy Selects Best Overall

**GIVEN** the routing strategy is set to "balanced" with equal weights (25% each)  
**WHEN** a routing request is received for all three chutes  
**THEN** the system SHALL calculate scores with equal emphasis on all metrics  
**AND** Kimi SHALL be selected due to best combination: lowest TTFT (6.45s), good TPS (28.31), highest quality (0.92), lowest utilization (0.41)

---

### Requirement: Pluggable Routing Strategies

The routing strategy SHALL support multiple predefined strategies that can be selected via configuration.

#### Scenario: Quality-Optimized Routing

**GIVEN** the routing strategy is set to "quality" with weights (TPS=0.15, TTFT=0.15, Quality=0.5, Utilization=0.2)  
**WHEN** a routing request is received  
**THEN** the system SHALL prioritize quality score in calculation  
**AND** Kimi SHALL be selected due to highest quality (0.92)

#### Scenario: Utilization-Only Fallback

**GIVEN** the routing strategy is set to "utilization_only"  
**WHEN** scoring is calculated  
**THEN** the system SHALL use only utilization metric (TPS=0, TTFT=0, Quality=0, Utilization=1.0)  
**AND** select the chute with lowest utilization

---

### Requirement: Metrics Caching

The routing strategy SHALL cache metrics with separate TTLs per metric type to reduce API calls.

#### Scenario: Cache Hit Uses Cached Metrics

**GIVEN** metrics were previously fetched and cached  
**AND** the cache age is within TTL (utilization: 30s, TPS: 300s, TTFT: 300s, quality: 300s)  
**WHEN** a routing request is received  
**THEN** the system SHALL use cached values without making API calls  
**AND** include "cache_hit: true" in the response  
**AND** set api_calls_made to 0

#### Scenario: Cache Miss Fetches Fresh Metrics

**GIVEN** the cache is empty or metrics have exceeded their TTL  
**WHEN** a routing request is received  
**THEN** the system SHALL fetch fresh metrics from the Chutes API  
**AND** store the results in cache with appropriate TTLs  
**AND** set api_calls_made to the number of API calls made

---

### Requirement: Fallback Handling

The routing strategy SHALL gracefully handle missing or unavailable metrics.

#### Scenario: Missing TPS/TTFT Falls Back to Utilization

**GIVEN** the Chutes API returns partial metrics with TPS=null and TTFT=null  
**AND** utilization data is available for all chutes  
**WHEN** a routing request is received  
**THEN** the system SHALL detect the missing metrics  
**AND** fallback to utilization-only mode  
**AND** select the chute with lowest utilization  
**AND** include "fallback_mode: true" in the response

#### Scenario: All Chutes at High Utilization

**GIVEN** all chutes have utilization above 0.8  
**WHEN** a routing request is received with balanced strategy  
**THEN** the system SHALL still route to a chute  
**AND** select the chute with lowest utilization  
**AND** include a warning about all chutes being above 80% utilization

#### Scenario: Single Chute Available

**GIVEN** only one chute is available in the system  
**WHEN** a routing request is received with any strategy  
**THEN** the system SHALL route to the sole available chute  
**AND** the decision reason SHALL indicate only one chute is available

---

### Requirement: Configuration

The routing strategy SHALL support configuration via YAML and environment variables.

#### Scenario: Strategy Configuration via YAML

**GIVEN** litellm-config.yaml contains routing_strategy setting  
**WHEN** the routing system initializes  
**THEN** the system SHALL load the strategy configuration from YAML  
**AND** apply the configured strategy weights

#### Scenario: Custom Weights Override Strategy Defaults

**GIVEN** a custom weight configuration is provided in config  
**WHEN** scoring is calculated  
**THEN** the custom weights SHALL override the strategy defaults  
**AND** the scoring SHALL reflect the custom weight distribution  
**AND** custom weights MUST sum to 1.0

---

### Requirement: Normalization Algorithm

The routing strategy SHALL use min-max normalization for all metrics before applying weights.

#### Scenario: Higher-is-Better Metrics Normalization

**GIVEN** metrics where higher is better (TPS, quality, low utilization)  
**WHEN** normalizing  
**THEN** the system SHALL use: normalized = (value - min) / (max - min)

#### Scenario: Lower-is-Better Metrics Normalization

**GIVEN** metrics where lower is better (TTFT, high utilization)  
**WHEN** normalizing  
**THEN** the system SHALL use: normalized = 1 - (value - min) / (max - min)

---

### Requirement: Quality Derivation

The routing strategy SHALL derive quality scores from total_invocations as a reliability proxy.

#### Scenario: Quality Derived from Total Invocations

**GIVEN** total_invocations is available from /chutes/utilization endpoint  
**WHEN** calculating quality score  
**THEN** the system SHALL derive quality using log scale: min(1.0, log10(total_invocations + 1) / 6.0)  
**AND** 10^6 invocations equals quality score of 1.0
