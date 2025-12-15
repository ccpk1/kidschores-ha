# Testing Agent Instructions - KidsChores Integration

Quick reference for AI agents working on the KidsChores test suite. Consult [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md) if issues persist after 3 attempts.

## Quick Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific file
python -m pytest tests/test_workflow_parent_actions.py -v

# Stop on first failure
python -m pytest tests/ -x
```

## Critical Decision Tree

### Step 1: Identify Test Type

| Test Type      | File Pattern                                   | Data Loading       |
| -------------- | ---------------------------------------------- | ------------------ |
| UI Workflow    | `test_config_flow.py`, `test_options_flow*.py` | Options flow       |
| Business Logic | `test_coordinator.py`, `test_services.py`      | Direct coordinator |
| User Workflow  | `test_workflow_*.py`                           | Direct + reload    |
| Dashboard      | `test_dashboard_templates.py`                  | Mock states        |

### Step 2: Load Data Correctly

**Options Flow** (UI simulation):

```python
result = await hass.config_entries.options.async_init(config_entry.entry_id)
result = await hass.config_entries.options.async_configure(
    result["flow_id"], user_input={"next_step": "add_kid"}
)
```

**Direct Loading** (business logic):

```python
config_entry, name_to_id_map = scenario_minimal
coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
kid_id = name_to_id_map["kid:Zoë"]
```

### Step 3: Execute Action

**Direct entity access** (workflow tests):

```python
button_entity = None
for entity in hass.data.get("entity_components", {}).get("button", {}).entities:
    if entity.entity_id == button_id:
        button_entity = entity
        break

button_entity._context = Context(user_id=mock_hass_users["parent1"].id)

with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
    await button_entity.async_press()
```

## Essential Patterns

1. **Platform Reload**: `await reload_entity_platforms(hass, config_entry)`
2. **Direct Entity Access**: Find entity in `hass.data.get("entity_components", {}).get("button", {}).entities`
3. **Mock Notifications**: `with patch.object(coordinator, "_notify_kid", new=AsyncMock())`
4. **Set User Context**: `button_entity._context = Context(user_id=mock_hass_users["parent1"].id)`
5. **Test Real Structures**: `penalty_applies`, `bonus_applies`, `point_stats`, `badges_earned`
6. **Badge Cycle Reset**: Check `badges_earned` or `baseline`, NOT `cycle_points` (resets to 0)

## Troubleshooting (3-Attempt Rule)

If issue persists after 3 attempts, consult [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md) sections:

- **Debugging** (line ~1100) - Full troubleshooting guide
- **Lessons Learned** (line ~1200) - Common pitfalls
- **Testing Patterns** (line ~900) - Detailed code patterns
- **Data Loading Methods** (line ~100) - When to use each method

## Code Quality Requirements

### Before Committing - Mandatory Checks

```bash
# ALWAYS RUN after EVERY change:
./utils/quick_lint.sh --fix

# This checks:
# - Pylint errors (critical severity 4+)
# - Type errors (Pyright/Pylance)
# - Trailing whitespace (auto-fixes)
# - Line length warnings

# Verify all tests pass
python -m pytest tests/ -v

# For detailed checks on specific files:
python utils/lint_check.py --file path/to/file.py
```

**See [utils/README_LINTING.md](../utils/README_LINTING.md) for complete linting guide.**

### Severity 4 Errors/Warnings - MUST FIX OR SUPPRESS

- ❌ **W0612**: Unused variables → Remove or use underscore `_`
- ❌ **W0613**: Unused arguments → Add `# pylint: disable=unused-argument`
- ❌ **W0611/F401**: Unused imports → Remove them
- ❌ **W0404**: Reimports → Don't import same module twice
- ❌ **W0621**: Redefined names → Suppress for pytest fixtures (module-level)
- ❌ **W0212**: Protected access → Suppress at module level for test files
- ❌ **F841**: Unused local variables → Remove them
- ❌ **F541**: F-strings without placeholders → Convert to regular strings

### Module-Level Suppressions (Critical Pattern)

**ALWAYS use module-level suppressions** for warnings appearing 3+ times in a file:

```python
"""Test module docstring."""

# pylint: disable=protected-access  # Accessing _context/_persist for testing
# pylint: disable=redefined-outer-name  # Pytest fixtures redefine names
# pylint: disable=unused-argument  # Fixtures needed for test setup

from unittest.mock import AsyncMock
```

**Place immediately after docstring, before imports**

### Acceptable Warnings (Severity 2)

- ✅ **C0301**: Line too long (acceptable for readability)
- ✅ **C0415**: Import outside toplevel (acceptable in fixtures)
- ✅ **C0302**: Too many lines (acceptable for conftest.py)
- ✅ **R0914/R0912/R0915**: Too many locals/branches/statements (acceptable in complex tests)

### Test File Checklist

- ✅ Type hints on all test functions
- ✅ Docstrings explain what test validates
- ✅ No debug code (print, pdb, f-strings without interpolation)
- ✅ Descriptive test names: `test_<feature>_<action>_<expected>`
- ✅ Module-level suppressions for repeated patterns
- ✅ Zero severity 4+ warnings (`pylint tests/*.py 2>&1 | grep -E "^[WE][0-9]{4}:" | wc -l` returns 0)

---

**Last Updated**: December 13, 2024
