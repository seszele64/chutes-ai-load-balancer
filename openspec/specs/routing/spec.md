# Routing Specification

## Purpose
The intelligent routing system provides multi-metric load balancing for the chutes-load-balancer, enabling requests to be routed to the optimal model deployment based on utilization, latency, throughput, and quality metrics. The system uses weighted scoring algorithms with configurable strategies to ensure requests are handled by the best available model instance.

## Requirements

### Requirement: The routing system SHALL intelligently select model instances
Users SHALL have their requests routed to the best available model instance based on multiple performance metrics.

#### Scenario: Multi-metric routing decision
- **GIVEN** multiple available model instances
- **WHEN** a request needs to be routed
- **THEN** the system selects the instance based on utilization, latency, throughput, and quality metrics
- **AND** the selection uses weighted scoring where higher scores indicate better candidates

### Requirement: The routing system SHALL support multiple routing strategies
Users SHALL be able to select from different routing strategies optimized for different use cases.

#### Scenario: Strategy selection
- **GIVEN** the routing system is configured
- **WHEN** a user selects a routing strategy (balanced, speed, latency, quality, or utilization_only)
- **THEN** the system applies the corresponding weight distribution to metrics
- **AND** requests are routed according to those weights

### Requirement: The routing system SHALL cache metrics with configurable TTLs
Users SHALL have metrics cached to reduce API calls while ensuring freshness.

#### Scenario: Metrics caching
- **GIVEN** metrics have been fetched from the Chutes API
- **WHEN** subsequent routing decisions are needed
- **THEN** the system uses cached metrics if within TTL
- **AND** different metrics can have different TTLs (utilization: 30s, TPS/TTFT/quality: 300s)

### Requirement: The routing system SHALL provide fallback behavior when metrics are unavailable
Users SHALL have requests routed even when some or all metrics are unavailable.

#### Scenario: Fallback to utilization-only mode
- **GIVEN** TPS and TTFT metrics are unavailable
- **WHEN** a routing decision is needed
- **THEN** the system falls back to utilization-only routing
- **AND** continues to route requests based on utilization data

#### Scenario: Fallback to random selection
- **GIVEN** no metrics are available from the API
- **WHEN** a routing decision is needed
- **THEN** the system randomly selects a model instance
- **AND** logs a warning about the fallback behavior

### Requirement: The routing system SHALL normalize metrics to a consistent scale
Users SHALL have metrics compared fairly across different raw values.

#### Scenario: Metric normalization
- **GIVEN** raw metric values from different model instances
- **WHEN** calculating scores
- **THEN** all metrics are normalized to 0.0-1.0 where higher is always better
- **AND** metrics where lower is better (TTFT, utilization) are inverted during normalization

## Overview

This specification defines the intelligent multi-metric routing system for the chutes-load-balancer project. The routing system uses multiple performance metrics from the Chutes AI API to intelligently route requests to the optimal model deployment based on configurable strategies.

The current implementation supports five routing strategies: balanced (default), speed, latency, quality, and utilization_only. Each strategy uses weighted scoring across four performance metrics.

## Current Implementation

### Architecture

```
Client Request
      │
      ▼
┌─────────────────┐
│ LiteLLM Router  │
│ (Port 4000)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│           IntelligentMultiMetricRouting                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           ChutesRoutingStrategy (ABC)                │  │
│  │   - select_chute() - Strategy pattern                │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                    │                  │          │
│         ▼                    ▼                  ▼          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐      │
│  │ MetricsCache│    │ScoringEngine│    │ChutesAPI   │      │
│  │ - utilization│    │ - TPS      │    │ Client     │      │
│  │ - TPS       │    │ - TTFT     │    │            │      │
│  │ - TTFT      │    │ - Quality  │    │            │      │
│  │ - Quality   │    │ - Util     │    │            │      │
│  └────────────┘    └────────────┘    └────────────┘      │
└────────┬────────────────────────────────────────────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌───────┐ ┌───────┐ ┌───────────┐
│ Kimi  │ │ GLM-5 │ │ Qwen3.5   │
│ K2.5  │ │ TEE   │ │ 397B      │
│ TEE   │ │       │ │ TEE       │
└───────┘ └───────┘ └───────────┘
```

### Core Components

#### 1. IntelligentMultiMetricRouting Class

**Location**: `src/litellm_proxy/routing/intelligent.py`

**Responsibilities**:
- Fetch multiple performance metrics from Chutes API (`/chutes/utilization`, `/invocations/stats/llm`)
- Cache metrics with configurable per-metric TTLs
- Calculate weighted scores based on strategy
- Route requests to the highest-scoring deployment
- Provide fallback behavior when metrics are unavailable

