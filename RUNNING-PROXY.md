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

# Circuit Breaker (enabled by default)
CIRCUIT_BREAKER_ENABLED=true              # Enable/disable circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3       # Failures before opening circuit
CIRCUIT_BREAKER_TIMEOUT_SECONDS=30        # Cooldown time before recovery
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2       # Successes needed to close circuit

# Graceful Degradation (enabled by default)
DEGRADATION_ENABLED=true                  # Enable/disable graceful degradation
USE_STRUCTURED_RESPONSES=true             # Legacy: enable structured responses

# Caching
CACHE_TTL_SECONDS=60                      # Default cache TTL for all metrics
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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Interactive API docs (Swagger UI) |
| `/health` | GET | Health check endpoint (LiteLLM) |
| `/health/liveliness` | GET | Basic alive check |
| `/health/readiness` GET | Ready to accept traffic |
| `/api/health` | GET | Health check with circuit breaker state |
| `/api/metrics` | GET | Prometheus metrics |
| `/api/v1/models` | GET | List available models |
| `/info` | GET | Model information |
| `/v1/chat/completions` | POST | Chat completion API |
| `/v1/completions` | POST | Text completion API |
| `/v1/models` | GET | List available models (OpenAI-compatible) |

### HTTP API Endpoints

The proxy provides additional HTTP endpoints with structured responses:

#### Health Check

```bash
curl http://localhost:4000/api/health
```

Response:
```json
{
  "status": "healthy",
  "degradation_level": 0,
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "cooldown_remaining": 0.0
  }
}
```

#### Metrics

```bash
curl http://localhost:4000/api/metrics
```

Response:
```text
# HELP chutes_routing_degradation_level Current degradation level (0-4)
# TYPE chutes_routing_degradation_level gauge
chutes_routing_degradation_level 0

# HELP chutes_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half-open)
# TYPE chutes_circuit_breaker_state gauge
chutes_circuit_breaker_state 0

# HELP chutes_routing_requests_total Total routing requests
# TYPE chutes_routing_requests_total counter
chutes_routing_requests_total{status="success"} 150
chutes_routing_requests_total{status="degraded"} 10
chutes_routing_requests_total{status="failed"} 2
```

#### List Models

```bash
curl http://localhost:4000/api/v1/models
```

Response headers include:
- `X-Degradation-Level`: Current degradation level (0-4)

### Response Headers

All API responses include the following headers:

| Header | Description | Values |
|--------|-------------|--------|
| `X-Degradation-Level` | Current degradation level | 0-4 |
| `X-Circuit-Breaker-State` | Circuit breaker state | closed, open, half_open |

### Error Response Format

Errors are returned in both RFC 9457 Problem Details and OpenAI-compatible formats:

```bash
# Example error response
curl -X POST http://localhost:4000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "chutes-models", "messages": [{"role": "user", "content": "test"}]}'
```

Response (503 Service Unavailable):
```json
{
  "error": {
    "message": "All degradation levels exhausted",
    "type": "server_error",
    "code": "routing_failed",
    "param": null
  },
  "problem_details": {
    "type": "https://api.chutes.ai/problems/routing-failed",
    "title": "Routing Failed",
    "status": 503,
    "detail": "All degradation levels exhausted: full, cached, utilization, random",
    "instance": "/v1/chat/completions",
    "code": "routing_failed"
  },
  "_routing_metadata": {
    "degradation_level": 4,
    "degradation_reason": "Complete failure"
  }
}
```

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
- `src/litellm_proxy/routing/intelligent.py` - Intelligent multi-metric routing
- `src/litellm_proxy/routing/circuit_breaker.py` - Circuit breaker implementation
- `src/litellm_proxy/routing/responses.py` - Structured response types (RFC 9457, OpenAI)
- `src/litellm_proxy/api/routes.py` - HTTP API endpoints
- `src/litellm_proxy/exceptions.py` - Custom exception types
- `.env` - Environment variables (API keys)

## Security Note

The proxy is secured with `LITELLM_MASTER_KEY`. All requests must include:
```
Authorization: Bearer <your-master-key>
```

Keep your API keys secure and never commit them to version control.
