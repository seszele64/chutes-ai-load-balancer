# Chutes Utilization-Based Routing for LiteLLM

This document explains the custom routing strategy that routes requests to the least utilized Chutes deployment based on real-time utilization data from the Chutes API.

## Overview

The `ChutesUtilizationRouting` class extends LiteLLM's `CustomRoutingStrategyBase` to provide intelligent routing based on actual deployment utilization. Instead of using simple round-robin or random selection, requests are routed to the Chutes deployment with the lowest current utilization.

## How It Works

1. **Utilization Fetching**: On each routing decision, the strategy fetches utilization data from the Chutes API
2. **Caching**: To avoid excessive API calls, utilization data is cached with a configurable TTL (default: 30 seconds)
3. **Selection**: The deployment with the lowest utilization is selected for the request
4. **Fallback**: If the Chutes API is unavailable, the strategy gracefully falls back to default routing

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Client Request │────▶│  LiteLLM Router  │────▶│ Custom Routing  │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                         ┌────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Chutes API         │
              │  /chutes/utilization│
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Return utilization  │
              │  for each chute      │
              └─────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `chutes_routing.py` | Custom routing strategy implementation |
| `start_litellm.py` | Startup script to initialize router |
| `litellm-config.yaml` | Model configuration |
| `.env` | Environment variables |

## Installation

### 1. Install Dependencies

```bash
pip install litellm requests pyyaml
```

### 2. Configure Environment Variables

Create or edit `.env`:

```bash
# Required
CHUTES_API_KEY=your-chutes-api-key

# Required for proxy security
LITELLM_MASTER_KEY=your-master-key

# Optional
LITELLM_PORT=4000
LITELLM_HOST=0.0.0.0
```

### 3. Get Your Chute IDs

1. Log in to the [Chutes Dashboard](https://chutes.ai)
2. Navigate to your deployments
3. Note the chute ID for each deployment
4. Update `litellm-config.yaml` with your actual chute IDs:

```yaml
model_list:
  - model_name: chutes-models
    litellm_params:
      model: openai/moonshotai/Kimi-K2.5-TEE
      # ...
    model_info:
      id: kimi-k2.5-tee
      chute_id: YOUR_ACTUAL_CHUTE_ID_HERE  # Replace this!
```

## Usage

### Starting the Proxy

```bash
# Recommended: Uses the startup script (handles .env loading and validation)
./scripts/run-proxy.sh

# Alternative: Run directly from project root
python start_litellm.py

# With custom port
python start_litellm.py --port 8080

# With debug logging
python start_litellm.py --debug

# With custom cache TTL (e.g., 60 seconds)
python start_litellm.py --cache-ttl 60
```

### Using the Proxy

Once running, you can send requests to the proxy:

```bash
# Set the API key for LiteLLM
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

## Configuration

### Router Settings

In `litellm-config.yaml`:

```yaml
router_settings:
  routing_strategy: simple-shuffle  # Fallback strategy
  enable_pre_call_checks: false    # Handled by custom strategy
  num_retries: 3
  timeout: 300
  allowed_fails: 5
  cooldown_time: 30
```

### Custom Routing Options

The `ChutesUtilizationRouting` class accepts these parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chutes_api_key` | str | env | API key for Chutes |
| `cache_ttl` | int | 30 | Cache TTL in seconds |
| `chutes_api_base` | str | https://api.chutes.ai | API base URL |

Example custom initialization:

```python
from chutes_routing import ChutesUtilizationRouting

routing = ChutesUtilizationRouting(
    chutes_api_key="your-api-key",
    cache_ttl=60,  # Cache for 60 seconds
    chutes_api_base="https://api.chutes.ai"
)
```

## Testing

### 1. Verify Routing Strategy is Active

```bash
# Start with debug logging
python start_litellm.py --debug

# Look for these log messages:
# "Custom Chutes utilization routing strategy registered"
# "Created Chutes utilization routing with 30s cache TTL"
```

### 2. Test Routing Decision

Send multiple requests and observe the logs:

```bash
# Send several requests
for i in {1..5}; do
  curl http://localhost:4000/v1/chat/completions \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "chutes-models",
      "messages": [{"role": "user", "content": "Test '$i'"}]
    }' &
done

# Check logs for routing decisions:
# "Routing to least utilized deployment: chute_xxx (utilization: 0.35)"
```

### 3. Verify Caching

Enable debug logging and check for cache hits:

```
# First request - cache miss
Fetching utilization for chute_xxx from https://api.chutes.ai/chutes/utilization

# Subsequent requests within TTL - cache hit
Cache hit for chute_xxx, age=5.2s, util=0.35
```

### 4. Test Fallback Behavior

Temporarily set an invalid API key:

```bash
CHUTES_API_KEY=invalid python start_litellm.py
# Should fall back to simple-shuffle strategy
```

## Troubleshooting

### "No Chutes API key available"

Ensure `CHUTES_API_KEY` is set in environment variables or passed to the routing strategy.

### "Timeout fetching utilization"

Check network connectivity to `https://api.chutes.ai`. The default timeout is 5 seconds.

### "Cache expired" warnings frequently

Increase the cache TTL with `--cache-ttl 60` or higher.

### Requests not routed to least utilized

1. Check debug logs for utilization values
2. Verify chute IDs in config match actual Chutes deployment IDs
3. Ensure the Chutes API is returning correct utilization data

## API Response Format

The Chutes API should return utilization data. The code handles multiple response formats:

```json
// Format 1: Direct value
{"utilization": 0.45}

// Format 2: Per-chute data
{"chutes": {"chute_id_1": {"utilization": 0.3}}}

// Format 3: Array
[{"chute_id": "chute_1", "utilization": 0.5}]
```

## Security Considerations

1. **API Key**: Keep `CHUTES_API_KEY` secure - don't commit to version control
2. **Master Key**: Set `LITELLM_MASTER_KEY` in production
3. **Network**: Consider running behind a firewall in production

## Performance

- **Cache TTL**: Default 30s provides a balance between freshness and API load
- **Timeout**: 5s timeout on API calls to prevent slow routing decisions
- **Async**: Both sync and async methods are implemented for compatibility

## License

MIT License
