# Intelligent Multi-Metric Routing Guide

This guide explains how to configure and use the intelligent multi-metric routing system for the LiteLLM proxy.

## Overview

The intelligent routing system routes requests based on multiple performance metrics rather than just utilization:

- **TPS** (Tokens Per Second): Measures throughput - higher is better
- **TTFT** (Time To First Token): Measures latency - lower is better
- **Quality**: Derived from total invocations - higher is better
- **Utilization**: Current load - lower is better

## Quick Start

### 1. Basic Usage

```bash
# Start with default balanced strategy
python start_litellm.py

# Start with specific strategy
python start_litellm.py --routing-strategy speed
python start_litellm.py --routing-strategy latency
python start_litellm.py --routing-strategy quality
```

### 2. Using Environment Variables

```bash
# Set strategy via environment
export ROUTING_STRATEGY=balanced
python start_litellm.py
```

## Routing Strategies

### Balanced (Default)

Equal weights for all metrics:
- TPS: 25%
- TTFT: 25%
- Quality: 25%
- Utilization: 25%

Best for general-purpose applications.

### Speed

Prioritizes throughput:
- TPS: 50%
- TTFT: 30%
- Quality: 10%
- Utilization: 10%

Best for high-volume batch processing.

### Latency

Prioritizes response time:
- TPS: 10%
- TTFT: 60%
- Quality: 15%
- Utilization: 15%

Best for interactive applications where fast response is critical.

### Quality

Prioritizes reliability:
- TPS: 15%
- TTFT: 15%
- Quality: 50%
- Utilization: 20%

Best for production workloads requiring consistent performance.

### Utilization Only

Legacy mode - routes to the least utilized model only. Use this if you want to revert to the old behavior.

## Configuration Files

### YAML Configuration

Edit `litellm-config.yaml`:

```yaml
router_settings:
  # Strategy selection
  routing_strategy: balanced  # balanced, speed, latency, quality, utilization_only
  
  # Optional: Custom weights (must sum to 1.0)
  routing_weights:
    tps: 0.25
    ttft: 0.25
    quality: 0.25
    utilization: 0.25
  
  # Optional: Cache TTLs in seconds
  cache_ttls:
    utilization: 30    # How often to refresh utilization data
    tps: 300          # How often to refresh TPS data
    ttft: 300         # How often to refresh TTFT data
    quality: 300      # How often to refresh quality data
  
  # Optional: API URL
  chutes_api_url: "https://api.chutes.ai"
  
  # Optional: High utilization warning threshold
  high_utilization_warning_threshold: 0.8
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ROUTING_STRATEGY` | Routing strategy | `balanced` |
| `ROUTING_TPS_WEIGHT` | TPS weight (0.0-1.0) | Strategy default |
| `ROUTING_TTFT_WEIGHT` | TTFT weight (0.0-1.0) | Strategy default |
| `ROUTING_QUALITY_WEIGHT` | Quality weight (0.0-1.0) | Strategy default |
| `ROUTING_UTILIZATION_WEIGHT` | Utilization weight (0.0-1.0) | Strategy default |
| `CACHE_TTL_UTILIZATION` | Utilization cache TTL (seconds) | 30 |
| `CACHE_TTL_TPS` | TPS cache TTL (seconds) | 300 |
| `CACHE_TTL_TTFT` | TTFT cache TTL (seconds) | 300 |
| `CACHE_TTL_QUALITY` | Quality cache TTL (seconds) | 300 |

## How It Works

### Request Flow

```
1. Request arrives at LiteLLM proxy
         │
         ▼
2. Router calls custom routing strategy
         │
         ▼
3. Check metrics cache for each chute
   - Cache hit: Use cached values
   - Cache miss: Fetch from API
         │
         ▼
4. Calculate scores based on strategy weights
         │
         ▼
5. Select highest-scoring chute
         │
         ▼
6. Route request to selected chute
```

### Caching

The system caches metrics to reduce API calls:

- **Utilization**: Refreshed every 30 seconds (configurable)
- **TPS/TTFT/Quality**: Refreshed every 5 minutes (configurable)

This ensures fast routing decisions while keeping data reasonably fresh.

### Fallback Behavior

If metrics cannot be fetched:

1. **Try cached data**: If available, use stale cached values
2. **Utilization-only mode**: If no metrics available, fall back to selecting least utilized
3. **Random selection**: If no data at all, select randomly

### High Utilization Warning

When all chutes are above 80% utilization (configurable), a warning is logged:

```
WARNING: All chutes above 80% utilization
```

This indicates you may need to scale your deployments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        LiteLLM Proxy                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   IntelligentRoutingStrategy                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ MetricsCache│  │ ScoringEngine│  │ ChutesAPIClient│   │
│  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Chutes API                             │
│  /chutes/utilization  │  /invocations/stats/llm           │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Logs Not Showing Routing Decisions

Enable debug logging:
```bash
python start_litellm.py --debug
```

### High Utilization Warnings

This indicates your chutes are under heavy load. Consider:
- Scaling up deployments
- Using a different routing strategy (e.g., utilization_only)
- Adding more chute instances

### Requests Always Go to Same Chute

Check the metrics:
1. Enable debug logging
2. Look for score breakdowns in logs
3. Verify the strategy weights match your expectations

### API Errors in Logs

If you see API errors:
1. Verify CHUTES_API_KEY is correct
2. Check network connectivity to api.chutes.ai
3. Verify your API key has sufficient permissions

## Advanced Usage

### Custom Weights

For fine-grained control, set custom weights:

```bash
# High throughput, low latency tolerance
export ROUTING_TPS_WEIGHT=0.6
export ROUTING_TTFT_WEIGHT=0.3
export ROUTING_QUALITY_WEIGHT=0.05
export ROUTING_UTILIZATION_WEIGHT=0.05
```

Note: Weights must sum to 1.0 (±0.001 tolerance).

### Custom Cache TTLs

Reduce TTLs for more responsive routing during deployments:

```bash
export CACHE_TTL_UTILIZATION=5
export CACHE_TTL_TPS=60
export CACHE_TTL_TTFT=60
```

Note: Lower TTLs mean more API calls.

### Programmatic Usage

```python
from litellm_proxy.routing.intelligent import IntelligentMultiMetricRouting
from litellm_proxy.routing.strategy import RoutingStrategy, StrategyWeights

# Create routing with custom strategy
routing = IntelligentMultiMetricRouting(
    strategy=RoutingStrategy.SPEED,
    custom_weights=StrategyWeights(tps=0.6, ttft=0.3, quality=0.05, utilization=0.05),
    chutes_api_key="your-api-key",
    cache_ttl_utilization=30,
    cache_ttl_tps=300,
    cache_ttl_ttft=300,
    cache_ttl_quality=300,
)
```

## Migration from Legacy Routing

If you were using the old utilization-only routing:

```bash
# Old behavior
python start_litellm.py

# New equivalent
python start_litellm.py --routing-strategy utilization_only
```

Or set environment variable:
```bash
export ROUTING_STRATEGY=utilization_only
```

See [Migration Guide](migration.md) for detailed instructions.