**Key Methods**:
- `async_get_available_deployment()` - Async routing decision
- `get_available_deployment()` - Sync routing decision
- `select_chute()` - Core scoring and selection logic
- `_calculate_scores()` - Normalize and weight metrics
- `_fallback_to_utilization()` - Fallback when TPS/TTFT unavailable

**Constructor Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | RoutingStrategy | BALANCED | The routing strategy to use |
| `custom_weights` | Optional[StrategyWeights] | None | Custom weights (overrides strategy) |
| `cache` | Optional[MetricsCache] | None | Custom cache instance |
| `api_client` | Optional[ChutesAPIClient] | None | Custom API client |
| `chutes_api_key` | Optional[str] | env.CHUTES_API_KEY | API key for Chutes |
| `chutes_api_base` | str | https://api.chutes.ai | API base URL |
| `cache_ttl_utilization` | int | 30 | Cache TTL for utilization (seconds) |
| `cache_ttl_tps` | int | 300 | Cache TTL for TPS (seconds) |
| `cache_ttl_ttft` | int | 300 | Cache TTL for TTFT (seconds) |
| `cache_ttl_quality` | int | 300 | Cache TTL for quality (seconds) |

#### 2. ChutesRoutingStrategy Abstract Base Class

**Location**: `src/litellm_proxy/routing/intelligent.py`

**Purpose**: Abstract base class for pluggable routing strategies using the Strategy pattern.

**Methods**:
- `select_chute(chutes: List[ChuteMetrics], weights: Optional[StrategyWeights]) -> RoutingDecision`

#### 3. RoutingStrategy Enum

**Location**: `src/litellm_proxy/routing/strategy.py`

Defines available routing strategies with predefined weights.

**Values**:
- `SPEED` - Prioritizes throughput (TPS)
- `LATENCY` - Prioritizes response time (TTFT)
- `BALANCED` - Equal weights (default)
- `QUALITY` - Prioritizes reliability
- `UTILIZATION_ONLY` - Legacy mode, utilization only

#### 4. StrategyWeights Dataclass

**Location**: `src/litellm_proxy/routing/strategy.py`

**Attributes**:
| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `tps` | float | 0.25 | Weight for TPS (higher is better) |
| `ttft` | float | 0.25 | Weight for TTFT (lower is better) |
| `quality` | float | 0.25 | Weight for quality (higher is better) |
| `utilization` | float | 0.25 | Weight for utilization (lower is better) |

**Methods**:
- `from_strategy(strategy: RoutingStrategy) -> StrategyWeights` - Get default weights
- `from_env() -> StrategyWeights` - Create from environment variables
- `validate() -> bool` - Validate weights sum to 1.0
- `to_dict() -> dict` - Convert to dictionary

#### 5. MetricsCache Class

**Location**: `src/litellm_proxy/routing/cache.py`

**Purpose**: Multi-metric cache with separate TTLs per metric type.

**Default TTLs**:
| Metric | TTL | Description |
|--------|-----|-------------|
| `utilization` | 30s | Needs fresh data for load balancing |
| `tps` | 300s | Throughput is relatively stable |
| `ttft` | 300s | Latency is relatively stable |
| `quality` | 300s | Derived from total_invocations |
| `total_invocations` | 300s | Changes slowly |

**Methods**:
- `get(chute_id: str, metric: str) -> Optional[Any]` - Get single metric
- `set(chute_id: str, metric: str, value: Any)` - Cache single metric
- `get_all(chute_id: str) -> Optional[ChuteMetrics]` - Get all metrics
- `set_all(metrics: ChuteMetrics)` - Cache all metrics
- `is_warm() -> bool` - Check if cache has data
- `clear(chute_id: Optional[str])` - Clear cache

#### 6. Data Models

**ChuteMetrics** (`src/litellm_proxy/routing/metrics.py`):
```python
@dataclass
class ChuteMetrics:
    chute_id: str
    model: str = ""
    tps: Optional[float] = None          # tokens per second
    ttft: Optional[float] = None          # time to first token (seconds)
    utilization: Optional[float] = None    # 0.0 - 1.0
    total_invocations: Optional[int] = None
    fetched_at: float = field(default_factory=time.time)
```

**ChuteScore**:
```python
@dataclass
class ChuteScore:
    chute_id: str
    tps_normalized: float = 0.0           # 0.0 - 1.0 (higher is better)
    ttft_normalized: float = 0.0           # 0.0 - 1.0 (higher is better)
    quality_normalized: float = 0.0       # 0.0 - 1.0 (higher is better)
    utilization_normalized: float = 0.0   # 0.0 - 1.0 (higher is better)
    total_score: float = 0.0              # Weighted sum
```

