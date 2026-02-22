# Tasks: Fix Cache TTL Spec Discrepancy

## Implementation Steps

### Task 1: Update Proxy Spec
- [x] Edit `openspec/specs/proxy/spec.md` line 162
- [x] Change "Cache TTL: 60 seconds" to "Cache TTL: 30 seconds"
- [x] Save the file

### Task 2: Verify Alignment
- [x] Confirm proxy spec line 162 now says "30 seconds"
- [x] Confirm routing spec line 150 says "30 seconds"
- [x] Confirm alignment is complete

## Completion Criteria

- [x] Proxy spec updated to 30 seconds
- [x] Both specs (proxy and routing) now show consistent 30 second TTL
- [x] No code changes needed (spec alignment only)
