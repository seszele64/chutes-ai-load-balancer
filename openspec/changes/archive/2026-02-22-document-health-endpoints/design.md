## Context

This is a documentation-only change to update the LiteLLM proxy specification. The current proxy spec lacks detail about LiteLLM's native health endpoints. The explorer discovered that LiteLLM provides multiple health endpoints with different purposes and authentication requirements.

## Goals / Non-Goals

**Goals:**
- Document all LiteLLM native health endpoints in the proxy spec
- Include authentication requirements for each endpoint
- Provide usage examples for different monitoring scenarios

**Non-Goals:**
- No code changes (LiteLLM handles health endpoints natively)
- No new functionality - only documentation update

## Decisions

1. **Document existing LiteLLM behavior**: Since LiteLLM already provides health endpoints, the decision is simply to document them accurately in the proxy spec.

2. **Categorize endpoints by auth requirement**: 
   - `/health` - requires Bearer token (makes actual API calls to models)
   - `/health/liveliness` - no auth needed (simple alive check)
   - `/health/readiness` - no auth needed (includes DB/cache status)

## Risks / Trade-offs

- No technical risks - this is a documentation update only
- LiteLLM version compatibility: Health endpoint behavior may vary slightly across LiteLLM versions
