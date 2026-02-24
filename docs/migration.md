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
