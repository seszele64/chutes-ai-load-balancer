# LiteLLM Proxy Specification

## Purpose
The LiteLLM proxy serves as a unified API gateway in the chutes-load-balancer system. It provides OpenAI-compatible endpoints that route requests to multiple Chutes AI model deployments using intelligent multi-metric load balancing, considering server utilization, latency, and response quality to optimize request distribution.

## Requirements

### Requirement: The proxy SHALL handle model routing
Users SHALL be able to route requests through the LiteLLM proxy to available model instances.

#### Scenario: Successful request routing
- **GIVEN** a running LiteLLM proxy with configured models
- **WHEN** a user sends a chat completion request to the proxy
- **THEN** the request is routed to an available model instance based on intelligent routing

#### Scenario: Fallback routing on primary model failure
- **GIVEN** a LiteLLM proxy with multiple configured models
- **WHEN** the primary model is unavailable
- **THEN** the request is automatically routed to a fallback model based on priority order

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
│  │   Router     │───▶│ Intelligent Multi-Metric Routing │ │
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
| `USE_STRUCTURED_RESPONSES` | No | true | Enable structured responses (legacy, use DEGRADATION_ENABLED) |
| `CIRCUIT_BREAKER_ENABLED` | No | true | Enable circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | No | 3 | Number of failures before opening circuit |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | No | 30 | Cooldown time in seconds before attempting recovery |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | No | 2 | Number of successes needed in half-open to close |
| `CACHE_TTL_SECONDS` | No | 60 | Default cache TTL for all metrics |
| `DEGRADATION_ENABLED` | No | true | Enable graceful degradation |

### Circuit Breaker

The proxy includes an API-level circuit breaker that prevents cascading failures by stopping API calls when the service is experiencing issues.

#### States

```
┌──────────┐     failure threshold     ┌──────┐
│  CLOSED  │ ───────────────────────▶ │ OPEN │
│ (normal) │                            │      │
└──────────┘                           └──────┘
     ▲                                      │
     │                                      │ cooldown
     │         ┌─────────────┐              │ expires
     │         │  HALF_OPEN  │ ◀─────────────┘
     │         │ (testing)   │
     │         └─────────────┘
     │               ▲
     └───────────────┘
    success threshold
```

| State | Description | Behavior |
|-------|-------------|----------|
| CLOSED | Normal operation | Requests flow normally, failures are tracked |
| OPEN | Failing | Requests return degraded responses immediately |
| HALF_OPEN | Testing recovery | Allows limited requests to test if service recovered |

#### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 3 | Consecutive failures before opening circuit |
| `cooldown_seconds` | 30 | Time to wait before attempting recovery |
| `success_threshold` | 2 | Successes needed in HALF_OPEN to close circuit |

#### Circuit Breaker Status

The circuit breaker status is exposed via the `/health` endpoint:

```json
{
  "status": "healthy",
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "cooldown_remaining": 0.0
  }
}
```

### Graceful Degradation

The proxy implements a multi-level graceful degradation system that allows it to continue operating even when metrics are unavailable.

#### Degradation Levels

| Level | Name | Description | Response Time |
|-------|------|-------------|---------------|
| 0 | FULL | All metrics available (TPS, TTFT, quality, utilization) | Normal |
| 1 | CACHED | Using cached metrics (cache expired) | Normal |
| 2 | UTILIZATION | Only utilization metrics available | Normal |
| 3 | RANDOM | Random selection (all metrics unavailable) | Normal |
| 4 | FAILED | Complete failure | 503 Service Unavailable |

#### Degradation Flow

1. **Level 0 (Full)**: All metrics fetched from API, full scoring applied
2. **Level 1 (Cached)**: Cache expired, using stale metrics
3. **Level 2 (Utilization-only)**: Only utilization available, other metrics use defaults
4. **Level 3 (Random)**: No metrics available, random selection with fallback order
5. **Level 4 (Failed)**: All backends failed, return 503

The degradation level is returned in the `X-Degradation-Level` response header.

### Routing Strategy

The proxy uses an intelligent multi-metric routing system that considers:
- Server utilization (GPU, CPU, memory)
- Response latency
- Response quality scores
- Health status

The routing is handled by:
- `src/litellm_proxy/routing/intelligent.py` - `IntelligentMultiMetricRouting` class
- `src/litellm_proxy/routing/strategy.py` - `ChutesRoutingStrategy` class (legacy compatibility)

Available strategies: `balanced`, `speed`, `latency`, `quality`, `utilization_only`

#### Routing Strategy Configuration

The routing strategy can be configured via the model configuration:

```yaml
router_settings:
  routing_strategy: simple-shuffle  # LiteLLM built-in
  # Custom routing is applied via custom_handler in litellm_params
```

#### Legacy Support

