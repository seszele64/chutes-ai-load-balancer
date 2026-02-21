# Routing Specification

## Overview

This specification defines the load balancer routing system for the chutes-load-balancer project. The routing system uses real-time utilization data from the Chutes AI API to intelligently route requests to the least utilized model deployment.

## Current Implementation

### Architecture

```
Client Request
      │
      ▼
┌─────────────────┐
│ LiteLLM Router  │
│ (Port 4000)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ ChutesUtilizationRouting Strategy      │
│ - Fetches utilization from Chutes API  │
│ - Caches results with configurable TTL  │
│ - Routes to least utilized deployment   │
└────────┬────────────────────────────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌───────┐ ┌───────┐ ┌───────────┐
│ Kimi  │ │ GLM-5 │ │ Qwen3.5   │
│ K2.5  │ │ TEE   │ │ 397B      │
│ TEE   │ │       │ │ TEE       │
└───────┘ └───────┘ └───────────┘
```

### Core Components

#### 1. ChutesUtilizationRouting Class

**Location**: `chutes_routing.py`

**Responsibilities**:
- Fetch real-time utilization data from Chutes API (`/chutes/utilization`)
- Cache utilization data with configurable TTL (default: 30 seconds)
- Route requests to the deployment with lowest utilization
- Fall back to default behavior when API is unavailable

**Key Methods**:
- `async_get_available_deployment()` - Async routing decision
- `get_available_deployment()` - Sync routing decision
- `_get_utilization()` - Fetch/cache utilization data
- `_parse_utilization_response()` - Parse API response

**Configuration Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chutes_api_key` | str | env.CHUTES_API_KEY | API key for Chutes |
| `cache_ttl` | int | 30 | Cache TTL in seconds |
| `chutes_api_base` | str | https://api.chutes.ai | API base URL |

#### 2. Utilization Data Format

The routing strategy expects the Chutes API to return utilization data in various formats. The implementation includes defensive parsing to handle API variations.

**Format 1: List format (primary)**

```json
[
  {
    "chute_id": "uuid...",
    "name": "moonshotai/Kimi-K2.5-TEE",
    "timestamp": "2024-01-01T00:00:00Z",
    "utilization_current": 0.5,
    "utilization_5m": 0.4,
    "utilization_15m": 0.3
  }
]
```

**Format 2: Dict format with various field names**

```json
{
  "chute_id": "uuid...",
  "utilization": 0.5,
  ...
}
```

The implementation also accepts: `util`, `usage`, `load`, `capacity`

**Format 3: Nested format with `chutes` key or `data` array**

```json
{
  "chutes": {
    "chute_id_1": {"utilization": 0.5},
    "chute_id_2": {"utilization": 0.3}
  }
}
```

Or:

```json
{
  "data": [
    {"chute_id": "uuid1", "utilization": 0.5},
    {"chute_id": "uuid2", "utilization": 0.3}
  ]
}
```

> **Note**: The implementation is defensive and handles these API variations automatically.

**Utilization Values**:
- `0.0` = Idle (no requests)
- `1.0` = Fully utilized (at capacity)
- Values between are linear interpolation

### Routing Logic

1. **Fetch Utilization**: For each configured deployment, fetch current utilization
2. **Cache Results**: Store results in memory with TTL
3. **Select Deployment**: Choose the deployment with lowest utilization value
4. **Fallback**: If API unavailable, use default 0.5 (mid-range)
5. **Error Handling**: Return None to fall back to LiteLLM default strategy

### Fallback Chain

When the custom routing strategy fails:

1. Custom strategy returns `None` → LiteLLM uses default routing
2. Default routing (`simple-shuffle`) → Random selection
3. All deployments fail → Return error to client

### Fallback Behavior

When the utilization API is unavailable or returns unexpected data:

1. **Cache Check**: If cached utilization data exists and is not stale, use it
2. **Default Utilization**: If no cache is available, use default value of 0.5 (mid-range) for all models
3. **Logging**: Warning is logged for monitoring purposes
4. **Continue Operation**: Routing continues with degraded behavior (less optimal but operational)

**Cache Behavior**:
- First request after startup: Fetch utilization from API
- During API outage: Use cached data or defaults
- Cache TTL: 30 seconds (configurable via `cache_ttl` parameter)

## API Reference

### Chutes Utilization API

**Endpoint**: `GET /chutes/utilization`

**Headers**:
```
X-API-Key: <chutes_api_key>
Content-Type: application/json
```

**Response**: See Utilization Data Format above

> **Note**: The utilization API endpoint is expected to be available at runtime.
> The implementation includes defensive fallback handling for cases where the API
> is unavailable or returns unexpected formats. See "Fallback Behavior" section
> for details.

### LiteLLM Router Configuration

**Config File**: `litellm-config.yaml`

```yaml
model_list:
  - model_name: chutes-models
    litellm_params:
      model: openai/moonshotai/Kimi-K2.5-TEE
      api_base: https://llm.chutes.ai/v1
      api_key: os.environ/CHUTES_API_KEY
    model_info:
      id: <chute_uuid>
      chute_id: chute_kimi_k2.5_tee
      order: 1  # Fallback priority

router_settings:
  routing_strategy: simple-shuffle  # Default fallback
  num_retries: 3
  timeout: 300
  allowed_fails: 5
  cooldown_time: 30
```

## Future Enhancements

See `openspec/changes/` for pending modifications.

### Potential Improvements

1. **Weighted Routing**: Support weighted distribution based on model capabilities
2. **Latency-based Routing**: Consider response time in addition to utilization
3. **Cost Optimization**: Factor in pricing per model
4. **Health Checks**: Add explicit health check endpoints
5. **Metrics Export**: Prometheus/Opentelemetry integration

## Testing

### Unit Tests

The routing strategy should be tested for:
- Cache hit/miss scenarios
- API timeout handling
- Response parsing (various formats)
- Fallback behavior

### Integration Tests

- End-to-end routing through LiteLLM proxy
- Failover when primary model is unavailable
- Cache expiration and refresh

## Related Files

- `chutes_routing.py` - Main routing implementation
- `start_litellm.py` - Proxy startup script
- `litellm-config.yaml` - Model configuration
- `openspec/specs/proxy/spec.md` - LiteLLM proxy spec
