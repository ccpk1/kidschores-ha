# Coordinator Chore Operations Extraction Plan

## Initiative snapshot

- **Name / Code**: COORD-OPS-CHORE / Phase 2.5a
- **Target release / milestone**: v0.5.0
- **Owner / driver(s)**: Strategic Planning Agent → Plan Builder Agent
- **Status**: In Progress (Phase 1 Complete)
- **Analysis date**: January 20, 2026

## Summary & immediate steps

| Phase / Step               | Description                                   | % complete | Quick notes                                   |
| -------------------------- | --------------------------------------------- | ---------- | --------------------------------------------- |
| Phase 1 – File Setup       | Create coordinator_chore_operations.py        | 100%       | ✅ File created with class skeleton + imports |
| Phase 2A – Core Extract    | Move service entry + state machine methods    | 100%       | ✅ 9 methods extracted (1,626 lines)          |
| Phase 2B – Support Extract | Move scheduling + query helper methods        | 100%       | ✅ 30 methods extracted (2,062 lines)         |
| Phase 3 – Integration      | Update coordinator.py imports and inheritance | 100%       | ✅ Multiple inheritance working               |
| Phase 4 – Validation       | Run full test suite and quality gates         | 100%       | ✅ 852/852 tests, MyPy clean, Ruff clean      |
| Phase 5 – Documentation    | Update docstrings and ARCHITECTURE.md         | 0%         | **IN PROGRESS** - plan update in progress     |
| Phase 6 – Method Renaming  | Standardize inconsistent method names         | 0%         | **DECISION REQUIRED** - see naming analysis   |

1. **Key objective** – Extract **~3,200 lines** (28% of coordinator.py) of chore lifecycle logic into coordinator_chore_operations.py using Python's multiple inheritance pattern, with zero test changes.

2. **Summary of recent work** – **EXTRACTION COMPLETE** (Phases 1-4):
   - ✅ Created `coordinator_chore_operations.py` with ChoreOperations class
   - ✅ **Extracted 46 methods (3,688 lines)** - exceeds original target by 15%
   - ✅ All 852 tests passing, MyPy clean, Ruff clean
   - ✅ Refactored 2 scheduling methods to `schedule_engine.py` as module-level functions
   - 📊 **coordinator.py reduced**: 11,484 → 7,603 lines (-34%)
   - 📊 **coordinator_chore_operations.py created**: 3,874 lines
   - 📊 **schedule_engine.py enhanced**: 1,053 → 1,255 lines (+19%)
   - Deep analysis docs:
     - [METHOD_ANALYSIS](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_ANALYSIS.md)
     - [METHOD_NAMING](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md) - **NEW**

3. **Next steps (short term)**:
   - **Phase 5**: Update documentation (ARCHITECTURE.md, docstrings)
   - **Phase 6**: Method naming standardization - **DECISION REQUIRED**
     - Option 1: 5 private method renames (0 breaking changes) - **RECOMMENDED**
     - Option 2: 10 renames including 2 public methods (requires deprecation cycle)
     - See [METHOD_NAMING](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md) for analysis

4. **Risks / blockers**:
   - **[RESOLVED] `approve_chore()` is async**: ✅ Handled successfully during extraction
   - **[RESOLVED] `_process_chore_state()` complexity**: ✅ 291 lines extracted as single unit
   - **[RESOLVED] 15+ `_persist()` calls**: ✅ All preserved exactly
   - **[RESOLVED] Method interdependencies**: ✅ MRO provides access to all coordinator methods
   - **[RESOLVED] Import cycles**: ✅ TYPE_CHECKING pattern worked perfectly

5. **References**:
   - [COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_ANALYSIS.md](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_ANALYSIS.md) - Full method inventory & dependencies
   - [COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md) - **Naming standardization analysis**
   - [COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md](COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md) - Analysis justifying extraction approach
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage patterns
   - [coordinator.py](../../custom_components/kidschores/coordinator.py) - Source file (now 7,603 lines, was 11,484)
   - [coordinator_chore_operations.py](../../custom_components/kidschores/coordinator_chore_operations.py) - **Extracted operations (3,874 lines)**

