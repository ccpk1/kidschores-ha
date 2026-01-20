# 📘 Development Standards & Coding Guidelines

**Purpose**: Prescriptive standards for how we code, organize, and maintain the KidsChores codebase.

**Audience**: All developers writing code for KidsChores.

**Contents**: Git workflows, naming conventions, coding patterns, entity standards, error handling.

**See Also**:

- [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md) – How we measure and track quality compliance
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) – Code review process and Phase 0 audit framework
- [ARCHITECTURE.md](ARCHITECTURE.md) – Data model and integration architecture

---

## 🏛️ KidsChores Repository Standards

### 1. Git & Workflow Standards

To maintain a clean history and stable environment use a **Traffic Controller** workflow.

- **Branching Strategy**: Use feature branches for all development.
- **The L10n-Staging Bridge**: All feature branches must be merged into `l10n-staging` to trigger translation syncs. Note l10n is shorthand for localization / translations.
- **Sync Protocol**: Regularly merge `l10n-staging` back into your active feature branches to receive the latest translations from Crowdin.
- **Commit Style**: Use **Conventional Commits** (e.g., `feat:`, `fix:`, `refactor:`, `chore(l10n):`) to ensure a readable, professional history.

---

### 2. Localization & Translation Standards

We strictly separate English "source" files from "localized" output to avoid manual editing conflicts.

- **Master Files**: Only the English master files (`en.json`, `en_notifications.json`, `en_dashboard.json`) are edited in the repository.
- **Crowdin-Managed**: All non-English files are read-only and sourced exclusively via the Crowdin GitHub Action.
- **Standard Integration Translations** (`en.json`): Must strictly nest under Home Assistant-approved keys (e.g., `exceptions`, `issues`, `entity`) for core integration features.
- **Custom Translations** (`translations_custom/`): Flexible files (`en_notifications.json`, `en_dashboard.json`) for dashboards and notifications. These mimic the HA JSON structure but handle features not natively supported by Home Assistant.
- **Template Pattern**: Use the **Template Translation System** for errors to reduce redundant work.
- **Logic**: Use one template (e.g., `not_authorized_action`) and pass the specific action as a placeholder (e.g., `approve_chores`).

---

### 3. Constant Naming Standards

With over 1,000 constants, we follow strict naming patterns to ensure the code remains self-documenting.

#### Primary Prefix Patterns

| Prefix               | Plurality    | Usage                               | Example                           |
| -------------------- | ------------ | ----------------------------------- | --------------------------------- |
| `DATA_*`             | **Singular** | Storage keys for specific entities  | `DATA_KID_NAME`                   |
| `CFOF_*`             | **Plural**   | Config/Options flow input fields    | `CFOF_KIDS_INPUT_NAME`            |
| `CONF_*`             | **N/A**      | Config entry data access only       | `CONF_POINTS_LABEL`               |
| `CFOP_ERROR_*`       | **Singular** | Flow validation error keys          | `CFOP_ERROR_KID_NAME`             |
| `TRANS_KEY_*`        | **N/A**      | Stable identifiers for translations | `TRANS_KEY_CFOF_DUPLICATE_KID`    |
| `CONFIG_FLOW_STEP_*` | **Action**   | Config flow step identifiers        | `CONFIG_FLOW_STEP_COLLECT_CHORES` |
| `OPTIONS_FLOW_*`     | **Action**   | Options flow identifiers            | `OPTIONS_FLOW_STEP_EDIT_CHORE`    |
| `DEFAULT_*`          | **N/A**      | Default configuration values        | `DEFAULT_POINTS_LABEL`            |
| `LABEL_*`            | **N/A**      | Consistent UI text labels           | `LABEL_CHORE`                     |

#### Storage-Only Architecture (v0.5.0+ Data Schema v42+)

**Critical Distinction**: Since moving to storage-only mode, constants have specific usage contexts:

**`DATA_*`** = **Internal Storage Keys**

- **Usage**: Accessing/modifying `.storage/kidschores_data`
- **Context**: `coordinator._data[const.DATA_KIDS][kid_id][const.DATA_KID_NAME]`
- **Rule**: Always singular entity names (`DATA_KID_*`, `DATA_PARENT_*`)

**`CFOF_*`** = **Config/Options Flow Input Fields**

