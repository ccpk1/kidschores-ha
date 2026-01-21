# Coordinator CRUD & Entity Management Refactor

# Initiative Plan: Coordinator CRUD Refactor

> **Status**: ✅ **READY FOR IMPLEMENTATION** (All decisions finalized 2026-01-21)

## Executive Summary - Builder Handoff

### What This Refactor Does

Migrate all 9 entity types from legacy CRUD patterns to modern `entity_helpers.build_X()` pattern established in Reward refactor (completed 2026-01-21). This eliminates ~47 lines of stub methods from coordinator.py, standardizes all config/options flows, and adds service-based CRUD for Chores.

### Implementation Scope (All Decisions Final)

| **Decision**         | **Answer**                                                                       | **Impact**                                                             |
| -------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Migration Module** | Keep migration_pre_v50.py unchanged, remove coordinator stubs per-entity         | Migration support preserved, coordinator cleaned incrementally         |
| **Notifications**    | "Chore Assigned" removed from wiki (✅ completed), no implementation             | Wiki corrected, scope reduced                                          |
| **Entity Order**     | Kids/Parents → Badges → Chores → Bonuses/Penalties → Achievements/Challenges     | Foundation first (field drift), modular code next, simple/complex last |
| **Services Scope**   | Chores only (Rewards ✅ done). Config+Options flow refactor for ALL entities     | 2 entity types get services, all 9 get flow standardization            |
| **Testing**          | Chore service tests + per-entity validation. Existing suite sufficient for flows | Focused testing, leverage 871+ existing tests                          |
| **Release**          | v0.5.0 (beta), no breaking changes                                               | Single coordinated release                                             |
| **Documentation**    | Not required (plan sufficient)                                                   | Builder executes directly from plan                                    |
| **Performance**      | Not required (reward refactor shows <1% impact)                                  | No validation step needed                                              |

### Execution Order (Start Here)

**Phase 1**: Kids & Parents (Foundation)

- Create `entity_helpers.build_kid()` and `build_parent()`
- Refactor config_flow.py kid/parent creation steps
- Refactor options_flow.py kid/parent edit steps
- Remove `_create_kid()`, `_update_kid()`, `_create_parent()`, `_update_parent()` stubs
- Run: `pytest tests/test_config_flow.py tests/test_options_flow.py -v`

**Phase 2**: Badges (Modular Code)

- Verify `entity_helpers.build_badge()` exists (likely needs creation)
- Refactor config/options flows for badge CRUD
- Remove `_create_badge()`, `_update_badge()` stubs
- Run: `pytest tests/test_workflow_badges.py -v`

**Phase 3**: Chores (Most Complex + Services)

- Create chore services: `kidschores.create_chore`, `kidschores.update_chore`, `kidschores.delete_chore`
- Refactor config/options flows to use `entity_helpers.build_chore()`
- Add service tests (follow reward service test pattern)
- Remove `_create_chore()`, `_update_chore()` stubs
- Run: `pytest tests/test_services_chores.py tests/test_workflow_chores.py -v`

**Phase 4**: Simple Entities (Bonuses, Penalties)

- Mirror reward pattern exactly (simplest entities)
- Refactor flows, remove stubs
- Run: `pytest tests/test_workflow_bonuses.py tests/test_workflow_penalties.py -v`

**Phase 5**: Linked Entities (Achievements, Challenges)

- Handle complex chore relationships carefully
- Verify relational integrity preserved
- Remove final stubs
- Run: `pytest tests/test_workflow_achievements.py tests/test_workflow_challenges.py -v`

**Phase 6**: Final Validation

- Run full test suite: `pytest tests/ -v`
- Run quality gates: `./utils/quick_lint.sh && mypy custom_components/kidschores/`
- Verify coordinator.py reduction: ~47 lines removed (stubs eliminated)

### Success Criteria

✅ All 9 entity types use `entity_helpers.build_X()` pattern in config/options flows
✅ All stub methods removed from coordinator.py
✅ Chore services functional with tests passing
✅ All 871+ tests passing
✅ MyPy clean (zero type errors)
✅ Coordinator ~47 lines smaller (stub removal only)

### Template Available

See "Lessons Learned from Reward Refactor" section (lines ~400-650) for complete implementation template including:

- Field mapping pattern (`_SERVICE_TO_X_FORM_MAPPING`)
- Service handler structure (create/update)
- Config/options flow refactor pattern
- Testing validation checklist
- Common pitfalls to avoid

---

## Initiative snapshot

- **Name / Code**: Coordinator CRUD Refactor (CCR-2026-001)
- **Target release / milestone**: v0.5.0 (beta)
- **Owner / driver(s)**: Development Team
- **Status**: Ready for implementation (Planning complete ✅)

## Summary & immediate steps

| Phase / Step              | Description                       | % complete | Quick notes                                                   |
| ------------------------- | --------------------------------- | ---------- | ------------------------------------------------------------- |
| Phase 1 – Kids & Parents  | Migrate to entity_helpers pattern | 100%       | ✅ Completed 2026-01-22 - ~100 lines removed from coordinator |
| Phase 2 – Badges          | Complex but modular code          | 100%       | ✅ Completed 2026-01-22 - ~26 lines removed from coordinator  |
| Phase 3 – Chores          | Most complex, most used           | 0%         | Services + config/options flow refactor                       |
| Phase 4 – Simple Entities | Bonuses, Penalties                | 0%         | Mirror reward pattern                                         |
| Phase 5 – Linked Entities | Achievements, Challenges          | 0%         | Complex relational data                                       |

1. **Key objective** – Migrate all entity types to modern `entity_helpers.build_X()` pattern. Services for Rewards (✅ done) and Chores. Config + Options flow refactor for all entities. Remove stub methods per entity as refactored.

2. **Summary of recent work** –
   - **2026-01-20**: Initial analysis identified 9× duplicated CRUD patterns
   - **2026-01-21**: **COMPREHENSIVE CODEBASE SEARCH COMPLETED** ✅
     - Verified 17/18 internal CRUD methods migration-only (moved to migration_pre_v50.py)
     - Discovered notification gap: "Chore Assigned" documented but not implemented
     - **DECISION: Remove from wiki** (completed ✅), implement in future if requested
     - All user decisions captured, plan ready for implementation
   - **2026-01-22**: **PHASE 1 COMPLETED** ✅
     - Created `entity_helpers.build_kid()` (~120 lines) and `build_parent()` (~80 lines)
     - Refactored config_flow.py: kid/parent creation uses `eh.build_kid()` / `eh.build_parent()`
     - Refactored options_flow.py: add/edit kid/parent use entity_helpers pattern
     - Shadow kid creation unified: uses `eh.build_kid(is_shadow=True, linked_parent_id=X)`
     - Removed unused `update_kid_entity()` and `update_parent_entity()` from coordinator.py
     - Fixed TypedDict `KidData` key: `is_shadow` → `is_shadow_kid` to match const value
     - All 871 tests passing, mypy clean, lint 9.8+/10
   - **2026-01-22**: **EXTENDED CLEANUP - All Kid/Parent Stubs Removed** ✅
     - Removed `_create_kid()`, `_create_parent()`, `_update_kid()`, `_update_parent()` from coordinator.py (~66 lines)
     - Migrated services.py shadow link handler to direct storage `.update()` calls
     - Migrated load_scenario_live.py test utility to direct storage writes
     - Added local `_create_kid()` method to migration_pre_v50.py (frozen, isolated from coordinator)
     - **Total coordinator reduction**: ~100 lines for kids/parents CRUD methods
     - All 871 tests passing, mypy clean, 37 shadow-related tests verified
   - **2026-01-22**: **PHASE 2 COMPLETED - Badges** ✅
     - Created `entity_helpers.build_badge()` (~420 lines) handling all 6 badge types
     - Refactored options_flow.py: `async_add_edit_badge_common()` uses `eh.build_badge()`
     - Changed options_flow from `coordinator.update_badge_entity()` to direct storage writes
     - Migrated load_scenario_live.py badge creation to direct storage writes
     - Removed `_create_badge()`, `_update_badge()`, `update_badge_entity()` from coordinator.py (~26 lines)
     - All 34 badge/options flow tests passing, mypy clean

---

## ⚠️ PHASE 3 DETAILED ANALYSIS: Chores (Most Complex Entity)

> **Date**: 2026-01-22 (Pre-implementation analysis)
> **Status**: ANALYSIS COMPLETE - Ready for decision on services scope

### Why Chores Are Different

Chores are the **most complex entity type** in KidsChores due to:

1. **Completion Criteria Modes** (3 modes, each with different behavior):
   - `SHARED` - All kids complete together, single state
   - `SHARED_FIRST` - First kid to complete wins
   - `INDEPENDENT` - Each kid has own tracking (per-kid dates, applicable days, times)

2. **Per-Kid Configuration** (INDEPENDENT mode only):
   - `per_kid_due_dates` - Each kid can have different due date
   - `per_kid_applicable_days` - Each kid can have different weekdays
   - `per_kid_daily_multi_times` - Each kid can have different time slots

3. **DAILY_MULTI Frequency** (special complexity):
   - Multiple time slots per day (e.g., "08:00,12:00,18:00")
   - Combined with INDEPENDENT = per-kid time slots
   - Requires separate "times helper" UI step

4. **Multi-Step Options Flow** (not single form):
   - Main form → Per-kid details helper (for INDEPENDENT multi-kid)
   - Main form → Daily multi times helper (for DAILY_MULTI)
   - Can chain: Main → Per-kid details → Daily multi times

5. **Update Returns Boolean** (unlike other entities):
   - `update_chore_entity()` returns `True` if assignments changed
   - Used to trigger reload only when kid entities added/removed

### Existing Code Patterns

**Data Building**: `fh.build_chores_data()` (~300 lines)

- Combines validation + data building (returns tuple `(data_dict, errors)`)
- Handles due date parsing, kid name→UUID conversion
- Builds `per_kid_due_dates` for all completion criteria types
- Complex validation: frequency/reset combos, daily_multi rules

**Coordinator Methods**:

```python
# Lines 991-998 - Simple stub (3 lines)
def _create_chore(self, chore_id: str, chore_data: dict[str, Any]) -> None:
    """Create chore (called by options_flow)."""
    self._data[DATA_CHORES][chore_id] = kh.build_default_chore_data(chore_id, chore_data)

# Lines 956-962 - Simple stub (7 lines)
def _update_chore(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
    """Update chore data. Returns False (no reload needed by stub)."""
    chore_info = self._data[DATA_CHORES][chore_id]
    for key, value in chore_data.items():
        chore_info[key] = value
    return False

# Lines 1149-1171 - Public method with business logic (~22 lines)
def update_chore_entity(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
    """Update chore entity in storage (Options Flow). Returns True if assignments changed."""
    # Validation, _update_chore call, badge recalculation, orphan cleanup
```

**Options Flow Callers** (9 total calls):

- `async_step_add_chore`: 4× `_create_chore()` (different code paths)
- `async_step_edit_chore`: 3× `update_chore_entity()`
- `async_step_edit_chore_per_kid_details`: 1× `update_chore_entity()`
- `async_step_chores_daily_multi`: 1× `update_chore_entity()`

**External Callers**:

- `load_scenario_live.py`: 1× `_create_chore()` (test utility)
- `migration_pre_v50.py`: Has own `_create_chore()` / `_update_chore()` (isolated)

### Recommended Approach: Two-Phase Chore Refactor

#### Phase 3A: Options Flow Refactor (No Services Yet)

**Goal**: Migrate options_flow.py chore handling to entity_helpers pattern

1. **Create `entity_helpers.build_chore()`**:
   - Extract field mapping from `fh.build_chores_data()`
   - Handle form input → storage format conversion
   - DO NOT include validation (keep in `fh.build_chores_data()`)
   - Handle internal_id override for edit mode

2. **Refactor options_flow.py**:
   - Replace `coordinator._create_chore()` → direct storage write
   - Replace `coordinator.update_chore_entity()` → direct storage write + business logic inline
   - Keep complex multi-step flow unchanged (just update data building)

3. **Remove coordinator stubs**:
   - `_create_chore()` (~3 lines)
   - `_update_chore()` (~7 lines)
   - `update_chore_entity()` (~22 lines) - Move business logic to options_flow

4. **Update `load_scenario_live.py`**:
   - Change to direct storage write (same as badges)

**Lines removed**: ~32 lines from coordinator.py
**Tests**: `pytest tests/test_options_flow_entity_crud.py tests/test_workflow_chores.py -v`

#### Phase 3B: Chore Services (Deferred - Requires Decision)

**Question**: What should chore services support?

---

### 🔴 DECISION REQUIRED: Chore Services Scope

#### Option A: No Chore CRUD Services (Recommended)

**Rationale**:

- Chore complexity is primarily UI-driven (per-kid config, multi-step helpers)
- Services would need to expose all complexity OR be severely limited
- Users already have claim/approve/disapprove services for runtime operations
- Options Flow provides complete functionality with proper validation

**Pros**:

- No new service maintenance burden
- Avoid confusion about what services can/cannot configure
- Focus on fixing entity_helpers pattern first

**Cons**:

- Can't create chores via automation (edge case use)
- Inconsistent with reward services

#### Option B: Simplified Chore Services (Create/Update/Delete with Limitations)

**Scope**: Services for BASIC chore management only

**Create Chore Service** (`kidschores.create_chore`):

```yaml
fields:
  name: required
  assigned_kids: required (list of names)
  points: required (no hidden defaults)
  # Optional simple fields:
  description: optional
  icon: optional
  labels: optional
  recurring_frequency: optional (NONE, DAILY, WEEKLY, MONTHLY only)
  due_date: optional
  # NOT SUPPORTED (too complex for services):
  # - completion_criteria (defaults to SHARED)
  # - DAILY_MULTI frequency
  # - per_kid_due_dates
  # - per_kid_applicable_days
  # - per_kid_daily_multi_times
  # - custom_interval / custom_interval_unit
```

**Update Chore Service** (`kidschores.update_chore`):

