## Why

There is a discrepancy in the cache TTL specification between the proxy spec and routing spec. The proxy spec (line 162) states 60 seconds, while the routing spec (line 150) and the implementation both use 30 seconds. This inconsistency can lead to confusion and potential misconfiguration.

## What Changes

- Update proxy spec to align cache TTL with routing spec (30 seconds)
- Document the rationale for the alignment

## Capabilities

### Modified Capabilities
- `proxy`: Update Cache TTL from 60 seconds to 30 seconds to match routing spec and implementation

## Impact

- Only documentation/spec changes
- No code modifications required
- Aligns specs with actual implementation behavior
