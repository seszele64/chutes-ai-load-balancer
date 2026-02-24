# Chutes Load Balancer with LiteLLM

A local proxy that load balances between chutes.ai models with automatic failover.

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
```

### Metrics Used

- **TPS** (Tokens Per Second): Throughput measurement
- **TTFT** (Time To First Token): Latency measurement  
- **Quality**: Derived from total invocations (reliability proxy)
- **Utilization**: Current load (0.0 = idle, 1.0 = fully utilized)

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
