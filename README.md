# Chutes Load Balancer with LiteLLM

A local proxy that load balances between chutes.ai models with automatic failover.

## Features

- **Intelligent Multi-Metric Routing**: Considers TPS, TTFT, quality, and utilization for optimal routing
- **Circuit Breaker**: Prevents cascading failures with automatic recovery
- **Graceful Degradation**: Multiple levels of fallback (Full → Cached → Utilization → Random → Failed)
- **Structured Error Responses**: RFC 9457 Problem Details + OpenAI-compatible format
- **HTTP API Endpoints**: Health checks, metrics, and model management
- **Automatic Failover**: Routes to fallback models when primary fails

## Setup

1. Install LiteLLM:
   ```bash
   pip install litellm[proxy]
   ```

2. Copy the example environment file and configure your keys:
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

3. Start the proxy:
   ```bash
   ./scripts/run-proxy.sh
   ```

   This script handles environment loading, validation, and logging automatically.

4. The proxy will run at `http://localhost:4000`

## Intelligent Multi-Metric Routing

The proxy supports multiple routing strategies that consider multiple performance metrics:

| Strategy | Description | Best For |
|----------|-------------|----------|
| `balanced` (default) | Equal weights for TPS, TTFT, quality, utilization | General purpose |
| `speed` | Prioritizes TPS (throughput) | High-volume requests |
| `latency` | Prioritizes TTFT (time to first token) | Interactive applications |
| `quality` | Prioritizes reliability/usage history | Production workloads |
| `utilization_only` | Routes to least utilized only | Legacy mode |

### Configuration

**Command Line:**
```bash
# Use speed strategy
python start_litellm.py --routing-strategy speed

# Use latency strategy
python start_litellm.py -r latency
```

**Environment Variables:**
```bash
# Set routing strategy
ROUTING_STRATEGY=balanced  # balanced, speed, latency, quality, utilization_only

# Custom weights (must sum to 1.0)
ROUTING_TPS_WEIGHT=0.5
ROUTING_TTFT_WEIGHT=0.3
ROUTING_QUALITY_WEIGHT=0.1
ROUTING_UTILIZATION_WEIGHT=0.1

# Cache TTLs (in seconds)
CACHE_TTL_UTILIZATION=30
CACHE_TTL_TPS=300
CACHE_TTL_TTFT=300
CACHE_TTL_QUALITY=300

# Circuit Breaker (enabled by default)
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT_SECONDS=30
CACHE_TTL_SECONDS=60

# Graceful Degradation (enabled by default)
DEGRADATION_ENABLED=true
```

### Metrics Used

- **TPS** (Tokens Per Second): Throughput measurement
- **TTFT** (Time To First Token): Latency measurement  
- **Quality**: Derived from total invocations (reliability proxy)
- **Utilization**: Current load (0.0 = idle, 1.0 = fully utilized)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LiteLLM Proxy                         │
│                    http://localhost:4000                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────┐ │
│  │   Router     │───▶│ Intelligent Multi-Metric Routing  │ │
│  │              │    └──────────────────────────────────┘ │
│  └──────┬───────┘                    │                     │
│         │                            ▼                     │
│    ┌────┴────┬────────────┬─────────────┐                │
│    ▼         ▼            ▼             ▼                │
│ ┌──────┐ ┌──────┐ ┌─────────┐ ┌──────────┐             │
│ │ Kimi │ │ GLM-5│ │ Qwen3.5 │ │  ...     │             │
│ │ K2.5 │ │ TEE  │ │ 397B    │ │ (future) │             │
│ └──────┘ └──────┘ └─────────┘ └──────────┘             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Circuit Breaker (closed/open/half-open)            │  │
│  │ Graceful Degradation (4 levels + failure)           │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Circuit Breaker

The circuit breaker prevents cascading failures:
- **CLOSED**: Normal operation, failures tracked
- **OPEN**: Too many failures, return degraded immediately
- **HALF_OPEN**: Testing recovery after cooldown

### Graceful Degradation Levels

| Level | Description |
|-------|-------------|
| 0 | Full metrics (TPS, TTFT, quality, utilization) |
| 1 | Cached metrics (cache expired) |
| 2 | Utilization only |
| 3 | Random selection |
| 4 | Complete failure (503) |

## Error Handling

Errors are returned in both RFC 9457 Problem Details and OpenAI-compatible formats:

```json
{
  "error": {
    "message": "All chutes unavailable",
    "type": "server_error",
    "code": "routing_failure",
    "param": null
  },
  "problem_details": {
    "type": "https://api.chutes.ai/problems/routing-failure",
    "title": "Routing Failed",
    "status": 503,
    "detail": "All chutes unavailable",
    "instance": "/v1/chat/completions",
    "code": "routing_failure"
  }
}
```

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Degradation-Level` | Current degradation level (0-4) |
| `X-Circuit-Breaker-State` | Circuit breaker state |

## HTTP API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with circuit breaker state |
| `/api/metrics` | GET | Prometheus metrics |
| `/api/v1/models` | GET | List available models |
| `/api/v1/chat/completions` | POST | Chat completions |

## Usage with OpenCode

Add this to your `~/.config/opencode/opencode.jsonc`:

```jsonc
"provider": {
  "litellm-chutes": {
    "name": "LiteLLM Chutes",
    "npm": "@ai-sdk/openai-compatible",
    "options": {
      "baseURL": "http://localhost:4000/v1"
      // Note: No apiKey field needed - OpenCode handles authentication automatically
    },
    "models": {
      "chutes-models": {
        "name": "Chutes Load Balanced (Kimi→GLM→Qwen)"
      }
    }
  }
}
```

> **Note**: The `apiKey` field should be omitted because OpenCode handles authentication automatically when no apiKey is specified.

## How It Works

- **Priority Order**: Kimi K2.5 → GLM-5 → Qwen3.5
- **Automatic Failover**: If a model fails, it automatically tries the next one
- **Cooldown**: Failed models are temporarily removed from rotation
- **Retries**: 3 retries with exponential backoff

## Testing

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{
    "model": "chutes-models",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```