- **Usage**: Form field names in schema definitions during user input
- **Context**: `vol.Required(const.CFOF_KIDS_INPUT_KID_NAME, ...)`
- **Rule**: Always plural entity names with `_INPUT_` (`CFOF_KIDS_INPUT_*`, `CFOF_PARENTS_INPUT_*`)

**`CONF_*`** = **Configuration Entry Data Access**

- **Usage**: ONLY for accessing the 9 system settings in `config_entry.options`
- **Context**: `config_entry.options[const.CONF_POINTS_LABEL]`
- **Scope**: System-wide settings (points theme, update intervals, retention periods)
- **Rule**: Never use in flow schemas - those should use `CFOF_*`

**Common Anti-Pattern** ❌:

```python
# WRONG: Using CONF_ in flow schema
vol.Required(const.CONF_PARENT_NAME, default=name): str

# CORRECT: Use CFOF_ for flow input fields
vol.Required(const.CFOF_PARENTS_INPUT_NAME, default=name): str
```

#### Entity State & Actions

- **`ATTR_*`**: Entity state attributes (100+ constants). e.g., `ATTR_KID_NAME`, `ATTR_CHORE_POINTS`.
- **`SERVICE_*`**: Service action names. e.g., `SERVICE_CLAIM_CHORE`.

#### Specialized Logic Patterns

- **`CHORE_STATE_*`**: Lifecycle states for chores (e.g., `CHORE_STATE_CLAIMED`, `CHORE_STATE_OVERDUE`).
- **`BADGE_*`**: Constants for badge logic, including `BADGE_TYPE_*`, `BADGE_STATE_*`, and `BADGE_RESET_SCHEDULE_*`.
- **`FREQUENCY_*`**: Recurrence options (e.g., `FREQUENCY_DAILY`, `FREQUENCY_CUSTOM`).
- **`PERIOD_*`**: Time period definitions (e.g., `PERIOD_DAY_END`, `PERIOD_ALL_TIME`).
- **`POINTS_SOURCE_*`**: Tracks point origins (e.g., `POINTS_SOURCE_CHORES`, `POINTS_SOURCE_BADGES`).
- **`ACTION_*`**: Notification action button titles.
- **`AWARD_ITEMS_*`**: Badge award composition (e.g., `AWARD_ITEMS_KEY_POINTS`).

#### Entity ID Generation (Dual-Variant System)

All entity platforms MUST provide both human-readable (`*_EID_*`) and machine-readable (`*_UID_*`) variants:

- **Sensors**: `SENSOR_KC_EID_*` / `SENSOR_KC_UID_*` (e.g., `kc_sarah_points` vs `kc_{uuid}_points`)
- **Buttons**: `BUTTON_KC_EID_*` / `BUTTON_KC_UID_*` (e.g., `kc_sarah_claim_chore` vs `kc_{uuid}_claim`)
- **Selects**: `SELECT_KC_EID_*` / `SELECT_KC_UID_*` (e.g., `kc_sarah_chore_list` vs `kc_{uuid}_chore_select`)
- **Calendars**: `CALENDAR_KC_*` (Standardized prefixes/suffixes)

#### Lifecycle Suffixes (Constant Management)

**`_DEPRECATED`** = **Active Production Code Pending Refactor**

- **Usage**: Constants actively used in production but planned for replacement in future versions
- **Code Impact**: Removing these WOULD break existing installations without migration
- **Organization**: Defined in dedicated section at bottom of `const.py` (lines 2935+)
- **Deletion**: Only after feature is refactored AND migration path implemented
- **Current Status**: None in use (all previous deprecations completed)

**`_LEGACY`** = **Migration Support Only**

- **Usage**: One-time data conversion during version upgrades (e.g., KC 3.x→4.x config migration)
- **Code Impact**: After migration completes, these keys NO LONGER EXIST in active storage
- **Organization**: Defined in dedicated section at bottom of `const.py` after `_DEPRECATED` section
- **Deletion**: Remove when migration support dropped (typically 2+ major versions, <1% users)

---

### 4. DateTime & Scheduling Standards

#### Always Use dt\_\* Helper Functions

**Required**: All date/time operations MUST use the `dt_*` helper functions from `kc_helpers.py`. Direct use of Python's `datetime` module is forbidden.