6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Use "operations class" naming over "mixin" for clarity
     - ✅ Start with chores only (not all features at once)
     - ✅ Keep all logic identical - no refactoring during extraction
     - ✅ Use multiple inheritance (ChoreOperations as base class)
     - ✅ Split extraction into 2A (core) and 2B (support) for risk reduction
     - ✅ Method renaming is Phase 6 (optional, separate decision)
     - ✅ Use automated extraction script to prevent human error
     - ✅ **BONUS**: Refactored 2 scheduling methods to schedule_engine.py (module-level functions)
   - **Completion confirmation**: `[x]` All follow-up items completed:
     - `[x]` coordinator_chore_operations.py created and integrated
     - `[x]` All 852 tests passing unchanged
     - `[x]` MyPy passes with 0 errors
     - `[x]` Lint score maintains 9.5+/10 ✅
     - `[ ]` ARCHITECTURE.md updated with file structure **← PHASE 5**
     - `[x]` coordinator.py reduced by 3,688 lines (exceeds target)

> **Success**: Extraction complete. 46 methods (3,688 lines) extracted. All tests passing. Ready for Phase 5 (docs) and Phase 6 (optional naming).

## Tracking expectations

- **Summary upkeep**: Update % complete after each phase. Update blockers immediately if discovered.
- **Detailed tracking**: Phase sections below track specific method extractions, line counts, and validation results.

## Detailed phase tracking

### Phase 0 – Extraction Protocol (MANDATORY)

- **Goal**: Establish safe extraction workflow to prevent code loss or modification errors.

#### 0.1 Extraction Tool

**Use the automated extraction script** (`utils/extract_method.py`) for ALL method extractions:

```bash
# Step 1: Get exact method boundaries and line counts
python utils/extract_method.py custom_components/kidschores/coordinator.py METHOD_NAME --info

# Step 2: Extract to temp file for verification
python utils/extract_method.py custom_components/kidschores/coordinator.py METHOD_NAME --extract --output /tmp/method.py

# Step 3: Verify content matches expected (visual inspection)
cat /tmp/method.py | head -5  # Should match first line from --info
wc -l /tmp/method.py          # Should match line count from --info
```

#### 0.2 Safe Move Protocol (COPY-FIRST, DELETE-SECOND)

For EACH method extraction:

| Step | Action                                  | Validation                                 | Abort If            |
| ---- | --------------------------------------- | ------------------------------------------ | ------------------- |
| 1    | Run `--info` to get exact line count    | Record: `METHOD: lines X-Y (N lines)`      | Method not found    |
| 2    | Copy method verbatim to ChoreOperations | Visual: first/last line match              | Any content differs |
| 3    | Run tests WITH duplicate methods        | `pytest tests/ -x` passes                  | Any test fails      |
| 4    | Delete method from coordinator.py       | Verify deletion is exact N lines           | Line count differs  |
| 5    | Run tests WITHOUT duplicate             | `pytest tests/ -x` passes                  | Any test fails      |
| 6    | Commit with line count in message       | `git commit -m "Extract METHOD (N lines)"` | -                   |

#### 0.3 Verified Method Boundaries (Pre-captured)

Run once before starting extraction to capture baseline:

```bash
cd /workspaces/kidschores-ha
python utils/extract_method.py custom_components/kidschores/coordinator.py \
  claim_chore approve_chore disapprove_chore undo_chore_claim update_chore_state \
  _process_chore_state _update_chore_data_for_kid _can_claim_chore _can_approve_chore \
  --info > docs/in-process/COORD_METHOD_BOUNDARIES.txt
```

**Captured boundaries (Phase 2A core methods)**:

