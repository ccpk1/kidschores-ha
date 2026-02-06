# Dashboard Template Guide

**Version**: v0.5.0-beta3 | **Last Updated**: 2026-02-05

This guide documents the rules and patterns for creating, modifying, and managing KidsChores dashboard templates.

---

## Architecture Overview

### Multi-View Dashboard Model

KidsChores generates a **single dashboard** with **multiple views (tabs)**:

```
kcd-chores (Dashboard)
├── Kid1 (View/Tab) ← kid template rendered with kid context
├── Kid2 (View/Tab)  ← kid template rendered with kid context
└── Admin (View/Tab) ← admin template rendered with empty context
```

**Key Points**:

- One dashboard per installation (user names it, e.g., "Chores")
- URL path: `kcd-{slugified-name}` (e.g., `kcd-chores`)
- Each kid gets their own view/tab
- Optional Admin tab for parent controls
- Style (full/minimal/compact) applies to all kid views

---

## Template File Structure

### Location

```
custom_components/kidschores/templates/
├── dashboard_full.yaml      # Full-featured kid dashboard
├── dashboard_minimal.yaml   # Essential features only
└── dashboard_admin.yaml     # Parent administration view
```

### Output Format (CRITICAL)

**All templates must output a SINGLE VIEW object, not a full dashboard.**

```yaml
# ✅ CORRECT - Single view (list item)
- max_columns: 4
  title: << kid.name >> Chores
  path: << kid.slug >>
  sections:
    - type: grid
      cards: [...]

# ❌ WRONG - Full dashboard with views wrapper
views:
  - max_columns: 4
    title: << kid.name >> Chores
    ...
```

The builder combines multiple single-view outputs into `{"views": [...]}`.

---

## Jinja2 Delimiter System (Dual-Layer)

Templates use **two different Jinja2 syntaxes** for different purposes:

### Build-Time (Python Jinja2) - `<< >>`

Processed by the integration when generating the dashboard.

| Delimiter   | Purpose             | Example                            |
| ----------- | ------------------- | ---------------------------------- |
| `<< >>`     | Variable injection  | `<< kid.name >>`, `<< kid.slug >>` |
| `<% %>`     | Block statements    | `<% if condition %>...<%endif%>`   |
| `<#-- --#>` | Comments (stripped) | `<#-- This is removed --#>`        |

**Available Context Variables** (kid templates only):

```python
{
    "kid": {
        "name": "Alice",     # Display name from storage
        "slug": "alice"      # URL-safe slugified name
    }
}
```

Admin templates receive empty context `{}`.

### Runtime (Home Assistant Jinja2) - `{{ }}`

Preserved in output, evaluated by HA when rendering the dashboard.

| Delimiter | Purpose                   | Example                                  |
| --------- | ------------------------- | ---------------------------------------- |
| `{{ }}`   | HA state/attribute access | `{{ states('sensor.kc_alice_points') }}` |
| `{% %}`   | HA template logic         | `{% for item in items %}...{% endfor %}` |
| `{# #}`   | HA template comments      | `{# This stays in output #}`             |

### Example: Both Syntaxes Together

```yaml
- type: custom:mushroom-template-card
  primary: << kid.name >>'s Points
  secondary: >-
    {{ states('sensor.kc_<< kid.slug >>_points') | int }} points
```

**After build-time render** (for kid "Alice"):

```yaml
- type: custom:mushroom-template-card
  primary: Alice's Points
  secondary: >-
    {{ states('sensor.kc_alice_points') | int }} points
```

---

## Comment Syntax Rules

### Build-Time Comments (Stripped)

```yaml
<#-- This comment is removed during template processing --#>
```

**Rules**:

1. Must have `<#--` opening and `--#>` closing on same logical block
2. Can span multiple lines BUT each line should be self-contained
3. Malformed comments cause YAML parse errors

**✅ Correct multi-line**:

```yaml
<#-- ============================================= --#>
<#-- KidsChores Dashboard Template - FULL Style   --#>
<#-- Template Schema Version: 1                   --#>
<#-- ============================================= --#>
```

**❌ Wrong - missing closer**:

```yaml
<#-- This comment has no closing
<#-- This line starts new comment --#>
```

**❌ Wrong - double closer**:

```yaml
<#-- Comment text --#> --#>
```

### Runtime Comments (Preserved)

```yaml
{#-- This comment stays in the rendered output --#}
```

Use for HA template debugging or documentation visible in Lovelace editor.

---

## Template Header Standard

Every template MUST start with this header block:

```yaml
<#-- ============================================= --#>
<#-- KidsChores Dashboard Template - [STYLE] Style --#>
<#-- Template Schema Version: 1                    --#>
<#-- Integration: v0.5.0-beta3 (Schema 43)         --#>
<#-- ============================================= --#>
<#--                                               --#>
<#-- [Brief description of this template]          --#>
<#-- OUTPUT: Single view object (combined by builder) --#>
<#--                                               --#>
<#-- Injection variables (Python Jinja2 << >>):    --#>
<#--   << kid.name >> - Child's display name        --#>
<#--   << kid.slug >> - URL-safe slug for path      --#>
<#--                                               --#>
<#-- All HA Jinja2 {{ }} syntax is preserved as-is --#>
<#-- ============================================= --#>

- max_columns: 4
  title: ...
```

For admin templates, omit the injection variables section and note "No injection needed".

---

## Entity ID Pattern

When referencing KidsChores entities in templates, use the pattern below. Never hard code entity names:

```
{#-- 1. User Configuration --#}

{%- set name = '<< kid.name >>' -%}  {#-- ⬅️ CHANGE THIS to your child's actual name #}


{#-- 2. Initialize Variables --#}
{%- set dashboard_helper = integration_entities('kidschores')
    | select('search', 'ui_dashboard_helper')
    | list
    | expand
    | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')
    | selectattr('attributes.kid_name', 'eq', name)
    | map(attribute='entity_id')
    | first
    | default("err-dashboard_helper_missing", true) -%}
```

---

## Validation Checklist

Before committing template changes:

### 1. Comment Syntax Check

```bash
# Look for unclosed or malformed comments
grep -n "<#--" templates/*.yaml | grep -v "\-\-#>"
```

### 2. Template Render Test

```bash
cd /workspaces/kidschores-ha && python3 << 'EOF'
import jinja2
import yaml
from pathlib import Path

template_path = Path("custom_components/kidschores/templates/dashboard_full.yaml")
template_str = template_path.read_text()

env = jinja2.Environment(
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#--",
    comment_end_string="--#>",
    autoescape=False,
)

context = {"kid": {"name": "TestKid", "slug": "testkid"}}
template = env.from_string(template_str)
rendered = template.render(**context)

config = yaml.safe_load(rendered)
if isinstance(config, list) and len(config) > 0:
    print(f"✅ Valid: Parsed as list, first item keys: {list(config[0].keys())[:5]}")
else:
    print(f"❌ Invalid: Expected list, got {type(config)}")
EOF
```

### 3. View Structure Check

Ensure output has required keys:

- `title` - View tab title
- `path` - URL path segment (unique per view)
- `sections` or `cards` - Content

---

## Adding a New Template Style

1. **Create template file**: `templates/dashboard_[style].yaml`
2. **Add constant**: `const.py` → `DASHBOARD_STYLE_[STYLE]`
3. **Add to style options**: `dashboard_helpers.py` → `build_dashboard_style_options()`
4. **Add translation**: `translations/en.json` → style label
5. **Test render**: Use validation script above

---

## Fetching Priority

Templates are fetched in this order:

1. **Remote** (GitHub raw): `https://raw.githubusercontent.com/ad-ha/kidschores-ha/main/templates/dashboard_[style].yaml`
2. **Local fallback**: `custom_components/kidschores/templates/dashboard_[style].yaml`

Remote fetch allows template updates without integration updates. Local ensures offline functionality.

---

## Common Pitfalls

| Issue                                 | Cause                           | Solution                                    |
| ------------------------------------- | ------------------------------- | ------------------------------------------- |
| `mapping values are not allowed here` | Malformed comment block         | Check all `<#-- --#>` pairs                 |
| `Template did not produce valid view` | Output has `views:` wrapper     | Remove wrapper, start with `- max_columns:` |
| Entity IDs not working                | Wrong slug format               | Use `<< kid.slug >>` not `<< kid.name >>`   |
| HA Jinja2 stripped                    | Used `<< >>` instead of `{{ }}` | Use `{{ }}` for runtime evaluation          |
| Build variables not replaced          | Used `{{ }}` instead of `<< >>` | Use `<< >>` for build-time injection        |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│ BUILD-TIME (Python)          RUNTIME (Home Assistant)   │
├─────────────────────────────────────────────────────────┤
│ << variable >>               {{ states('sensor.x') }}   │
│ <% if cond %>...<% endif %>  {% if cond %}...{% endif %}│
│ <#-- stripped comment --#>   {# preserved comment #}    │
├─────────────────────────────────────────────────────────┤
│ Context: kid.name, kid.slug  Context: Full HA state     │
│ When: Dashboard generation   When: Dashboard render     │
└─────────────────────────────────────────────────────────┘
```