**Why**: Ensures consistent timezone handling (UTC-aware, local-aware), DST safety, and testability across the codebase.

**Available DateTime Functions (dt\_\* prefix)**:

| Function                        | Purpose                                           |
| ------------------------------- | ------------------------------------------------- |
| `dt_today_local()`              | Today's date in local timezone                    |
| `dt_today_iso()`                | Today's date as ISO string                        |
| `dt_now_local()`                | Current time in local timezone                    |
| `dt_now_iso()`                  | Current time as ISO string                        |
| `dt_to_utc(dt)`                 | Convert to UTC-aware datetime                     |
| `dt_parse(value)`               | Parse ISO datetime string                         |
| `dt_add_interval(dt, interval)` | DST-safe interval arithmetic                      |
| `dt_next_schedule(config)`      | Calculate next recurrence (uses RecurrenceEngine) |
| `dt_parse_date(value)`          | Parse date string                                 |
| `dt_format_short(dt)`           | Format for display                                |
| `dt_format(dt, fmt)`            | Custom format                                     |

**Anti-Pattern** ❌:

```python
today = datetime.now().date()
next_time = datetime.now() + timedelta(days=1)
```

**Correct Pattern** ✅:

```python
from custom_components.kidschores.kc_helpers import dt_today_local, dt_add_interval
today = dt_today_local()
next_time = dt_add_interval(dt_now_local(), {"interval": 1, "interval_unit": "day"})
```

#### RecurrenceEngine for Schedule Calculations

For chore/badge recurrence calculations, use `RecurrenceEngine` class instead of manual date arithmetic:

```python
from custom_components.kidschores.schedule_engine import RecurrenceEngine
from custom_components.kidschores.type_defs import ScheduleConfig

config: ScheduleConfig = {
    "frequency": "WEEKLY",
    "interval": 2,
    "interval_unit": "week",
    "base_date": "2026-01-19T00:00:00+00:00",
    "applicable_days": [0, 1, 2, 3, 4],
}
engine = RecurrenceEngine(config)
occurrences = engine.get_occurrences(start, end, limit=100)
rrule_str = engine.to_rrule_string()  # For iCal export
```

**Benefits**: Unified logic, RFC 5545 RRULE generation, edge case handling (monthly clamping, leap years, DST).

---

### 5. Code Quality & Performance Standards

These standards ensure we maintain Silver quality compliance. See [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md) for compliance tracking and Home Assistant alignment.

- **No Hardcoded Strings**: All user-facing text (errors, logs, UI) **must** use constants and translation keys.
- **Lazy Logging**: Never use f-strings in logging. Use lazy formatting (`_LOGGER.info("Message: %s", variable)`) for performance.
- **Type Hinting**: 100% type hint coverage for all function arguments and return types.
  - **TypedDict for static structures**: Entity definitions, config objects with fixed schemas
  - **dict[str, Any] for dynamic structures**: Runtime-built aggregations, variable key access patterns
  - See Section 5.1 (Type System) below for details
- **Docstrings**: All public functions, methods, and classes MUST have docstrings.
  - Module docstrings: Describe purpose and list entity types/count by scope.
  - Class docstrings: Explain entity purpose and when it updates.
  - Method docstrings: Brief description of what it does (especially for complex logic).
- **Entity Lookup Pattern**: Always use the `get_*_id_or_raise()` helper functions in `kc_helpers.py` for service handlers to eliminate code duplication.
- **Coordinator Persistence**: All entity modifications must follow the **Modify → Persist (`_persist()`) → Notify (`async_update_listeners()`)** pattern.
- **Header Documentation**: Every entity file MUST include a header listing total count, categorized list (Kid-Specific vs System-Level), and legacy imports with clear numbering.
- **Test Coverage**: All new code must maintain 95%+ test coverage. See Section 7 for validation commands.

#### 5.1 Type System

**File**: [type_defs.py](../custom_components/kidschores/type_defs.py)

KidsChores uses a **hybrid typing strategy** that matches types to actual code patterns:

**Use TypedDict When**:

- ✅ Structure has fixed keys known at design time
- ✅ Keys are always accessed with literal strings
- ✅ IDE autocomplete and type safety are valuable