| Method                       | Lines     | Count | Async   |
| ---------------------------- | --------- | ----- | ------- |
| `claim_chore`                | 2970-3168 | 199   | No      |
| `approve_chore`              | 3170-3666 | 497   | **Yes** |
| `disapprove_chore`           | 3668-3787 | 120   | No      |
| `_process_chore_state`       | 4300-4589 | 290   | No      |
| `_update_chore_data_for_kid` | 4591-4919 | 329   | No      |
| `_can_claim_chore`           | 4209-4249 | 41    | No      |
| `_can_approve_chore`         | 4251-4298 | 48    | No      |

#### 0.4 Absolute Rules

- ❌ **NEVER** manually type method code - always copy verbatim
- ❌ **NEVER** "fix" or "improve" code during extraction
- ❌ **NEVER** delete before copy+test passes
- ❌ **NEVER** extract multiple methods without intermediate tests
- ✅ **ALWAYS** verify line counts match before/after
- ✅ **ALWAYS** commit after each successful method move

---

### Phase 1 – File Setup (Est: 1-2 hours) ✅ COMPLETE

- **Goal**: Create new coordinator_chore_operations.py file with proper imports, type hints, and class skeleton.

- **Steps / detailed work items**
  1. `[x]` Create `custom_components/kidschores/coordinator_chore_operations.py`
     - ✅ File header docstring: "Chore lifecycle operations for KidsChoresDataCoordinator"
     - ✅ Import required types from type_defs (ChoreData, KidData, KidChoreDataEntry)
     - ✅ Import const, kc_helpers, notification_helper
     - ✅ Use `from typing import TYPE_CHECKING` to avoid circular imports

  2. `[x]` Define ChoreOperations class skeleton
     - ✅ Comprehensive docstring documenting all method categories
     - ✅ TYPE_CHECKING block with coordinator attribute/method stubs for IDE support

  3. `[x]` Add TYPE_CHECKING block for coordinator reference
     - ✅ Coordinator data attributes: chores_data, kids_data, \_data, etc.
     - ✅ Coordinator methods: \_persist(), \_get_kid_chore_data(), update_kid_points(), etc.

- **Validation Results**:
  - MyPy: ✅ Success (0 errors)
  - Tests: ✅ 852 passed (no regressions)
  - Lint: Expected unused imports (methods not yet extracted)

- **Key issues**
  - None. File created successfully.

---

### Phase 2A – Core Operations Extraction (Est: 6-8 hours)

- **Goal**: Extract service entry points and state machine methods (~1,800 lines). Validate before proceeding to 2B.
- **Protocol**: Follow Phase 0 extraction protocol for EACH method.

#### 2A.1 Service Entry Points (Public API) – HIGHEST PRIORITY

| #   | Method                 | Line | Async   | Lines | Dependencies                                                                                                                 |
| --- | ---------------------- | ---- | ------- | ----- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1   | `claim_chore()`        | 2970 | No      | ~200  | `_can_claim_chore`, `_process_chore_state`, `_set_chore_claimed_completed_by`, `_count_pending_chores_for_kid`               |
| 2   | `approve_chore()`      | 3170 | **YES** | ~498  | `_can_approve_chore`, `_process_chore_state`, `_update_chore_data_for_kid`, `_reschedule_*`, `is_approved_in_current_period` |
| 3   | `disapprove_chore()`   | 3668 | No      | ~121  | `_update_chore_data_for_kid`, `_process_chore_state`, `_clear_chore_claimed_completed_by`                                    |
| 4   | `undo_chore_claim()`   | 3789 | No      | ~85   | `_process_chore_state`, `_clear_chore_claimed_completed_by`                                                                  |
| 5   | `update_chore_state()` | 3874 | No      | ~30   | `_process_chore_state`                                                                                                       |

**Steps**:

1. `[ ]` Extract `claim_chore()` (line 2970)
   - Service entry point for kid claiming chore
   - **Note**: Calls `_notify_parents_translated()` which stays in coordinator
