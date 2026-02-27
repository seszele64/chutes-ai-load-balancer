# Deep Dive Analysis: /invocations/stats/llm Endpoint

> **Note: Historical Data**
>
> This document contains performance analysis data from February 24, 2026.
> The metrics, chute IDs, and performance characteristics documented here
> represent a point-in-time snapshot and may no longer reflect the current
> state of the system. Chute IDs and model deployments frequently change.
>
> For current performance data, refer to the latest utilization API or
> monitoring dashboard.

**Analysis Date:** 2026-02-24  
**API Key:** API_KEY_REMOVED

---

## 1. Response Structure Overview

The endpoint returns a JSON array of **51,008 entries** (~12MB), where each entry represents daily statistics for a specific chute (model deployment).

| Property | Value |
|----------|-------|
| Root Type | Array of objects |
| Total Entries | 51,008 |
| Valid Entries (with metrics) | 37,852 |
| Date Range | 2025-01-30 to 2026-02-23 (390 days) |
| Total Unique Chutes | 6,102 |
| Total Unique Models | 3,482 |

### Sample Entry Structure

```json
{
  "chute_id": "6964d7d5-a5ea-508e-aec8-50f22e1d2bed",
  "name": "ModelName/ModelVersion",
  "date": "2026-02-23",
  "total_requests": 138,
  "total_input_tokens": 470754,
  "total_output_tokens": 133273,
  "average_tps": 73.02,
  "average_ttft": 0.83
}
```

---

## 2. Available Metrics

| Field | Type | Description |
|-------|------|-------------|
| `chute_id` | string | Unique identifier for the deployment/chute |
| `name` | string | Model name (or "[unknown]" for some chutes) |
| `date` | string | Date of the statistics (YYYY-MM-DD) |
| `total_requests` | integer | Number of requests on this date |
| `total_input_tokens` | integer | Total input tokens processed |
| `total_output_tokens` | integer | Total output tokens generated |
| `average_tps` | float | Average tokens per second (throughput) |
| `average_ttft` | float | Average time to first token in seconds (latency) |

**Note:** Some entries have `null` values for `average_tps` and `average_ttft` (12,726 entries) - these represent chutes with no successful generations.

**Note:** Error counts and rate limit counts are NOT available in this endpoint.

---

## 3. Performance Data for User's Models

### User's Chutes

| Model | Chute ID | Total Requests | Avg TPS | Avg TTFT | Total Tokens |
|-------|----------|-----------------|---------|----------|--------------|
| **Kimi K2.5 TEE** (moonshotai) | `2ff25e81-4586-5ec8-b892-3a6f342693d7` | 2,969,764 | 28.31 | 6.45s | 97B |
| **GLM-5 TEE** (zai-org) | `e51e818e-fa63-570d-9f68-49d7d1b4d12f` | 1,260,049 | 22.68 | 28.85s | 50B |
| **Qwen3.5 397B A17B TEE** (Qwen) | `51a4284a-a5a0-5e44-a9cc-6af5a2abfbcf` | 109,757 | 29.45 | 9.41s | 3.5B |

### Daily Breakdown (Recent - Feb 23, 2026)

| Model | Requests | TPS | TTFT | Input Tokens | Output Tokens |
|-------|----------|-----|------|--------------|---------------|
| Kimi K2.5 TEE | 204,960 | 27.25 | 5.44s | 5.33B | 217M |
| GLM-5 TEE | 161,341 | 23.99 | 38.00s | 5.40B | 150M |
| Qwen3.5 397B | 15,448 | 30.37 | 10.01s | 589M | 19M |

---

## 4. Comparison Table

| Metric | Kimi K2.5 TEE | GLM-5 TEE | Qwen3.5 397B | Winner |
|--------|---------------|-----------|--------------|--------|
| **TPS (throughput)** | 28.31 | 22.68 | 29.45 | **Qwen** |
| **TTFT (latency)** | 6.45s | 28.85s | 9.41s | **Kimi** |
| **Total Requests** | 2,969,764 | 1,260,049 | 109,757 | **Kimi** |
| **Total Tokens** | 97B | 50B | 3.5B | **Kimi** |

### Performance Rankings

1. **Highest Throughput (TPS):** Qwen3.5 397B (29.45 tok/s)
2. **Lowest Latency (TTFT):** Kimi K2.5 TEE (6.45s)
3. **Most Reliable/Popular:** Kimi K2.5 TEE (2.97M requests)

---

## 5. Recommendations

### Current Chute Status

| Model | Chute ID | Status | Notes |
|-------|----------|--------|-------|
| **Kimi K2.5 TEE** | `2ff25e81-...` | ✅ GOOD | Best TTFT; alternatives available with higher TPS |
| **GLM-5 TEE** | `e51e818e-...` | ⚠️ SLOW | Highest TTFT (28.85s); consider switching |
| **Qwen3.5 397B** | `51a4284a-...` | ✅ BEST | Highest throughput; many alternatives available |

### Best Alternative Chutes by Model Family

| Model | Best Chute ID | TPS | TTFT | Requests |
|-------|---------------|-----|------|----------|
| **Kimi** | `59825321-d5dd-5980-b9f2-d517048e1ef3` | 189.19 | 1.52s | 803 |
| **GLM** | `2020d266-2de3-5d95-b665-13cd8b108d76` | 133.72 | 2.21s | 9,826 |
| **Qwen** | `0d5ce0e6-5d96-5931-9ca2-3f6d9edcb37c` | 248.55 | 0.34s | 11,948 |

### High-Volume Proven Chutes (Recommended for Production)

| Model | Chute ID | TPS | TTFT | Total Requests |
|-------|----------|-----|------|----------------|
| Kimi | `8d008c10-60d3-51e8-9272-c428ed6ff576` | 68.68 | 2.97s | 2,206,416 |
| Qwen | `fa065f66-c8d4-5af0-a6b4-af47e2ef2473` | 171.35 | 0.80s | 7,595,467 |
| GLM | `8f2105c5-b200-5aa5-969f-0720f7690f3c` | 71.61 | 4.43s | 688,108 |

### Routing Recommendations

1. **For LOW LATENCY (fast first token):** Use Kimi K2.5 TEE
2. **For HIGH THROUGHPUT:** Use Qwen3.5 397B or better chutes
3. **For GLM:** Current chute has poor TTFT (28.85s) - strongly consider switching to `2020d266-2de3-5d95-b665-13cd8b108d76`
4. **For PRODUCTION:** Use proven high-volume chutes with balanced TPS/TTFT

---

## 6. API Query Used

```bash
curl -X GET "https://api.chutes.ai/invocations/stats/llm" \
  -H "X-API-Key: API_KEY_REMOVED" \
  -H "Content-Type: application/json" > /tmp/llm_stats.json
```

---

## Notes

- The `name` field shows `[unknown]` for your specific chutes - this may be a limitation of the stats endpoint for certain deployment types or TEE configurations.
- Error counts and rate limit counts are NOT available in this endpoint - only throughput and latency metrics.
- Data covers ~1 year of historical performance.
