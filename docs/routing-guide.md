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

The routing system provides five predefined strategies, each optimized for different use cases. Choose the strategy that best matches your workload requirements.

### Strategy Comparison Table

| Strategy | TPS Weight | TTFT Weight | Quality Weight | Utilization Weight | Best For |
|----------|------------|-------------|----------------|--------------------|----------|
| **BALANCED** (default) | 25% | 25% | 25% | 25% | General purpose, no specific requirements |
| **SPEED** | 50% | 30% | 10% | 10% | High-throughput workloads, batch processing |
| **LATENCY** | 10% | 60% | 15% | 15% | Interactive applications, chat, real-time responses |
| **QUALITY** | 15% | 15% | 50% | 20% | Critical tasks, production workloads |
| **UTILIZATION_ONLY** | 0% | 0% | 0% | 100% | Fallback mode, simple load balancing |

### Detailed Strategy Descriptions

#### 1. BALANCED (Default)

```
Environment variable: ROUTING_STRATEGY=balanced
```

**Weights:**
- TPS: 25%
- TTFT: 25%
- Quality: 25%
- Utilization: 25%

**Best for:**
- General-purpose applications with no specific performance requirements
- Mixed workloads that need reasonable performance across all metrics
- Getting started - provides good defaults without tuning

**Example use cases:**
- Standard API endpoints serving diverse client requests
- Development and testing environments
- When you're unsure which strategy to use

---

#### 2. SPEED

```
Environment variable: ROUTING_STRATEGY=speed
```

**Weights:**
- TPS: 50%
- TTFT: 30%
- Quality: 10%
- Utilization: 10%

**Best for:**
- High-throughput batch processing
- Applications where volume matters more than individual response quality
- Data processing pipelines

**Example use cases:**
- Bulk text generation tasks
- Document processing jobs
- Image captioning at scale

**Configuration:**
```bash
export ROUTING_STRATEGY=speed
# or
python start_litellm.py --routing-strategy speed
```

---

#### 3. LATENCY

```
Environment variable: ROUTING_STRATEGY=latency
```

**Weights:**
- TPS: 10%
- TTFT: 60%
- Quality: 15%
- Utilization: 15%

**Best for:**
- Interactive applications where response time is critical
- Chat interfaces and conversational AI
- Real-time response requirements
- User-facing applications

**Example use cases:**
- Customer service chatbots
- Real-time code assistants
- Interactive dashboard queries
- Voice assistants

**Configuration:**
```bash
export ROUTING_STRATEGY=latency
# or
python start_litellm.py --routing-strategy latency
```

---

#### 4. QUALITY

```
Environment variable: ROUTING_STRATEGY=quality
```

**Weights:**
- TPS: 15%
- TTFT: 15%
- Quality: 50%
- Utilization: 20%

**Best for:**
- Critical tasks requiring reliable, consistent performance
- Production workloads where quality is paramount
- Applications with strict reliability requirements

**Example use cases:**
- Financial analysis and reporting
- Medical or legal document generation
- High-stakes customer interactions
- Production systems requiring SLAs

**Configuration:**
```bash
export ROUTING_STRATEGY=quality
# or
python start_litellm.py --routing-strategy quality
```

---

#### 5. UTILIZATION_ONLY

```
Environment variable: ROUTING_STRATEGY=utilization_only
```

**Weights:**
- TPS: 0%
- TTFT: 0%
- Quality: 0%
- Utilization: 100%

**Best for:**
- Fallback mode when other metrics are unavailable
- Simple load balancing scenarios
- Legacy systems migrating to the new routing
- Debugging and troubleshooting

**Example use cases:**
- When metrics API is temporarily unavailable
- Simple horizontal scaling scenarios
- Testing new deployments
- Fallback during maintenance windows

**Configuration:**
```bash
export ROUTING_STRATEGY=utilization_only
# or
python start_litellm.py --routing-strategy utilization_only
```

---

### Custom Weights

For fine-grained control, you can set custom weights using environment variables:

```bash
# Example: Prioritize throughput with minimal latency concern
export ROUTING_TPS_WEIGHT=0.45
export ROUTING_TTFT_WEIGHT=0.45
export ROUTING_QUALITY_WEIGHT=0.05
export ROUTING_UTILIZATION_WEIGHT=0.05

# Then start with balanced (custom weights override)
python start_litellm.py --routing-strategy balanced
```

