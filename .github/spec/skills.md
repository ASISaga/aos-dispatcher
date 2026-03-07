# Skill Files Specification

**Version**: 1.0.0
**Status**: Active
**Last Updated**: 2026-03-07

## Overview

Specifies the format, structure, and conventions for GitHub Copilot agent skill files (`SKILL.md`) stored in `.github/skills/<skill-name>/`. Skill files follow the [agentskills.io](https://agentskills.io) specification.

## Scope

- YAML frontmatter requirements for `SKILL.md` files
- Directory structure and subdirectory conventions
- Body structure and content guidelines
- Naming conventions

## Specification

### File Format

Every `SKILL.md` must begin with valid YAML frontmatter:

```yaml
---
name: skill-name          # kebab-case; matches the directory name exactly
description: One-sentence purpose with discoverable keywords (1–1024 chars)
---
```

### Required Fields

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | string | kebab-case; must match the directory name |
| `description` | string | 1–1024 characters; keyword-rich for discoverability |

### Directory Structure

```
.github/skills/skill-name/
└── SKILL.md              # Main skill definition
```

### Body Structure

`SKILL.md` files must follow this section order:

1. **Description** — one-line summary of the skill
2. **When to Use This Skill** — explicit activation triggers
3. **Key Concepts** — domain concepts and architecture
4. **File Structure** — relevant file locations
5. **Development Workflow** — step-by-step setup and usage
6. **Common Patterns** — code patterns and examples
7. **Testing** — how to test the skill's subject area
8. **Common Issues and Solutions** — troubleshooting guide
9. **Best Practices** — numbered list of conventions
10. **Monitoring and Debugging** — observability guidance
11. **File Locations** — core and related file paths
12. **Related Skills** — cross-references to other skills
13. **Additional Resources** — external links and internal docs

## Skills in This Repository

| Skill | Directory | Description |
|-------|-----------|-------------|
| `azure-functions` | `.github/skills/azure-functions/` | Expert knowledge for developing, deploying, and debugging Azure Functions in AOS, including Foundry Agent Service integration |

## Validation

Before committing a skill:

1. YAML frontmatter is valid and parseable
2. `name` field is present and in kebab-case
3. `description` field is present and descriptive
4. `name` matches the skill's directory name
5. `SKILL.md` body follows the required section order

```bash
# Validate YAML frontmatter
python -c "
import yaml
content = open('.github/skills/azure-functions/SKILL.md').read()
front = content.split('---')[1]
data = yaml.safe_load(front)
assert data.get('name'), 'name is required'
assert data.get('description'), 'description is required'
print('Frontmatter valid:', data)
"
```

## References

→ **Repository spec**: `.github/spec/repository.md`
→ **Azure Functions skill**: `.github/skills/azure-functions/SKILL.md`
→ **agentskills.io specification**: https://agentskills.io
