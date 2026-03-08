# Migration Guide: Intelligent Multi-Metric Routing

This guide helps you migrate from the old utilization-only routing to the new intelligent multi-metric routing system.

## What's Different?

### Old Behavior (Utilization-Only)

The old routing system selected the chute with the lowest utilization:
- Only considered current load
- No consideration of throughput (TPS)
- No consideration of latency (TTFT)
- No consideration of reliability

### New Behavior (Multi-Metric)

The new routing considers multiple metrics:
- **TPS**: Throughput - higher is better
- **TTFT**: Latency - lower is better
- **Quality**: Derived from usage history - higher is better
- **Utilization**: Current load - lower is better

## Migration Steps

### Step 1: Understand Your Needs

Choose a routing strategy that matches your use case:

| Use Case | Recommended Strategy |
|----------|---------------------|
| General purpose | `balanced` |
| High-volume batch processing | `speed` |
| Interactive applications | `latency` |
| Production workloads | `quality` |
| Legacy behavior | `utilization_only` |

### Step 2: Test the New Routing

Before deploying to production, test with the new routing:

```bash
# Start with balanced strategy (recommended default)
python start_litellm.py --routing-strategy balanced
```

### Step 3: Monitor Routing Decisions

Enable debug logging to see routing decisions:

```bash
python start_litellm.py --debug
```

Look for log messages like:
```
kimi-k2.5-tee selected: highest TPS (28.31), lowest TTFT (6.45s)
```

### Step 4: Fine-tune Weights (Optional)

If the default strategies don't meet your needs, customize weights:

```bash
# Example: High throughput focus
export ROUTING_TPS_WEIGHT=0.5
export ROUTING_TTFT_WEIGHT=0.3
export ROUTING_QUALITY_WEIGHT=0.1
export ROUTING_UTILIZATION_WEIGHT=0.1
```

### Step 5: Deploy

Once satisfied with testing, deploy to production:

```bash
# Set environment variable
export ROUTING_STRATEGY=balanced

# Start the proxy
python start_litellm.py
```

## Rollback

If you need to revert to the old behavior:

```bash
# Option 1: Use environment variable
export ROUTING_STRATEGY=utilization_only
python start_litellm.py

# Option 2: Use CLI argument
python start_litellm.py --routing-strategy utilization_only
```

## Configuration Comparison

### Before (utilization-only)

```yaml
# litellm-config.yaml
router_settings:
  routing_strategy: simple-shuffle
```

Environment:
```bash
# No special configuration needed
```

### After (multi-metric)

```yaml
# litellm-config.yaml
router_settings:
  routing_strategy: simple-shuffle  # Fallback
  routing_strategy_multi_metric: balanced  # New: balanced, speed, latency, quality
  
  # Optional: Custom weights
  # routing_weights:
  #   tps: 0.25
  #   ttft: 0.25
  #   quality: 0.25
  #   utilization: 0.25
  
  # Optional: Cache TTLs
  # cache_ttls:
  #   utilization: 30
  #   tps: 300
  #   ttft: 300
  #   quality: 300
```

Environment:
```bash
# Required: Set strategy
export ROUTING_STRATEGY=balanced
```

## Common Issues

### "All chutes above 80% utilization"

This warning appears when all chutes are heavily loaded. This is expected behavior - the system will still route requests, just with a warning.

**Solution**: 
- Scale up your deployments
- Consider using `utilization_only` strategy during high load

### "Falling back to utilization-only mode"

This occurs when TPS/TTFT metrics cannot be fetched from the API.

**Solution**:
- Check API key permissions
- Check network connectivity
- Verify API is responding

### Requests going to unexpected chute

This can happen if the weights don't match your expectations.

**Solution**:
1. Enable debug logging
2. Check the score breakdown in logs
3. Adjust weights if needed

---

## Circuit Breaker Behavior

The circuit breaker pattern is now enabled by default to prevent cascading failures. This is a new feature that tracks consecutive failures and temporarily stops routing to unhealthy chutes.

### What Changed?

- Circuit breaker is now **enabled by default**
- After 3 consecutive failures (configurable), the circuit "opens"
- Requests are rejected during the open state
- After 30 seconds (configurable), the circuit enters "half-open" state
- After 2 successful requests (configurable), the circuit closes

### Configuration

```bash
# Disable circuit breaker (not recommended)
export CIRCUIT_BREAKER_ENABLED=false

# Customize thresholds
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
export CIRCUIT_BREAKER_TIMEOUT_SECONDS=60
export CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3
```

### Migration Notes

If you were relying on the old behavior where requests always went to a chute regardless of failures:

1. The new behavior is more resilient - it prevents overload of failing chutes
2. If you need the old behavior, set `CIRCUIT_BREAKER_ENABLED=false`
3. Monitor `X-Circuit-Breaker-State` header to track circuit health

---

## Degradation Levels

The system now has 4 levels of graceful degradation to ensure continued service availability.

### What Changed?

Previously, if metrics couldn't be fetched, the system would return an error. Now, it degrades gracefully:

| Level | Name | Description |
|-------|------|-------------|
| **0** | Full | Normal operation - all metrics available |
| **1** | Cached | Use cached metrics instead of live |
| **2** | Utilization-Only | Use utilization metric only |
| **3** | Random | Random selection |
| **4** | Failure | Return error (all degradation exhausted) |

### Configuration

```bash
# Disable graceful degradation (not recommended)
export DEGRADATION_ENABLED=false

# Enable structured error responses
export USE_STRUCTURED_RESPONSES=true
```

### Response Headers

Track degradation via response headers:

```bash
# Check degradation level
curl -I http://localhost:4000/v1/chat/completions ... 2>&1 | grep X-Degradation-Level
```

---

## Exception Types

New exception types may be raised by the routing system:

| Exception | Description |
|-----------|-------------|
| `CircuitBreakerOpenError` | Circuit breaker is open, request rejected |
| `DegradationExhaustedError` | All degradation levels exhausted |
| `MetricsUnavailableError` | Metrics cannot be fetched |

### Error Response Format

When `USE_STRUCTURED_RESPONSES=true`, errors are returned in RFC 9457 format:

```json
{
  "error": {
    "message": "All routing degradation levels exhausted: circuit breaker open",
    "type": "server_error",
    "code": "degradation_exhausted",
    "param": null,
    "degradation_level": 4,
    "circuit_breaker_state": "OPEN"
  }
}
```

### Migration Notes

- These exceptions are handled internally by graceful degradation
- If you see these errors in logs, check circuit breaker state and API connectivity
- The system automatically recovers when metrics become available again

## Performance Considerations

### Cache TTLs

| Metric | Default TTL | When to Adjust |
|--------|-------------|----------------|
| Utilization | 30s | Lower during deployments |
| TPS | 300s | Rarely |
| TTFT | 300s | Rarely |
| Quality | 300s | Never (derived) |

### API Calls

- Utilization: ~2 requests per minute (30s TTL)
- TPS/TTFT: ~4 requests per hour (300s TTL)

Total: ~2-6 API calls per minute depending on traffic.

## Summary

| Task | Command |
|------|---------|
| Test new routing | `python start_litellm.py --routing-strategy balanced --debug` |
| Use speed strategy | `python start_litellm.py --routing-strategy speed` |
| Use latency strategy | `python start_litellm.py --routing-strategy latency` |
| Use quality strategy | `python start_litellm.py --routing-strategy quality` |
| Revert to legacy | `python start_litellm.py --routing-strategy utilization_only` |
| Custom weights | `export ROUTING_TPS_WEIGHT=0.5` (and others) |

For more details, see [Routing Guide](routing-guide.md).