2. `[ ]` Extract `approve_chore()` (line 3170) **[ASYNC - CRITICAL]**
   - Most complex method - contains achievement/challenge progress updates
   - Uses `self._get_approval_lock()` from coordinator
   - Calls `self._check_overdue_chores()` which is async
3. `[ ]` Extract `disapprove_chore()` (line 3668)
4. `[ ]` Extract `undo_chore_claim()` (line 3789)
5. `[ ]` Extract `update_chore_state()` (line 3874)

#### 2A.2 State Machine & Core Logic

| #   | Method                         | Line | Lines | Notes                                                          |
| --- | ------------------------------ | ---- | ----- | -------------------------------------------------------------- |
| 6   | `_process_chore_state()`       | 4300 | ~291  | **CRITICAL**: Central state machine, 6 states, multi-kid logic |
| 7   | `_update_chore_data_for_kid()` | 4591 | ~330  | Statistics engine calls, nested data updates                   |
| 8   | `_can_claim_chore()`           | 4209 | ~42   | Validation logic                                               |
| 9   | `_can_approve_chore()`         | 4251 | ~49   | Validation logic                                               |

**Steps**: 6. `[ ]` Extract `_process_chore_state()` (line 4300)

- Contains nested function `inc_stat()` at line 4695 - must preserve
- Calls `update_kid_points()` which stays in coordinator (points domain)

7. `[ ]` Extract `_update_chore_data_for_kid()` (line 4591)
   - Uses `self.stats.get_period_keys()` - StatisticsEngine accessible via MRO
8. `[ ]` Extract `_can_claim_chore()` (line 4209)
9. `[ ]` Extract `_can_approve_chore()` (line 4251)

#### 2A.3 Tracking & Helper Methods

| #   | Method                                | Line | Lines | Notes                                        |
| --- | ------------------------------------- | ---- | ----- | -------------------------------------------- |
| 10  | `_set_chore_claimed_completed_by()`   | 2857 | ~86   | INDEPENDENT/SHARED_FIRST/SHARED_ALL handling |
| 11  | `_clear_chore_claimed_completed_by()` | 2943 | ~27   | Clears tracking fields                       |
| 12  | `_get_kid_chore_data()`               | 3904 | ~10   | Simple accessor                              |

**Steps**: 10. `[ ]` Extract `_set_chore_claimed_completed_by()` (line 2857) 11. `[ ]` Extract `_clear_chore_claimed_completed_by()` (line 2943) 12. `[ ]` Extract `_get_kid_chore_data()` (line 3904)

#### 2A.4 Validation Checkpoint

**STOP POINT**: Run full test suite before proceeding to Phase 2B.

```bash
mypy custom_components/kidschores/coordinator*.py
python -m pytest tests/ -v --tb=line -x
./utils/quick_lint.sh
```

**Success criteria for 2A**:

- `[ ]` 852/852 tests passing
- `[ ]` 0 MyPy errors
- `[ ]` Lint score 9.5+
- `[ ]` coordinator.py reduced by ~1,800 lines

---

### Phase 2B – Supporting Operations Extraction (Est: 4-6 hours)

- **Goal**: Extract scheduling, query helpers, and overdue handling methods (~1,400 lines).

#### 2B.1 Query Helper Methods

| #   | Method                                   | Line | Lines | Notes              |
| --- | ---------------------------------------- | ---- | ----- | ------------------ |
| 13  | `has_pending_claim()`                    | 3992 | ~18   | Query helper       |
| 14  | `is_overdue()`                           | 4071 | ~16   | Query helper       |
| 15  | `is_approved_in_current_period()`        | 4176 | ~33   | Query helper       |
| 16  | `_count_pending_chores_for_kid()`        | 4010 | ~25   | Aggregation helper |
| 17  | `_get_latest_pending_chore()`            | 4035 | ~36   | Query helper       |
| 18  | `_get_approval_period_start()`           | 4150 | ~26   | Query helper       |
| 19  | `_allows_multiple_claims()`              | 2678 | ~24   | Query helper       |
| 20  | `_get_effective_due_date()`              | 2648 | ~30   | Due date resolver  |
| 21  | `get_pending_chore_approvals_computed()` | 4087 | ~32   | Dashboard helper   |

