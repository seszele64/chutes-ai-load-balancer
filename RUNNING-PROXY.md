# Running the LiteLLM Proxy

This document describes how to run and use the LiteLLM proxy with Chutes routing.

## Overview

The LiteLLM proxy provides a unified API endpoint that routes requests to multiple Chutes AI deployments based on real-time utilization data. This load balancer ensures requests are distributed efficiently across available chutes.

## Quick Start

### 1. Start the Proxy

```bash
./scripts/run-proxy.sh
```

The proxy will start on port 4000 (default) and bind to `0.0.0.0` (accessible from localhost and network).

### 2. Verify It's Running

```bash
./scripts/test-proxy.sh --health
```

Or open in your browser:
- http://localhost:4000
- http://localhost:4000/health

### 3. Make a Test Request

```bash
./scripts/test-proxy.sh
```

## Accessing the Proxy

### From Localhost

```bash
# Using the test script
./scripts/test-proxy.sh

# Using curl
curl http://localhost:4000/health

# Making a chat request
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -d '{
    "model": "chutes-models",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### From OpenCode

Since OpenCode runs in the same environment, use:

```python
import requests

response = requests.post(
    "http://localhost:4000/v1/chat/completions",
    headers={
        "Authorization": "Bearer ${LITELLM_MASTER_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "chutes-models",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)

print(response.json())
```

### From Other Tools

Any tool that can make HTTP requests can access the proxy:

```bash
# Python
requests.post("http://localhost:4000/v1/chat/completions", ...)

# JavaScript/Node
fetch("http://localhost:4000/v1/chat/completions", ...)

# Go
http.Post("http://localhost:4000/v1/chat/completions", ...)

# cURL
curl http://localhost:4000/v1/chat/completions ...
```

## Configuration

### Environment Variables

Create a `.env` file (or use the existing one):

```bash
# Required
CHUTES_API_KEY=your-chutes-api-key

# Required for security
LITELLM_MASTER_KEY=your-master-key

# Optional
LITELLM_PORT=4000           # Default: 4000
LITELLM_HOST=0.0.0.0        # Default: 0.0.0.0 (accessible from localhost)
LITELLM_CONFIG_PATH=./litellm-config.yaml
```

### Custom Port

```bash
# Start on custom port
./scripts/run-proxy.sh 4001

# Or set environment variable
LITELLM_PORT=4001 ./scripts/run-proxy.sh
```

## Managing the Proxy

### Stop the Proxy

```bash
./scripts/run-proxy.sh stop
```

### Restart the Proxy

```bash
./scripts/run-proxy.sh restart
```

### Check Status

```bash
# Check if proxy is running
curl http://localhost:4000/health

# Check logs
tail -f /tmp/litellm-proxy.log
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Interactive API docs (Swagger UI) |
| `GET /health` | Health check endpoint |
| `GET /info` | Model information |
| `POST /v1/chat/completions` | Chat completion API |
| `POST /v1/completions` | Text completion API |
| `GET /v1/models` | List available models |

## Making Requests

### Chat Completions

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chutes-models",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is 2+2?"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### Streaming Responses

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "model": "chutes-models",
    "messages": [{"role": "user", "content": "Count to 5"}],
    "stream": true
  }'
```

### Using with OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-litellm-master-key",
    base_url="http://localhost:4000"
)

response = client.chat.completions.create(
    model="chutes-models",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

## Troubleshooting

### Proxy Won't Start

1. **Check environment variables:**
   ```bash
   source .env
   echo $CHUTES_API_KEY
   echo $LITELLM_MASTER_KEY
   ```

2. **Check if port is in use:**
   ```bash
   lsof -i :4000
   # or
   netstat -tuln | grep 4000
   ```

3. **Check logs:**
   ```bash
   tail -f /tmp/litellm-proxy.log
   ```

### Requests Fail

1. **Check proxy is running:**
   ```bash
   curl http://localhost:4000/health
   ```

2. **Verify API key:**
   ```bash
   # Make sure you're passing the correct Authorization header
   curl -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
     http://localhost:4000/health
   ```

3. **Check Chutes API key:**
   Ensure `CHUTES_API_KEY` is valid in your `.env` file.

### Can't Connect from OpenCode

1. **Verify proxy binds to correct interface:**
   The proxy should bind to `0.0.0.0` (not `127.0.0.1`) to be accessible from other processes.

2. **Check firewall:**
   ```bash
   # Allow connections on port 4000
   sudo ufw allow 4000
   ```

3. **Verify from command line:**
   ```bash
   curl http://localhost:4000/health
   ```

### Routing Issues

The proxy uses a custom routing strategy that routes to the least utilized chute. Check the logs for routing decisions:

```bash
tail -f /tmp/litellm-proxy.log | grep -i routing
```

## Files

- `scripts/run-proxy.sh` - Start/stop script for the proxy
- `scripts/test-proxy.sh` - Test script to verify proxy is working
- `start_litellm.py` - Main Python startup script
- `litellm-config.yaml` - Model configuration
- `chutes_routing.py` - Custom routing logic
- `.env` - Environment variables (API keys)

## Security Note

The proxy is secured with `LITELLM_MASTER_KEY`. All requests must include:
```
Authorization: Bearer <your-master-key>
```

Keep your API keys secure and never commit them to version control.
