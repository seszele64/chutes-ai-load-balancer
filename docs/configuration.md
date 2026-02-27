# Configuration Reference

Complete configuration reference for the intelligent multi-metric routing system.

## Environment Variables

### Required Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CHUTES_API_KEY` | API key for Chutes AI | Yes |
| `LITELLM_MASTER_KEY` | Master key for LiteLLM proxy | Recommended |

### Routing Strategy Variables

| Variable | Description | Default | Valid Values |
|----------|-------------|---------|--------------|
| `ROUTING_STRATEGY` | Routing strategy to use | `balanced` | `balanced`, `speed`, `latency`, `quality`, `utilization_only` |

### Custom Weight Variables

All weights must sum to 1.0 (±0.001 tolerance).

| Variable | Description | Default (balanced) | Range |
|----------|-------------|-------------------|-------|
| `ROUTING_TPS_WEIGHT` | Weight for TPS (throughput) | 0.25 | 0.0 - 1.0 |
| `ROUTING_TTFT_WEIGHT` | Weight for TTFT (latency) | 0.25 | 0.0 - 1.0 |
| `ROUTING_QUALITY_WEIGHT` | Weight for quality | 0.25 | 0.0 - 1.0 |
| `ROUTING_UTILIZATION_WEIGHT` | Weight for utilization | 0.25 | 0.0 - 1.0 |

### Cache TTL Variables

| Variable | Description | Default | Unit |
|----------|-------------|---------|------|
| `CACHE_TTL_UTILIZATION` | Cache TTL for utilization | 30 | seconds |
| `CACHE_TTL_TPS` | Cache TTL for TPS | 300 | seconds |
| `CACHE_TTL_TTFT` | Cache TTL for TTFT | 300 | seconds |
| `CACHE_TTL_QUALITY` | Cache TTL for quality | 300 | seconds |

### API Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CHUTES_API_URL` | Base URL for Chutes API | `https://api.chutes.ai` |
| `HIGH_UTILIZATION_THRESHOLD` | Threshold for high utilization warnings | 0.8 |

### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LITELLM_PORT` | Port to run the proxy on | 4000 |
| `LITELLM_HOST` | Host to bind to | 0.0.0.0 |
| `LITELLM_CONFIG_PATH` | Path to litellm-config.yaml | ./litellm-config.yaml |

## YAML Configuration

### Router Settings

```yaml
router_settings:
  # Fallback routing strategy (used if custom strategy fails)
  routing_strategy: simple-shuffle
  
  # Intelligent routing strategy
  routing_strategy_multi_metric: balanced  # Options: balanced, speed, latency, quality, utilization_only
  
  # Custom weights (optional, must sum to 1.0)
  routing_weights:
    tps: 0.25
    ttft: 0.25
    quality: 0.25
    utilization: 0.25
  
  # Cache TTLs in seconds (optional)
  cache_ttls:
    utilization: 30
    tps: 300
    ttft: 300
    quality: 300
  
  # Chutes API URL (optional)
  chutes_api_url: "https://api.chutes.ai"
  
  # High utilization warning threshold (optional)
  high_utilization_warning_threshold: 0.8
  
  # Router settings
  enable_pre_call_checks: false
  num_retries: 3
  timeout: 300
  allowed_fails: 5
  cooldown_time: 30
```

### Model List Configuration

```yaml
model_list:
  - model_name: chutes-models
    litellm_params:
      model: openai/moonshotai/Kimi-K2.5-TEE
      api_base: https://llm.chutes.ai/v1
      api_key: os.environ/CHUTES_API_KEY
    model_info:
      id: chute-id-from-dashboard
      chute_id: chute_kimi_k2.5_tee
      order: 1
  
  # Add more models as needed...
```

### General Settings

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY

litellm_settings:
  public_routes:
    - "/health"
    - "/health/liveness"
    - "/health/readiness"
    - "/metrics"
    - "/"
    - "/v1/models"
  allow_requests_on_missing_api_key: true
  ui_access: true
