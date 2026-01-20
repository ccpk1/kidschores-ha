# Coordinator Chore Operations Extraction Plan

## Initiative snapshot

- **Name / Code**: COORD-OPS-CHORE / Phase 2.5a
- **Target release / milestone**: v0.5.0 (Pre-v0.6.0 refactor)
- **Owner / driver(s)**: Strategic Planning Agent → Plan Builder Agent
- **Status**: Not started

## Summary & immediate steps

| Phase / Step             | Description                                   | % complete | Quick notes                            |
| ------------------------ | --------------------------------------------- | ---------- | -------------------------------------- |
| Phase 1 – File Setup     | Create coordinator_chore_operations.py        | 0%         | New file with class skeleton           |
| Phase 2 – Method Extract | Move 20+ chore methods to operations class    | 0%         | Zero logic changes, pure code movement |
| Phase 3 – Integration    | Update coordinator.py imports and inheritance | 0%         | Multiple inheritance setup             |
| Phase 4 – Validation     | Run full test suite and quality gates         | 0%         | Must pass 782 tests, MyPy, lint        |
| Phase 5 – Documentation  | Update docstrings and ARCHITECTURE.md         | 0%         | Document new file structure            |

1. **Key objective** – Extract 1,200+ lines of chore lifecycle logic from coordinator.py into coordinator_chore_operations.py using Python's multiple inheritance pattern, reducing coordinator size by ~10% with zero test changes.

2. **Summary of recent work** – Not started. Analysis complete in COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md recommending operations class pattern over full architectural refactor.

3. **Next steps (short term)**:
   - Create coordinator_chore_operations.py with ChoreOperations class
   - Extract claim_chore, approve_chore, disapprove_chore methods
   - Extract chore state machine methods (\_process_chore_state, etc.)
   - Extract chore scheduling methods (reset, reschedule)
   - Update coordinator.py to inherit from ChoreOperations

4. **Risks / blockers**:
   - **Method interdependencies**: Chore methods may call badge/reward methods (acceptable - coordinator has all methods via multiple inheritance)
   - **Import cycles**: New file imports coordinator types → mitigate with TYPE_CHECKING
   - **Test discovery**: Pytest should find all tests unchanged (services still call coordinator.claim_chore())

5. **References**:
   - [COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md](COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md) - Analysis justifying this approach
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage patterns
   - [coordinator.py](../../custom_components/kidschores/coordinator.py) - Source file (11,952 lines)

6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Use "operations class" naming over "mixin" for clarity
     - ✅ Start with chores only (not all features at once)
     - ✅ Keep all logic identical - no refactoring during extraction
     - ✅ Use multiple inheritance (ChoreOperations as base class)
   - **Completion confirmation**: `[ ]` All follow-up items completed:
     - `[ ]` coordinator_chore_operations.py created and integrated
     - `[ ]` All 782 tests passing unchanged
     - `[ ]` MyPy passes with 0 errors
     - `[ ]` Lint score maintains 9.5+/10
     - `[ ]` ARCHITECTURE.md updated with file structure
     - `[ ]` coordinator.py reduced by 1,200+ lines

> **Important:** This is a **surgical code movement**, not a refactor. Logic stays identical. Success = tests pass unchanged.

## Tracking expectations

- **Summary upkeep**: Update % complete after each phase. Update blockers immediately if discovered.
- **Detailed tracking**: Phase sections below track specific method extractions, line counts, and validation results.

## Detailed phase tracking

### Phase 1 – File Setup (Est: 1-2 hours)

- **Goal**: Create new coordinator_chore_operations.py file with proper imports, type hints, and class skeleton.

- **Steps / detailed work items**
  1. `[ ]` Create `custom_components/kidschores/coordinator_chore_operations.py`
     - Add file header docstring: "Chore lifecycle operations for KidsChoresDataCoordinator"
     - Import required types from type_defs (ChoreData, KidData, etc.)
     - Import const, kc_helpers, notification_helper
     - Use `from typing import TYPE_CHECKING` to avoid circular imports

  2. `[ ]` Define ChoreOperations class skeleton

     ```python
     class ChoreOperations:
         """Chore lifecycle operations: claim, approve, disapprove, scheduling.

         This class provides all chore-related coordinator methods via multiple
         inheritance. Methods access coordinator state through `self` (parent
         coordinator instance).

         Extracted from coordinator.py to improve code organization without
         changing behavior. All logic remains identical to original.
         """
     ```

  3. `[ ]` Add TYPE_CHECKING block for coordinator reference
     ```python
     if TYPE_CHECKING:
         from .coordinator import KidsChoresDataCoordinator
     ```

