## Why

The current proxy spec only briefly mentions `/health` endpoint without details. LiteLLM provides multiple native health endpoints with different purposes and authentication requirements. This needs to be documented so users understand which endpoint to use for different monitoring scenarios.

## What Changes

- Update `openspec/specs/proxy/spec.md` to document LiteLLM's native health endpoints
- Add comprehensive documentation for `/health`, `/health/liveliness`, and `/health/readiness`
- Include authentication requirements, response formats, and usage examples

## Capabilities

### New Capabilities
- None (documentation update only)

### Modified Capabilities
- `proxy`: Document new health endpoint behavior and authentication requirements

## Impact

- Documentation: `openspec/specs/proxy/spec.md`
- No code changes required
