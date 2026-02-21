# OpenSpec AI Assistant Instructions

## Overview

This project uses **OpenSpec**, a spec-driven development framework for building and maintaining the system. OpenSpec provides structured workflows for proposing, designing, implementing, and tracking changes to the chutes-load-balancer system.

## Project Context

### chutes-load-balancer

A load balancer system that routes requests between chutes.ai model deployments:
- **Primary Model**: Kimi K2.5 TEE (moonshotai)
- **Secondary Model**: GLM-5 TEE (zai-org)  
- **Tertiary Model**: Qwen3.5 397B A17B TEE (Qwen)

**Key Components**:
- `chutes_routing.py` - Custom LiteLLM routing strategy based on real-time utilization
- `start_litellm.py` - LiteLLM proxy startup script
- `litellm-config.yaml` - Model configuration
- `openspec/` - Specification documents and change tracking

**LiteLLM Proxy**: http://localhost:4000

## OpenSpec Workflow

### Core Workflow

1. **Initialize** - Run `openspec init` to set up the project
2. **Explore** - Use `/opsx:explore` to think through ideas
3. **Create Change** - Use `/opsx:new` for interactive creation or `/opsx:ff` for fast-forward
4. **Iterate** - Use `/opsx:continue` to create next artifact based on dependencies
5. **Implement** - Use `/opsx:apply` to implement tasks
6. **Archive** - Use `/opsx:archive` to archive completed changes

### Artifact Dependency Chain

```
proposal.md (root - no dependencies)
    ↓
specs/ (detailed requirements - depends on proposal)
    ↓
design.md (technical design - depends on proposal + specs)
    ↓
tasks.md (implementation checklist - depends on specs + design)
```

### Quick Commands

| Command | Purpose |
|---------|---------|
| `/opsx:explore` | Think through ideas before committing |
| `/opsx:new` | Start new change with interactive prompts |
| `/opsx:ff` | Fast-forward: create proposal+specs+design+tasks at once |
| `/opsx:continue` | Create next artifact in dependency chain |
| `/opsx:apply` | Implement tasks from tasks.md |
| `/opsx:sync` | Sync delta specs to master specs |
| `/opsx:archive` | Archive completed change to history |

## Available Slash Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `/opsx:explore` | Think through ideas and explore solutions |
| `/opsx:new` | Start new change with interactive prompts |
| `/opsx:ff` | Fast-forward: create all artifacts at once |
| `/opsx:continue` | Create next artifact based on dependencies |
| `/opsx:propose` | Create a new spec proposal |
| `/opsx:design` | Create detailed design document |
| `/opsx:task` | Generate implementation tasks |
| `/opsx:apply` | Apply a delta spec (ADDED/MODIFIED/REMOVED) |
| `/opsx:sync` | Sync delta specs to master specs |
| `/opsx:archive` | Archive completed change |
| `/opsx:review` | Review pending changes |

### Backward Compatibility

The following legacy commands are aliased to their `/opsx:*` equivalents:
- `/spec-propose` → `/opsx:propose`
- `/spec-design` → `/opsx:design`
- `/spec-task` → `/opsx:task`
- `/spec-apply` → `/opsx:apply`
- `/spec-review` → `/opsx:review`

## CLI Commands

> **Note**: These CLI commands are provided by the external OpenSpec tool
> (`openspec` npm/package), not implemented in this repository. They are
> documented here for reference when using the OpenSpec workflow.

OpenSpec provides CLI commands for managing specs and changes:

| Command | Description |
|---------|-------------|
| `openspec list` | List all active changes |
| `openspec show <name>` | Show details of a specific change |
| `openspec view` | Open interactive dashboard |
| `openspec validate [name]` | Validate changes/specs for correctness |
| `openspec archive <name>` | Archive a completed change |
| `openspec status --change <name>` | Check artifact status for a change |
| `openspec instructions <artifact>` | Get instructions for an artifact type |

## Delta Specs (Change Management)

Changes to the system are tracked using delta specifications in `openspec/changes/`. Each delta spec follows this format:

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

## Artifact Structure

Each spec directory can contain:

```
openspec/specs/<category>/
├── spec.md          # Current specification (master)
├── proposal.md      # Proposed change (optional)
├── design.md        # Design document (optional)
├── tasks.md         # Implementation tasks (optional)
└── history/         # Archived versions
```

The `spec.md` always represents the current state of the system. Changes are tracked in `openspec/changes/`.

## Best Practices

1. **Always reference specs**: When making changes, reference the relevant spec file
2. **Use delta specs**: All changes to system behavior should be documented as delta specs
3. **Test independently**: Each task should be independently verifiable
4. **Keep specs in sync**: Update spec.md when implementation diverges
5. **Review before apply**: Use `/opsx:review` to see pending changes before applying

## Quick Reference

| Topic | Location |
|-------|----------|
| Project Config | `openspec/config.yaml` |
| Routing Spec | `openspec/specs/routing/spec.md` |
| Proxy Spec | `openspec/specs/proxy/spec.md` |
| Changes | `openspec/changes/` |
| Source Code | Root directory |

## Getting Help

- Review existing specs in `openspec/specs/`
- Check `openspec/changes/` for recent modifications
- Reference `README.md` for system overview
