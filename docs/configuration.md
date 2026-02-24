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

### Balanced (Default)

```yaml
routing_weights:
  tps: 0.25
  ttft: 0.25
  quality: 0.25
  utilization: 0.25
```

### Speed

```yaml
routing_weights:
  tps: 0.50
  ttft: 0.30
  quality: 0.10
  utilization: 0.10
```

### Latency

```yaml
routing_weights:
  tps: 0.10
  ttft: 0.60
  quality: 0.15
  utilization: 0.15
```

### Quality

```yaml
routing_weights:
  tps: 0.15
  ttft: 0.15
  quality: 0.50
  utilization: 0.20
```

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