```

## Strategy Presets

### Quick Comparison

| Strategy | TPS | TTFT | Quality | Utilization | Use Case |
|----------|-----|------|---------|-------------|----------|
| **balanced** | 25% | 25% | 25% | 25% | General purpose |
| **speed** | 50% | 30% | 10% | 10% | Batch processing |
| **latency** | 10% | 60% | 15% | 15% | Interactive apps |
| **quality** | 15% | 15% | 50% | 20% | Production workloads |
| **utilization_only** | 0% | 0% | 0% | 100% | Simple load balancing |

### Balanced (Default)

Best for: General-purpose applications with no specific performance requirements

```yaml
routing_strategy: balanced
routing_weights:
  tps: 0.25
  ttft: 0.25
  quality: 0.25
  utilization: 0.25
```

**Example use cases:**
- Standard API endpoints serving diverse client requests
- Development and testing environments
- Mixed workloads that need reasonable performance across all metrics

---

### Speed

Best for: High-throughput batch processing and volume-oriented workloads

```yaml
routing_strategy: speed
routing_weights:
  tps: 0.50
  ttft: 0.30
  quality: 0.10
  utilization: 0.10
```

**Example use cases:**
- Bulk text generation tasks
- Document processing pipelines
- Image captioning at scale
- Data transformation jobs

---

### Latency

Best for: Interactive applications where response time is critical

```yaml
routing_strategy: latency
routing_weights:
  tps: 0.10
  ttft: 0.60
  quality: 0.15
  utilization: 0.15
```

**Example use cases:**
- Customer service chatbots
- Real-time code assistants
- Interactive dashboard queries
- Voice assistants

---

### Quality

Best for: Critical tasks requiring reliable, consistent performance

```yaml
routing_strategy: quality
routing_weights:
  tps: 0.15
  ttft: 0.15
  quality: 0.50
  utilization: 0.20
```

**Example use cases:**
- Financial analysis and reporting
- Medical or legal document generation
- High-stakes customer interactions
- Production systems requiring SLAs

---

### Utilization Only

Best for: Fallback mode, simple load balancing, or legacy systems

```yaml
routing_strategy: utilization_only
routing_weights:
  tps: 0.0
  ttft: 0.0
  quality: 0.0
  utilization: 1.0
```

**Example use cases:**
- When metrics API is temporarily unavailable
- Simple horizontal scaling scenarios
- Testing new deployments
- Fallback during maintenance windows

## CLI Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--port` | `-p` | Port to run on | 4000 |
| `--host` | | Host to bind to | 0.0.0.0 |
| `--config` | | Path to config file | ./litellm-config.yaml |
| `--debug` | | Enable debug logging | false |
| `--cache-ttl` | | Cache TTL for utilization | 30 |
| `--routing-strategy` | `-r` | Routing strategy | balanced |

## Programmatic Configuration

### Python API

```python
from litellm_proxy.routing.intelligent import IntelligentMultiMetricRouting
from litellm_proxy.routing.strategy import RoutingStrategy, StrategyWeights
from litellm_proxy.routing.config import RoutingConfig

# Option 1: Use predefined strategy
routing = IntelligentMultiMetricRouting(
    strategy=RoutingStrategy.BALANCED,
    chutes_api_key="your-api-key",
)

# Option 2: Use custom weights
routing = IntelligentMultiMetricRouting(
    strategy=RoutingStrategy.BALANCED,  # Still need a base strategy
    custom_weights=StrategyWeights(
        tps=0.5,
        ttft=0.3,
        quality=0.1,
        utilization=0.1
    ),
    chutes_api_key="your-api-key",
)

# Option 3: Load from environment
config = RoutingConfig.from_env()
routing = IntelligentMultiMetricRouting(
    strategy=config.strategy,
    custom_weights=config.custom_weights,
    chutes_api_key="your-api-key",
    cache_ttl_utilization=config.cache_ttls.get("utilization", 30),
    cache_ttl_tps=config.cache_ttls.get("tps", 300),
    cache_ttl_ttft=config.cache_ttls.get("ttft", 300),
    cache_ttl_quality=config.cache_ttls.get("quality", 300),
)
```

## Configuration Priority

Configuration is loaded in the following priority order (highest to lowest):

1. **CLI arguments** (e.g., `--routing-strategy`)
2. **Environment variables** (e.g., `ROUTING_STRATEGY`)
3. **YAML configuration** (e.g., `routing_strategy_multi_metric`)
4. **Default values**

## Validation

The configuration is validated at startup:

- Weights must sum to 1.0 (±0.001)
- Strategy must be valid
- TTLs must be positive integers
- Threshold must be between 0 and 1

If validation fails, the proxy will exit with an error message.
