# LiteLLM Proxy Specification

## Overview

This specification defines the LiteLLM proxy component of the chutes-load-balancer project. The proxy acts as a unified API gateway that routes requests to multiple Chutes AI model deployments using intelligent load balancing.

## Current Implementation

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LiteLLM Proxy                         │
│                    http://localhost:4000                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────┐ │
│  │   Router     │───▶│ ChutesUtilizationRouting Strategy│ │
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
└─────────────────────────────────────────────────────────────┘
```

### Startup

**Entry Point**: `start_litellm.py`

```bash
# Basic usage
python start_litellm.py

# With custom port
python start_litellm.py --port 4000

# With debug logging
python start_litellm.py --debug

# With custom config
python start_litellm.py --config ./litellm-config.yaml
```

**Environment Variables**:
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHUTES_API_KEY` | Yes | - | API key for Chutes AI |
| `LITELLM_MASTER_KEY` | No | - | Master key for proxy auth |
| `LITELLM_PORT` | No | 4000 | Proxy port |
| `LITELLM_HOST` | No | 0.0.0.0 | Bind host |
| `LITELLM_CONFIG_PATH` | No | ./litellm-config.yaml | Config file path |

### Configuration

#### Model Configuration

The proxy is configured via `litellm-config.yaml`:

```yaml
model_list:
  - model_name: chutes-models
    litellm_params:
      model: openai/<org>/<model-name>
      api_base: https://llm.chutes.ai/v1
      api_key: os.environ/CHUTES_API_KEY
    model_info:
      id: <chute-uuid>
      chute_id: <chute-id>
      order: <priority>

router_settings:
  routing_strategy: simple-shuffle
  enable_pre_call_checks: false
  num_retries: 3
  timeout: 300
  allowed_fails: 5
  cooldown_time: 30
```

#### Deployed Models

| Model | Organization | Chute ID | Fallback Order |
|-------|--------------|----------|----------------|
| Kimi K2.5 TEE | moonshotai | 2ff25e81-4586-5ec8-b892-3a6f342693d7 | 1 (Primary) |
| GLM-5 TEE | zai-org | e51e818e-fa63-570d-9f68-49d7d1b4d12f | 2 (Secondary) |
| Qwen3.5 397B A17B TEE | Qwen | 51a4284a-a5a0-5e44-a9cc-6af5a2abfbcf | 3 (Tertiary) |

### API Usage

#### OpenAI-Compatible Endpoints

The proxy exposes OpenAI-compatible API endpoints:

**Chat Completions**:
```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chutes-models",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**Models List**:
```bash
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

#### Request Flow

1. Client sends request to `/v1/chat/completions`
2. LiteLLM Router receives request
3. Custom routing strategy (`ChutesUtilizationRouting`) is invoked
4. Strategy fetches utilization from Chutes API
5. Strategy selects least-utilized deployment
6. Request is forwarded to selected Chutes endpoint
7. Response is streamed/passed back to client

### Security

#### Authentication

- Master key authentication via `Authorization: Bearer` header
- API keys stored in environment variables (not in config files)
- Optional: Set `LITELLM_MASTER_KEY` to secure the proxy

#### API Key Management

| Key | Purpose | Storage |
|-----|---------|---------|
| `CHUTES_API_KEY` | Chutes AI API | Environment variable |
| `LITELLM_MASTER_KEY` | Proxy auth | Environment variable |

### Error Handling

#### HTTP Errors
| Error | Cause | Response |
|-------|-------|----------|
| 401 Unauthorized | Missing/invalid master key | `{"error": "Authentication error"}` |
| 404 Not Found | Model not found in configuration | `{"error": "Not found"}` |
| 429 Too Many Requests | Rate limit exceeded | `{"error": "Rate limit exceeded"}` |
| 500 Internal Server Error | Unexpected server error | `{"error": "All models failed"}` |
| 503 Service Unavailable | Model temporarily unavailable | `{"error": "No deployment available"}` |

#### Chutes API Unavailable
When the Chutes API cannot be reached:
1. Return cached utilization data if available (not stale)
2. If cache is empty/stale, use default utilization of 0.5 for all models
3. Log warning and continue with degraded routing

#### Cache Miss Behavior
- First request after startup: Fetch utilization from API
- During API outage: Use cached data or defaults
- Cache TTL: 60 seconds (configurable)

#### Timeout Scenarios
- API request timeout: 10 seconds
- On timeout: Treat as API unavailable (see above)
- Log timeout event for monitoring

### Monitoring

#### Logging

- Request/response logging via LiteLLM
- Custom routing strategy logs utilization decisions
- Configurable log levels: INFO (default), DEBUG

#### Health Check

```bash
# Check proxy health
curl http://localhost:4000/health
```

## Future Enhancements

### Planned Features

1. **Authentication Providers**
   - OAuth2/OIDC integration
   - API key management UI

2. **Rate Limiting**
   - Per-user rate limits
   - Token-based limits

3. **Metrics & Observability**
   - Prometheus metrics endpoint
   - OpenTelemetry tracing
   - Usage analytics dashboard

4. **Advanced Routing**
   - Cost-based routing
   - Latency-based routing
   - Custom routing rules

5. **Caching**
   - Response caching
   - Prompt caching

## Related Files

- `start_litellm.py` - Proxy startup implementation
- `chutes_routing.py` - Custom routing strategy
- `litellm-config.yaml` - Model configuration
- `openspec/specs/routing/spec.md` - Routing spec
