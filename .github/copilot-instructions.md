# KidsChores Home Assistant Integration - AI Coding Instructions

**Core Pattern**: All entities use `internal_id` (UUID) as primary key. Names are changeable; IDs persist across renames.

## Tech Stack

- **Python 3.12+**, PEP 8, Black formatting, mandatory type hints
- **Async I/O**: All I/O must be async; use `hass.async_add_executor_job` only for blocking third-party calls
- **Imports**: Relative (e.g., `from . import const`)
- **Logging**: `const.LOGGER` with `DEBUG:`, `INFO:`, `WARNING:`, `ERROR:` prefixes (lazy logging: `_LOGGER.debug("Message: %s", value)`)
- **Shared code**: Add common functions to `kc_helpers.py` or `flow_helpers.py`, not elsewhere

## Code Quality Standards

- **Automated linting**: `./utils/quick_lint.sh --fix` or `python utils/lint_check.py --integration`
- **No linting errors**: Script checks pylint (critical errors only), type errors, trailing whitespace
- **No type errors**: Pyright/Pylance errors are caught by lint scripts (set VS Code to "basic" mode)
- **Type hints**: All functions/methods must have type hints (params and return)
- **Docstrings**: All public functions/methods/classes require docstrings
- **Error handling**: Use specific exceptions (`HomeAssistantError`, `ServiceValidationError`, `ConfigEntryNotReady`, `ConfigEntryAuthFailed`)
- **No debug code**: Remove print statements, pdb, commented code before committing
- **Descriptive naming**: Functions/variables should be self-documenting (e.g., `get_kid_by_name()`, not `get_k()`)
- **DRY principle**: Use helper functions in `kc_helpers.py`/`flow_helpers.py` instead of duplicating code

## Architecture Overview

**Storage → Coordinator → Entities**

- **Storage** (`storage_manager.py`): JSON persistence, keyed by `internal_id`
- **Coordinator** (`coordinator.py`): 8000+ lines handling chore lifecycle, badge calculations, notifications, recurring schedules
- **Entities**: `sensor.py` (50+ entity types across multiple platforms), `button.py` (claim/approve/disapprove actions), `calendar.py` (event scheduling), `select.py` (entity selection menus)
- **Config**: `const.py` (2400+ lines) centralizes constants across 18+ prefix categories (see Constant Naming Standards below)

## Critical Patterns

**Entity Identification**: Always use `internal_id`, never names for lookups (names change on renames).

**DateTime**: Store as UTC-aware ISO strings via `kc_helpers.parse_datetime_to_utc()`. Migration logic in `coordinator._migrate_stored_datetimes()`.

**Recurring Chores**: Coordinator resets on midnight via `async_track_time_change` using daily/weekly/monthly intervals.

**Notifications**: Action strings embed `kid_id` and `chore_id` (e.g., `"approve_chore_<kid_id>_<chore_id>"`). Handlers in `notification_action_handler.py` route to coordinator.

**Access Control**: `is_user_authorized_for_kid(hass, user_id, kid_id)` and `is_user_authorized_for_global_action()` in `kc_helpers.py`. Admins always allowed; non-admins checked against parents/kids lists.

**Badges**: Tracked by type (`achievement`, `challenge`, `cumulative`, `daily`, `periodic`, `special`), with progress in kid's `badges_earned` list (includes `internal_id`, `last_awarded_date`, multiplier).

## Configuration & Services

**Config Flow** (`config_flow.py`, 1300+ lines): Multi-step UI setup. **Options Flow** (`options_flow.py`): Manage existing entities. Must sync with storage via `coordinator._merge_and_update_entities()`.

**Services** (18 total in `services.yaml`): Receive entity names → resolve to `internal_id` → call coordinator. Lifecycle: `claim_chore`, `approve_chore`, `disapprove_chore`. Rewards: `redeem_reward`, `approve_reward`, `disapprove_reward`. Points: `adjust_points`, `apply_bonus`, `apply_penalty`. Resets: `reset_all_chores`, `reset_penalties`, etc.

## Helper Utilities

