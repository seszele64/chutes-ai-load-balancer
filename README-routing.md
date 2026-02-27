# Intelligent Multi-Metric Routing for LiteLLM

This document describes the intelligent multi-metric routing system that routes requests across multiple Chutes AI model deployments based on real-time performance metrics.

## Overview

The intelligent routing system replaces the legacy utilization-only approach with a sophisticated multi-metric scoring system. Instead of simply routing to the least utilized deployment, it considers:

- **TPS** (Tokens Per Second): Throughput - higher is better
- **TTFT** (Time To First Token): Latency - lower is better  
- **Quality**: Derived from total invocations - higher is better (reliability proxy)
- **Utilization**: Current load - lower is better

### Key Differences from Legacy Routing

| Aspect | Legacy (Utilization-Only) | New (Multi-Metric) |
|--------|---------------------------|-------------------|
| Metrics Used | Utilization only | TPS, TTFT, Quality, Utilization |
| Selection Logic | Minimum utilization | Highest weighted score |
| Scoring | Single value | Normalized multi-dimensional |
| Customization | None | Strategy + custom weights |

## Architecture

### Core Components

```
src/litellm_proxy/routing/
├── intelligent.py    # IntelligentMultiMetricRouting class
├── strategy.py      # RoutingStrategy enum, StrategyWeights
├── metrics.py       # ChuteMetrics, ChuteScore, RoutingDecision
├── config.py        # RoutingConfig (YAML/env loading)
└── cache.py        # MetricsCache (multi-metric caching)
```

### Class Overview

| Class | Purpose |
|-------|---------|
| `IntelligentMultiMetricRouting` | Main routing strategy implementation |
| `ChutesRoutingStrategy` | Abstract base class for routing strategies |
| `RoutingStrategy` | Enum defining available strategies |
| `StrategyWeights` | Dataclass for custom weight configuration |
| `ChuteMetrics` | Data model for per-chute metrics |
| `ChuteScore` | Normalized score breakdown |
| `RoutingDecision` | Routing decision result |
| `RoutingConfig` | Configuration from YAML/env |

### Request Flow

```
1. Request arrives at LiteLLM proxy
           │
           ▼
2. Router calls IntelligentMultiMetricRouting
           │
           ▼
3. Check metrics cache for each chute
   - Cache hit: Use cached values
   - Cache miss: Fetch from API
           │
           ▼
4. Calculate normalized scores per metric
           │
           ▼
5. Apply strategy weights and compute total score
           │
           ▼
6. Select highest-scoring chute
           │
           ▼
7. Route request to selected deployment
```

## Routing Strategies

The system provides five predefined strategies:

### Strategy Comparison

| Strategy | TPS | TTFT | Quality | Utilization | Best For |
|----------|-----|------|---------|-------------|----------|
| **balanced** | 25% | 25% | 25% | 25% | General purpose |
| **speed** | 50% | 30% | 10% | 10% | Batch processing |
| **latency** | 10% | 60% | 15% | 15% | Interactive apps |
| **quality** | 15% | 15% | 50% | 20% | Production workloads |
| **utilization_only** | 0% | 0% | 0% | 100% | Legacy fallback |

### Detailed Descriptions

#### `balanced` (Default)
Equal weights across all metrics. Best for general-purpose applications with no specific performance requirements.

```bash
python start_litellm.py --routing-strategy balanced
# or
export ROUTING_STRATEGY=balanced
```

#### `speed`
Optimizes for high throughput. Best for batch processing and high-volume workloads.

```bash
python start_litellm.py --routing-strategy speed
# or
export ROUTING_STRATEGY=speed
```

#### `latency` (Alias: `speed`)
Optimizes for lowest time-to-first-token. Best for interactive applications, chat interfaces, and real-time responses.

```bash
python start_litellm.py --routing-strategy latency
# or
export ROUTING_STRATEGY=latency
```

#### `quality`
Prioritizes reliability and consistency. Best for production workloads where quality is paramount.