- Same limited fields as create
- Cannot change completion_criteria after creation
- Cannot enable INDEPENDENT mode via service

**Delete Chore Service** (`kidschores.delete_chore`):

- Simple delete by ID or name (same as rewards)

**Pros**:

- Consistent API (rewards have services, chores have services)
- Covers 80% of simple use cases
- Clear documentation on what's NOT supported

**Cons**:

- Services are incomplete (power users still need Options Flow)
- May create user confusion ("why can't I set per-kid dates?")
- Additional service testing burden

#### Option C: Full Chore Services (Maximum Complexity)

**Scope**: All chore features available via services

**NOT RECOMMENDED** because:

- Service calls with 20+ optional fields are unwieldy
- INDEPENDENT mode with per-kid config would require nested structures
- DAILY_MULTI would require separate times_config parameter
- Testing matrix would be enormous
- Documentation would be extensive

---

### Recommendation: Option A (No Chore CRUD Services) or Option B (Simplified)

**For v0.5.0**: Start with **Option A** (No chore CRUD services)

- Focus on entity_helpers pattern migration (Phase 3A)
- Existing claim/approve/disapprove services cover runtime operations
- Options Flow handles all configuration complexity

**For v0.6.0+**: Consider **Option B** (Simplified services) if users request

- Clear scope: "basic chores only via services"
- Document limitations prominently

### Phase 3 Execution Plan (Assuming Option A)

**Step 1**: Create `entity_helpers.build_chore()` (~150 lines)

- Extract from `fh.build_chores_data()` the field mapping logic
- Keep validation in flow_helpers (it returns errors dict)
- Handle both add (new UUID) and edit (existing data) modes

**Step 2**: Refactor `async_step_add_chore()` in options_flow.py

- Replace `coordinator._create_chore()` with direct storage write
- Pattern: `coordinator._data[DATA_CHORES][internal_id] = eh.build_chore(...)`

**Step 3**: Refactor `async_step_edit_chore()` in options_flow.py

- Replace `coordinator.update_chore_entity()` with:
  - Direct storage write
  - Inline assignment change detection (for reload flag)
  - Call `coordinator._recalculate_all_badges()` directly
  - Call `coordinator._remove_orphaned_kid_chore_entities()` directly

**Step 4**: Refactor helper steps (per-kid details, daily_multi)

- Update `update_chore_entity()` calls to direct storage

**Step 5**: Remove coordinator stubs

- `_create_chore()`, `_update_chore()`, `update_chore_entity()`
- Update `load_scenario_live.py` to direct storage

**Step 6**: Validation

- Run: `pytest tests/test_options_flow_entity_crud.py tests/test_workflow_chores.py -v`
- Lint + MyPy

---

### ChoreData TypedDict Reference (41 fields)

```python
class ChoreData(TypedDict):
    # Core identification (3)
    internal_id: str
    name: str
    state: str  # PENDING, CLAIMED, APPROVED, OVERDUE

    # Points and configuration (4)
    default_points: float
    approval_reset_type: str
    overdue_handling_type: str
    approval_reset_pending_claim_action: str

    # Description and display (3)
    description: str
    chore_labels: list[str]
    icon: str

    # Assignment (1)
    assigned_kids: list[str]  # List of kid UUIDs

    # Scheduling (4)
    recurring_frequency: str
    custom_interval: NotRequired[int | None]
    custom_interval_unit: NotRequired[str | None]
    daily_multi_times: NotRequired[list[str]]

    # Due dates (5)
    due_date: NotRequired[str | None]
    per_kid_due_dates: dict[str, str | None]
    applicable_days: list[str]
    per_kid_applicable_days: NotRequired[dict[str, list[str]]]
    per_kid_daily_multi_times: NotRequired[dict[str, list[str]]]

    # Runtime tracking (5)
    last_completed: NotRequired[str | None]
    last_claimed: NotRequired[str | None]
    approval_period_start: NotRequired[str | None]
    claimed_by: NotRequired[list[str]]
    completed_by: NotRequired[list[str]]

    # Notifications (4)
    notify_on_claim: bool
    notify_on_approval: bool
    notify_on_disapproval: bool
    notify_on_reminder: NotRequired[bool]

    # Calendar and features (2)
    show_on_calendar: NotRequired[bool]
    auto_approve: NotRequired[bool]

    # Completion criteria (1)
    completion_criteria: str  # SHARED, SHARED_FIRST, INDEPENDENT
```

---

3. **Next steps (immediate execution)** –
   - Start Phase 3: Chores migration (most complex + services)
   - **REVIEW Phase 3 Detailed Analysis below before starting**
   - Each entity follows 4-phase pattern: Prepare → Refactor → Cleanup → Test
   - Remove stub methods per-entity as modern pattern implemented
   - Full test suite run after all entities migrated

4. **Risks / blockers** –
   - Must maintain 100% backward compatibility (v0.5.0 beta, no breaking changes)
   - Cannot break options flow workflows during transition
   - Preserve all existing logging/debug behavior

5. **References** –
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Storage schema v42+, data model
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Naming conventions, constant usage
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) – Phase 0 audit standards
   - Coordinator analysis: Lines 421-2566 (2,145 lines of CRUD/cleanup code)

6. **Decisions & completion check**
   - **Decisions captured**:
     - **[2026-01-21] Delete operations architectural decision**: Delete methods will NOT be moved to entity_helpers (deeply coupled to coordinator: `_data`, `_persist()`, `async_update_listeners()`, entity registry, cleanup orchestration). Moving would require passing coordinator everywhere. Documented as acknowledged architectural inconsistency with create/update patterns.
     - **[2026-01-21] Modern CRUD pattern (reward example)**: Services use `entity_helpers.build_X()` + direct storage manipulation (bypasses internal `_create_*`/`_update_*` layer). Other entity types still use legacy internal method delegation. **Goal**: Migrate ALL entity types to modern pattern during this refactor.
     - **[2026-01-21] Migration method cleanup**: Internal `_create_*`/`_update_*` stub methods in coordinator.py removed per-entity-type as modern service pattern implemented. Migration-only versions remain in migration_pre_v50.py for pre-v50 upgrade compatibility.
     - **[2026-01-21] Notification gap resolution**: "Chore Assigned" notification documented in wiki but not implemented. Decision: Remove from wiki documentation, implement in future release if requested by users.
     - **[2026-01-21] Entity migration scope**: Kids, Parents, Chores, Badges, Rewards (done), Bonuses, Penalties, Achievements, Challenges. Services created for Rewards (done) and Chores only. All entities get config flow + options flow refactor to use entity_helpers pattern.
     - **[2026-01-21] Testing strategy**: Add service tests for chores only. Existing config/options flow tests sufficient. Run entity-specific tests per refactor, full suite at end.
     - **[2026-01-21] Release target**: All work targeted for v0.5.0 (beta). No breaking changes.
     - Use decorator pattern for schema validation (non-breaking)
     - Keep existing public API signatures (`update_*_entity`, `delete_*_entity`)
     - Defer soft-delete/undo to future release (requires storage schema change)
   - **Completion confirmation**: `[ ]` All follow-up items completed (stub removal, config/options flow updates) before requesting owner approval to mark initiative done.

> **Important:** This plan focuses on code consolidation and performance. Shadow kid deletion complexity was explicitly excluded per user request (unlink/relink is sufficient).

## Tracking expectations

- **Summary upkeep**: Update summary table percentages after each phase milestone. Reference commit SHAs for completed steps.
- **Detailed tracking**: Use phase sections below for granular progress. Do not pollute summary with implementation details.

---

## Lessons Learned from Reward Refactor (Modern Pattern Template)

**Date**: 2026-01-21
**Refactored Entity**: Rewards
**Result**: Successfully migrated from legacy `_create_*`/`_update_*` delegation to modern `entity_helpers.build_X()` direct pattern

### Quick Summary (TL;DR)

**What changed**:

