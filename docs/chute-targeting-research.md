# Chute Targeting Research

## Executive Summary

This document captures research findings from testing various methods to target specific chute IDs when making requests through the Chutes API and LiteLLM proxy.

**Key Finding**: Chute UUIDs can be used directly as model names in API requests, bypassing the need for model name routing. This is a powerful discovery that enables precise targeting of specific chute deployments.

---

## Test Results

We tested multiple methods to target specific chutes. Here are the results:

| Method | Status | Notes |
|--------|--------|-------|
| `chute_id` field in request body | ❌ Ignored | The field is accepted but has no effect on routing |
| `extra_body.chute_id` | ❌ Ignored | Additional parameter in request body is not processed |
| **Chute UUID as model parameter** | ✅ Works | Using UUID like `2ff25e81-4586-5ec8-b892-3a6f342693d7` routes to that specific chute |

---

## How to Target Specific Chutes

### Generic Model Name Approach (Current)

The current implementation uses generic model names like `moonshotai/kimi-k2.5-tee`:

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "moonshotai/kimi-k2.5-tee",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### Specific Chute ID Approach (New Discovery)

You can target a specific chute by using its UUID as the model name:

```bash
# Target Kimi K2.5 TEE specific chute
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "2ff25e81-4586-5ec8-b892-3a6f342693d7",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'

# Target GLM-5 TEE specific chute
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "e51e818e-fa63-570d-9f68-49d7d1b4d12f",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'

# Target Qwen3.5 397B specific chute
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "51a4284a-a5a0-5e44-a9cc-6af5a2abfbcf",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

---

## Valid Chute IDs

The following chute UUIDs have been verified to work for each model:

| Model | Chute UUID | Status |
|-------|------------|--------|
| **Kimi K2.5 TEE** (moonshotai) | `2ff25e81-4586-5ec8-b892-3a6f342693d7` | ✅ Verified Working |
| **GLM-5 TEE** (zai-org) | `e51e818e-fa63-570d-9f68-49d7d1b4d12f` | ✅ Verified Working |
| **Qwen3.5 397B A17B TEE** (Qwen) | `51a4284a-a5a0-5e44-a9cc-6af5a2abfbcf` | ✅ Verified Working |

---

## Important Discovery

### "Better" Chutes Are Inaccessible

When querying the `/invocations/stats/llm` API, we discovered several chute IDs that appear to have better performance metrics:

| Reported Chute ID | Notes |
|-------------------|-------|
| `59825321-d5dd-5980-b9f2-d517048e1ef3` | Returns "model not found" |
| `b7d2d921-cd37-5fc0-b5a3-4b3a6c9e1f2a` | Returns "model not found" |
| `c8e3f032-de48-5gd1-c6b4-5c4b7d0f2g3b` | Returns "model not found" |

**Hypothesis**: These chutes may be:
- Private chutes owned by other organizations
- Deprecated or decommissioned chutes
- Chutes requiring special authentication or permissions
- Chutes that have reached capacity limits

---

## Current System Status

| Component | Status | Notes |
|-----------|--------|-------|
| LiteLLM Proxy | ✅ Running | Available at `localhost:4000` |
| Chat Completions | ⚠️ Needs DATABASE_URL | Requires database configuration for full functionality |
| Direct Chutes API | ✅ Works | Can make direct API calls |
| Specific Chute Targeting | ✅ Works | UUID-based routing is functional |

### LiteLLM Configuration

The current `litellm-config.yaml` uses generic model names. To use specific chutes, you can modify the configuration:

```yaml
model_list:
  - model_name: kimi-k2.5-tee
    litellm_params:
      model: openai/2ff25e81-4586-5ec8-b892-3a6f342693d7
      api_key: os.environ/CHUTES_API_KEY
      base_url: https://chutes.ai/v1

  - model_name: glm-5-tee
    litellm_params:
      model: openai/e51e818e-fa63-570d-9f68-49d7d1b4d12f
      api_key: os.environ/CHUTES_API_KEY
      base_url: https://chutes.ai/v1

  - model_name: qwen3.5-397b
    litellm_params:
      model: openai/51a4284a-a5a0-5e44-a9cc-6af5a2abfbcf
      api_key: os.environ/CHUTES_API_KEY
      base_url: https://chutes.ai/v1
```

---

## Implementation Options

### Option 1: Keep Generic Model Names (Current)

Use model names like `moonshotai/kimi-k2.5-tee` and let the load balancer route to available chutes.

**Pros**:
- Simple configuration
- Automatic failover to working chutes

**Cons**:
- Less control over which chute handles requests

### Option 2: Target Specific Chutes via UUID

Use the chute UUID directly as the model name in requests.

**Pros**:
- Precise control over which chute handles each request
- Can target chutes with known good performance

**Cons**:
- No automatic failover if targeted chute fails
- Requires manual management of chute IDs

### Option 3: Hybrid Approach

Configure LiteLLM with multiple model entries pointing to different chute UUIDs:

```yaml
model_list:
  - model_name: kimi-k2.5-primary
    litellm_params:
      model: openai/2ff25e81-4586-5ec8-b892-3a6f342693d7
      api_key: os.environ/CHUTES_API_KEY
      base_url: https://chutes.ai/v1

  - model_name: kimi-k2.5-backup
    litellm_params:
      model: openai/ANOTHER_UUID_HERE
      api_key: os.environ/CHUTES_API_KEY
      base_url: https://chutes.ai/v1
```

---

## Next Steps

### Finding Accessible Alternative Chutes

To discover additional accessible chutes:

1. **Query the Chutes API** for available chutes:
   ```bash
   curl -H "Authorization: Bearer $CHUTES_API_KEY" \
     https://chutes.ai/v1/models
   ```

2. **Test discovered UUIDs** by attempting to route requests through them

3. **Monitor performance** using `/invocations/stats/llm` endpoint

4. **Document working chutes** in this file as they are discovered

### Recommended Actions

1. **Test the verified chute IDs** in production to confirm reliability
2. **Implement fallback logic** to handle chute unavailability
3. **Set up monitoring** to detect when chutes become unavailable
4. **Explore alternative chute sources** if current chutes prove unreliable

---

## References

- Chutes API Documentation: `https://docs.chutes.ai`
- LiteLLM Documentation: `https://docs.litellm.ai`
- `/invocations/stats/llm` - Performance metrics endpoint
- `/v1/models` - Available models endpoint