```bash
python start_litellm.py --routing-strategy quality
# or
export ROUTING_STRATEGY=quality
```

#### `utilization_only`
Legacy behavior - routes to the least utilized deployment only. Use for fallback or simple load balancing.

```bash
python start_litellm.py --routing-strategy utilization_only
# or
export ROUTING_STRATEGY=utilization_only
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ROUTING_STRATEGY` | Routing strategy name | `balanced` |
| `ROUTING_TPS_WEIGHT` | TPS weight (0.0-1.0) | Strategy default |
| `ROUTING_TTFT_WEIGHT` | TTFT weight (0.0-1.0) | Strategy default |
| `ROUTING_QUALITY_WEIGHT` | Quality weight (0.0-1.0) | Strategy default |
| `ROUTING_UTILIZATION_WEIGHT` | Utilization weight (0.0-1.0) | Strategy default |
| `CACHE_TTL_UTILIZATION` | Utilization cache TTL (seconds) | 30 |
| `CACHE_TTL_TPS` | TPS cache TTL (seconds) | 300 |
| `CACHE_TTL_TTFT` | TTFT cache TTL (seconds) | 300 |
| `CACHE_TTL_QUALITY` | Quality cache TTL (seconds) | 300 |
| `CACHE_TTL_SECONDS` | General metrics cache TTL (seconds) | 60 |
| `CIRCUIT_BREAKER_ENABLED` | Enable circuit breaker | `true` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before opening | 3 |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | Cooldown period (seconds) | 30 |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | Successes to close circuit | 2 |
| `DEGRADATION_ENABLED` | Enable graceful degradation | `true` |
| `USE_STRUCTURED_RESPONSES` | Enable structured error responses | `false` |
| `CHUTES_API_URL` | Chutes API base URL | `https://api.chutes.ai` |
| `HIGH_UTILIZATION_THRESHOLD` | Warning threshold | 0.8 |

### YAML Configuration

Edit `litellm-config.yaml`:

```yaml
router_settings:
  # Strategy selection
  routing_strategy: balanced
  
  # Optional: Custom weights (must sum to 1.0)
  routing_weights:
    tps: 0.25
    ttft: 0.25
    quality: 0.25
    utilization: 0.25
  
  # Optional: Cache TTLs in seconds
  cache_ttls:
    utilization: 30
    tps: 300
    ttft: 300
    quality: 300
  
  # Optional: API URL
  chutes_api_url: "https://api.chutes.ai"
  
  # Optional: High utilization warning threshold
  high_utilization_warning_threshold: 0.8
```

### Custom Weights

For fine-grained control, set custom weights using environment variables:

```bash
# Example: Prioritize throughput with minimal latency concern
export ROUTING_TPS_WEIGHT=0.45
export ROUTING_TTFT_WEIGHT=0.45
export ROUTING_QUALITY_WEIGHT=0.05
export ROUTING_UTILIZATION_WEIGHT=0.05

python start_litellm.py --routing-strategy balanced
```

**Important:** Weights must sum to 1.0 (±0.001 tolerance).

## Usage Examples

### Starting the Proxy

```bash
# Default balanced strategy
python start_litellm.py

# With specific strategy
python start_litellm.py --routing-strategy speed

# With environment variable
export ROUTING_STRATEGY=latency
python start_litellm.py

# With debug logging to see routing decisions
python start_litellm.py --debug
```

### Making Requests

```bash
# Set the API key
export LITELLM_KEY=your-master-key

# Make a request
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chutes-models",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Programmatic Usage

```python
from litellm_proxy.routing.intelligent import IntelligentMultiMetricRouting
from litellm_proxy.routing.strategy import RoutingStrategy, StrategyWeights
from litellm_proxy.routing.cache import MetricsCache

# Create routing with default balanced strategy
routing = IntelligentMultiMetricRouting(
    chutes_api_key="your-api-key",
)