**`kc_helpers.py`** (1400+): Entity lookups, datetime parsing, authorization checks, dashboard translation loading.

**`flow_helpers.py`** (2000+): Schema builders (`build_kid_schema`, `build_chore_schema`, etc.) with Voluptuous & selectors. Input validation for config/options flows.

Add shared functions to these files, not elsewhere.

## Development

**Validation**: HACS & Hassfest via GitHub Actions. Local: `./utils/quick_lint.sh --fix` (comprehensive linting including pylint, type checking, and formatting).

**Linting**: During development, you may run quick individual file lints. **Before completion**: See mandatory requirements below.

**Testing**: 150 automated tests (139 passing, 11 intentionally skipped, ~7 seconds execution). **CRITICAL**: When working on tests, follow `tests/TESTING_AGENT_INSTRUCTIONS.md` (quick reference). For detailed troubleshooting after 3 failed attempts, consult `tests/TESTING_GUIDE.md`.

### Before Completion - MANDATORY REQUIREMENTS ✅

**Work is NOT complete until BOTH commands pass:**

```bash
# 1. FULL LINT CHECK (~22 seconds)
./utils/quick_lint.sh --fix

# 2. FULL TEST SUITE (~7 seconds - 150 tests)
python -m pytest tests/ -v --tb=line
```

**NEVER declare work complete without running both commands above.** During development, individual file tests are acceptable for quick iteration, but final validation requires full suite execution.

**Testing as Debugging Tool**: The test suite is highly effective for debugging both the integration and dashboard. When investigating issues:

- Write a test that reproduces the bug → reveals exact failure point
- Use coordinator tests to verify business logic without UI
- Use dashboard template tests to validate Jinja2 syntax and data access
- Scenario YAML files provide consistent, reproducible test data

**Key Test Patterns**:

- **Options Flow**: UI simulation for validation tests
- **Direct Coordinator Loading**: Business logic via YAML scenarios + platform reload
- **Direct Entity Access**: Bypass service dispatcher after reload
- **Mock Notifications**: Always `patch.object(coordinator, "_notify_kid", new=AsyncMock())`
- **User Context**: `button_entity._context = Context(user_id=mock_user.id)`

**Test Code Quality** (mandatory before committing):