- **Key issues**
  - None anticipated. Standard Python file creation.

---

### Phase 2 – Method Extraction (Est: 8-12 hours)

- **Goal**: Move 20+ chore methods from coordinator.py to ChoreOperations class. Zero logic changes.

#### 2.1 Core Lifecycle Methods (Priority 1)

- **Steps**
  1. `[ ]` Extract `claim_chore()` (line 2945, ~700 lines)
     - Service entry point for kid claiming chore
     - Includes validation, state checks, timestamp logic
     - Calls: `_can_claim_chore()`, `_process_chore_state()`, `_notify_kid()`

  2. `[ ]` Extract `approve_chore()` (line ~3162, ~460 lines)
     - Service entry point for parent approval
     - Complex: points, streaks, badges, achievements, notifications
     - **Most complex method** - handle carefully

  3. `[ ]` Extract `disapprove_chore()` (line 3643, ~120 lines)
     - Simpler: reverts claim, no point changes

  4. `[ ]` Extract `_process_chore_state()` (line 4299, ~290 lines)
     - Central state machine logic
     - Updates kid_chore_data with timestamps
     - Handles SHARED_ALL vs INDEPENDENT logic

#### 2.2 Support Methods (Priority 2)

- **Steps**
  1. `[ ]` Extract `_update_chore_data_for_kid()` (line 4590, ~140 lines)
     - Updates kid's chore_data dict with new state/timestamps

  2. `[ ]` Extract `_can_claim_chore()` (find line, ~60 lines)
     - Validation logic: already claimed? completed by other? pending?

  3. `[ ]` Extract `_add_kid_to_chore_tracking_lists()` (line ~2850, ~60 lines)
     - SHARED_ALL helper: adds kid to claimed_by/completed_by

  4. `[ ]` Extract `_clear_chore_claimed_completed_by()` (line ~2920, ~40 lines)
     - Clears claimed_by/completed_by fields

#### 2.3 Scheduling Methods (Priority 3)

- **Steps**
  1. `[ ]` Extract `_reschedule_shared_recurring_chore()` (line 9511, ~35 lines)
     - Resets shared chore for next occurrence

  2. `[ ]` Extract `_reschedule_independent_recurring_chore()` (line 9545, ~180 lines)
     - Resets independent chore per-kid

  3. `[ ]` Extract `_reset_shared_chore_status()` (line 9723, ~80 lines)
     - Midnight reset for shared chores

  4. `[ ]` Extract `_reset_independent_chore_status()` (line 9800, ~290 lines)
     - Midnight reset for independent chores

  5. `[ ]` Extract `_reschedule_chore_next_due_date()` (line 10094, ~85 lines)
     - Calculates next due date using schedule_engine

  6. `[ ]` Extract `_reschedule_chore_next_due_date_for_kid()` (line 10178, ~130 lines)
     - Per-kid due date calculation

#### 2.4 Utility Methods (Priority 4)

- **Steps**
  1. `[ ]` Extract `_update_chore()` (line 1325, ~50 lines)
     - Updates chore definition in storage

  2. `[ ]` Extract `_update_chore_badge_references_for_kid()` (line 6930, ~80 lines)
     - Updates badge tracked_chores when chore claimed/approved
     - **Note**: This bridges chore→badge logic (acceptable)

- **Key issues**
  - **Method calls across features**: approve_chore() calls `_check_badges_for_kid()` (badge logic). This is OK - coordinator has all methods via multiple inheritance.
  - **Notification calls**: Many methods call `_notify_kid()` (notification operations). Extract notifications separately later.
  - **Line numbers may shift**: Verify line numbers during extraction.

---

### Phase 3 – Integration (Est: 2 hours)

- **Goal**: Update coordinator.py to use ChoreOperations via multiple inheritance.