# Create routing with custom strategy
routing = IntelligentMultiMetricRouting(
    strategy=RoutingStrategy.SPEED,
    chutes_api_key="your-api-key",
)

# Create routing with custom weights
routing = IntelligentMultiMetricRouting(
    strategy=RoutingStrategy.BALANCED,
    custom_weights=StrategyWeights(
        tps=0.40,
        ttft=0.40,
        quality=0.10,
        utilization=0.10
    ),
    chutes_api_key="your-api-key",
    cache_ttl_utilization=30,
    cache_ttl_tps=300,
    cache_ttl_ttft=300,
    cache_ttl_quality=300,
)

# Set router reference (required for LiteLLM integration)
routing.set_router(router)
```

## API Reference

### IntelligentMultiMetricRouting

Main class implementing the multi-metric routing strategy.

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | `RoutingStrategy` | `BALANCED` | Routing strategy to use |
| `custom_weights` | `Optional[StrategyWeights]` | `None` | Custom weights (overrides strategy) |
| `cache` | `Optional[MetricsCache]` | `None` | Custom cache instance |
| `api_client` | `Optional[ChutesAPIClient]` | `None` | Custom API client |
| `chutes_api_key` | `Optional[str]` | `None` | API key for Chutes |
| `chutes_api_base` | `str` | `https://api.chutes.ai` | API base URL |
| `cache_ttl_utilization` | `int` | 30 | Cache TTL for utilization |
| `cache_ttl_tps` | `int` | 300 | Cache TTL for TPS |
| `cache_ttl_ttft` | `int` | 300 | Cache TTL for TTFT |
| `cache_ttl_quality` | `int` | 300 | Cache TTL for quality |

#### Methods

##### `select_chute(chutes, weights=None)`

Select the best chute based on metrics and weights.

**Parameters:**
- `chutes: List[ChuteMetrics]` - List of chute metrics
- `weights: Optional[StrategyWeights]` - Optional custom weights

**Returns:** `RoutingDecision` - Contains selected_chute, scores, decision_reason, etc.

##### `set_router(router)`

Set reference to the LiteLLM Router instance.

**Parameters:**
- `router` - LiteLLM Router instance

### RoutingStrategy Enum

```python
class RoutingStrategy(Enum):
    SPEED = "speed"
    LATENCY = "latency"
    BALANCED = "balanced"
    QUALITY = "quality"
    UTILIZATION_ONLY = "utilization_only"
    
    @classmethod
    def from_string(cls, value: str) -> "RoutingStrategy":
        """Create enum from string value."""
```

### StrategyWeights Dataclass

```python
@dataclass
class StrategyWeights:
    tps: float = 0.25
    ttft: float = 0.25
    quality: float = 0.25
    utilization: float = 0.25
    
    @classmethod
    def from_strategy(cls, strategy: RoutingStrategy) -> "StrategyWeights":
        """Get default weights for a routing strategy."""
    
    @classmethod
    def from_env(cls) -> "StrategyWeights":
        """Create weights from environment variables."""
    
    def validate(self) -> bool:
        """Validate that weights sum to 1.0."""
```

### ChuteMetrics Dataclass

```python
@dataclass
class ChuteMetrics:
    chute_id: str
    model: str = ""
    tps: Optional[float] = None
    ttft: Optional[float] = None
    utilization: Optional[float] = None
    total_invocations: Optional[int] = None
    fetched_at: float = field(default_factory=time.time)
    
    def is_complete(self) -> bool:
        """Check if core performance metrics are available."""
```

## Caching

The system uses multi-tier caching to reduce API calls:

| Metric | Default TTL | Description |
|--------|-------------|-------------|
| Utilization | 30 seconds | Changes frequently, needs fresh data |
| TPS | 5 minutes | Relatively stable |
| TTFT | 5 minutes | Relatively stable |
| Quality | 5 minutes | Derived from invocations, very stable |

This ensures fast routing decisions while keeping data reasonably fresh.

## Fallback Behavior

If metrics cannot be fetched:

1. **Try cached data**: If available, use stale cached values
2. **Utilization-only mode**: If no metrics available, fall back to selecting least utilized
3. **Random selection**: If no data at all, select randomly

### High Utilization Warning

When all chutes are above the threshold (default 80%), a warning is logged:

```
WARNING: All chutes above 80% utilization
```

This indicates you may need to scale your deployments.

---

## Circuit Breaker

The system includes a circuit breaker pattern to prevent cascading failures when chutes become unhealthy.

### States

| State | Description |
|-------|-------------|
| **CLOSED** | Normal operation - requests flow normally |
| **OPEN** | Circuit tripped - requests are rejected |
| **HALF_OPEN** | Testing recovery - limited requests allowed |

### Configuration

```bash
export CIRCUIT_BREAKER_ENABLED=true
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
export CIRCUIT_BREAKER_TIMEOUT_SECONDS=30
export CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2
```

### Monitoring

Check circuit state via response headers:

```bash
curl -I http://localhost:4000/v1/chat/completions ...
# X-Circuit-Breaker-State: CLOSED
```

---

## Graceful Degradation

The system implements 4 levels of graceful degradation to ensure continued service availability:

| Level | Name | Description |
|-------|------|-------------|
| **0** | Full | Normal operation with all metrics |
| **1** | Cached | Use cached metrics |
| **2** | Utilization-Only | Use utilization metric only |
| **3** | Random | Random selection |
| **4** | Failure | Return error (exhausted) |

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Degradation-Level` | Current degradation level (0-4) |
| `X-Circuit-Breaker-State` | Circuit breaker state |

### Configuration

```bash
export DEGRADATION_ENABLED=true
export USE_STRUCTURED_RESPONSES=true
```

---

## Error Response Format (RFC 9457)

When `USE_STRUCTURED_RESPONSES=true`, errors are returned in RFC 9457 Problem Details format:

```json
{
  "error": {
    "message": "All routing degradation levels exhausted: circuit breaker open",
    "type": "server_error",
    "code": "degradation_exhausted",
    "param": null,
    "degradation_level": 4,
    "circuit_breaker_state": "OPEN"
  }
}
```

The error response includes:
- `message`: Human-readable error description
- `type`: Error category (matches OpenAI format)
- `code`: Specific error code
- `degradation_level`: Current degradation level (if applicable)
- `circuit_breaker_state`: Circuit state (if applicable)

---

## Migration from Legacy Routing

To revert to the old utilization-only behavior:

```bash
# Option 1: CLI argument
python start_litellm.py --routing-strategy utilization_only

# Option 2: Environment variable
export ROUTING_STRATEGY=utilization_only
python start_litellm.py
```

See [docs/migration.md](migration.md) for detailed migration instructions.

## Troubleshooting

### Logs Not Showing Routing Decisions

Enable debug logging:

```bash
python start_litellm.py --debug
```

### High Utilization Warnings

This indicates your chutes are under heavy load. Consider:
- Scaling up deployments
- Using `utilization_only` strategy during high load
- Adding more chute instances

### Requests Always Go to Same Chute

Check the metrics:
1. Enable debug logging
2. Look for score breakdowns in logs
3. Verify the strategy weights match your expectations

### API Errors in Logs

If you see API errors:
1. Verify `CHUTES_API_KEY` is correct
2. Check network connectivity to `api.chutes.ai`
3. Verify your API key has sufficient permissions

## Files

| File | Description |
|------|-------------|
| `src/litellm_proxy/routing/intelligent.py` | Main routing implementation |
| `src/litellm_proxy/routing/strategy.py` | Strategy types and weights |
| `src/litellm_proxy/routing/metrics.py` | Data models |
| `src/litellm_proxy/routing/config.py` | Configuration loading |
| `src/litellm_proxy/routing/cache.py` | Metrics caching |
| `start_litellm.py` | Startup script |
| `litellm-config.yaml` | Model configuration |

## License

MIT License