```python
class ChoreData(TypedDict):
    """Entity with fixed schema."""
    internal_id: str
    name: str
    state: str
    default_points: float
```

**Use dict[str, Any] When**:

- ✅ Keys are determined at runtime
- ✅ Code accesses structure with variable keys
- ✅ Structure is built dynamically from aggregations
- ✅ Enables smart, efficient code patterns that type checkers can't fully understand

```python
# ❌ WRONG: TypedDict with dynamic access
class StatsEntry(TypedDict):
    approved: int
    claimed: int

# Later in code:
field_name = "approved" if cond else "claimed"
stats[field_name] += 1  # ❌ mypy error: variable key not allowed

# ✅ CORRECT: dict[str, Any] for dynamic access
StatsEntry = dict[str, Any]
"""Aggregated stats with dynamic keys."""

# Later in code:
field_name = "approved" if cond else "claimed"
stats[field_name] += 1  # ✅ Works as intended
```

**Why This Matters**:

- Using TypedDict for dynamic structures requires 100+ `# type: ignore` suppressions
- Those suppressions disable type checking where it's most needed
- Being honest about structure type enables mypy to catch real bugs
- **Variable-based key access is idiomatic, efficient Python**—type checkers flag it because they can't infer runtime key values, not because the code is wrong
- Type suppressions are **IDE-level hints only**: they don't affect runtime performance or indicate code quality issues

**Acceptable Suppressions** (when TypedDict storage contracts differ from intermediate values):

```python
# Hybrid types: date objects converted to ISO strings before storage
progress.update({
    "maintenance_end_date": next_end  # next_end: str | date | None
})  # pyright: ignore[reportArgumentType]

# Dynamic field resets in loops
for field, default in reset_fields:
    progress[field] = default  # type: ignore[literal-required]
```

**Current Type Breakdown** (`type_defs.py`):

- **TypedDict**: 18 entity/config classes (ParentData, ChoreData, BadgeData, etc.)
- **dict[str, Any]**: 6 dynamic structures (KidChoreDataEntry, KidChoreStats, etc.)
- **Total**: 24 type definitions + 9 collection aliases

