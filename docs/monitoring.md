# Monitoring and Observability

This guide explains how to monitor and observe the intelligent multi-metric routing system.

## Log Messages

### Startup Logs

These messages appear when the proxy starts:

```
# Intelligent multi-metric routing
IntelligentMultiMetricRouting initialized with strategy=balanced, weights={...}

# Utilization-only (legacy)
ChutesUtilizationRouting initialized with cache_ttl=30s, api_base=https://api.chutes.ai
```

### Routing Decision Logs

These messages appear for each request:

```
# Standard routing decision
kimi-k2.5-tee selected: highest TPS (28.31), lowest TTFT (6.45s)

# High utilization warning
WARNING: All chutes above 80% utilization

# Fallback mode (when API unavailable)
Fallback to utilization-only: chute_kimi_k2.5_tee (0.45)
```

### Cache Logs

These messages show cache behavior:

```
# Cache miss (first fetch)
Fetching utilization for chute_kimi_k2.5_tee from https://api.chutes.ai

# Cache hit
Cache hit for chute_kimi_k2.5_tee, age=5.2s, util=0.35
```

### Error Logs

These messages indicate problems:

```
# API error
Error fetching metrics from API: Connection timeout

# No data available
No utilization data available, falling back to default

# Weight validation error
Weights must sum to 1.0
```

## Enabling Debug Logging

### CLI

```bash
python start_litellm.py --debug
```

### Environment

```bash
export LOG_LEVEL=DEBUG
python start_litellm.py
```

## Key Metrics to Monitor

### Routing Metrics

| Metric | Description | Healthy Range |
|--------|-------------|---------------|
| `routing.cache_hit_rate` | Percentage of cache hits | > 70% |
| `routing.fallback_count` | Number of fallback decisions | Low (< 5%) |
| `routing.high_utilization_warnings` | High utilization warnings | Low |

### Performance Metrics

| Metric | Description | Healthy Range |
|--------|-------------|---------------|
| `routing.decision_latency` | Time to make routing decision | < 10ms |
| `routing.api_latency` | Time to fetch from Chutes API | < 500ms |

### Business Metrics

| Metric | Description | Healthy Range |
|--------|-------------|---------------|
| `requests.total` | Total requests | Growing |
| `requests.success` | Successful requests | > 99% |
| `requests.failed` | Failed requests | Low (< 1%) |

## Prometheus Metrics

If using Prometheus for metrics collection:

```bash
# Add to your Prometheus scrape config
- job_name: 'litellm'
  static_configs:
    - targets: ['localhost:4000']
```

Key metrics exposed by LiteLLM:
- `litellm_requests_total` - Total requests
- `litellm_request_latency` - Request latency
- `litellm_model_latency` - Model-specific latency
- `litellm_errors_total` - Error counts

## Health Checks

### Liveness Probe

```bash
curl http://localhost:4000/health/liveness
```

Expected response:
```json
{"status": "ok"}
```

### Readiness Probe

```bash
curl http://localhost:4000/health/readiness
```

Expected response:
```json
{"status": "ok"}
```

### Metrics Endpoint

```bash
curl http://localhost:4000/metrics
```

This returns Prometheus-formatted metrics.

## Alerting

### High Utilization Alert

Trigger when:
```
rate(litellm_requests_failed_total[5m]) > 0.05
```

Action: Check chute health, consider scaling

### Routing Failure Alert

Trigger when:
```
routing_fallback_count > 10
```

Action: Check API connectivity, verify API key

### High Latency Alert

Trigger when:
```
histogram_quantile(0.95, litellm_request_latency_seconds) > 10
```

Action: Check chute performance, consider different routing strategy

## Logging Configuration

### JSON Logging

For production, use JSON-formatted logs:

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        return json.dumps(log_data)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.addHandler(handler)
```

### Log Aggregation

For production deployments, forward logs to:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Splunk**
- **Datadog**
- **CloudWatch Logs**

Example with Filebeat:
```yaml
filebeat.inputs:
- type: log
  paths:
    - /var/log/litellm/*.log
  fields:
    service: litellm-proxy
    environment: production
```

## Troubleshooting with Logs

### Issue: Requests always go to same chute

1. Enable debug logging
2. Check score breakdown in logs
3. Verify metrics are being fetched
4. Check for high utilization warnings

### Issue: High fallback count

1. Check API connectivity
2. Verify API key has permissions
3. Check for API rate limiting
4. Consider increasing cache TTLs

### Issue: Slow routing decisions

1. Check API latency in logs
2. Monitor cache hit rate
3. Consider reducing cache TTLs
4. Check network latency to Chutes API

## Observability Best Practices

1. **Always use structured logging** - JSON format for easy parsing
2. **Include correlation IDs** - Track requests through the system
3. **Monitor cache health** - High miss rate indicates problems
4. **Track routing decisions** - Understand which chutes get traffic
5. **Alert on anomalies** - Don't wait for users to report issues

## Dashboard Example

A recommended Grafana dashboard would include:

- **Request Rate** (requests/second)
- **Error Rate** (errors/second)
- **Latency** (p50, p95, p99)
- **Cache Hit Rate** (percentage)
- **Fallback Count** (count)
- **High Utilization Warnings** (count)
- **Requests by Chute** (pie chart)
- **Routing Strategy** (status)
