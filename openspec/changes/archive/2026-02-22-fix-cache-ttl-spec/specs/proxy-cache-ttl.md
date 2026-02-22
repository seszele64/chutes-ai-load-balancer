# MODIFIED: Cache TTL in Proxy Spec

## Summary
Update the cache TTL value in the proxy spec to align with the routing spec and implementation.

## Previous Behavior
Proxy spec (line 162) stated: "Cache TTL: 60 seconds (configurable)"

## New Behavior
Proxy spec now states: "Cache TTL: 30 seconds (configurable)"

## Rationale
- Implementation uses 30 seconds as default (source of truth)
- Routing spec specifies 30 seconds (authoritative for routing behavior)
- Proxy spec should align to avoid confusion

## Files Changed
- `openspec/specs/proxy/spec.md` - Line 162: Changed "60 seconds" to "30 seconds"

## Verification
- Confirm proxy spec line 162 now says 30 seconds
- Confirm alignment with routing spec (line 150)