**RoutingDecision**:
```python
@dataclass
class RoutingDecision:
    selected_chute: str
    scores: Dict[str, ChuteScore] = field(default_factory=dict)
    decision_reason: str = ""
    fallback_mode: bool = False
    cache_hit: bool = False
    api_calls_made: int = 0
    warning: Optional[str] = None
```

## Routing Strategies

### Strategy Comparison Table

| Strategy | TPS Weight | TTFT Weight | Quality Weight | Utilization Weight | Best For |
|----------|------------|-------------|----------------|--------------------|----------|
| **BALANCED** (default) | 25% | 25% | 25% | 25% | General purpose |
| **SPEED** | 50% | 30% | 10% | 10% | High-throughput workloads |
| **LATENCY** | 10% | 60% | 15% | 15% | Interactive applications |
| **QUALITY** | 15% | 15% | 50% | 20% | Critical production tasks |
| **UTILIZATION_ONLY** | 0% | 0% | 0% | 100% | Legacy fallback mode |

### Detailed Strategy Descriptions

#### 1. BALANCED (Default)

**Configuration**: `ROUTING_STRATEGY=balanced`

**Weights**:
- TPS: 25% (throughput)
- TTFT: 25% (latency)
- Quality: 25% (reliability proxy)
- Utilization: 25% (load distribution)

**Best for**:
- General-purpose applications
- Mixed workloads
- Initial deployment without specific requirements

#### 2. SPEED

**Configuration**: `ROUTING_STRATEGY=speed`

**Weights**:
- TPS: 50%
- TTFT: 30%
- Quality: 10%
- Utilization: 10%

**Best for**:
- High-throughput batch processing
- Data processing pipelines
- Volume-oriented workloads

#### 3. LATENCY

**Configuration**: `ROUTING_STRATEGY=latency`

**Weights**:
- TPS: 10%
- TTFT: 60%
- Quality: 15%
- Utilization: 15%

**Best for**:
- Interactive chat applications
- Real-time responses
- User-facing applications

#### 4. QUALITY

**Configuration**: `ROUTING_STRATEGY=quality`

**Weights**:
- TPS: 15%
- TTFT: 15%
- Quality: 50%
- Utilization: 20%

**Best for**:
- Production workloads
- Critical tasks requiring reliability
- Systems with SLA requirements

#### 5. UTILIZATION_ONLY

**Configuration**: `ROUTING_STRATEGY=utilization_only`

**Weights**:
- TPS: 0%
- TTFT: 0%
- Quality: 0%
- Utilization: 100%

**Best for**:
- Legacy compatibility
- Simple load balancing
- Fallback mode during metrics API outages

## Scoring Algorithm

### Normalization

Each metric is normalized to a 0.0-1.0 scale where higher is always better:

| Metric | Raw Value | Normalization | Notes |
|--------|-----------|---------------|-------|
| **TPS** | tokens/sec | `value / max(values)` | Higher is better |
| **TTFT** | seconds | `min(values) / value` | Lower is better (inverted) |
| **Quality** | invocations | `log10(invocations+1) / 6` | Derived from total_invocations |
| **Utilization** | 0.0-1.0 | `min(values) / value` | Lower is better (inverted) |

### Score Calculation

```
total_score = (tps_normalized * tps_weight)
            + (ttft_normalized * ttft_weight)
            + (quality_normalized * quality_weight)
            + (utilization_normalized * utilization_weight)
```

The chute with the highest `total_score` is selected.

### Edge Cases

1. **Single Chute**: Return immediately without scoring
2. **Missing Metrics**: If TPS/TTFT unavailable, fall back to utilization-only
3. **No Metrics at All**: Random selection
4. **All Chutes High Utilization**: Log warning when all > 80%

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ROUTING_STRATEGY` | Strategy selection | `balanced` |
| `ROUTING_TPS_WEIGHT` | Custom TPS weight | Strategy default |
| `ROUTING_TTFT_WEIGHT` | Custom TTFT weight | Strategy default |
| `ROUTING_QUALITY_WEIGHT` | Custom quality weight | Strategy default |
| `ROUTING_UTILIZATION_WEIGHT` | Custom utilization weight | Strategy default |
| `CACHE_TTL_UTILIZATION` | Utilization cache TTL | 30 |
| `CACHE_TTL_TPS` | TPS cache TTL | 300 |
| `CACHE_TTL_TTFT` | TTFT cache TTL | 300 |
| `CACHE_TTL_QUALITY` | Quality cache TTL | 300 |
| `CHUTES_API_KEY` | API key for Chutes | Required |
| `CHUTES_API_BASE` | API base URL | `https://api.chutes.ai` |