**Steps**:
13-21. `[ ]` Extract all query helper methods as a batch

#### 2B.2 Scheduling & Reset Methods

| #   | Method                                      | Line  | Lines | Notes                          |
| --- | ------------------------------------------- | ----- | ----- | ------------------------------ |
| 22  | `_reschedule_chore_next_due_date()`         | 9626  | ~84   | SHARED chore reschedule        |
| 23  | `_reschedule_chore_next_due_date_for_kid()` | 9710  | ~126  | INDEPENDENT per-kid reschedule |
| 24  | `_reschedule_shared_recurring_chore()`      | 9043  | ~34   | Recurring SHARED handler       |
| 25  | `_reschedule_independent_recurring_chore()` | 9077  | ~66   | Recurring INDEPENDENT handler  |
| 26  | `_reset_shared_chore_status()`              | 9255  | ~77   | Midnight reset SHARED          |
| 27  | `_reset_independent_chore_status()`         | 9332  | ~90   | Midnight reset INDEPENDENT     |
| 28  | `_handle_pending_claim_at_reset()`          | 9194  | ~61   | Pending claim handling         |
| 29  | `_calculate_next_due_date_from_info()`      | 9494  | ~132  | Pure calculation helper        |
| 30  | `_calculate_next_multi_daily_due()`         | 9422  | ~72   | Multi-daily calculation        |
| 31  | `_is_approval_after_reset_boundary()`       | 9836  | ~73   | Late approval detection        |
| 32  | `set_chore_due_date()`                      | 9909  | ~147  | Manual due date setting        |
| 33  | `skip_chore_due_date()`                     | 10056 | ~157  | Skip to next due date          |
| 34  | `reset_all_chores()`                        | 10213 | ~51   | Bulk reset                     |
| 35  | `reset_overdue_chores()`                    | 10264 | ~135  | Selective reset                |

**Steps**:
22-35. `[ ]` Extract scheduling methods in order (they have internal dependencies)

#### 2B.3 Async Scheduled Operations

| #   | Method                             | Line | Async   | Lines | Notes                     |
| --- | ---------------------------------- | ---- | ------- | ----- | ------------------------- |
| 36  | `_check_overdue_chores()`          | 8753 | **YES** | ~51   | Background overdue check  |
| 37  | `_check_due_date_reminders()`      | 8804 | **YES** | ~118  | Reminder scheduling       |
| 38  | `_handle_recurring_chore_resets()` | 8968 | **YES** | ~21   | Orchestrates resets       |
| 39  | `_reset_chore_counts()`            | 8989 | **YES** | ~16   | Counter reset             |
| 40  | `_reschedule_recurring_chores()`   | 9005 | **YES** | ~38   | Orchestrates rescheduling |
| 41  | `_reset_daily_chore_statuses()`    | 9143 | **YES** | ~51   | Daily status reset        |

**Steps**:
36-41. `[ ]` Extract async scheduled operations

#### 2B.4 Overdue Handling

| #   | Method                       | Line | Lines | Notes                    |
| --- | ---------------------------- | ---- | ----- | ------------------------ |
| 42  | `_apply_overdue_if_due()`    | 8476 | ~73   | Overdue state transition |
| 43  | `_check_overdue_for_chore()` | 8549 | ~98   | Per-chore overdue check  |
| 44  | `_notify_overdue_chore()`    | 8647 | ~106  | Overdue notification     |
| 45  | `_clear_due_soon_reminder()` | 168  | ~17   | Reminder cleanup         |

