# MODIFIED: LiteLLM Proxy Health Endpoints

## Summary

Update the Health Check section in the proxy spec to document LiteLLM's native health endpoints with their authentication requirements and usage examples.

## Previous Behavior

The Health Check section only mentioned a basic `/health` endpoint without details:

```bash
# Check proxy health
curl http://localhost:4000/health
```

## New Behavior

The proxy now documents three native health endpoints:

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `/health` | Comprehensive model health - makes actual API calls | Yes (Bearer token) |
| `/health/liveliness` | Basic alive check - returns "I'm alive!" | No |
| `/health/readiness` | Ready to accept traffic - includes DB/cache status | No |

### Endpoint Details

#### `/health` - Comprehensive Health Check

Makes actual API calls to configured models to verify end-to-end health.

- **Authentication**: Required (Bearer token)
- **Response**: JSON with model health status

```bash
# Check proxy health (requires auth)
curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/health
```

Example response:
```json
{
  "status": "healthy",
  "healthy_deployments": ["model-1", "model-2"],
  "unhealthy_deployments": []
}
```

#### `/health/liveliness` - Liveliness Probe

Simple alive check that returns immediately without checking model availability.

- **Authentication**: Not required
- **Response**: Text "I'm alive!"

```bash
# Simple liveliness check (no auth)
curl http://localhost:4000/health/liveliness
```

Example response: `{"status": "ok"}`

#### `/health/readiness` - Readiness Probe

Checks if the proxy is ready to accept traffic, including database and cache connectivity.

- **Authentication**: Not required
- **Response**: JSON with component status

```bash
# Readiness check (no auth)
curl http://localhost:4000/health/readiness
```

Example response:
```json
{
  "status": "ready",
  "database": "connected",
  "cache": "connected"
}
```

## Files Changed

- `openspec/specs/proxy/spec.md` - Updated Health Check section (lines 177-182)

## Verification

Verify the health endpoints work as documented:

1. Test `/health/liveliness` without auth - should return 200 OK
2. Test `/health/readiness` without auth - should return 200 OK
3. Test `/health` without auth - should return 401 Unauthorized
4. Test `/health` with valid Bearer token - should return 200 OK with model status