- ✅ Services now use `entity_helpers.build_reward()` + direct storage writes
- ✅ Removed internal `_create_reward()` and `_update_reward()` methods (migration-only)
- ✅ Reuse validation from Options Flow (`fh.validate_rewards_inputs()`)
- ✅ Kept `delete_reward_entity()` as public coordinator method (can't be moved)
- ✅ Verified NO notifications needed for create/update (only for approve/disapprove state changes)

**Lines impacted**:

- services.py: Refactored 3 service handlers (~120 lines)
- coordinator.py: Removed 2 internal methods (~50 lines)
- migration_pre_v50.py: Kept legacy methods unchanged (frozen module)

**Time to complete**: ~2 hours (research, implementation, testing, documentation)

**Next entities to migrate**:

1. Kids & Parents (field drift issues, foundational)
2. Badges (complex but code already modular)
3. Chores (most complex, most used, code already modular)
4. Bonuses/Penalties (simple, mirror rewards)
5. Achievements/Challenges (complex linked data, defer to later in sequence)

### What We Did (Step-by-Step)

#### 1. Service Layer Refactor

**Before** (Legacy Pattern):

```python
# services.py - Old pattern (other entities still use this)
async def handle_create_chore(call: ServiceCall):
    # Build data dict manually
    chore_data = {
        DATA_CHORE_NAME: call.data[FIELD_CHORE_NAME],
        DATA_CHORE_POINTS: call.data[FIELD_POINTS],
        # ... 15+ fields manually mapped
    }
    # Call internal coordinator method
    coordinator._create_chore(chore_id, chore_data)
    coordinator._persist()
```

**After** (Modern Pattern):

```python
# services.py - New pattern (rewards use this)
from . import entity_helpers as eh

async def handle_create_reward(call: ServiceCall):
    # Map service fields to form fields (DRY - reuses Options Flow mapping)
    form_input = _map_service_to_form_input(
        dict(call.data), _SERVICE_TO_REWARD_FORM_MAPPING
    )

    # Validate using existing flow_helpers (Layer 2 validation)
    errors = fh.validate_rewards_inputs(form_input, coordinator.rewards_data)
    if errors:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key=errors[0])

    # Build entity using entity_helpers (handles defaults, conversions, UUID generation)
    reward_dict = eh.build_reward(form_input)
    internal_id = reward_dict[DATA_REWARD_INTERNAL_ID]

    # Direct storage write (no internal method)
    coordinator._data[DATA_REWARDS][internal_id] = dict(reward_dict)
    coordinator._persist()
    coordinator.async_update_listeners()
```

**Key Changes**:

- ✅ Reuse `_map_service_to_form_input()` mapping (DRY)
- ✅ Reuse `fh.validate_rewards_inputs()` (same validation as Options Flow)
- ✅ Use `eh.build_reward()` for data structure creation (consistency)
- ✅ Direct storage manipulation (no internal `_create_reward()` needed)
- ✅ No migration logic in active code path (notifications were migration-only)

#### 2. Coordinator Method Cleanup

**Removed Methods**:

- ❌ `_create_reward()` - Was only called from migration_pre_v50.py
- ❌ `_update_reward()` - Was only called from migration_pre_v50.py
- ✅ **Kept** `delete_reward_entity()` - Public API method (coordinator-coupled, can't move to helpers)

**Result**: Coordinator reduced by ~50 lines for reward CRUD (just delete method remains)

#### 3. Migration Handling

**Pattern**: Migration-only methods stay in migration_pre_v50.py:

```python
# migration_pre_v50.py (frozen, not actively developed)
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]) -> None:
    """Legacy reward creation with notifications (migration-only)."""
    # Full notification logic for pre-v50 upgrades
    self._data[DATA_REWARDS][reward_id] = reward_data

    # Notify assigned kids (legacy behavior preserved)
    for kid_id in reward_data.get(DATA_REWARD_ASSIGNED_KIDS, []):
        await self._notify_kid(kid_id, title="New Reward", message=f"...")
```

**When to Remove**: Can delete entire migration_pre_v50.py module when user base is 100% on v0.5.0+ (target: v0.7.0 or later)

### Critical Findings

#### ❗ Notification Discovery - **CRITICAL GAP FOUND**

**Issue**: User questioned whether entity creation/assignment should trigger kid notifications per wiki documentation.

**Wiki Documentation Claims** ([Configuration:-Notifications.md](../../kidschores-ha.wiki/Configuration:-Notifications.md)):

- **"Chore Assigned"** - Trigger: "Chore assigned to kid via options flow" → Recipients: Kid
- Translation keys exist: `TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED` and `TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED`
- Translation content: `"New chore {chore_name} was assigned to you! Due: {due_date}"`

**Code Reality Check**:

1. **Migration methods**: migration_pre_v50.py contains NO calls to these notification keys
2. **Options Flow**: options_flow.py contains NO notification calls for chore assignment
3. **Services**: NO calls to chore assignment notifications
4. **Result**: Translation keys defined in const.py and translations JSON but **NEVER CALLED**

**Status**:

- ❌ **MISSING FEATURE** - Wiki documents "Chore Assigned" notification that doesn't exist in code
- ⚠️ **Documentation/Code Mismatch** - Users expect notification per wiki, but code doesn't implement it
- ❓ **Intent Unknown** - Was this feature planned but not implemented? Or removed and wiki not updated?

**Current Active Notifications**:

- ✅ **Chore Claimed** - Kid claims → Parents notified (implemented)
- ✅ **Chore Approved** - Parent approves → Kid notified (implemented)
- ✅ **Chore Disapproved** - Parent disapproves → Kid notified (implemented)
- ✅ **Chore Overdue** - Past due date → Kid + Parents notified (implemented)
- ✅ **Chore Due Soon** - Due within window → Kid notified (implemented)
- ✅ **Badge Earned** - Badge completed → Kid + Parents notified (implemented)
- ✅ **Penalty/Bonus Applied** - Points changed → Kid notified (implemented)
- ✅ **Achievement/Challenge Completed** - Milestone reached → Kid + Parents notified (implemented)

**Decision Made [2026-01-21]**: **Option 2 - Remove from documentation**

- Update wiki Configuration:-Notifications.md to remove "Chore Assigned" entry
- Document as potential future enhancement if users request
- No implementation work during this refactor

**Rationale**: Parent creates/assigns chores via UI, already aware of action. Assignment notifications add complexity without clear user value. Can revisit if users request feature.

**Implementation removed from scope**. Original recommendation was:

- Add notification call after successful assignment
- Pattern: `await coordinator._notify_kid_translated(kid_id, TRANS_KEY_NOTIF_TITLE_X_ASSIGNED, TRANS_KEY_NOTIF_MESSAGE_X_ASSIGNED, {...})`
- Only notify on NEW assignments (not edits that don't change assigned kids)
- Check similar gaps for badges/rewards/achievements

**No action required during this refactor**. Translation keys remain in codebase for potential future use.

**Removed from current scope per user decision [2026-01-21]**.

#### ✅ Delete Methods Stay in Coordinator

**Rationale**: Delete operations are coordinator-coupled:

- Require `self._data` access (storage)
- Require `self._persist()` call (persistence)
- Require `self.async_update_listeners()` (HA integration)
- Require `self._remove_entities_in_ha()` (entity registry cleanup)
- Require cleanup method calls (`_cleanup_pending_reward_approvals()`, etc.)

**Pattern**: Delete is a public API method that orchestrates multiple coordinator operations:

```python
def delete_reward_entity(self, reward_id: str) -> None:
    """Delete reward from storage and cleanup references."""
    # Validate
    if reward_id not in self._data.get(DATA_REWARDS, {}):
        raise HomeAssistantError(...)

    # Delete from storage
    del self._data[DATA_REWARDS][reward_id]

    # Cleanup entity registry
    self._remove_entities_in_ha(reward_id)

    # Cleanup relational data
    self._cleanup_pending_reward_approvals()

    # Persist
    self._persist()
    self.async_update_listeners()
```

**Decision**: All delete methods stay in coordinator. Only create/update migrate to entity_helpers pattern.

### Migration Checklist (Apply to Each Entity Type)

Use this checklist when migrating other entity types (chores, badges, bonuses, penalties, achievements, challenges) to modern pattern:

#### Phase 1: Preparation

- [ ] **Verify entity_helpers.build_X() exists** for entity type
  - If not, create following `build_reward()` pattern
  - Handles: defaults, type conversions, UUID generation, validation (Layer 1)
- [ ] **Identify all service callers** using grep:
  ```bash
  grep -rn "handle_create_X\|handle_update_X" custom_components/kidschores/services.py
  ```
- [ ] **Verify config_flow.py usage** - Check if entity type used in initial setup wizard:
  ```bash
  grep -rn "build_X_data" custom_components/kidschores/config_flow.py
  ```

#### Phase 2: Service Refactor

- [ ] **Create field mapping** (service fields → form fields):
  ```python
  _SERVICE_TO_X_FORM_MAPPING = {
      FIELD_NAME: CFOF_X_INPUT_NAME,
      FIELD_POINTS: CFOF_X_INPUT_POINTS,
      # ... map all service fields
  }
  ```
- [ ] **Update create service**:
  ```python
  form_input = _map_service_to_form_input(dict(call.data), _SERVICE_TO_X_FORM_MAPPING)
  errors = fh.validate_X_inputs(form_input, coordinator.X_data)
  if errors: raise HomeAssistantError(...)
  entity_dict = eh.build_X(form_input)
  coordinator._data[DATA_X][internal_id] = dict(entity_dict)
  coordinator._persist()
  coordinator.async_update_listeners()
  ```
- [ ] **Update update service** (similar pattern with `existing=` parameter):
  ```python
  existing_entity = coordinator.X_data[entity_id]
  form_input = _map_service_to_form_input(...)
  entity_dict = eh.build_X(form_input, existing=existing_entity)
  coordinator._data[DATA_X][entity_id] = dict(entity_dict)
  coordinator._persist()
  coordinator.async_update_listeners()
  ```
- [ ] **Update config_flow.py** if entity type used in initial setup:
  - Replace `build_X_data()` call with `entity_helpers.build_X()` pattern
  - Match options_flow pattern for consistency
- [ ] **Update options_flow.py** create/edit steps:
  - Use `entity_helpers.build_X()` instead of direct storage writes
  - Reuse field mappings for DRY
- [ ] **Verify delete service** uses `coordinator.delete_X_entity()` (no changes needed)

#### Phase 3: Coordinator Cleanup

- [ ] **Remove internal methods** if migration-only:
  - [ ] `_create_X()` - Check callers via grep first
  - [ ] `_update_X()` - Check callers via grep first
- [ ] **Keep public methods** (coordinator-coupled):
  - [ ] `update_X_entity()` - If it wraps internal method, refactor to direct storage
  - [ ] `delete_X_entity()` - Always keep (orchestrates cleanup)

#### Phase 4: Testing

- [ ] **Service calls** - Test create/update/delete via Services tab
- [ ] **Options Flow** - Verify UI create/edit still works
- [ ] **Full test suite** - Run pytest for entity type
- [ ] **Migration test** - If possible, test upgrade from pre-v50 data

#### Phase 5: Coordinator Cleanup & Documentation

- [ ] **After all entities migrated**: Consider removing migration_pre_v50.py in future release if:
  - User base is 100% on v0.5.0+
  - Migration support window has passed (e.g., 12+ months)
- [ ] **Update plan document** with completion status and lessons learned

### Common Pitfalls to Avoid

1. **❌ Don't add notifications to entity creation** - Only state transitions trigger notifications
2. **❌ Don't move delete methods to entity_helpers** - They're coordinator-coupled
3. **❌ Don't bypass validation** - Always call `fh.validate_X_inputs()` before `eh.build_X()`
4. **❌ Don't modify migration methods** - They're frozen for backwards compatibility
5. **✅ Do reuse field mappings** - Service → Form mappings are DRY
6. **✅ Do check migration callers first** - Verify method is migration-only before deleting
7. **✅ Do test both services and Options Flow** - Both code paths must work

### Performance Impact

**Metrics from Reward Refactor**:

- **Lines removed**: 50 lines (internal `_create_reward()` and `_update_reward()` methods)
- **Validation calls**: Reduced from 2 → 1 (reuse flow validation instead of duplicate logic)
- **Code paths**: Service and Options Flow now use identical data-building logic

**Projected impact when all entities refactored**:

- **Lines removed**: ~350 lines (7 entity types × ~50 lines each)
- **Coordinator size**: 6,405 lines → ~6,050 lines (5.5% reduction)
- **Consistency**: 100% of CRUD operations use same patterns

---

## Method Inventory & Refactor Analysis

**Last Updated**: 2026-01-21 (Comprehensive codebase search completed)

This section catalogs ALL CRUD and helper methods across the codebase with actual caller analysis. Each method group requires a decision on refactor approach.

### Coordinator Internal CRUD Methods (`_create_*` / `_update_*`)

These are internal methods in `coordinator.py` that directly modify storage.

| Method                  | Lines     | Callers                                                                                       | Migration Status              | Recommended Action                            | Alternative                                                         |
| ----------------------- | --------- | --------------------------------------------------------------------------------------------- | ----------------------------- | --------------------------------------------- | ------------------------------------------------------------------- |
| **Kids**                |
| `_create_kid()`         | 1038-1087 | • migration_pre_v50.py:1563<br>• options_flow.py:395<br>• coordinator.py:1265 (shadow kid)    | In use (3 callers)            | **KEEP** - Convert to helper pattern          | N/A - Required by options flow                                      |
| `_update_kid()`         | 1088-1104 | • migration_pre_v50.py:1564<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed post-v50  | Extract to migration module if only used there                      |
| **Parents**             |
| `_create_parent()`      | 1105-1160 | • migration_pre_v50.py:1568<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | May be legacy from pre-parent services era                          |
| `_update_parent()`      | 1161-1177 | • migration_pre_v50.py:1569<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | May be legacy from pre-parent services era                          |
| **Chores**              |
| `_create_chore()`       | 1359-1388 | • migration_pre_v50.py:1573<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow uses direct storage writes                             |
| `_update_chore()`       | 1389-1742 | • migration_pre_v50.py:1574<br>• **NO OTHER CALLERS** (354 lines!)                            | Migration-only                | **ANALYZE** - Complex logic, verify necessity | Contains completion criteria conversion - may be migration-specific |
| **Badges**              |
| `_create_badge()`       | 1744-1760 | • migration_pre_v50.py:1578<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| `_update_badge()`       | 1761-1777 | • migration_pre_v50.py:1579<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| **Rewards**             |
| `_create_reward()`      | 1778-1800 | • migration_pre_v50.py:1586<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Services/flows use entity_helpers.build_reward()                    |
| `_update_reward()`      | 1801-1825 | • migration_pre_v50.py:1587<br>• coordinator.py:2435 (wrapper)<br>• **wrapper has 0 callers** | Migration-only + dead wrapper | **SAFE TO REMOVE** after migration module     | Only called by unused update_reward_entity()                        |
| **Bonuses**             |
| `_create_bonus()`       | 1826-1848 | • migration_pre_v50.py:1603<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| `_update_bonus()`       | 1849-1872 | • migration_pre_v50.py:1604<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| **Penalties**           |
| `_create_penalty()`     | 1873-1895 | • migration_pre_v50.py:1594<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| `_update_penalty()`     | 1896-1919 | • migration_pre_v50.py:1595<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| **Achievements**        |
| `_create_achievement()` | 1920-1967 | • migration_pre_v50.py:1599<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| `_update_achievement()` | 1968-2019 | • migration_pre_v50.py:1600<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| **Challenges**          |
| `_create_challenge()`   | 2020-2073 | • migration_pre_v50.py:1608<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |
| `_update_challenge()`   | 2074-2127 | • migration_pre_v50.py:1609<br>• **NO OTHER CALLERS**                                         | Migration-only                | **ANALYZE** - Check if still needed           | Options flow likely uses direct storage                             |

**Key Finding**: Nearly ALL `_create_*` and `_update_*` methods are **ONLY** called from migration_pre_v50.py. This suggests the entire CRUD layer was replaced by direct storage writes in v0.5.0 refactor, but migration methods weren't updated to use the new pattern.

**Decision Required**:

1. **Extract to migration module?** Move all migration-only methods to migration_pre_v50.py
2. **Delete migration module entirely?** If user base is on v0.5.0+, remove pre-v50 migration support
3. **Keep as-is?** Maintain for backwards compatibility with very old installations

---

### Coordinator Public Entity Methods (`*_entity()`)

These are public methods in `coordinator.py` that orchestrate CRUD operations (storage + entity registry + cleanup).

| Method                        | Lines     | Callers                                                        | Usage Status                    | Recommended Action                      | Alternative                                       |
| ----------------------------- | --------- | -------------------------------------------------------------- | ------------------------------- | --------------------------------------- | ------------------------------------------------- |
| **Kids**                      |
| `update_kid_entity()`         | 2168-2197 | • options_flow.py:1251                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_kid_entity()`         | 2198-2234 | • options_flow.py:2914<br>• test_parent_shadow_kid.py:536, 681 | **ACTIVE** (1 caller + 2 tests) | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Parents**                   |
| `update_parent_entity()`      | 2262-2276 | • options_flow.py:1425                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_parent_entity()`      | 2277-2310 | • options_flow.py:2942<br>• test_parent_shadow_kid.py:590, 639 | **ACTIVE** (1 caller + 2 tests) | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Chores**                    |
| `update_chore_entity()`       | 2312-2334 | • options_flow.py:1530, 1645, 1695, 2240, 2427                 | **ACTIVE** (5 callers)          | **KEEP** - Heavily used by options flow | N/A - Core functionality                          |
| `delete_chore_entity()`       | 2335-2365 | • options_flow.py:2972                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Badges**                    |
| `update_badge_entity()`       | 2367-2386 | • options_flow.py:877                                          | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_badge_entity()`       | 2387-2422 | • options_flow.py:3002                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Rewards**                   |
| `update_reward_entity()`      | 2424-2438 | • **NO CALLERS FOUND**                                         | **DEAD CODE** ⚠️                | **SAFE TO REMOVE**                      | Replaced by entity_helpers.build_reward() pattern |
| `delete_reward_entity()`      | 2439-2467 | • services.py:1682<br>• options_flow.py:3032                   | **ACTIVE** (2 callers)          | **KEEP** - Required thin wrapper        | Could inline cleanup logic in callers             |
| **Penalties**                 |
| `update_penalty_entity()`     | 2466-2482 | • options_flow.py:2618                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_penalty_entity()`     | 2483-2508 | • options_flow.py:3062                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Bonuses**                   |
| `update_bonus_entity()`       | 2509-2523 | • options_flow.py:2667                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_bonus_entity()`       | 2524-2547 | • options_flow.py:3158                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Achievements**              |
| `update_achievement_entity()` | 2548-2564 | • options_flow.py:2726                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_achievement_entity()` | 2565-2590 | • options_flow.py:3094                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |
| **Challenges**                |
| `update_challenge_entity()`   | 2591-2607 | • options_flow.py:2868                                         | **ACTIVE** (1 caller)           | **KEEP** - Used by options flow edit    | N/A - Required API                                |
| `delete_challenge_entity()`   | 2608-2634 | • options_flow.py:3128                                         | **ACTIVE** (1 caller)           | **KEEP** - Required for deletion        | N/A - Core functionality                          |

**Critical Finding**: Only `update_reward_entity()` is **confirmed dead code** with zero callers. All other `*_entity()` methods are actively used by options_flow.py.

---

### Flow Helpers Builder Functions (`build_*_data()`)

These are in `flow_helpers.py` and construct entity data dicts from user input.

| Function                    | Lines     | Callers                                                           | Migration Status                | Recommended Action                      | Alternative                                        |
| --------------------------- | --------- | ----------------------------------------------------------------- | ------------------------------- | --------------------------------------- | -------------------------------------------------- |
| `build_points_data()`       | 155-174   | • config_flow.py:521<br>• options_flow (system settings)          | **ACTIVE** - System settings    | **KEEP** - Not entity-related           | N/A - Different pattern                            |
| `build_kids_data()`         | 472-527   | • config_flow.py:572 (setup wizard)                               | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_parents_data()`      | 682-747   | • config_flow.py:649 (setup wizard)                               | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_shadow_kid_data()`   | 808-858   | • config_flow.py:658 (parent setup)                               | **ACTIVE** - Initial setup only | **KEEP** - Specialized logic            | Shadow kids are unique pattern                     |
| `build_chores_data()`       | 1091-1407 | • config_flow.py:755 (setup wizard)                               | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_badge_common_data()` | 1409-1627 | • config_flow.py:864 (setup wizard)                               | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_rewards_data()`      | 2688-2714 | • config_flow.py:953 (setup wizard)<br>• **Deprecated in v0.5.0** | **PARTIALLY REPLACED**          | **REFACTOR config_flow** → remove after | Already delegates to entity_helpers.build_reward() |
| `build_bonuses_data()`      | 2798-2835 | • config_flow.py:1088 (setup wizard)                              | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_penalties_data()`    | 2923-2960 | • config_flow.py:1020 (setup wizard)                              | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_achievements_data()` | 2998-3100 | • config_flow.py:1151 (setup wizard)                              | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |
| `build_challenges_data()`   | 3102-3262 | • config_flow.py (setup wizard)                                   | **ACTIVE** - Initial setup only | **KEEP** - Config wizard needs it       | Options flow uses direct storage                   |

**Key Finding**: ALL `build_*_data()` functions are used by config_flow.py (initial setup wizard). These are NOT dead code. Options flow was refactored to use direct storage writes, but config_flow still uses the builder pattern.

**Decision**: Keep all builders - they serve the initial setup wizard. Only `build_rewards_data()` can be refactored to match entity_helpers pattern.

---

### Flow Helpers Schema Functions (`build_*_schema()`)

These generate UI form schemas for options flow.

| Function                             | Lines     | Status                           | Recommended Action |
| ------------------------------------ | --------- | -------------------------------- | ------------------ |
| `build_points_schema()`              | 139-153   | **KEEP** - UI presentation layer | No change needed   |
| `build_chore_schema()`               | 860-1089  | **KEEP** - Complex chore form    | No change needed   |
| `build_badge_common_schema()`        | 1970-2646 | **KEEP** - Badge type selection  | No change needed   |
| `build_reward_schema()`              | 2648-2686 | **KEEP** - Reward form UI        | No change needed   |
| `build_bonus_schema()`               | 2753-2796 | **KEEP** - Bonus form UI         | No change needed   |
| `build_penalty_schema()`             | 2874-2921 | **KEEP** - Penalty form UI       | No change needed   |
| `build_achievement_schema()`         | 3264-3386 | **KEEP** - Achievement form UI   | No change needed   |
| `build_challenge_schema()`           | 3388-3515 | **KEEP** - Challenge form UI     | No change needed   |
| `build_general_options_schema()`     | 3517-4174 | **KEEP** - System settings UI    | No change needed   |
| `build_all_system_settings_schema()` | 4176-4343 | **KEEP** - Full settings form    | No change needed   |

**All schema builders are UI presentation layer - no refactor needed.**

---

### Flow Helpers Validation Functions (`validate_*_inputs()`)

These check for duplicate names and other business rules.

| Function                         | Lines     | Status                                | Recommended Action         |
| -------------------------------- | --------- | ------------------------------------- | -------------------------- |
| `validate_points_inputs()`       | 176-190   | **KEEP** - System settings validation | No change needed           |
| `validate_kids_inputs()`         | 529-680   | **KEEP** - Uniqueness checks          | No change needed           |
| `validate_parents_inputs()`      | 749-806   | **KEEP** - Uniqueness checks          | No change needed           |
| `validate_badge_common_inputs()` | 1629-1968 | **KEEP** - Badge validation           | No change needed           |
| `validate_rewards_inputs()`      | 2716-2751 | **KEEP** - Uniqueness checks          | Used by services and flows |
| `validate_bonuses_inputs()`      | 2837-2872 | **KEEP** - Uniqueness checks          | No change needed           |
| `validate_penalties_inputs()`    | 2962-2996 | **KEEP** - Uniqueness checks          | No change needed           |

**All validators are UI-layer business rules - no refactor needed.**

---

## Summary of Critical Decisions Needed

### Decision 1: Migration Module Approach ⚠️ CRITICAL

**Question**: What to do with methods only called from migration_pre_v50.py?

**Confirmed Migration-Only Methods** (18 methods, ~800 lines):

- ALL `_create_*()` methods (9 methods) - except `_create_kid()` which has 2 other callers
- ALL `_update_*()` methods (9 methods) - except none have other callers

**Breakdown**:
| Method | Lines | Non-Migration Callers |
|--------|-------|-----------------------|
| `_create_kid()` | 1038-1087 | ✅ options_flow.py:395, coordinator.py:1265 (shadow) |
| `_update_kid()` | 1088-1104 | ❌ None - migration-only |
| `_create_parent()` | 1105-1160 | ❌ None - migration-only |
| `_update_parent()` | 1161-1177 | ❌ None - migration-only |
| `_create_chore()` | 1359-1388 | ❌ None - migration-only |
| `_update_chore()` | 1389-1742 | ❌ None - migration-only (354 lines!) |
| `_create_badge()` | 1744-1760 | ❌ None - migration-only |
| `_update_badge()` | 1761-1777 | ❌ None - migration-only |
| `_create_reward()` | 1778-1800 | ❌ None - migration-only |
| `_update_reward()` | 1801-1825 | ❌ None - migration-only |
| `_create_bonus()` | 1826-1848 | ❌ None - migration-only |
| `_update_bonus()` | 1849-1872 | ❌ None - migration-only |
| `_create_penalty()` | 1873-1895 | ❌ None - migration-only |
| `_update_penalty()` | 1896-1919 | ❌ None - migration-only |
| `_create_achievement()` | 1920-1967 | ❌ None - migration-only |
| `_update_achievement()` | 1968-2019 | ❌ None - migration-only |
| `_create_challenge()` | 2020-2073 | ❌ None - migration-only |
| `_update_challenge()` | 2074-2127 | ❌ None - migration-only |

**Options**:

1. **Extract to migration module** - Move all migration-only methods to migration_pre_v50.py (~750 lines moved)
   - **Pro**: Clearer separation, coordinator.py ~35% smaller
   - **Con**: Migration module becomes very large (2,300 + 750 = 3,050 lines)
   - **Note**: Keep `_create_kid()` in coordinator as it's used for shadow kid creation

2. **Delete migration support entirely** - Remove migration_pre_v50.py if user base is on v0.5.0+
   - **Pro**: Eliminates ~2,300 + 750 = 3,050 lines of code
   - **Con**: Breaks upgrades for installations older than v0.5.0
   - **Question**: When was KC v0.5.0 released? What % of users have upgraded?

3. **Keep as-is** - Maintain current structure for backwards compatibility
   - **Pro**: No breaking changes, safest option
   - **Con**: ~750 lines of code in coordinator.py only used during migration

**Recommendation**: **Need user input on migration support policy**. If KC v0.5.0 was released 6+ months ago and adoption is >90%, Option 2 (delete) is cleanest. Otherwise Option 1 (extract).

**Impact**: This decision affects ~35% of coordinator.py CRUD code.

---

### Decision 2: config_flow.py Reward Refactor

**Question**: Should we refactor config_flow.py to use entity_helpers.build_reward() pattern?

**Current State**:

- config_flow.py:953 still calls `build_rewards_data()`
- build_rewards_data() is deprecated (v0.5.0) but maintained as thin wrapper
- All other flows (options_flow, services) use entity_helpers directly

**Options**:

1. **Refactor now** - Update config_flow reward step to match options_flow pattern
   - **Pro**: Consistency across codebase, can delete build_rewards_data() wrapper (24 lines)
   - **Pro**: Validates entity_helpers pattern works for initial setup wizard
   - **Con**: Requires testing of setup wizard reward step
   - **Effort**: ~1 hour (update config_flow.py:945-965, test initial setup)

2. **Leave as-is** - Keep thin wrapper for config_flow
   - **Pro**: No risk to setup wizard, zero effort
   - **Con**: Inconsistent patterns (config_flow uses old pattern, everything else uses new)
   - **Con**: 24 lines of deprecated wrapper code maintained indefinitely

**Recommendation**: **Refactor now** - Initial setup wizard needs comprehensive testing anyway for parent-chores feature. This validates the entity_helpers pattern is robust enough for all use cases.

**Impact**: Can remove 24-line `build_rewards_data()` wrapper + validates unified pattern.

---

### Decision 3: Dead Entity Methods

**Question**: Remove `update_reward_entity()` and verify no other dead `*_entity()` methods?

**Confirmed Dead Code**:

- ✅ `update_reward_entity()` - Zero callers found (15 lines)

**Verified Active Methods** (ALL other `*_entity()` methods are used):

- `update_kid_entity()` - 1 caller (options_flow.py:1251)
- `delete_kid_entity()` - 1 caller + 2 tests
- `update_parent_entity()` - 1 caller (options_flow.py:1425)
- `delete_parent_entity()` - 1 caller + 2 tests
- `update_chore_entity()` - 5 callers (options_flow.py multiple locations)
- `delete_chore_entity()` - 1 caller
- `update_badge_entity()` - 1 caller
- `delete_badge_entity()` - 1 caller
- `delete_reward_entity()` - 2 callers (services.py:1682, options_flow.py:3032)
- `update_penalty_entity()` - 1 caller
- `delete_penalty_entity()` - 1 caller
- `update_bonus_entity()` - 1 caller
- `delete_bonus_entity()` - 1 caller
- `update_achievement_entity()` - 1 caller
- `delete_achievement_entity()` - 1 caller
- `update_challenge_entity()` - 1 caller
- `delete_challenge_entity()` - 1 caller

**Recommendation**: **Remove `update_reward_entity()` immediately** - It's confirmed dead code. No risk, clean deletion.

**Impact**: 15-line reduction, confirms reward CRUD is fully migrated to unified pattern.

---

## Action Items Before Phase 1

- [x] **Complete systematic grep search** for ALL `*_entity()` method callers ✅
- [x] **Verify build\_\*\_data usage** - All used by config_flow.py (setup wizard) ✅
- [x] **Catalog test usage** - test_parent_shadow_kid.py uses delete methods ✅
- [x] **Document service usage** - Only delete_reward_entity() used by services ✅
- [x] **Update analysis table** with complete caller breakdown ✅
- [x] **User decision**: Migration module approach → **EXTRACT** (v0.5.0 not released yet) ✅
- [x] **Remove dead code**: Delete `update_reward_entity()` (15 lines) ✅ **DONE**
- [x] **Refactor config_flow.py** reward step to use entity_helpers.build_reward() ✅ **DONE**
- [x] **Remove deprecated wrapper**: Delete `build_rewards_data()` (30 lines) ✅ **DONE**
- [ ] **Move migration-only methods** to migration_pre_v50.py:
  - 3 `remove_deprecated*` methods (~226 lines)
  - 17 `_create_*`/`_update_*` methods (~750 lines)
  - **Total**: ~976 lines to move
- [ ] **Document pattern** for future entity migrations (capture in DEVELOPMENT_STANDARDS.md)

---

## Detailed phase tracking

### Phase 1 – Foundation (Helpers & Validation)

**Goal**: Extract reusable patterns from duplicated CRUD code and add missing validation layer.

**Steps / detailed work items**:

1. **Create `entity_crud_helper.py` module** (Status: Not started)
   - Location: `custom_components/kidschores/entity_crud_helper.py`
   - Extract generic validation function:
     ```python
     def validate_entity_exists(
         data: dict[str, dict],
         entity_type_key: str,
         entity_id: str,
         label_key: str
     ) -> None:
         """Raise HomeAssistantError if entity not found."""
     ```
   - Extract generic entity creation logger:
     ```python
     def log_entity_operation(
         operation: str,  # "Added" | "Updated" | "Deleted"
         entity_type: str,
         entity_name: str,
         entity_id: str
     ) -> None:
         """Standardized logging for CRUD operations."""
     ```
   - Extract field update helper:
     ```python
     def update_entity_fields(
         entity_info: dict[str, Any],
         update_data: dict[str, Any],
         field_mappings: dict[str, tuple[str, Any]]  # (const_key, default_value)
     ) -> None:
         """Generic field updater with defaults."""
     ```

2. **Add schema validation decorators** (Status: Not started)
   - Create `@validate_entity_schema` decorator in `entity_crud_helper.py`
   - Define schema validators for each entity type:
     - `SCHEMA_KID_CREATE` / `SCHEMA_KID_UPDATE`
     - `SCHEMA_PARENT_CREATE` / `SCHEMA_PARENT_UPDATE`
     - `SCHEMA_CHORE_CREATE` / `SCHEMA_CHORE_UPDATE`
     - `SCHEMA_BADGE_CREATE` / `SCHEMA_BADGE_UPDATE`
     - `SCHEMA_REWARD_CREATE` / `SCHEMA_REWARD_UPDATE`
     - `SCHEMA_PENALTY_CREATE` / `SCHEMA_PENALTY_UPDATE`
     - `SCHEMA_BONUS_CREATE` / `SCHEMA_BONUS_UPDATE`
     - `SCHEMA_ACHIEVEMENT_CREATE` / `SCHEMA_ACHIEVEMENT_UPDATE`
     - `SCHEMA_CHALLENGE_CREATE` / `SCHEMA_CHALLENGE_UPDATE`
   - Apply decorators to all `_create_*` and `_update_*` methods
   - Validation should:
     - Check required fields presence
     - Validate field types (str, int, float, list, dict)
     - Reject unknown fields (strict mode)
     - Log validation failures at WARNING level

3. **Refactor `_create_kid()` as reference implementation** (Status: Not started)
   - File: `coordinator.py`, Line ~971
   - Before (current):
     ```python
     def _create_kid(self, kid_id: str, kid_data: dict[str, Any]):
         self._data[const.DATA_KIDS][kid_id] = {
             const.DATA_KID_NAME: kid_data.get(const.DATA_KID_NAME, const.SENTINEL_EMPTY),
             const.DATA_KID_POINTS: kid_data.get(const.DATA_KID_POINTS, const.DEFAULT_ZERO),
             # ... 20+ more fields
         }
         const.LOGGER.debug("DEBUG: Kid Added - '%s', ID '%s'", ...)
     ```
   - After (using helpers):
     ```python
     @validate_entity_schema(SCHEMA_KID_CREATE)
     def _create_kid(self, kid_id: str, kid_data: dict[str, Any]):
         self._data[const.DATA_KIDS][kid_id] = build_kid_data_structure(kid_data)
         log_entity_operation("Added", const.LABEL_KID, kid_data[const.DATA_KID_NAME], kid_id)
     ```

4. **Migrate remaining entity types to helpers** (Status: Not started)
   - Parents: Lines ~1038-1093 (`_create_parent`, `_update_parent`)
   - Chores: Lines ~1292-1320 (`_create_chore`) - Note: `_update_chore` is complex, keep separate
   - Badges: Lines ~1677-1709 (`_create_badge`, `_update_badge`)
   - Rewards: Lines ~1711-1756 (`_create_reward`, `_update_reward`)
   - Penalties: Lines ~1807-1852 (`_create_penalty`, `_update_penalty`)
   - Bonuses: Lines ~1759-1804 (`_create_bonus`, `_update_bonus`)
   - Achievements: Lines ~1855-1952 (`_create_achievement`, `_update_achievement`)
   - Challenges: Lines ~1955-2081 (`_create_challenge`, `_update_challenge`)

5. **Testing** (Status: Not started)
   - Run full test suite: `pytest tests/ -v`
   - Validate no regressions in existing CRUD workflows
   - Add unit tests for new helpers: `tests/test_entity_crud_helper.py`
   - Test schema validation rejection paths
   - Verify logging output unchanged (grep for "Added", "Updated" patterns)

**Key issues**:

- Risk: Schema validation could break existing options flow if schemas too strict
- Mitigation: Start with warning-only mode, promote to errors after validation
- Chore update logic (`_update_chore`) is complex due to completion criteria conversion - keep separate initially

---

### Phase 2 – Performance (Entity Registry Optimization)

**Goal**: Reduce entity registry scan overhead from O(n×m) to O(n) and cache expected entity UIDs.

**Steps / detailed work items**:

1. **Extract common entity registry removal pattern** (Status: Not started)
   - Add to `kc_helpers.py` (after Line ~1630, Device Info section):

     ```python
     async def remove_orphaned_entities_by_pattern(
         hass: HomeAssistant,
         entry_id: str,
         entity_domain: str,  # "sensor" | "button"
         suffix: str | None,
         validation_func: Callable[[str, EntityEntry], bool],
         label: str  # For logging
     ) -> int:
         """Generic orphaned entity removal by UID pattern matching.

         Returns count of removed entities.
         """
     ```

   - Replace 4× duplicated patterns:
     - `_remove_orphaned_shared_chore_sensors()` (Line 439)
     - `_remove_orphaned_achievement_entities()` (Line 536)
     - `_remove_orphaned_challenge_entities()` (Line 563)
     - `_remove_orphaned_kid_chore_entities()` (Line 461) - **Critical bottleneck**

2. **Optimize `_remove_orphaned_kid_chore_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 461-534
   - Current complexity: O(entities × chores × kids)
   - Target: O(entities) with set lookups
   - Before (current):
     ```python
     for entity_entry in list(ent_reg.entities.values()):
         # ... nested chore loop
         for chore_id in self.chores_data:  # ❌ O(n×m)
     ```
   - After (optimized):

     ```python
     # Build valid combinations once: O(kids + chores)
     valid_uids = set()
     for chore_id, chore_info in self.chores_data.items():
         for kid_id in chore_info[const.DATA_CHORE_ASSIGNED_KIDS]:
             # Add all expected UID patterns for this kid+chore
             valid_uids.add(f"{prefix}{kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}")
             valid_uids.add(f"{prefix}{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}")
             # ... etc

     # Scan registry once: O(entities)
     for entity_entry in list(ent_reg.entities.values()):
         if entity_entry.unique_id not in valid_uids:  # O(1) set lookup
             ent_reg.async_remove(entity_entry.entity_id)
     ```

   - Measure: Log before/after performance with `time.perf_counter()`
   - Target: <.1fs for medium setups (was .3fs), linear scaling

3. **Add expected entity UID cache** (Status: Not started)
   - File: `coordinator.py` `__init__` method (after Line ~400)
   - Add coordinator fields:
     ```python
     self._expected_entity_cache: dict[str, set[str]] = {
         "buttons": set(),
         "sensors": set(),
     }
     self._cache_invalidated: bool = True
     ```
   - Create cache rebuilder:
     ```python
     def _rebuild_expected_entities_cache(self) -> None:
         """Build expected entity UIDs once per config change."""
         self._expected_entity_cache["buttons"] = self._build_expected_button_uids()
         self._expected_entity_cache["sensors"] = self._build_expected_sensor_uids()
         self._cache_invalidated = False
         const.LOGGER.debug("PERF: Rebuilt entity UID cache (%d buttons, %d sensors)",
             len(self._expected_entity_cache["buttons"]),
             len(self._expected_entity_cache["sensors"]))
     ```
   - Invalidate cache on:
     - Kid/parent/chore/reward/badge assignment changes
     - Entity creation/deletion via options flow
     - Config entry reload

4. **Refactor `remove_deprecated_button_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 771-853
   - Current: Rebuilds whitelist every call (~100 lines)
   - After: Use cached expected UIDs:

     ```python
     def remove_deprecated_button_entities(self) -> None:
         if self._cache_invalidated:
             self._rebuild_expected_entities_cache()

         allowed_uids = self._expected_entity_cache["buttons"]
         # ... simple diff against registry
     ```

   - Estimated reduction: 100 lines → 20 lines

5. **Refactor `remove_deprecated_sensor_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 855-970
   - Current: Rebuilds whitelist every call (~115 lines)
   - After: Use cached expected UIDs (same pattern as buttons)
   - Estimated reduction: 115 lines → 20 lines

6. **Performance validation** (Status: Not started)
   - Create large test scenario: 50 kids, 30 chores, 20 rewards, 10 badges
   - Measure entity registry cleanup time before/after
   - Target metrics:
     - `_remove_orphaned_kid_chore_entities()`: <.1fs (was .3fs)
     - `remove_deprecated_button_entities()`: <.05fs
     - `remove_deprecated_sensor_entities()`: <.05fs
     - Total cleanup overhead: <.2fs (down from ~.5fs+)
   - Add performance regression test to CI

**Key issues**:

- Risk: Cache invalidation logic could miss edge cases
- Mitigation: Add cache validation in debug mode (compare cache vs rebuild)
- Risk: Set operations could have memory overhead with 1000+ entities
- Mitigation: Profile memory usage, consider LRU cache if needed

---

### Phase 3 – Organization (Cleanup Orchestration)

**Goal**: Consolidate 8 separate cleanup methods into unified orchestrator with dependency resolution.

**Steps / detailed work items**:

1. **Create cleanup orchestrator class** (Status: Not started)
   - File: `coordinator.py` (new class before Line ~421)
   - Design:

     ```python
     class EntityCleanupOrchestrator:
         """Manages cleanup operations after entity deletions.

         Ensures cleanup steps execute in correct order with dependency resolution.
         """

         def __init__(self, coordinator: KidsChoresDataCoordinator):
             self.coordinator = coordinator
             self._cleanup_graph = self._build_cleanup_dependency_graph()

         async def cleanup_after_deletion(
             self,
             entity_type: str,
             entity_id: str,
             cascade: bool = True
         ) -> CleanupResult:
             """Execute cleanup steps for deleted entity."""
     ```

2. **Define cleanup dependency graph** (Status: Not started)
   - Map relationships:

     ```
     Kid deletion →
       1. Remove kid entities (buttons, sensors)
       2. Remove kid from chore assignments
       3. Remove kid from achievement assignments
       4. Remove kid from challenge assignments
       5. Remove kid from parent associations
       6. Cleanup pending reward approvals
       7. Cleanup unused translation sensors

     Chore deletion →
       1. Remove chore entities (shared state sensors)
       2. Remove chore from kids' kid_chore_data
       3. Remove chore from achievement selected_chore_id
       4. Remove chore from challenge selected_chore_id
       5. Remove orphaned kid-chore entities

     Parent deletion →
       1. Cascade to shadow kid (if exists)
       2. Cleanup unused translation sensors
     ```

   - Encode as directed acyclic graph (DAG) with topological sort

3. **Migrate existing cleanup methods** (Status: Not started)
   - Wrap existing methods in orchestrator:
     - `_cleanup_chore_from_kid` (Line 617)
     - `_cleanup_pending_reward_approvals` (Line 636)
     - `_cleanup_deleted_kid_references` (Line 649)
     - `_cleanup_deleted_chore_references` (Line 690)
     - `_cleanup_parent_assignments` (Line 702)
     - `_cleanup_deleted_chore_in_achievements` (Line 716)
     - `_cleanup_deleted_chore_in_challenges` (Line 728)
   - Keep methods as internal steps, orchestrator manages invocation order

4. **Update public delete methods** (Status: Not started)
   - Replace manual cleanup sequences:
     - `delete_kid_entity()` (Line 2363): Currently calls 4 cleanup methods
     - `delete_chore_entity()` (Line 2277): Currently calls 3 cleanup methods + async task
     - `delete_parent_entity()` (Line 2222): Currently calls 1 cleanup method
     - `delete_reward_entity()` (Line 2394): Currently calls 1 cleanup method
     - `delete_achievement_entity()` (Line 2505): Currently calls 1 async task
     - `delete_challenge_entity()` (Line 2543): Currently calls 1 async task
   - Replace with single orchestrator call:
     ```python
     async def delete_kid_entity(self, kid_id: str) -> None:
         # ... validation
         del self._data[const.DATA_KIDS][kid_id]
         await self._cleanup_orchestrator.cleanup_after_deletion("kid", kid_id)
         self._persist()
         self.async_update_listeners()
     ```

5. **Add cleanup validation/testing** (Status: Not started)
   - Create `tests/test_cleanup_orchestration.py`
   - Test scenarios:
     - Delete kid with active chores (verify all references removed)
     - Delete chore assigned to multiple kids (verify all kid entities removed)
     - Delete parent with associated kids (verify parent associations cleared)
     - Delete chore selected in achievement/challenge (verify references cleared)
   - Add orchestrator dry-run mode for debugging:
     ```python
     result = await orchestrator.cleanup_after_deletion("kid", kid_id, dry_run=True)
     print(result.planned_steps)  # Shows cleanup steps without executing
     ```

6. **Documentation** (Status: Not started)
   - Update `ARCHITECTURE.md` with cleanup orchestration section
   - Document cleanup dependency graph in docstrings
   - Add troubleshooting guide for orphaned entities

**Key issues**:

- Risk: Orchestrator could introduce new bugs if dependency graph incomplete
- Mitigation: Keep existing cleanup methods, orchestrator just invokes them in correct order
- Risk: Async task cleanup could be missed (achievements, challenges)
- Mitigation: Orchestrator should track async cleanup tasks and ensure completion

---

### Phase 4 – Advanced Features (Deferred to v0.7.0+)

**Goal**: Add audit trail, soft-delete with undo, and batch entity registry operations.

**Rationale**: These features require storage schema changes (audit log structure) and significant testing. Defer unless priority escalates.

**Steps / detailed work items**:

1. **Audit trail for options flow changes** (Status: Deferred)
   - Design: Add `audit_log` section to storage schema v43+
   - Track: who, when, what changed (entity type, entity ID, changed fields)
   - Storage format:
     ```json
     "audit_log": {
       "entries": [
         {
           "timestamp": "2026-01-20T15:30:00Z",
           "user_id": "user.parent1",
           "action": "update",
           "entity_type": "kid",
           "entity_id": "kid-uuid",
           "changes": {
             "name": {"old": "Sarah", "new": "Sarah M."},
             "points": {"old": 100, "new": 150}
           }
         }
       ]
     }
     ```
   - Retention: Configurable via options (default: 90 days)

2. **Soft-delete with undo mechanism** (Status: Deferred)
   - Add `deleted_at` timestamp to entity data
   - Keep deleted entities in storage for grace period (default: 7 days)
   - Add `restore_deleted_entity()` service call
   - UI: Show "Recently Deleted" section in options flow
   - Auto-purge after grace period expires

3. **Batch entity registry operations** (Status: Deferred)
   - Investigate HA core support for batch `async_remove()`
   - If not available, implement custom batching:
     ```python
     async def async_batch_remove_entities(
         ent_reg: EntityRegistry,
         entity_ids: list[str]
     ) -> int:
         """Remove multiple entities in single registry write."""
         # Implementation depends on HA core internals
     ```
   - Target: Reduce registry write overhead by 80%+ for bulk operations

4. **Performance telemetry** (Status: Deferred)
   - Add opt-in performance metrics collection
   - Track: entity registry scan times, cleanup durations, cache hit rates
   - Report: Expose as diagnostic sensor for debugging

**Key issues**:

- Requires storage schema v43+ (breaking change)
- Needs comprehensive migration testing
- UI work for "Recently Deleted" section
- Consider privacy implications of audit trail

---

## Testing & validation

### Phase 1 Testing

- [ ] Unit tests for `entity_crud_helper.py` validators
- [ ] Schema validation rejection tests (malformed data)
- [ ] Full integration test suite (no regressions)
- [ ] Verify logging output unchanged

### Phase 2 Testing

- [ ] Performance benchmarks before/after (50 kids, 30 chores scenario)
- [ ] Entity registry cleanup correctness (no false positives)
- [ ] Cache invalidation edge cases
- [ ] Memory profiling for large datasets

### Phase 3 Testing

- [ ] Cleanup orchestration correctness (all references removed)
- [ ] Dependency graph validation (no circular dependencies)
- [ ] Dry-run mode verification
- [ ] Cascade deletion integration tests

### Phase 4 Testing (Deferred)

- [ ] Audit trail storage/retrieval
- [ ] Soft-delete restore workflows
- [ ] Batch operation performance
- [ ] Migration from v42 → v43 schema

### Quality Gates

- All phases require:
  - `./utils/quick_lint.sh --fix` passing (9.5+/10)
  - `mypy custom_components/kidschores/` zero errors
  - `pytest tests/ -v` 100% pass rate
  - Code coverage maintained at 95%+

---

## Notes & follow-up

### Architecture decisions

1. **Why decorator pattern for validation?**
   - Non-breaking: Can be added incrementally
   - Testable: Validation logic isolated from CRUD logic
   - Flexible: Can switch to warning-only mode during transition

2. **Why cache expected entity UIDs?**
   - Performance: Rebuilding whitelist on every cleanup is O(n×m×k)
   - Cache: One-time cost O(n+m+k), then O(1) lookups
   - Trade-off: ~1-2KB memory for 10× performance improvement

3. **Why orchestrator pattern for cleanup?**
   - Correctness: Ensures cleanup steps execute in dependency order
   - Maintainability: Single place to manage cleanup logic
   - Testability: Can dry-run cleanup without side effects
   - Extensibility: Easy to add new cleanup steps

### Code reduction estimate

| Section                   | Current Lines | After Refactor | Reduction  |
| ------------------------- | ------------- | -------------- | ---------- |
| CRUD methods (Phase 1)    | ~800          | ~200           | -600       |
| Entity registry (Phase 2) | ~500          | ~200           | -300       |
| Cleanup methods (Phase 3) | ~300          | ~150           | -150       |
| **Total**                 | **~1,600**    | **~550**       | **-1,050** |

Plus ~300 lines of new helper code = **Net reduction: ~750 lines (~35% smaller)**

### Performance improvement estimate

| Operation                        | Before    | After      | Improvement |
| -------------------------------- | --------- | ---------- | ----------- |
| Kid-chore entity cleanup         | .3fs      | <.1fs      | 3×          |
| Deprecated button entity removal | ~.05fs    | <.01fs     | 5×          |
| Deprecated sensor entity removal | ~.05fs    | <.01fs     | 5×          |
| **Total cleanup overhead**       | **~.4fs** | **~.12fs** | **3.3×**    |

### Follow-up tasks

1. **Phase 1 completion** → Update [ARCHITECTURE.md](../ARCHITECTURE.md) with validation decorator pattern
2. **Phase 2 completion** → Document entity UID cache behavior in [ARCHITECTURE.md](../ARCHITECTURE.md)
3. **Phase 3 completion** → Add cleanup orchestration diagram to [ARCHITECTURE.md](../ARCHITECTURE.md)
4. **All phases** → Update [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) Phase 0 checklist with new patterns

### Dependencies

- No external package dependencies required
- Compatible with current storage schema v42
- No changes to entity platform files (sensor.py, button.py)
- No changes to config/options flow logic (flow signatures unchanged)

### Risk mitigation

- **Backward compatibility**: Keep existing method signatures, add helpers internally
- **Incremental rollout**: Phase 1 validation in warning-only mode initially
- **Performance validation**: Benchmark before/after with realistic data
- **Rollback plan**: Git revert possible at any phase boundary (no schema changes)

---

## Completion criteria

This initiative is considered complete when:

- [ ] Phase 1 complete: Generic CRUD helpers extracted, validation added
- [ ] Phase 2 complete: Entity registry operations optimized, cache implemented
- [ ] Phase 3 complete: Cleanup orchestrator deployed, all delete methods migrated
- [ ] All tests passing (unit + integration + performance)
- [ ] Documentation updated (ARCHITECTURE.md, CODE_REVIEW_GUIDE.md)
- [ ] Performance benchmarks meet targets (3× improvement in cleanup)
- [ ] Code coverage maintained at 95%+
- [ ] No regressions in options flow workflows
- [ ] Peer review completed (2+ reviewers)

**Phase 4 deferred** to v0.7.0+ unless priority changes.

---

_Plan created: 2026-01-20_
_Last updated: 2026-01-20 (Deep dive added)_
_Status: Planning phase - awaiting approval to begin Phase 1_

---

# 🔬 DEEP DIVE: Implementation Details & Critical Patterns

## Table of Contents

1. [CRUD Method Pattern Analysis](#crud-method-pattern-analysis)
2. [Entity Type Catalog](#entity-type-catalog)
3. [Default Value Patterns](#default-value-patterns)
4. [Validation Requirements](#validation-requirements)
5. [Logging Standards](#logging-standards)
6. [Storage Access Patterns](#storage-access-patterns)
7. [Entity Registry UID Patterns](#entity-registry-uid-patterns)
8. [Overlooked Opportunities](#overlooked-opportunities)
9. [Hidden Traps & Edge Cases](#hidden-traps--edge-cases)
10. [Migration Safety Checklist](#migration-safety-checklist)

---

## 1. CRUD Method Pattern Analysis

### Current Duplication Map

**Pattern A: Simple Create (7 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    self._data[const.DATA_XS][x_id] = {
        const.DATA_X_FIELD1: x_data.get(const.DATA_X_FIELD1, DEFAULT),
        const.DATA_X_FIELD2: x_data.get(const.DATA_X_FIELD2, DEFAULT),
        # ... N more fields
        const.DATA_X_INTERNAL_ID: x_id,  # ⚠️ Always last field
    }
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)
```

**Used by**: Rewards, Bonuses, Penalties, Achievements, Challenges, Parents (partial), Badges (partial)

**Pattern B: Simple Update (9 entity types)**

```python
def _update_X(self, x_id: str, x_data: dict[str, Any]):
    x_info = self._data[const.DATA_XS][x_id]
    x_info[const.DATA_X_FIELD1] = x_data.get(const.DATA_X_FIELD1, x_info[const.DATA_X_FIELD1])
    x_info[const.DATA_X_FIELD2] = x_data.get(const.DATA_X_FIELD2, x_info[const.DATA_X_FIELD2])
    # ... N more fields
    const.LOGGER.debug("DEBUG: X Updated - '%s', ID '%s'", name, x_id)
```

**Used by**: Rewards, Bonuses, Penalties, Achievements, Challenges, Badges (partial), Parents

**Pattern C: Complex Create with Side Effects (2 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    # Pre-processing/validation
    validated_refs = [ref for ref in x_data.get(REFS) if ref in other_data]

    self._data[const.DATA_XS][x_id] = { ... }
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)

    # Post-create side effects
    for kid_id in assigned_kids:
        self.hass.async_create_task(self._notify_kid(...))
```

**Used by**: Chores (notifications), Parents (kid validation)

**Pattern D: Delegated Create (2 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    # Delegates to helper function
    self._data[const.DATA_XS][x_id] = kh.build_default_X_data(x_id, x_data)
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)
```

**Used by**: Chores (`kh.build_default_chore_data`), Kids (partial - uses `.get()` pattern)

**Pattern E: Update with State Machine (1 entity type)**

```python
def _update_X(self, x_id: str, x_data: dict[str, Any]) -> bool:
    x_info = self._data[const.DATA_XS][x_id]

    # Complex state transitions
    old_state = x_info.get(STATE_FIELD)
    new_state = x_data.get(STATE_FIELD)

    if new_state != old_state:
        self._handle_state_transition(x_id, x_info, old_state, new_state)

    # ... field updates

    return state_changed  # Signals reload needed
```

**Used by**: Chores (completion criteria conversion, assignment changes)

### Complexity Matrix

| Entity Type | Create Lines | Update Lines | Side Effects | State Machine | Helper Delegation  |
| ----------- | ------------ | ------------ | ------------ | ------------- | ------------------ |
| Reward      | ~24          | ~18          | None         | No            | No                 |
| Bonus       | ~24          | ~18          | None         | No            | No                 |
| Penalty     | ~24          | ~18          | None         | No            | No                 |
| Achievement | ~28          | ~25          | None         | No            | No                 |
| Challenge   | ~32          | ~30          | None         | No            | No                 |
| Badge       | ~14          | ~14          | None         | No            | No (direct assign) |
| Kid         | ~45          | ~10          | None         | No            | Partial            |
| Parent      | ~40          | ~55          | Validation   | No            | No                 |
| **Chore**   | **~30**      | **~155**     | **Notify**   | **YES**       | **YES**            |

**Key Insight**: Chores are 3-5× more complex than other entity types. **DO NOT** consolidate chore update logic initially.

---

## 2. Entity Type Catalog

### Entity Field Inventory

#### Kids (22 fields)

```python
{
    const.DATA_KID_NAME: str,
    const.DATA_KID_POINTS: float,
    const.DATA_KID_BADGES_EARNED: dict[str, Any],  # badge_id → earned_data
    const.DATA_KID_HA_USER_ID: str | None,
    const.DATA_KID_INTERNAL_ID: str,  # UUID
    const.DATA_KID_POINTS_MULTIPLIER: float,
    const.DATA_KID_PENALTY_APPLIES: dict[str, int],  # penalty_id → count
    const.DATA_KID_BONUS_APPLIES: dict[str, int],  # bonus_id → count
    const.DATA_KID_REWARD_DATA: dict[str, Any],  # v0.5.0+ reward tracking
    const.DATA_KID_ENABLE_NOTIFICATIONS: bool,
    const.DATA_KID_MOBILE_NOTIFY_SERVICE: str,
    const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: bool,
    const.DATA_KID_OVERDUE_CHORES: list[str],  # chore_ids
    const.DATA_KID_OVERDUE_NOTIFICATIONS: dict[str, str],  # chore_id → timestamp
    const.DATA_KID_CHORE_DATA: dict[str, Any],  # v0.4.0+ timestamp tracking
    # Additional runtime fields (not in _create_kid):
    const.DATA_KID_BADGE_PROGRESS: dict[str, Any],  # badge_id → progress
    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS: dict[str, Any],
    const.DATA_KID_CHORE_STATS: dict[str, Any],  # completion counters
    const.DATA_KID_POINT_STATS: dict[str, Any],  # earned/spent tracking
    const.DATA_KID_IS_SHADOW: bool,  # Shadow kid marker
    const.DATA_KID_LINKED_PARENT_ID: str | None,  # Parent UUID
    const.DATA_KID_DASHBOARD_LANGUAGE: str,  # ISO language code
}
```

#### Parents (12 fields)

```python
{
    const.DATA_PARENT_NAME: str,
    const.DATA_PARENT_HA_USER_ID: str | None,
    const.DATA_PARENT_ASSOCIATED_KIDS: list[str],  # kid UUIDs
    const.DATA_PARENT_ENABLE_NOTIFICATIONS: bool,
    const.DATA_PARENT_MOBILE_NOTIFY_SERVICE: str,
    const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS: bool,
    const.DATA_PARENT_INTERNAL_ID: str,  # UUID
    const.DATA_PARENT_DASHBOARD_LANGUAGE: str,
    const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: bool,  # v0.6.0+
    const.DATA_PARENT_ENABLE_CHORE_WORKFLOW: bool,
    const.DATA_PARENT_ENABLE_GAMIFICATION: bool,
    const.DATA_PARENT_LINKED_SHADOW_KID_ID: str | None,  # Shadow kid UUID
}
```

#### Chores (20+ fields) ⚠️ COMPLEX

```python
{
    const.DATA_CHORE_NAME: str,
    const.DATA_CHORE_STATE: str,  # enabled/disabled/archived
    const.DATA_CHORE_DEFAULT_POINTS: float,
    const.DATA_CHORE_APPROVAL_RESET_TYPE: str,  # daily/weekly/monthly
    const.DATA_CHORE_DESCRIPTION: str,
    const.DATA_CHORE_LABELS: list[str],
    const.DATA_CHORE_ICON: str,
    const.DATA_CHORE_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_CHORE_RECURRING_FREQUENCY: str,  # daily/weekly/custom/etc.
    const.DATA_CHORE_DUE_DATE: str | None,  # ISO datetime
    const.DATA_CHORE_LAST_COMPLETED: str | None,  # ISO datetime
    const.DATA_CHORE_LAST_CLAIMED: str | None,  # ISO datetime
    const.DATA_CHORE_APPLICABLE_DAYS: list[int] | None,  # 0-6 (Mon-Sun)
    const.DATA_CHORE_NOTIFY_ON_CLAIM: bool,
    const.DATA_CHORE_NOTIFY_ON_APPROVAL: bool,
    const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL: bool,
    const.DATA_CHORE_CUSTOM_INTERVAL: int | None,
    const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: str | None,  # days/weeks/months
    const.DATA_CHORE_DAILY_MULTI_TIMES: str | None,  # CSV "08:00,14:00,20:00"
    const.DATA_CHORE_COMPLETION_CRITERIA: str,  # independent/shared
    const.DATA_CHORE_PER_KID_DUE_DATES: dict[str, str | None],  # kid_id → ISO
    const.DATA_CHORE_PER_KID_APPLICABLE_DAYS: dict[str, list[int]],  # PKAD-2026-001
    const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES: dict[str, str],  # PKAD-2026-001
    const.DATA_CHORE_INTERNAL_ID: str,  # UUID
}
```

#### Badges (11 fields)

```python
{
    const.DATA_BADGE_NAME: str,
    const.DATA_BADGE_DESCRIPTION: str,
    const.DATA_BADGE_ICON: str,
    const.DATA_BADGE_TYPE: str,  # cumulative/periodic
    const.DATA_BADGE_TRIGGER: str,  # chore_count/points_earned/streak/etc.
    const.DATA_BADGE_THRESHOLD: int,
    const.DATA_BADGE_PERIOD: str | None,  # daily/weekly/monthly (periodic only)
    const.DATA_BADGE_SELECTED_CHORE_ID: str | None,  # UUID
    const.DATA_BADGE_POINT_REWARD: float,
    const.DATA_BADGE_LABELS: list[str],
    const.DATA_BADGE_INTERNAL_ID: str,  # UUID
}
```

#### Rewards (6 fields)

```python
{
    const.DATA_REWARD_NAME: str,
    const.DATA_REWARD_COST: float,
    const.DATA_REWARD_DESCRIPTION: str,
    const.DATA_REWARD_LABELS: list[str],
    const.DATA_REWARD_ICON: str,
    const.DATA_REWARD_INTERNAL_ID: str,  # UUID
}
```

#### Penalties (6 fields)

```python
{
    const.DATA_PENALTY_NAME: str,
    const.DATA_PENALTY_POINTS: float,  # Negative value
    const.DATA_PENALTY_DESCRIPTION: str,
    const.DATA_PENALTY_LABELS: list[str],
    const.DATA_PENALTY_ICON: str,
    const.DATA_PENALTY_INTERNAL_ID: str,  # UUID
}
```

#### Bonuses (6 fields)

```python
{
    const.DATA_BONUS_NAME: str,
    const.DATA_BONUS_POINTS: float,
    const.DATA_BONUS_DESCRIPTION: str,
    const.DATA_BONUS_LABELS: list[str],
    const.DATA_BONUS_ICON: str,
    const.DATA_BONUS_INTERNAL_ID: str,  # UUID
}
```

#### Achievements (11 fields)

```python
{
    const.DATA_ACHIEVEMENT_NAME: str,
    const.DATA_ACHIEVEMENT_DESCRIPTION: str,
    const.DATA_ACHIEVEMENT_LABELS: list[str],
    const.DATA_ACHIEVEMENT_ICON: str,
    const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_ACHIEVEMENT_TYPE: str,  # streak/completion/points
    const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: str,  # UUID or ""
    const.DATA_ACHIEVEMENT_CRITERIA: str,
    const.DATA_ACHIEVEMENT_TARGET_VALUE: int,
    const.DATA_ACHIEVEMENT_REWARD_POINTS: float,
    const.DATA_ACHIEVEMENT_PROGRESS: dict[str, Any],  # kid_id → progress_data
    const.DATA_ACHIEVEMENT_INTERNAL_ID: str,  # UUID
}
```

#### Challenges (13 fields)

```python
{
    const.DATA_CHALLENGE_NAME: str,
    const.DATA_CHALLENGE_DESCRIPTION: str,
    const.DATA_CHALLENGE_LABELS: list[str],
    const.DATA_CHALLENGE_ICON: str,
    const.DATA_CHALLENGE_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_CHALLENGE_TYPE: str,  # daily_min/weekly_min/total
    const.DATA_CHALLENGE_SELECTED_CHORE_ID: str,  # UUID or SENTINEL_EMPTY
    const.DATA_CHALLENGE_CRITERIA: str,
    const.DATA_CHALLENGE_TARGET_VALUE: int,
    const.DATA_CHALLENGE_REWARD_POINTS: float,
    const.DATA_CHALLENGE_START_DATE: str | None,  # ISO date
    const.DATA_CHALLENGE_END_DATE: str | None,  # ISO date
    const.DATA_CHALLENGE_PROGRESS: dict[str, Any],  # kid_id → progress_data
    const.DATA_CHALLENGE_INTERNAL_ID: str,  # UUID
}
```

---

## 3. Default Value Patterns

### Default Constant Mapping

**CRITICAL**: These defaults must match exactly or validation will fail.

```python
# Entity-specific defaults (from const.py)
DEFAULT_ZERO = 0
DEFAULT_REWARD_COST = 10.0
DEFAULT_REWARD_ICON = "mdi:gift"
DEFAULT_BONUS_POINTS = 5.0
DEFAULT_BONUS_ICON = "mdi:star"
DEFAULT_PENALTY_POINTS = 5.0  # Applied as negative
DEFAULT_PENALTY_ICON = "mdi:alert"
DEFAULT_ACHIEVEMENT_TARGET = 5
DEFAULT_ACHIEVEMENT_REWARD_POINTS = 10.0
DEFAULT_CHALLENGE_TARGET = 3
DEFAULT_CHALLENGE_REWARD_POINTS = 5.0
DEFAULT_KID_POINTS_MULTIPLIER = 1.0
DEFAULT_NOTIFY_ON_CLAIM = True
DEFAULT_NOTIFY_ON_APPROVAL = True
DEFAULT_NOTIFY_ON_DISAPPROVAL = True
DEFAULT_APPROVAL_RESET_TYPE = "daily"
DEFAULT_DASHBOARD_LANGUAGE = "en"
DEFAULT_PARENT_ALLOW_CHORE_ASSIGNMENT = False
DEFAULT_PARENT_ENABLE_CHORE_WORKFLOW = True
DEFAULT_PARENT_ENABLE_GAMIFICATION = True

# Sentinel values (not defaults, but markers)
SENTINEL_EMPTY = ""
```

### `.get()` Pattern Analysis

**Pattern 1: Simple default** (most common)

```python
x_data.get(const.DATA_X_FIELD, const.DEFAULT_VALUE)
```

**Pattern 2: Nested fallback** (update methods)

```python
x_data.get(const.DATA_X_FIELD, x_info[const.DATA_X_FIELD])
# Or with double fallback:
x_data.get(const.DATA_X_FIELD, x_info.get(const.DATA_X_FIELD, const.DEFAULT))
```

**Pattern 3: Conditional default** (challenges, achievements)

```python
(
    x_data.get(const.DATA_X_FIELD)
    if x_data.get(const.DATA_X_FIELD) not in [None, {}]
    else None
)
```

**Pattern 4: List/dict defaults**

```python
x_data.get(const.DATA_X_LABELS, x_info.get(const.DATA_X_LABELS, []))
x_data.get(const.DATA_X_PROGRESS, {})
```

**TRAP**: Inconsistent `.get()` usage across entity types. Some use 2-level fallback, some don't.

---

## 4. Validation Requirements

### Current Validation Gaps (Missing in `_create_*` methods)

**❌ No Type Checking**:

```python
# Current: Accepts anything
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    self._data[const.DATA_REWARDS][reward_id] = {
        const.DATA_REWARD_COST: reward_data.get(const.DATA_REWARD_COST, 10.0),  # What if string?
    }
```

**❌ No Required Field Validation**:

```python
# Current: Silently uses SENTINEL_EMPTY if missing
const.DATA_REWARD_NAME: reward_data.get(const.DATA_REWARD_NAME, const.SENTINEL_EMPTY)
# Should: Raise error if name not provided
```

**❌ No Range Validation**:

```python
# Current: Accepts negative costs, zero points, etc.
const.DATA_REWARD_COST: reward_data.get(const.DATA_REWARD_COST, 10.0)
# Should: Validate cost > 0
```

**❌ No Reference Validation**:

```python
# Current: Parents can reference non-existent kids
const.DATA_PARENT_ASSOCIATED_KIDS: parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, [])
# Should: Validate all kid_ids exist in self.kids_data
```

### Required Validation Rules Per Entity

#### Universal Rules (All Entities)

- `internal_id`: Must be valid UUID string
- `name`: Required, non-empty string, max 100 chars
- `description`: Optional string, max 500 chars
- `labels`: Optional list of strings
- `icon`: Optional string, must match `mdi:*` pattern

#### Entity-Specific Rules

**Rewards**:

- `cost`: Required, float > 0

**Penalties**:

- `points`: Required, float (stored as negative)

**Bonuses**:

- `points`: Required, float > 0

**Kids**:

- `points`: float >= 0
- `points_multiplier`: float > 0, <= 10.0
- `ha_user_id`: Optional, must exist in HA users if provided
- `mobile_notify_service`: Optional, must match notify.\* service if provided

**Parents**:

- `associated_kids`: list[str], all UUIDs must exist in kids_data
- `ha_user_id`: Optional, must exist in HA users if provided
- `linked_shadow_kid_id`: If set, must point to valid shadow kid

**Chores** ⚠️ COMPLEX:

- `assigned_kids`: list[str], all UUIDs must exist in kids_data
- `default_points`: float >= 0
- `recurring_frequency`: Must be valid frequency constant
- `completion_criteria`: Must be "independent" or "shared"
- `per_kid_due_dates`: If present, keys must match assigned_kids
- `applicable_days`: list[int], all values 0-6
- `daily_multi_times`: If present, must be valid CSV time format

**Achievements/Challenges**:

- `assigned_kids`: list[str], all UUIDs must exist in kids_data
- `selected_chore_id`: If not empty, must exist in chores_data
- `target_value`: int > 0
- `reward_points`: float >= 0

**Badges**:

- `threshold`: int > 0
- `selected_chore_id`: If not None, must exist in chores_data
- `period`: If badge_type is "periodic", must be set

### Validation Strategy

**Phase 1**: Warning-only mode

```python
@validate_entity_schema(SCHEMA_REWARD_CREATE, mode="warn")
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    # Logs warnings but doesn't block
```

**Phase 2**: After 1 release, promote to errors

```python
@validate_entity_schema(SCHEMA_REWARD_CREATE, mode="error")
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    # Raises HomeAssistantError on validation failure
```

---

## 5. Logging Standards

### Current Logging Patterns

**Create methods**:

```python
const.LOGGER.debug(
    "DEBUG: X Added - '%s', ID '%s'",
    self._data[const.DATA_XS][x_id][const.DATA_X_NAME],
    x_id,
)
```

**Update methods**:

```python
const.LOGGER.debug(
    "DEBUG: X Updated - '%s', ID '%s'",
    x_info[const.DATA_X_NAME],
    x_id,
)
```

**Delete methods** (public):

```python
const.LOGGER.info("INFO: Deleted X '%s' (ID: %s)", x_name, x_id)
```

**Shadow kid operations**:

```python
const.LOGGER.info(
    "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
    parent_info.get(const.DATA_PARENT_NAME),
    shadow_kid_id,
    parent_info.get(const.DATA_PARENT_NAME),
    parent_id,
)
```

### Logging Anti-Patterns to Avoid

❌ **Redundant prefixes**:

```python
const.LOGGER.debug("DEBUG: message")  # Log level already shown
```

❌ **F-strings in logs**:

```python
const.LOGGER.debug(f"Value: {var}")  # Use lazy logging
```

✅ **Correct**:

```python
const.LOGGER.debug("Value: %s", var)
```

❌ **Inconsistent naming**:

```python
# Don't mix "Added" / "Created" / "Inserted"
const.LOGGER.debug("Added kid '%s'", ...)
const.LOGGER.debug("Created parent '%s'", ...)  # Pick one term
```

### Logging Consolidation Target

**Extract to helper**:

```python
def log_entity_crud(
    operation: str,  # "created", "updated", "deleted"
    entity_type: str,  # const.LABEL_KID, const.LABEL_CHORE, etc.
    entity_name: str,
    entity_id: str,
    level: str = "debug"  # "debug" or "info"
) -> None:
    """Standardized CRUD operation logging."""
    message = f"{operation.capitalize()} {entity_type} '%s' (ID: %s)"
    logger_func = getattr(const.LOGGER, level)
    logger_func(message, entity_name, entity_id)
```

---

## 6. Storage Access Patterns

### Dict Access Methods

**Pattern 1: Direct assignment** (create)

```python
self._data[const.DATA_KIDS][kid_id] = { ... }
```

**Pattern 2: Update existing** (update)

```python
kid_info = self._data[const.DATA_KIDS][kid_id]
kid_info[const.DATA_KID_NAME] = new_name
```

**Pattern 3: Update with .update()** (badge)

```python
existing = badges.get(badge_id, {})
existing.update(badge_data)  # Merge new fields
badges[badge_id] = existing
```

**Pattern 4: Setdefault** (badge create)

```python
self._data.setdefault(const.DATA_BADGES, {})[badge_id] = badge_data
```

**TRAP**: Inconsistent dict access patterns across entity types. Badge uses `.setdefault()` + `.update()`, others use direct assignment.

### Storage Hierarchy

```
self._data
├── const.DATA_KIDS: dict[str, KidData]
├── const.DATA_PARENTS: dict[str, ParentData]
├── const.DATA_CHORES: dict[str, ChoreData]
├── const.DATA_BADGES: dict[str, BadgeData]
├── const.DATA_REWARDS: dict[str, RewardData]
├── const.DATA_PENALTIES: dict[str, PenaltyData]
├── const.DATA_BONUSES: dict[str, BonusData]
├── const.DATA_ACHIEVEMENTS: dict[str, AchievementData]
├── const.DATA_CHALLENGES: dict[str, ChallengeData]
└── const.DATA_META: dict[str, Any]
```

**CRITICAL**: Always use `const.DATA_*` keys, never hardcoded strings.

---

## 7. Entity Registry UID Patterns

### UID Construction Formulas

**Kid-specific sensors**:

```
{entry_id}_{kid_id}{SENSOR_KC_UID_SUFFIX_*}
```

**Kid-chore sensors**:

```
{entry_id}_{kid_id}_{chore_id}{SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}
```

**Kid-chore buttons**:

```
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_CLAIM}
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_APPROVE}
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_DISAPPROVE}
```

**Reward buttons/sensors**:

```
{entry_id}_{BUTTON_REWARD_PREFIX}{kid_id}_{reward_id}
{entry_id}_{kid_id}_{reward_id}{BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}
{entry_id}_{kid_id}_{reward_id}{SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}
```

**Penalty/Bonus buttons**:

```
{entry_id}_{BUTTON_PENALTY_PREFIX}{kid_id}_{penalty_id}
{entry_id}_{BUTTON_BONUS_PREFIX}{kid_id}_{bonus_id}
```

**Points adjust buttons**:

```
{entry_id}_{kid_id}{BUTTON_KC_UID_MIDFIX_ADJUST_POINTS}{delta}
```

**Global sensors**:

```
{entry_id}{SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}
{entry_id}{SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}
```

**Shared chore global state**:

```
{entry_id}_{chore_id}{DATA_GLOBAL_STATE_SUFFIX}
```

**Dashboard helper** (hardcoded):

```
{entry_id}_{kid_id}_ui_dashboard_helper
```

**Badge progress sensors**:

```
{entry_id}_{kid_id}_{badge_id}{SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}
```

**Achievement/Challenge progress sensors**:

```
{entry_id}_{kid_id}_{achievement_id}{SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}
{entry_id}_{kid_id}_{challenge_id}{SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}
```

### UID Cache Structure

**Proposed cache**:

```python
self._expected_entity_cache = {
    "buttons": {
        "chore_claim": set(),  # kid-chore claim buttons
        "chore_approve": set(),  # kid-chore approve buttons
        "chore_disapprove": set(),
        "reward_claim": set(),
        "reward_approve": set(),
        "reward_disapprove": set(),
        "penalty_apply": set(),
        "bonus_apply": set(),
        "points_adjust": set(),
    },
    "sensors": {
        "kid": set(),  # kid-specific sensors (points, badges, etc.)
        "chore_status": set(),  # kid-chore status sensors
        "reward_status": set(),
        "penalty_applies": set(),
        "bonus_applies": set(),
        "badge_progress": set(),
        "achievement_progress": set(),
        "challenge_progress": set(),
        "shared_chore_state": set(),
        "global": set(),  # pending approvals
    },
}
```

---

## 8. Overlooked Opportunities

### 1. **Shadow Kid Workflow Integration**

**Opportunity**: Extend CRUD helpers to handle shadow kid creation/unlinking consistently.

**Current State**: Shadow kid logic scattered:

- `_create_shadow_kid_for_parent()` (Line 1170)
- `_unlink_shadow_kid()` (Line 1270)
- Duplicates kid creation logic with special markers

**Improvement**:

```python
# In entity_crud_helper.py
def create_shadow_kid_from_parent(
    parent_id: str,
    parent_data: dict[str, Any],
    coordinator: KidsChoresDataCoordinator
) -> tuple[str, dict[str, Any]]:
    """Build shadow kid data structure from parent.

    Returns:
        (shadow_kid_id, kid_data) tuple ready for _create_kid()
    """
    shadow_kid_id, kid_data = fh.build_shadow_kid_data(parent_id, parent_data)
    # Add shadow markers
    kid_data[const.DATA_KID_IS_SHADOW] = True
    kid_data[const.DATA_KID_LINKED_PARENT_ID] = parent_id
    return shadow_kid_id, kid_data
```

**Impact**: Reduces shadow kid creation from 30 lines → 5 lines.

### 2. **Notification Side Effects as Decorator**

**Current**: Chore creation sends notifications inline (Line 1375-1389).

**Opportunity**:

```python
@notify_after_create(
    entity_type="chore",
    recipient_field=const.DATA_CHORE_ASSIGNED_KIDS,
    notification_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED
)
def _create_chore(self, chore_id: str, chore_data: dict[str, Any]):
    # Just create, decorator handles notifications
```

**Benefit**: Separates data creation from side effects, easier testing.

### 3. **Field Update Batch Operations**

**Current**: Each update field is individual `.get()` call (18 lines for reward update).

**Opportunity**:

```python
# Define field mappings once
REWARD_UPDATE_FIELDS = {
    const.DATA_REWARD_NAME: (str, None),  # (type, default)
    const.DATA_REWARD_COST: (float, None),
    const.DATA_REWARD_DESCRIPTION: (str, None),
    const.DATA_REWARD_LABELS: (list, None),
    const.DATA_REWARD_ICON: (str, None),
}

# Update in one call
update_entity_fields(reward_info, reward_data, REWARD_UPDATE_FIELDS)
```

**Impact**: 18 lines → 1 line per entity update.

### 4. **Delegated Create Standardization**

**Current**: Only chores delegate to helper (`kh.build_default_chore_data`).

**Opportunity**: Extend pattern to all entity types:

```python
# In entity_crud_helper.py
def build_default_kid_data(kid_id: str, kid_data: dict[str, Any]) -> KidData:
    """Single source of truth for kid data structure."""

def build_default_parent_data(parent_id: str, parent_data: dict[str, Any]) -> ParentData:
    """Single source of truth for parent data structure."""
```

**Benefit**: Coordinator methods become thin wrappers, all logic in testable helpers.

### 5. **Transaction-like Operations**

**Current**: No rollback if operation fails mid-process.

**Opportunity**:

```python
class EntityTransaction:
    """Context manager for transactional entity operations."""

    def __enter__(self):
        self._snapshot = copy.deepcopy(self.coordinator._data)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Rollback on exception
            self.coordinator._data = self._snapshot
```

**Use case**: Complex chore conversion (SHARED ↔ INDEPENDENT) could corrupt data mid-conversion.

### 6. **Entity Reference Graph**

**Current**: Manual reference tracking in cleanup methods.

**Opportunity**: Build dependency graph at startup:

```python
# At coordinator init
self._entity_graph = EntityReferenceGraph(self._data)
# Query dependencies
refs = self._entity_graph.get_references_to("kid", kid_id)
# Returns: [("chore", chore_id), ("achievement", ach_id), ...]
```

**Benefit**: Automated orphan detection, cleanup validation.

---

## 9. Hidden Traps & Edge Cases

### TRAP 1: Badge Update Uses `.update()` Instead of Direct Assignment

**Location**: `_update_badge()` (Line 1694)

**Code**:

```python
existing = badges.get(badge_id, {})
existing.update(badge_data)  # ⚠️ Merges instead of replaces
badges[badge_id] = existing
```

**Other entity types**:

```python
badge_info = self._data[const.DATA_BADGES][badge_id]
badge_info[FIELD] = new_value  # Direct field updates
```

**Risk**: If helper uses direct assignment pattern, badge updates will break.

**Solution**: Helper must support both update strategies:

```python
def update_entity(
    entity_dict: dict,
    entity_id: str,
    update_data: dict,
    update_strategy: str = "fields"  # "fields" or "merge"
):
    if update_strategy == "merge":
        existing = entity_dict.get(entity_id, {})
        existing.update(update_data)
        entity_dict[entity_id] = existing
    else:
        # Field-by-field updates
        entity_info = entity_dict[entity_id]
        for key, value in update_data.items():
            entity_info[key] = value
```

### TRAP 2: Parent Validation Must Check Kid Existence

**Location**: `_create_parent()` / `_update_parent()` (Lines 1108-1119, 1173-1182)

**Code**:

```python
for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
    if kid_id in self.kids_data:
        associated_kids_ids.append(kid_id)
    else:
        const.LOGGER.warning(
            "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
            parent_data.get(const.DATA_PARENT_NAME, parent_id),
            kid_id,
        )
```

**Risk**: Generic helper won't have access to `self.kids_data` for validation.

**Solution**: Pass coordinator reference to validation:

```python
@validate_entity_schema(SCHEMA_PARENT_CREATE, coordinator_ref=True)
def _create_parent(self, parent_id: str, parent_data: dict[str, Any]):
    # Decorator injects self (coordinator) for cross-entity validation
```

### TRAP 3: Chore Update Returns Boolean (Reload Signal)

**Location**: `_update_chore()` (Line 1393)

**Signature**:

```python
def _update_chore(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
    # Returns True if assigned_kids changed (requires reload)
```

**Risk**: Generic update helper signature won't match.

**Solution**: Keep chore update separate, or use optional return:

```python
def update_entity(...) -> dict[str, Any]:
    """Returns metadata about update."""
    return {
        "success": True,
        "reload_needed": False,  # Chores can set True
        "side_effects": [],
    }
```

### TRAP 4: Chore Conversion Logic is Stateful

**Location**: `_convert_independent_to_shared()` / `_convert_shared_to_independent()` (Lines 1575-1740)

**Complexity**:

- Modifies both `chore_info` AND `chore_data` dicts
- Clears per-kid fields when converting to SHARED
- Populates per-kid fields when converting to INDEPENDENT
- Must handle `applicable_days` type conversion (strings → integers)

**Risk**: Cannot consolidate into generic helper without significant refactoring.

**Solution**: **DO NOT consolidate chore update initially**. Phase 1 skips chores.

### TRAP 5: Challenge/Achievement Date Fields Need Null Coalescing

**Location**: `_create_challenge()` (Lines 2000-2009)

**Code**:

```python
const.DATA_CHALLENGE_START_DATE: (
    challenge_data.get(const.DATA_CHALLENGE_START_DATE)
    if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
    else None
),
```

**Reason**: Options flow might send `{}` instead of `None` for empty dates.

**Risk**: Generic helper using simple `.get()` will store `{}` instead of `None`.

**Solution**: Add date field preprocessor:

```python
def normalize_optional_date(value: Any) -> str | None:
    """Convert empty values to None for date fields."""
    return value if value not in [None, {}, ""] else None
```

### TRAP 6: Kid Create Has No Side Effects, But Update Does (Device Registry)

**Location**: `update_kid_entity()` (Line 2353)

**Code**:

```python
# Check if name is changing
old_name = self._data[const.DATA_KIDS][kid_id].get(const.DATA_KID_NAME)
new_name = kid_data.get(const.DATA_KID_NAME)

self._update_kid(kid_id, kid_data)
# ...

# Update device registry if name changed
if new_name and new_name != old_name:
    self._update_kid_device_name(kid_id, new_name)
```

**Risk**: Generic update helper won't trigger device registry update.

**Solution**: Post-update hook system:

```python
@post_update_hook("update_device_name")
def _update_kid(self, kid_id: str, kid_data: dict[str, Any]):
    # Decorator calls hook after update if name changed
```

### TRAP 7: Internal ID Must Always Be Last Field

**Pattern observed** (all create methods):

```python
{
    const.DATA_X_FIELD1: value1,
    const.DATA_X_FIELD2: value2,
    # ... more fields
    const.DATA_X_INTERNAL_ID: x_id,  # ⚠️ Always last
}
```

**Reason**: Likely code review convention for easy visual verification.

**Risk**: Auto-generated dict might put internal_id first alphabetically.

**Solution**: Use OrderedDict or explicit field ordering in helper.

### TRAP 8: Logging Extracts Name from Created Dict vs Updated Dict

**Create**:

```python
const.LOGGER.debug(
    "DEBUG: X Added - '%s', ID '%s'",
    self._data[const.DATA_XS][x_id][const.DATA_X_NAME],  # ⚠️ From storage
    x_id,
)
```

**Update**:

```python
const.LOGGER.debug(
    "DEBUG: X Updated - '%s', ID '%s'",
    x_info[const.DATA_X_NAME],  # ⚠️ From local variable
    x_id,
)
```

**Risk**: Logger helper must know where to get name (storage vs parameter).

**Solution**: Always pass name explicitly:

```python
def log_entity_crud(operation, entity_type, entity_name, entity_id):
    # Caller responsible for extracting name
```

---

## 10. Migration Safety Checklist

### Pre-Implementation Validation

- [ ] **Identify ALL usage of `_create_*` / `_update_*` methods**
  - `grep -r "_create_kid\|_update_kid" custom_components/kidschores/`
  - Validate no external calls outside coordinator/options_flow

- [ ] **Verify ALL entity types have consistent field structures**
  - Run storage validator against test scenarios
  - Check for unexpected nested dicts or type inconsistencies

- [ ] **Document ALL side effects**
  - Chore create → notifications
  - Parent create → kid validation + shadow kid creation
  - Parent update → shadow kid linking/unlinking
  - Kid update → device registry update
  - Chore update → completion criteria conversion
  - Badge update → progress recalculation

- [ ] **Map ALL cleanup method dependencies**
  - Which cleanup methods call other cleanup methods?
  - What's the execution order?
  - Are there circular dependencies?

### Implementation Checkpoints

**After creating `entity_crud_helper.py`**:

- [ ] Module imports without circular dependency
- [ ] All helper functions have type hints
- [ ] All helpers have docstrings
- [ ] Unit tests for each helper (no coordinator needed)

**After migrating first entity (Reward)**:

- [ ] Existing tests pass unchanged
- [ ] Storage structure identical (diff `.storage/kidschores_data`)
- [ ] Logging output identical (compare logs before/after)
- [ ] Options flow works for create/update/delete

**After migrating all simple entities**:

- [ ] Code reduction target met (~600 lines → ~200 lines)
- [ ] No new test failures
- [ ] Performance unchanged (measure entity creation time)
- [ ] Validate with `./utils/quick_lint.sh --fix` (9.5+/10)
- [ ] MyPy zero errors

**After Phase 2 (Performance)**:

- [ ] Benchmark entity registry cleanup (before/after)
- [ ] Measure cache memory usage
- [ ] Verify cache invalidation triggers correctly
- [ ] Test with large dataset (50 kids, 30 chores, 20 rewards)

**After Phase 3 (Orchestration)**:

- [ ] All cleanup paths tested (kid, chore, parent, etc.)
- [ ] Orphan entity verification (none left after deletions)
- [ ] Dry-run mode works correctly
- [ ] Async task cleanup completes

### Rollback Triggers

**Abort migration if**:

- Storage corruption detected in any test scenario
- More than 5% performance regression
- Any test failure that cannot be resolved in 1 hour
- MyPy errors increase above baseline
- Lint score drops below 9.5/10

**Rollback procedure**:

1. `git revert <commit-range>`
2. Verify tests pass on reverted code
3. Document issue in plan as "Blocked" item
4. Analyze root cause before retry

---

## Summary: Critical Success Factors

✅ **DO**:

1. Start with simplest entity (Reward) as reference implementation
2. Keep chore update separate initially (too complex)
3. Use validation decorators with warning-only mode first
4. Measure before/after performance for every optimization
5. Test with multiple storage schema scenarios
6. Preserve ALL existing logging behavior
7. Extract helpers incrementally (one entity type at a time)

❌ **DON'T**:

1. Consolidate chore logic in Phase 1 (defer to Phase 2/3)
2. Change method signatures (break compatibility)
3. Skip validation warnings (silent failures are worse)
4. Optimize without measuring (premature optimization)
5. Batch-migrate all entities at once (too risky)
6. Forget device registry side effects (kid name changes)
7. Ignore edge cases in date handling (null vs {})

🎯 **Key Metrics**:

- Code reduction: ~750 lines (-35%)
- Performance improvement: 3× faster cleanup
- Test coverage: Maintain 95%+
- MyPy errors: Zero
- Lint score: 9.5+/10
- Storage compatibility: 100%

---

_Deep dive completed: 2026-01-20_
_Ready for implementation approval_