- **Steps / detailed work items**
  1. `[ ]` Add import to coordinator.py (line ~50)

     ```python
     from .coordinator_chore_operations import ChoreOperations
     ```

  2. `[ ]` Update KidsChoresDataCoordinator class definition (line ~67)

     ```python
     # OLD
     class KidsChoresDataCoordinator(DataUpdateCoordinator):

     # NEW
     class KidsChoresDataCoordinator(ChoreOperations, DataUpdateCoordinator):
         """Coordinator for KidsChores integration.

         Organized via operations classes:
         - ChoreOperations: Chore lifecycle methods
         (More operations classes to be added in future phases)
         """
     ```

  3. `[ ]` Remove extracted methods from coordinator.py
     - Delete lines for all methods moved to ChoreOperations
     - Verify no duplicate definitions remain

  4. `[ ]` Verify import statements in coordinator.py
     - Ensure all imports needed by remaining methods are present
     - ChoreOperations handles its own imports

- **Key issues**
  - **Multiple inheritance order**: ChoreOperations BEFORE DataUpdateCoordinator (Python MRO)
  - **Method resolution**: If method exists in both classes, ChoreOperations wins (desired)

---

### Phase 4 – Validation (Est: 2-3 hours)

- **Goal**: Prove zero behavioral changes via automated testing.

- **Steps / detailed work items**
  1. `[ ]` Run MyPy type checking

     ```bash
     mypy custom_components/kidschores/
     ```

     - **Success criteria**: 0 errors (same as before)
     - If errors appear: likely circular import or missing TYPE_CHECKING

  2. `[ ]` Run pytest full suite

     ```bash
     python -m pytest tests/ -v --tb=line
     ```

     - **Success criteria**: 782/782 passing (exact same count)
     - **Critical**: No test file changes should be needed
     - Services call `coordinator.claim_chore()` which resolves via inheritance

  3. `[ ]` Run quick_lint.sh

     ```bash
     ./utils/quick_lint.sh --fix
     ```

     - **Success criteria**: 9.5+/10 score maintained
     - May need to fix import ordering or docstring issues

  4. `[ ]` Verify line count reduction
     ```bash
     wc -l custom_components/kidschores/coordinator.py
     wc -l custom_components/kidschores/coordinator_chore_operations.py
     ```

     - **Expected**: coordinator.py ~10,750 lines (was 11,952)
     - **Expected**: coordinator_chore_operations.py ~1,200 lines

- **Key issues**
  - **Test failures**: If ANY test fails, stop and investigate. This should be impossible if logic unchanged.
  - **Import errors**: Likely circular import - use TYPE_CHECKING pattern.
  - **Attribute errors**: Method calls may fail if inheritance order wrong.

---

### Phase 5 – Documentation (Est: 1 hour)

- **Goal**: Update documentation to reflect new file structure.

- **Steps / detailed work items**
  1. `[ ]` Update ARCHITECTURE.md § "Core Components"
     - Add entry for coordinator_chore_operations.py
     - Explain operations class pattern
     - Note: "Uses Python multiple inheritance to organize code by feature"

  2. `[ ]` Update coordinator.py module docstring (line 1-10)
     - Add: "Organized via operations classes (see coordinator\_\*\_operations.py)"

  3. `[ ]` Add coordinator_chore_operations.py to code tour docs (if exists)

  4. `[ ]` Update COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md
     - Mark Phase 2.5a as complete
     - Note actual line counts achieved
     - Document any unexpected issues

- **Key issues**
  - None anticipated.

---

## Testing & validation

### Pre-Extraction Baseline

**Capture before starting**:

- `[ ]` MyPy errors: **\_** (should be 0)
- `[ ]` Pytest results: \_\_\_/782 passing
- `[ ]` Lint score: **\_**/10
- `[ ]` coordinator.py line count: 11,952

### Post-Extraction Validation

**Must match or improve**:

- `[ ]` MyPy errors: 0 (no new errors introduced)
- `[ ]` Pytest results: 782/782 passing (exact match)
- `[ ]` Lint score: 9.5+ (maintained or better)
- `[ ]` coordinator.py line count: ~10,750 (-1,200)
- `[ ]` coordinator_chore_operations.py line count: ~1,200

### Specific Test Scenarios to Verify

**Service-based tests** (most important):

- `[ ]` `tests/test_services.py::test_claim_chore` - Kid claims chore
- `[ ]` `tests/test_services.py::test_approve_chore` - Parent approves
- `[ ]` `tests/test_services.py::test_disapprove_chore` - Parent disapproves
- `[ ]` `tests/test_workflow_chores.py` - Full chore lifecycle workflows

**Workflow tests**:

