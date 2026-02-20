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
   litellm --config litellm-config.yaml
   ```

4. The proxy will run at `http://localhost:4000`

## Usage with OpenCode

Add this to your `~/.config/opencode/opencode.jsonc`:

```jsonc
"provider": {
  "litellm-chutes": {
    "name": "LiteLLM Chutes",
    "npm": "@ai-sdk/openai-compatible",
    "options": {
      "baseURL": "http://localhost:4000/v1",
      "apiKey": "os.environ/LITELLM_MASTER_KEY"
    },
    "models": {
      "chutes-models": {
        "name": "Chutes Load Balanced"
      }
    }
  }
}
```

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
