## Overview

This change aligns the cache TTL value in the proxy spec with the routing spec and implementation.

## Problem

- **Proxy spec** (line 162): States 60 seconds
- **Routing spec** (line 150): States 30 seconds  
- **Implementation**: Uses 30 seconds

This discrepancy creates confusion about the actual cache TTL behavior.

## Solution

Update proxy spec line 162 from "60 seconds" to "30 seconds" to match:
1. The routing spec (authoritative for routing behavior)
2. The implementation (source of truth)

## Changes

### Documentation Only
- `openspec/specs/proxy/spec.md` - Line 162

No code changes required.

## Testing

Verify:
1. Proxy spec line 162 now says "30 seconds"
2. Routing spec line 150 says "30 seconds" (already correct)
3. Implementation uses 30 seconds (already correct)