See [ARCHITECTURE.md](ARCHITECTURE.md#type-system-architecture) for architectural rationale.

---

### 6. Entity Standards

We enforce strict naming patterns for both **Entity IDs** (runtime identifiers) and **Class Names** (codebase structure) to ensure persistence, readability, and immediate scope identification.

#### Entity ID Construction (Dual-Variant System)

Entities must support two identifiers to balance human readability with registry persistence:

1.  **UNIQUE_ID** (`unique_id`): Internal, stable registry identifier.
    - **Format**: `entry_id + [_kid_id] + [_entity_id] + SUFFIX` (e.g., `..._kid123_points`)
    - **Why Required**: Ensures history and settings persist even if users rename kids or chores.
2.  **ENTITY_ID** (`entity_id`): User-visible UI identifier.
    - **Format**: `domain.kc_[name] + [MIDFIX] + [name2] + [SUFFIX]` (e.g., `sensor.kc_sarah_points`)
    - **Why Required**: Provides descriptive, readable IDs for automations and dashboards.

**Pattern Components**:

- **SUFFIX** (`_points`): Appended to end. Used in both UID and EID. Defined in `const.py`.
- **MIDFIX** (`_chore_claim_`): Embedded between names (EID only) for semantic clarity in multi-part entities.

#### Entity Class Naming

All classes must follow the `[Scope][Entity][Property]EntityType` pattern (e.g., `KidPointsSensor`, `ParentChoreApproveButton`).

**1. Scope (Required)**
Indicates data ownership and initiation source. **Rule**: No blank scopes allowed.

- **`Kid`**: Per-kid data/actions initiated by the kid (e.g., `KidChoreClaimButton`).
- **`Parent`**: Per-kid actions initiated by a parent (e.g., `ParentChoreApproveButton`).
- **`System`**: Global aggregates shared across all kids (e.g., `SystemChoresPendingApprovalSensor`).

**2. Entity & Property**

- **Entity**: The subject (`Chore`, `Badge`, `Points`). Use **Plural** for collections (`SystemChores...`), **Singular** for items (`KidChore...`).
- **Property**: The aspect (`Status`, `Approvals`, `Claim`). **Rule**: Property must follow Entity (`KidBadgeHighest`, never `KidHighestBadge`).

**3. Platform Consistency**
This pattern applies to **all** platforms.

- **Sensor**: `KidPointsSensor` (State: Balance)
- **Button**: `KidChoreClaimButton` (Action: Claim)
- **Select**: `SystemRewardsSelect` (List: All Shared Rewards)
- **Calendar**: `KidScheduleCalendar` (View: Kid's timeline)

---

### 7. Error Handling Standards

We strictly enforce Home Assistant's exception handling patterns to ensure errors are translatable, actionable, and properly categorized.

- **Translation Keys Required**: All exceptions MUST use `translation_key` and `translation_placeholders`. **Never** raise exceptions with hardcoded strings.
- **Specific Exception Types**:
  - `ServiceValidationError`: For invalid user input (e.g., entity not found, invalid date).
  - `HomeAssistantError`: For system/runtime failures (e.g., API error, calculation failure).
  - `UpdateFailed`: Exclusive to Coordinator update failures.
  - `ConfigEntryAuthFailed`: For authentication expiration/invalid credentials.
- **Exception Chaining**: Always use `from err` when re-raising to preserve stack traces.
- **Input Validation**: Validate inputs _before_ processing action logic. Use `get_*_or_raise` helpers.

#### Correct Pattern (Gold Standard)

```python
try:
    kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Approve Chore")
except ValueError as err:
    # ✅ Specific exception, translation key, and chaining
    raise ServiceValidationError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_INVALID_INPUT,
        translation_placeholders={"details": str(err)}
    ) from err
```

#### Wrong Pattern (Do Not Use)

```python
# ❌ Hardcoded string, undefined exception type, no chaining
if not kid_id:
    raise Exception(f"Kid {kid_name} not found!")
```

---

### 8. Development Workflow & Quality Validation

Before committing code changes, validate they meet quality standards using these mandatory commands:

#### Linting Check (9.5+/10 Required)

```bash
./utils/quick_lint.sh --fix  # Auto-fix formatting, verify no critical errors
```

- Catches unused imports, format violations, and code quality issues
- Must pass before marking work complete

#### Type Checking (100% Coverage) - ENFORCED IN CI/CD

MyPy type checking is now **mandatory** and runs automatically in `quick_lint.sh`.

```bash
mypy custom_components/kidschores/  # Verify all type hints are correct
```

**Current Strictness**: Silver-level compliance (as of January 2026)

- `strict_optional = true` - No implicit None types
- `check_untyped_defs = true` - All function signatures must be typed
- `python_version = 3.12` - Modern Python syntax required

**Requirements**:

- All functions MUST have complete type hints (args + return)
- Zero mypy errors required for code to pass CI/CD
- Use Python 3.10+ syntax (`str | None` not `Optional[str]`)
- Use modern collections (`dict[str, Any]` not `Dict[str, Any]`)

**Common Type Fixes**:

- Import from `collections.abc`: Use `Callable`, `Mapping`, `Sequence`
- Use `from __future__ import annotations` for forward references
- Replace `Optional[X]` with `X | None`
- Use `Any` sparingly (only when truly dynamic)

**Configuration**: See `pyproject.toml` for complete MyPy settings

#### Full Test Suite (All Tests Must Pass)

```bash
python -m pytest tests/ -v --tb=line  # Run complete test suite
```

- Validates all business logic, platforms, and integrations
- Detects regressions in existing features
- Must pass before work is considered complete

#### Comprehensive Validation (Do Not Skip)

**Work is NOT complete until ALL THREE pass**:

1. Linting passes (`./utils/quick_lint.sh --fix`)
2. Tests pass (`python -m pytest tests/ -v --tb=line`)
3. All errors fixed (lint errors, test failures)

**For Detailed Guidance**:

- **Test Validation & Debugging**: See [AGENT_TESTING_USAGE_GUIDE.md](../tests/AGENT_TESTING_USAGE_GUIDE.md)
  - Which tests to run for specific changes
  - Debugging failing tests
  - Module-level suppressions for test files

- **Creating New Tests**: See [AGENT_TEST_CREATION_INSTRUCTIONS.md](../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
  - Only needed for genuinely new functionality
  - Modern testing patterns and fixtures
  - Scenario-based test setup