### CLI Arguments

The routing strategy can be configured via command line:

```bash
python start_litellm.py --routing-strategy balanced
python start_litellm.py --routing-strategy speed
python start_litellm.py --routing-strategy latency
python start_litellm.py --routing-strategy quality
python start_litellm.py --routing-strategy utilization_only
```

### YAML Configuration

In `litellm-config.yaml`:

```yaml
router_settings:
  routing_strategy: balanced
  routing_weights:
    tps: 0.25
    ttft: 0.25
    quality: 0.25
    utilization: 0.25
  cache_ttls:
    utilization: 30
    tps: 300
    ttft: 300
    quality: 300
  chutes_api_url: "https://api.chutes.ai"
  high_utilization_warning_threshold: 0.8
```

## Fallback Behavior

### Fallback Chain

When the intelligent routing strategy fails:

1. **Cache Check**: Use cached metrics if available
2. **Utilization-Only Mode**: If TPS/TTFT unavailable, use utilization only
3. **Random Selection**: If no metrics available, select randomly
4. **Return None**: Fall back to LiteLLM default routing

### Fallback Conditions

| Condition | Fallback Action |
|-----------|-----------------|
| No model list available | Return None |
| No metrics from API | Return None |
| TPS/TTFT unavailable | Use utilization-only |
| No utilization data | Random selection |
| All chutes high utilization | Log warning, continue |

## High Utilization Warning

When all chutes exceed the utilization threshold (default: 80%), a warning is logged:

```
WARNING: All chutes above 80% utilization
```

This indicates potential capacity issues requiring scaling.

## Chutes API Integration

### Endpoints Used

| Endpoint | Purpose | Metrics Retrieved |
|----------|---------|------------------|
| `GET /chutes/utilization` | Load data | utilization, total_invocations |
| `GET /invocations/stats/llm` | Performance | tps, ttft |

### API Response Formats

**Utilization Response**:
```json
[
  {
    "chute_id": "uuid...",
    "name": "moonshotai/Kimi-K2.5-TEE",
    "utilization_current": 0.5,
    "utilization_5m": 0.4,
    "utilization_15m": 0.3,
    "total_invocations": 1000000
  }
]
```

**LLM Stats Response**:
```json
{
  "chute_id": {
    "tps": 45.2,
    "ttft": 0.85
  }
}
```

## LiteLLM Router Configuration

**Config File**: `litellm-config.yaml`

```yaml
model_list:
  - model_name: chutes-models
    litellm_params:
      model: openai/moonshotai/Kimi-K2.5-TEE
      api_base: https://llm.chutes.ai/v1
      api_key: os.environ/CHUTES_API_KEY
    model_info:
      id: <chute_uuid>
      chute_id: chute_kimi_k2.5_tee
      order: 1

router_settings:
  routing_strategy: simple-shuffle  # Default fallback
  num_retries: 3
  timeout: 300
  allowed_fails: 5
  cooldown_time: 30
```

## Migration from Legacy Routing

### Old System

The previous system used:
- `chutes_routing.py` - Main implementation
- `ChutesUtilizationRouting` class
- Single metric: utilization only

### New System

The new system uses:
- `src/litellm_proxy/routing/intelligent.py` - Main implementation
- `IntelligentMultiMetricRouting` class
- Multiple metrics: TPS, TTFT, Quality, Utilization

### Migration Steps

1. **Strategy Selection**: Choose appropriate strategy or use defaults
2. **Weight Tuning**: Adjust weights if needed
3. **Cache TTLs**: Configure based on API rate limits

### Equivalent Configurations

| Old Behavior | New Configuration |
|--------------|-------------------|
| Utilization-only | `--routing-strategy utilization_only` |
| Default | `--routing-strategy balanced` |

## Testing

### Unit Tests

The routing strategy should be tested for:
- Score calculation with various weight combinations
- Normalization edge cases (zero values, single item)
- Cache hit/miss scenarios
- API timeout handling
- Fallback behavior

### Integration Tests

- End-to-end routing through LiteLLM proxy
- Failover when primary model is unavailable
- Cache expiration and refresh
- High utilization warnings

## Related Files

- `src/litellm_proxy/routing/intelligent.py` - Main routing implementation
- `src/litellm_proxy/routing/strategy.py` - Strategy types and weights
- `src/litellm_proxy/routing/metrics.py` - Data models
- `src/litellm_proxy/routing/cache.py` - Caching implementation
- `src/litellm_proxy/api/client.py` - Chutes API client
- `docs/routing-guide.md` - User guide
- `litellm-config.yaml` - Model configuration
- `openspec/specs/proxy/spec.md` - LiteLLM proxy spec