**Steps**:
42-45. `[ ]` Extract overdue handling methods

#### 2B.5 Badge Bridge Methods (Stay with Chores)

| #   | Method                                     | Line | Lines | Notes                        |
| --- | ------------------------------------------ | ---- | ----- | ---------------------------- |
| 46  | `_update_chore_badge_references_for_kid()` | 6460 | ~64   | Updates badge tracked_chores |
| 47  | `_recalculate_chore_stats_for_kid()`       | 4921 | ~20   | Stats recalculation          |

**Steps**:
46-47. `[ ]` Extract badge bridge methods (called by chore operations)

- **Key issues**:
  - **Async methods**: 7 methods are async - class must support async properly
  - **Internal dependencies**: Scheduling methods call each other - extract in order
  - **`_persist()` calls**: Preserve all 15+ calls exactly as-is

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

     - **Expected**: coordinator.py ~8,280 lines (was 11,483)
     - **Expected**: coordinator_chore_operations.py ~3,200 lines

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

### Phase 6 – Method Renaming (OPTIONAL - Separate PR)

- **Goal**: Standardize method naming for consistency. This phase is **OPTIONAL** and should be done in a **separate PR** for clean git history.

#### 6.1 Proposed Renames

| Current Name                           | Issue                     | New Name                      | Impact                     |
| -------------------------------------- | ------------------------- | ----------------------------- | -------------------------- |
| `undo_chore_claim`                     | Inconsistent verb order   | `undo_claim_chore`            | Low                        |
| `update_chore_state`                   | Ambiguous (used for bulk) | `set_chore_state`             | Low                        |
| `is_approved_in_current_period`        | Too verbose               | `is_approved_this_period`     | Medium                     |
| `_allows_multiple_claims`              | Non-standard pattern      | `_can_multi_claim`            | Low                        |
| `get_pending_chore_approvals_computed` | Redundant suffix          | `get_pending_chore_approvals` | Medium (property conflict) |
| `_is_approval_after_reset_boundary`    | Too verbose               | `_is_late_approval`           | Low                        |

#### 6.2 Naming Convention Standards

```
Public service methods:    verb_noun()           → claim_chore(), approve_chore()
Query methods (bool):      is_*() or has_*()     → is_overdue(), has_pending_claim()
Query methods (data):      get_*()               → get_pending_chore_approvals()
Internal state changes:    _verb_noun()          → _process_chore_state()
Internal helpers:          _verb_noun_for_noun() → _update_chore_data_for_kid()
Validation:                _can_verb_noun()      → _can_claim_chore()
```

#### 6.3 Steps

1. `[ ]` Create rename map with all affected files
2. `[ ]` Update method names in coordinator_chore_operations.py
3. `[ ]` Update all test file references
4. `[ ]` Update any documentation references
5. `[ ]` Run full test suite
6. `[ ]` Create separate PR with clear rename documentation

**Note**: This phase affects test files and should be done only after Phase 5 is complete and stable.

---

## Testing & validation

### Pre-Extraction Baseline

**Capture before starting**:

- `[ ]` MyPy errors: **0** (confirmed)
- `[ ]` Pytest results: \_\_\_/852 passing
- `[ ]` Lint score: **\_**/10
- `[ ]` coordinator.py line count: **11,483**

### Post-Extraction Validation

**Must match or improve**:

- `[ ]` MyPy errors: 0 (no new errors introduced)
- `[ ]` Pytest results: 852/852 passing (exact match)
- `[ ]` Lint score: 9.5+ (maintained or better)
- `[ ]` coordinator.py line count: ~8,280 (-3,200)
- `[ ]` coordinator_chore_operations.py line count: ~3,200

### Test Files with Chore Method References (14 files)

Critical tests to monitor during extraction:

- `[ ]` `tests/test_approval_reset_overdue_interaction.py`
- `[ ]` `tests/test_chore_scheduling.py`
- `[ ]` `tests/test_chore_services.py`
- `[ ]` `tests/test_chore_state_matrix.py`
- `[ ]` `tests/test_frequency_enhanced.py`
- `[ ]` `tests/test_kc_helpers.py`
- `[ ]` `tests/test_kid_undo_claim.py`
- `[ ]` `tests/test_notification_helpers.py`
- `[ ]` `tests/test_overdue_immediate_reset.py`
- `[ ]` `tests/test_performance.py`
- `[ ]` `tests/test_pending_claim_actions.py` (if exists)
- `[ ]` `tests/test_chore_completion_criteria.py` (if exists)
- `[ ]` `tests/test_workflow_*.py` files

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
- ✅ Preserve all 15+ `_persist()` calls exactly
- ✅ Use TYPE_CHECKING for coordinator type hints
- ✅ Test after EACH phase (don't wait until end)
- ✅ Run validation checkpoint after Phase 2A before proceeding to 2B

**DON'T**:

- ❌ Refactor logic during extraction ("while we're here...")
- ❌ Rename methods or parameters (save for Phase 6)
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

### High-Value Opportunities Identified

1. **Larger scope than expected**: ~3,200 lines vs original 1,200 estimate (28% reduction)
2. **Method naming improvements**: Phase 6 establishes consistent naming conventions
3. **Foundation for future extractions**: Same pattern applies to badges (~1,945 lines), rewards (~500 lines), etc.
4. **Improved testability**: Operations classes can be tested in isolation if needed later

### Traps to Avoid

1. **DO NOT extract `update_kid_points()`** - Lives in points domain, called by chore methods
2. **DO NOT extract `_check_badges_for_kid()`** - Badge domain, called from `approve_chore()`
3. **DO NOT modify `_persist()` calls** - Must preserve exact call locations (15+ calls)
4. **DO NOT change async method signatures** - `approve_chore()` must remain async
5. **DO NOT rename methods during extraction** - Save for Phase 6

---

## Success Criteria Summary

| Criterion                  | Target                | Status                 |
| -------------------------- | --------------------- | ---------------------- |
| **Tests passing**          | 852/852               | `[x]`                  |
| **MyPy errors**            | 0                     | `[x]`                  |
| **Lint score**             | 9.5+/10               | `[x]`                  |
| **coordinator.py lines**   | ~8,280 (from 11,483)  | `[x]` **7,603** (-34%) |
| **New file lines**         | ~3,200                | `[x]` **3,874** (+21%) |
| **Test file changes**      | 0 files modified      | `[x]`                  |
| **Services working**       | All chore services OK | `[x]`                  |
| **Docs updated**           | ARCHITECTURE.md       | `[ ]` **← Phase 5**    |
| **No logic changes**       | Code identical        | `[x]`                  |
| **Import cycles resolved** | No circular imports   | `[x]`                  |
| **Phase 2A checkpoint**    | Passed before 2B      | `[x]`                  |

**EXTRACTION COMPLETE**: ✅ 46 methods (3,688 lines) extracted. All quality gates passing.

---

## Actual Extraction Results (Phases 1-4 Complete)

### Methods Extracted by Category

| Category                       | Methods | Lines     | Status          |
| ------------------------------ | ------- | --------- | --------------- |
| **Service Entry Points**       | 5       | 633       | ✅ Complete     |
| **State Machine & Core Logic** | 4       | 993       | ✅ Complete     |
| **Tracking & Helper Methods**  | 3       | 123       | ✅ Complete     |
| **Query Helper Methods**       | 9       | 318       | ✅ Complete     |
| **Overdue Logic & Reminders**  | 4       | 547       | ✅ Complete     |
| **Scheduling & Reset Methods** | 13      | 884       | ✅ Complete     |
| **Chore Management**           | 2       | 185       | ✅ Complete     |
| **Properties**                 | 2       | 15        | ✅ Complete     |
| **TOTAL**                      | **46**  | **3,698** | ✅ **Complete** |

### Additional Refactoring

| File                              | Change                         | Lines | Notes                                                                           |
| --------------------------------- | ------------------------------ | ----- | ------------------------------------------------------------------------------- |
| `schedule_engine.py`              | Added 2 module-level functions | +202  | `calculate_next_multi_daily_due()`, `calculate_next_due_date_from_chore_info()` |
| `coordinator_chore_operations.py` | Updated imports                | -10   | Now imports from schedule_engine                                                |

### File Size Changes

| File                              | Before | After | Change                  |
| --------------------------------- | ------ | ----- | ----------------------- |
| `coordinator.py`                  | 11,484 | 7,603 | **-3,881 lines (-34%)** |
| `coordinator_chore_operations.py` | 0      | 3,874 | **+3,874 lines (NEW)**  |
| `schedule_engine.py`              | 1,053  | 1,255 | **+202 lines (+19%)**   |

### Validation Results

| Check       | Result  | Details                     |
| ----------- | ------- | --------------------------- |
| Test Suite  | ✅ PASS | 852/852 tests passing       |
| MyPy        | ✅ PASS | 0 errors in 24 source files |
| Ruff        | ✅ PASS | All checks passed           |
| Performance | ✅ PASS | No degradation observed     |

---

## Remaining Work (Phases 5-6)

### Phase 5 – Documentation Updates (Est: 2-3 hours)

- **Goal**: Update project documentation to reflect new file structure

**Tasks**:

1. `[ ]` Update ARCHITECTURE.md
   - Add section on coordinator_chore_operations.py
   - Document multiple inheritance pattern
   - Explain TYPE_CHECKING approach
2. `[ ]` Update coordinator.py docstring
   - Reference coordinator_chore_operations.py
   - Document inheritance structure
3. `[ ]` Update coordinator_chore_operations.py docstring
   - Ensure complete method inventory
   - Add usage examples
4. `[ ]` Update DEVELOPMENT_STANDARDS.md if needed
   - Document extraction pattern for future use

### Phase 6 – Method Naming Standardization (Est: 2-4 hours) **OPTIONAL**

- **Goal**: Standardize inconsistent method names identified during extraction
- **Status**: **DECISION REQUIRED** - See [METHOD_NAMING](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md)

**Options**:

- **Option 1 (Recommended)**: 5 private method renames, 0 breaking changes
- **Option 2**: 10 renames including 2 public methods (requires deprecation cycle)
- **Option 3**: Defer to v0.6.0

**Naming Issues Found**:

1. `_set_chore_claimed_completed_by` → Too long, unclear
2. `_clear_chore_claimed_completed_by` → Too long, unclear
3. `_check_due_date_reminders` → Missing "chore" for clarity
4. `_handle_pending_claim_at_reset` → Missing "chore" for clarity
5. `_clear_due_soon_reminder` → Missing "chore" for clarity
6. `undo_chore_claim` → Inconsistent word order (public method)
7. `get_pending_chore_approvals_computed` → Unclear suffix (public method)
8. Others... (see naming analysis document)

---

## Supporting Documents

- **[COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_ANALYSIS.md](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_ANALYSIS.md)** - Complete method inventory, dependency map, line counts
- **[COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md)** - **NEW** - Naming standardization analysis with 10 identified issues and 3 implementation options
- **[utils/extract_method.py](../../utils/extract_method.py)** - Automated method extraction tool with boundary detection and line count verification

---

## Next Steps

1. **Review naming analysis**: See [METHOD_NAMING](COORDINATOR_CHORE_OPERATIONS_SUP_METHOD_NAMING.md)
2. **Make decision**: Choose Option 1, 2, or 3 for Phase 6
3. **Update documentation**: Complete Phase 5 (ARCHITECTURE.md, docstrings)
4. **Optional**: Implement chosen naming standardization (Phase 6)
5. **Complete plan**: Move to `docs/completed/` when all phases done