- ✅ **No severity 8 errors** (import errors, attribute access issues, TypedDict issues)
- ✅ **No severity 4 warnings** unless explicitly acceptable (see below)
- ✅ **No unused imports or variables** (remove or prefix with `_`)
- ✅ **No reimports** (don't import same thing twice)
- ✅ **No TODO/FIXME comments** (resolve or create issue)
- ✅ Type hints on all test functions (params and return type)
- ✅ Docstrings explain what test validates
- ✅ **No debug code** (remove all `print()`, `pdb`, commented code, f-strings without interpolation)
- ✅ Descriptive test names: `test_<feature>_<action>_<expected>`

**Acceptable test warnings** (severity 2-4, can ignore or suppress):

- `too-many-locals` (R0914) - Test setup often needs many variables
- `import-outside-toplevel` (C0415) - Acceptable in test fixtures (severity 2)
- `too-many-lines` (C0302) - conftest.py can exceed 1000 lines (severity 2)
- `line-too-long` (C0301) - Acceptable for readability (severity 2)

**Must fix or suppress before committing** (severity 4):

- Import errors (`no-name-in-module`, `reportAttributeAccessIssue`)
- TypedDict access issues (`reportTypedDictNotRequiredAccess` - use `.get()` with defaults)
- Unused imports/variables (F401, W0611, F841, W0612) - remove them
- Unused arguments (W0613) - suppress in skipped tests or remove parameter: `# pylint: disable=unused-argument`
- Reimports (W0404) - don't import same module twice
- TODO/FIXME comments (W0511) - resolve or create issue
- Redefined names (W0621) - suppress for pytest fixtures: `# pylint: disable=redefined-outer-name`
- Protected access (W0212) - **ALWAYS suppress at module level for test files**:
  ```python
  # pylint: disable=protected-access  # Accessing _context/_persist for testing
  ```
  Place immediately after module docstring, before imports

**False positives**: If linter reports errors but code works correctly, suppress with comments:

```python
# pylint: disable=no-member  # False positive - dynamic attribute
# type: ignore[attr-defined]  # Mypy false positive
```

**Critical: Module-Level Suppressions for Test Files**

When a warning applies to **multiple locations** in a test file (e.g., W0212 protected-access used 8+ times), use **module-level suppression** instead of inline suppressions:

```python
"""Test module docstring."""

# pylint: disable=protected-access  # Accessing _context/_persist for testing

from unittest.mock import AsyncMock
```

**Why module-level?**

- Prevents missing warnings in large files (8+ occurrences easily overlooked)
- More maintainable - one suppression instead of 8+
- Standard practice for test files accessing internal APIs
- IDE diagnostics may not refresh immediately after adding suppressions

**Common module-level suppressions for tests**:

- `protected-access` - Tests accessing `_context`, `_persist()`, `_get_*()` internal methods
- `redefined-outer-name` - Entire test file uses pytest fixtures that shadow fixture names
- `unused-argument` - Can also use at function level for skipped tests

**Verification after fixing warnings**:

1. Run `pylint tests/*.py 2>&1 | grep -E "^[WE][0-9]{4}:"`
2. Restart VS Code or reload window to refresh IDE diagnostics
3. Check file in editor - green checkmark = no warnings

**Key Files**: `coordinator.py` (business logic), `const.py` (all constants), `storage_manager.py` (persistence), `services.py` (service schemas → coordinator calls), entity platforms (`sensor.py`, `button.py`, `calendar.py`, `select.py`).

## Common Pitfalls

1. Don't use entity names as keys; use `internal_id`
2. Store datetimes as UTC-aware ISO strings via `kc_helpers.parse_datetime_to_utc()`
3. Don't cache entity data outside coordinator; coordinator is single source of truth
4. Never hardcode user-facing strings; use `const.TRANS_KEY_*`
5. Services receive names; resolve to `internal_id` before coordinator calls
6. Notification action strings must embed both `kid_id` and `chore_id`/`reward_id`

## Adding/Modifying Features

- **New entity**: Update `config_flow.py`, `options_flow.py`, coordinator merge logic, entity platform
- **New service**: Schema in `services.py`, add to `services.yaml`, implement in coordinator
- **Data structure change**: Update storage version in `const.py`, add migration in coordinator
- **New constant**: Add to `const.py` with proper prefix; update translations if user-facing

## Entity Design

Inherit from `CoordinatorEntity` for automatic coordinator updates. Set `unique_id` (stable via `internal_id`), `device_info` (for device registry), and override `_handle_coordinator_update()` for data processing.

**Coordinator error handling**: Wrap I/O in try/except, log with `const.LOGGER.error()`, return last known data on transient failures. Use `UpdateFailed` only for persistent errors.

**Dashboard**: Use modern template sensors, standard Lovelace cards (Entities, Tile, Button), or `mushroom-cards`. Reload translations via `_async_reload_translations()`.

## Constant Naming Standards

The codebase uses strict, consistent naming patterns for all constants in `const.py` (95%+ consistency). Follow these patterns precisely:

### Primary Constant Prefixes (8 Categories)

1. **`DATA_*`** - Storage/runtime data keys (120+ occurrences, 100% consistent)

   - Pattern: `DATA_{ENTITY}_{PROPERTY}` (singular entity name)
   - Examples: `DATA_KID_NAME`, `DATA_CHORE_POINTS`, `DATA_BADGE_TYPE`
   - Used for: Accessing dictionary keys in stored entity data

2. **`CFOF_*`** - Config Flow & Options Flow input field names (150+ occurrences, 80% consistent)

   - Pattern: `CFOF_{ENTITIES}_INPUT_{GENERIC_FIELD}` (plural entity, generic field)
   - Examples: `CFOF_KIDS_INPUT_NAME`, `CFOF_CHORES_INPUT_DESCRIPTION`, `CFOF_BADGES_INPUT_ICON`
   - Note: 80% use generic fields (NAME/DESCRIPTION/ICON), 20% use entity-specific fields
   - Used for: User input field keys in config/options flow schemas

3. **`CFOP_ERROR_*`** - Config Flow & Options Flow error keys (20+ occurrences, 100% consistent after fixes)

   - Pattern: `CFOP_ERROR_{FIELD_NAME}` (snake_case field name matching input field)
   - Examples: `CFOP_ERROR_KID_NAME`, `CFOP_ERROR_PARENT_NAME`, `CFOP_ERROR_START_DATE`
   - Used for: Error dictionary keys to mark which field has validation error

4. **`TRANS_KEY_CFOF_*`** - Translation keys for config/options flows (100+ occurrences, 95% consistent)

   - Pattern: `TRANS_KEY_CFOF_{TYPE}_{DETAIL}` or `TRANS_KEY_CFOF_{ERROR_DESCRIPTION}`
   - Examples: `TRANS_KEY_CFOF_DUPLICATE_KID`, `TRANS_KEY_CFOF_INVALID_BADGE_TYPE`, `TRANS_KEY_CFOF_BADGE_ASSIGNED_TO`
   - Used for: User-facing error messages and field labels (localized)

5. **`CONFIG_FLOW_STEP_*`** - Config flow step identifiers (20+ occurrences, 100% consistent)

   - Pattern: `CONFIG_FLOW_STEP_{ACTION}_{ENTITY}` (action then entity)
   - Examples: `CONFIG_FLOW_STEP_COUNT_KIDS`, `CONFIG_FLOW_STEP_COLLECT_CHORES`, `CONFIG_FLOW_STEP_SUMMARY`
   - Used for: Defining unique step IDs in multi-step config flow

6. **`OPTIONS_FLOW_*`** - Options flow menu/action identifiers (40+ occurrences, 100% consistent)

   - Pattern: `OPTIONS_FLOW_{ACTION}_{ENTITY}` (action then entity)
   - Examples: `OPTIONS_FLOW_ADD_KID`, `OPTIONS_FLOW_EDIT_CHORE`, `OPTIONS_FLOW_DELETE_BADGE`
   - Used for: Menu items and action handlers in options flow

7. **`DEFAULT_*`** - Default values for config/options (30+ occurrences, 100% consistent)

   - Pattern: `DEFAULT_{SETTING_NAME}` (descriptive setting name)
   - Examples: `DEFAULT_POINTS_LABEL`, `DEFAULT_UPDATE_INTERVAL`, `DEFAULT_ICON`
   - Used for: Providing fallback values when user doesn't specify

8. **`LABEL_*`** - UI label constants (8+ occurrences, 100% consistent)
   - Pattern: `LABEL_{ENTITY_TYPE}` (entity type in singular)
   - Examples: `LABEL_KID`, `LABEL_CHORE`, `LABEL_BADGE`
   - Used for: Consistent UI text across components

### Critical Rules

- **Entity naming**: Use SINGULAR for `DATA_*` keys (data about one entity), PLURAL for `CFOF_*` inputs (form collecting multiple)
- **Field naming**: Use SNAKE_CASE consistently (e.g., `KID_NAME` not `KIDNAME`)
- **Error keys**: Must match input field names exactly (e.g., `CFOP_ERROR_PARENT_NAME` pairs with `CFOF_PARENTS_INPUT_NAME`)
- **Never mix patterns**: Don't create `CFPO_ERROR_*` (typo), `DATA_KIDS_*` (wrong plurality), or `CONFIG_FLOW_KIDS_*` (wrong order)

### Quality Control

All constants are validated during code review to ensure 100% pattern consistency. Use existing constants as templates when adding new ones.

---

## Debugging

- Debug logging: `logger: custom_components.kidschores: debug` in `configuration.yaml`
- Storage: `.storage/kidschores_data` (JSON with `internal_id` keys)
- Entity registry: `.storage/core.entity_registry`
- Services: Developer Tools → Services to test
- Coordinator: Check `last_update_success` property