For backward compatibility, `ChutesUtilizationRouting` in `routing/strategy.py` still exists but is deprecated in favor of `IntelligentMultiMetricRouting`.

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
3. Custom routing strategy (`IntelligentMultiMetricRouting`) is invoked
4. Strategy fetches utilization from Chutes API
5. Strategy selects least-utilized deployment
6. Request is forwarded to selected Chutes endpoint
7. Response is streamed/passed back to client

### HTTP API Endpoints

The proxy exposes additional HTTP endpoints for health checks, metrics, and model management:

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/health` | GET | Health check with circuit breaker state | No |
| `/api/metrics` | GET | Prometheus metrics | No |
| `/api/v1/models` | GET | List available models | No |
| `/api/v1/chat/completions` | POST | Chat completions with structured responses | No |

#### Response Headers

All API responses include the following headers:

| Header | Description | Values |
|--------|-------------|--------|
| `X-Degradation-Level` | Current degradation level | 0-4 |
| `X-Circuit-Breaker-State` | Circuit breaker state | closed, open, half_open |

#### Health Check Response

```bash
curl http://localhost:4000/api/health
```

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

#### Metrics Response

```bash
curl http://localhost:4000/api/metrics
```

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

#### Error Response Formats

The proxy returns errors in both RFC 9457 Problem Details format and OpenAI-compatible format:

**RFC 9457 Problem Details Format**:
```json
{
  "type": "https://api.chutes.ai/problems/routing-failure",
  "title": "Routing Failed",
  "status": 503,
  "detail": "All chutes unavailable after degradation cascade",
  "instance": "/v1/chat/completions",
  "code": "routing_failure"
}
```

**OpenAI-Compatible Format**:
```json
{
  "error": {
    "message": "All chutes unavailable",
    "type": "server_error",
    "code": "routing_failure",
    "param": null
  }
}
```

#### HTTP Errors
| Error | Cause | Response |
|-------|-------|----------|
| 401 Unauthorized | Missing/invalid master key | `{"error": "Authentication error"}` |
| 404 Not Found | Model not found in configuration | `{"error": "Not found"}` |
| 429 Too Many Requests | Rate limit exceeded | `{"error": "Rate limit exceeded"}` |
| 500 Internal Server Error | Unexpected server error | `{"error": "All models failed"}` |
| 503 Service Unavailable | Model temporarily unavailable | `{"error": "No deployment available"}` |

#### Exception Types

The proxy defines custom exception types in `src/litellm_proxy/exceptions.py`:

| Exception | Description |
|-----------|-------------|
| `ChutesRoutingError` | Base exception for all routing errors |
| `DegradationExhaustedError` | Raised when all degradation levels have failed |
| `CircuitBreakerOpenError` | Raised when circuit breaker is open |
| `MetricsUnavailableError` | Raised when metrics cannot be fetched |
| `AllBackendsDegradedError` | Raised when all backends are in degraded state |
| `RoutingError` | General routing error |
| `ConfigurationError` | Invalid configuration |

#### Chutes API Unavailable
When the Chutes API cannot be reached:
1. Return cached utilization data if available (not stale)
2. If cache is empty/stale, use default utilization of 0.5 for all models
3. Log warning and continue with degraded routing

#### Cache Miss Behavior
- First request after startup: Fetch utilization from API
- During API outage: Use cached data or defaults
- Cache TTL: 30 seconds (configurable)

#### Timeout Scenarios
- API request timeout: 10 seconds
- On timeout: Treat as API unavailable (see above)
- Log timeout event for monitoring

### Monitoring

#### Logging

- Request/response logging via LiteLLM
- Custom routing strategy logs utilization decisions
- Configurable log levels: INFO (default), DEBUG

#### Health Check Endpoints

LiteLLM provides built-in health endpoints:

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `/health` | Comprehensive model health - makes actual API calls | Yes (Bearer token) |
| `/health/liveliness` | Basic alive check - returns "I'm alive!" | No |
| `/health/readiness` | Ready to accept traffic - includes DB/cache status | No |

```bash
# Check proxy health (requires auth)
curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/health

# Simple liveliness check (no auth)
curl http://localhost:4000/health/liveliness
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
- `src/litellm_proxy/routing/intelligent.py` - Intelligent multi-metric routing
- `src/litellm_proxy/routing/circuit_breaker.py` - Circuit breaker implementation
- `src/litellm_proxy/routing/responses.py` - Structured response types (RFC 9457, OpenAI)
- `src/litellm_proxy/routing/strategy.py` - Routing strategy implementation
- `src/litellm_proxy/api/routes.py` - HTTP API endpoints
- `src/litellm_proxy/exceptions.py` - Custom exception types
- `litellm-config.yaml` - Model configuration
- `openspec/specs/routing/spec.md` - Routing spec
