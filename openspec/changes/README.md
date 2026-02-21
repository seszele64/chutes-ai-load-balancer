# OpenSpec Changes

This directory contains pending changes to the system. Each change gets its own folder with:
- `proposal.md` - The "Why" and "What"
- `specs/` - Delta specs (ADDED/MODIFIED/REMOVED)
- `design.md` - Technical design
- `tasks.md` - Implementation checklist

## Delta Spec Format

### ADDED - New Feature

```markdown
# ADDED: <Feature Name>

## Summary
Brief description of what was added.

## Specification
Detailed specification of the addition.

## Files Changed
- `path/to/file.py` - Added new function/feature

## Verification
How to verify this change works correctly.
```

### MODIFIED - Existing Feature Change

```markdown
# MODIFIED: <Feature Name>

## Summary
Brief description of what was modified.

## Previous Behavior
Description of how it worked before.

## New Behavior
Description of how it works now.

## Files Changed
- `path/to/file.py` - Modified function/behavior

## Migration Notes
Any steps needed to migrate existing setups.
```

### REMOVED - Feature Removal

```markdown
# REMOVED: <Feature Name>

## Summary
Brief description of what was removed.

## Reason
Why this feature was removed.

## Files Changed
- `path/to/file.py` - Removed function/feature

## Impact
What users need to do as a result.
```

## Examples

### Example: ADDED

```markdown
# ADDED: Health Check Endpoint

## Summary
Added a health check endpoint to the LiteLLM proxy for monitoring and load balancer integration.

## Specification
The proxy now exposes a `/health` endpoint that returns:
- HTTP 200 with `{"status": "healthy"}` when all models are available
- HTTP 503 with `{"status": "degraded", "unavailable_models": [...]}` when some models are down

## Files Changed
- `start_litellm.py` - Added health check route
- `litellm-config.yaml` - Added health check configuration

## Verification
1. Start the proxy: `python start_litellm.py`
2. Request: `curl http://localhost:4000/health`
3. Verify response is `{"status": "healthy"}`

## Migration Notes
No migration required. This is a new endpoint.
```

### Example: MODIFIED

```markdown
# MODIFIED: Cache TTL Configuration

## Summary
Increased cache TTL from 60 seconds to 300 seconds to reduce API calls.

## Previous Behavior
Cache entries expired after 60 seconds, causing frequent cache misses.

## New Behavior
Cache entries now expire after 300 seconds (5 minutes).

## Files Changed
- `chutes_routing.py` - Changed `CACHE_TTL` constant from 60 to 300

## Verification
1. Check `chutes_routing.py` line X: `CACHE_TTL = 300`
2. Monitor cache hit rate over 10 minutes

## Migration Notes
Existing cache entries will use the old TTL until they expire.
```

### Example: REMOVED

```markdown
# REMOVED: Legacy Fallback Model

## Summary
Removed the tertiary fallback model (Qwen3.5) from the routing chain.

## Reason
The primary and secondary models now provide sufficient reliability.

## Files Changed
- `litellm-config.yaml` - Removed Qwen model from model list
- `chutes_routing.py` - Updated fallback chain

## Impact
Users should monitor for increased latency during primary model outages.
```

## Changelog

| Date | Change | Type | Status |
|------|--------|------|--------|
| 2026-02-21 | Initial OpenSpec setup | N/A | Archived |

### Active Changes

No active changes currently.

### Archived Changes

- `initial-openspec-setup/` - Initial OpenSpec framework integration