- `[ ]` `tests/test_workflow_chores.py::test_shared_chore_multi_kid` - SHARED_ALL logic
- `[ ]` `tests/test_workflow_chores.py::test_independent_chore_per_kid` - INDEPENDENT logic
- `[ ]` `tests/test_workflow_chores.py::test_chore_scheduling` - Reset/reschedule

**Button entity tests**:

- `[ ]` `tests/test_button.py` - Button entities call coordinator methods

### Test Failure Protocol

**If ANY test fails**:

1. STOP extraction immediately
2. Check for:
   - Missing import in coordinator_chore_operations.py
   - Method accidentally removed from coordinator.py
   - Circular import causing initialization failure
3. Fix issue before proceeding
4. Re-run ALL tests (not just failed ones)

---

## Notes & follow-up

### Extraction Guidelines

**DO**:

- ✅ Copy methods exactly as-is (including comments, line breaks)
- ✅ Keep all docstrings unchanged
- ✅ Preserve all const.LOGGER.debug() calls
- ✅ Use TYPE_CHECKING for coordinator type hints
- ✅ Test after EACH phase (don't wait until end)

**DON'T**:

- ❌ Refactor logic during extraction ("while we're here...")
- ❌ Rename methods or parameters
- ❌ Change error handling patterns
- ❌ Add new features
- ❌ "Improve" code - that comes later

### Implementation Order

**Why chores first?**

1. **Largest cohesive group**: ~1,200 lines of clearly related methods
2. **Well-defined boundaries**: Chore lifecycle is conceptually distinct
3. **Service entry points**: claim/approve/disapprove are top-level services
4. **Test coverage**: Excellent test coverage for validation

### Future Phases

**After chore operations complete**:

- Phase 2.5b: coordinator_badge_operations.py (~1,945 lines)
- Phase 2.5c: coordinator_reward_operations.py (~500 lines)
- Phase 2.5d: coordinator_achievement_operations.py (~300 lines)
- Phase 2.5e: coordinator_points_operations.py (~400 lines)
- Phase 2.5f: coordinator_notification_operations.py (~600 lines)

**End goal**: coordinator.py ~3,000 lines (core + init only)

### Architectural Notes

**Why multiple inheritance works here**:

- Operations classes are **not mixins in Django sense** (no state)
- They're **method containers** that access coordinator state via `self`
- No diamond problem (only DataUpdateCoordinator has initialization)
- Python MRO is straightforward: ChoreOperations → DataUpdateCoordinator → object

**What this ISN'T**:

- ❌ Not dependency injection (operations don't have their own instances)
- ❌ Not composition (no `self.chore_ops` attribute)
- ❌ Not strategy pattern (no interface contracts)

**What this IS**:

- ✅ Organizational pattern for large classes
- ✅ Python's standard approach to code organization
- ✅ Used throughout Home Assistant core (20+ examples)

### Risk Mitigation

**Circular import prevention**:

```python
# In coordinator_chore_operations.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import KidsChoresDataCoordinator

# In coordinator.py
from .coordinator_chore_operations import ChoreOperations
# No problem - ChoreOperations doesn't import coordinator at runtime
```

**Method resolution verification**:

```python
# After integration, verify:
coordinator = KidsChoresDataCoordinator(...)
assert hasattr(coordinator, 'claim_chore')  # From ChoreOperations
assert hasattr(coordinator, '_async_update_data')  # From DataUpdateCoordinator
```

---

## Success Criteria Summary

| Criterion                  | Target                | Status |
| -------------------------- | --------------------- | ------ |
| **Tests passing**          | 782/782               | `[ ]`  |
| **MyPy errors**            | 0                     | `[ ]`  |
| **Lint score**             | 9.5+/10               | `[ ]`  |
| **coordinator.py lines**   | ~10,750 (from 11,952) | `[ ]`  |
| **New file lines**         | ~1,200                | `[ ]`  |
| **Test file changes**      | 0 files modified      | `[ ]`  |
| **Services working**       | All chore services OK | `[ ]`  |
| **Docs updated**           | ARCHITECTURE.md       | `[ ]`  |
| **No logic changes**       | Code identical        | `[ ]`  |
| **Import cycles resolved** | No circular imports   | `[ ]`  |

**Definition of Done**: All checkboxes above checked, plan moved to `docs/completed/COORDINATOR_CHORE_OPERATIONS_COMPLETE.md`.
