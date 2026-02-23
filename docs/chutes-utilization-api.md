# Chutes Utilization API Documentation

This document describes the Chutes.ai Utilization API used to monitor chute deployment status, utilization metrics, and scaling information.

## API Endpoint

| Attribute | Value |
|-----------|-------|
| Base URL | `https://api.chutes.ai` |
| Endpoint | `/chutes/utilization` |
| Method | `GET` |

## Authentication

The API uses API Key authentication via the `X-API-Key` header:

```bash
curl -X GET "https://api.chutes.ai/chutes/utilization" \
  -H "X-API-Key: <YOUR_API_KEY>"
```

## Response Structure

The API returns a **JSON array** of chute objects. Each object contains detailed utilization and status information for a specific deployed model.

### Array Response Format

```json
[
  {
    "chute_id": "uuid-string",
    "name": "moonshotai/Kimi-K2.5-TEE",
    "utilization_current": 0.41,
    ...
  },
  ...
]
```

## Available Fields

### Utilization Metrics

| Field | Type | Description |
|-------|------|-------------|
| `utilization_current` | `float` | Current utilization (0-1 scale, e.g., 0.41 = 41%) |
| `utilization_5m` | `float` | Average utilization over last 5 minutes |
| `utilization_15m` | `float` | Average utilization over last 15 minutes |
| `utilization_1h` | `float` | Average utilization over last 1 hour |

### Rate Limiting Info

| Field | Type | Description |
|-------|------|-------------|
| `rate_limit_ratio_5m` | `float` | Rate limit ratio over last 5 minutes |
| `rate_limit_ratio_15m` | `float` | Rate limit ratio over last 15 minutes |
| `rate_limit_ratio_1h` | `float` | Rate limit ratio over last 1 hour |
| `total_requests_5m` | `float` | Total requests in last 5 minutes |
| `total_requests_15m` | `float` | Total requests in last 15 minutes |
| `total_requests_1h` | `float` | Total requests in last 1 hour |
| `completed_requests_5m` | `float` | Completed requests in last 5 minutes |
| `completed_requests_15m` | `float` | Completed requests in last 15 minutes |
| `completed_requests_1h` | `float` | Completed requests in last 1 hour |
| `rate_limited_requests_5m` | `float` | Rate-limited requests in last 5 minutes |
| `rate_limited_requests_15m` | `float` | Rate-limited requests in last 15 minutes |
| `rate_limited_requests_1h` | `float` | Rate-limited requests in last 1 hour |
| `total_rate_limit_errors` | `float` | Total rate limit errors |

### Scaling Info

| Field | Type | Description |
|-------|------|-------------|
| `instance_count` | `integer` | Current number of active instances |
| `target_count` | `integer` | Target instance count (for scaling) |
| `total_instance_count` | `integer` | Total number of instances |
| `active_instance_count` | `integer` | Number of active instances |
| `scalable` | `boolean` | Whether the chute supports auto-scaling |
| `scale_allowance` | `integer` | Scale allowance/limit |
| `action_taken` | `string` | Last scaling action taken (e.g., "scale_up_candidate", "no_action") |
| `effective_multiplier` | `float` | Effective scaling multiplier |
| `avg_busy_ratio` | `float` | Average busy ratio across instances |
| `total_invocations` | `float` | Total number of invocations |

### Other

| Field | Type | Description |
|-------|------|-------------|
| `chute_id` | `string` | Unique chute identifier (UUID format) |
| `name` | `string` | Chute display name (e.g., "moonshotai/Kimi-K2.5-TEE") |
| `timestamp` | `string` | ISO timestamp of the response |

## Filtering

**Important**: The API returns ALL chutes (~60+) regardless of any filtering parameters. Query parameter filtering does not currently work - you must filter client-side by `chute_id` or `name`.

## Example Response

### Kimi K2.5 TEE (moonshotai)

```json
[
  {
    "chute_id": "12345678-1234-1234-1234-123456789abc",
    "name": "moonshotai/Kimi-K2.5-TEE",
    "utilization_current": 0.41,
    "utilization_5m": 0.38,
    "utilization_15m": 0.35,
    "utilization_1h": 0.32,
    "rate_limit_ratio_5m": 0.42,
    "rate_limit_ratio_15m": 0.40,
    "rate_limit_ratio_1h": 0.38,
    "total_requests_5m": 125.0,
    "total_requests_15m": 380.0,
    "total_requests_1h": 1520.0,
    "completed_requests_5m": 118.0,
    "completed_requests_15m": 358.0,
    "completed_requests_1h": 1432.0,
    "rate_limited_requests_5m": 7.0,
    "rate_limited_requests_15m": 22.0,
    "rate_limited_requests_1h": 88.0,
    "total_rate_limit_errors": 156.0,
    "instance_count": 8,
    "target_count": 8,
    "total_instance_count": 10,
    "active_instance_count": 8,
    "scalable": true,
    "scale_allowance": 50,
    "action_taken": "no_action",
    "effective_multiplier": 1.0,
    "avg_busy_ratio": 0.41,
    "total_invocations": 45678.0,
    "timestamp": "2026-02-23T10:30:00Z"
  }
]
```

## Important Notes

- **Utilization Scale**: Utilization values are on a 0-1 scale (e.g., 0.41 = 41%), not 0-100.
- **All Chutes Returned**: The API returns data for all ~60+ chutes in a single response. There is no server-side filtering.
- **Client-Side Filtering**: Since query parameters don't work, you must filter the response client-side using `chute_id` or `name` fields.
- **Rate Limiting Fields**: The rate limiting metrics (ratio, requests, errors) are provided for multiple time windows (5m, 15m, 1h).
- **Scaling Information**: The scaling info fields (`scalable`, `action_taken`, `effective_multiplier`, etc.) indicate the current scaling state and any actions taken.