**Important:** Weights must sum to 1.0 (±0.001 tolerance).

### Quick Reference

| Workload Type | Recommended Strategy |
|---------------|---------------------|
| General API | BALANCED |
| Batch processing | SPEED |
| Chat/Interactive | LATENCY |
| Production/Reliability | QUALITY |
| Simple load balancing | UTILIZATION_ONLY |

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
| `CACHE_TTL_SECONDS` | General metrics cache TTL (seconds) | 60 |
| `CIRCUIT_BREAKER_ENABLED` | Enable circuit breaker | `true` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before opening | 3 |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | Cooldown period (seconds) | 30 |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | Successes to close circuit | 2 |
| `DEGRADATION_ENABLED` | Enable graceful degradation | `true` |
| `USE_STRUCTURED_RESPONSES` | Enable structured error responses | `false` |

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

---

## Circuit Breaker

The circuit breaker pattern prevents cascading failures by tracking consecutive failures and temporarily stopping requests to unhealthy chutes.

### Circuit States

| State | Description | Behavior |
|-------|-------------|----------|
| **CLOSED** | Normal operation | Requests flow normally, failures are counted |
| **OPEN** | Circuit tripped | Requests are rejected immediately |
| **HALF_OPEN** | Testing recovery | Limited requests allowed to test recovery |

### State Transitions

```
CLOSED → OPEN: After CIRCUIT_BREAKER_FAILURE_THRESHOLD consecutive failures
     ↓
OPEN → HALF_OPEN: After CIRCUIT_BREAKER_TIMEOUT_SECONDS cooldown period
     ↓
HALF_OPEN → CLOSED: After CIRCUIT_BREAKER_SUCCESS_THRESHOLD successful requests
HALF_OPEN → OPEN: If any request fails during test
```

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|--------------|
| `CIRCUIT_BREAKER_ENABLED` | `true` | Enable/disable circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `3` | Failures before opening circuit |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | `30` | Seconds to wait before half-open |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `2` | Successes to close circuit |

### Example: Monitoring Circuit State

Check the `X-Circuit-Breaker-State` header in responses:

```bash
curl -I http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "chutes-models", "messages": [{"role": "user", "content": "test"}]}'

# Response headers include:
# X-Circuit-Breaker-State: CLOSED
# X-Circuit-Breaker-State: OPEN
# X-Circuit-Breaker-State: HALF_OPEN
```

---

## Graceful Degradation

When the routing system encounters failures, it gracefully degrades to ensure continued service availability.

### Degradation Levels

| Level | Name | Description | When Triggered |
|-------|------|-------------|----------------|
| **0** | Full | Normal operation - all metrics available | Default |
| **1** | Cached | Use cached metrics instead of live | API timeout |
| **2** | Utilization-Only | Use utilization metric only | Multiple API failures |
| **3** | Random | Random selection | No metrics available |
| **4** | Failure | Return error | All degradation exhausted |

### Degradation Flow

```
Request arrives
      │
      ▼
Level 0: Try normal routing with live metrics
      │
      ├─ Success → Return response
      │
      ▼ (failure)
Level 1: Use cached metrics
      │
      ├─ Success → Return response + X-Degradation-Level: 1
      │
      ▼ (failure)
Level 2: Use utilization only
      │
      ├─ Success → Return response + X-Degradation-Level: 2
      │
      ▼ (failure)
Level 3: Random selection
      │
      ├─ Success → Return response + X-Degradation-Level: 3
      │
      ▼ (failure)
Level 4: Return structured error + X-Degradation-Level: 4
```

### Response Headers

| Header | Values | Description |
|--------|--------|-------------|
| `X-Degradation-Level` | 0-4 | Current degradation level |
| `X-Circuit-Breaker-State` | CLOSED, OPEN, HALF_OPEN | Circuit breaker status |

### Example Response with Degradation

```bash
# Request with degradation
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "chutes-models", "messages": [{"role": "user", "content": "test"}]}'

# Response headers:
# X-Degradation-Level: 1
# X-Circuit-Breaker-State: CLOSED
```

### Error Response Format (RFC 9457)

Errors are returned in RFC 9457 Problem Details format with OpenAI compatibility:

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

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|--------------|
| `DEGRADATION_ENABLED` | `true` | Enable/disable graceful degradation |
| `USE_STRUCTURED_RESPONSES` | `false` | Enable structured error responses |

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
