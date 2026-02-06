# Strategic Analysis: v0.5.1 Chore Feature Enhancements

## Initiative snapshot

- **Name / Code**: CHORE-FEATURES-V051 (Missed State, Due Window Claim Restrictions, Rotation Completion Criteria)
- **Target release / milestone**: v0.5.1 (post-beta stabilization)
- **Owner / driver(s)**: @ad-ha (product), TBD (implementation)
- **Status**: Analysis / Planning

## Summary & immediate steps

| Phase / Step              | Description                                          | % complete | Quick notes                                  |
| ------------------------- | ---------------------------------------------------- | ---------- | -------------------------------------------- |
| Phase 0 – Analysis        | Strategic analysis of 3 feature sets, identify traps | 100%       | This document                                |
| Phase 1 – Missed State    | New "missed" tracking mechanism for overdue chores   | 0%         | Stats tracking, new overdue handling options |
| Phase 2 – Due Window Lock | Restrict claims until due window opens               | 0%         | New reset timing options, unavailable state  |
| Phase 3 – Rotation Chores | Assignment rotation for shared chores                | 0%         | New completion criteria, index tracking      |

1. **Key objective** – Analyze three proposed chore feature enhancements to identify opportunities to leverage existing framework, unexpected complexities, and potential traps before implementation.

2. **Summary of recent work** – Completed deep analysis of:
   - Current chore state machine and FSM transitions
   - Overdue handling type options
   - Completion criteria mechanics (INDEPENDENT, SHARED, SHARED_FIRST)
   - Statistics engine period tracking patterns
   - Signal-based manager communication

3. **Next steps (short term)** – Decision required on:
   - Feature priority order
   - Whether to tackle as single initiative or split into three
   - Schema version bump strategy (one increment vs. per-feature)

4. **Risks / blockers** – See detailed analysis below for each feature's complexity assessment

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, storage, layered architecture
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding patterns, event architecture
   - [CHORE_TIMER_REFACTOR_COMPLETE.md](../completed/CHORE_TIMER_REFACTOR_COMPLETE.md) - Current overdue/approval reset mechanics

6. **Decisions & completion check**
   - **Decisions captured**: See "Strategic Recommendations" section
   - **Completion confirmation**: `[ ]` Analysis reviewed and approved before implementation begins

---

## Feature 1: Missed State Tracking

### 1.1 Concept Summary

Add a mechanism to track when chores are "missed" (not completed on time) for statistical purposes, without necessarily changing the visible chore state.

**Three trigger mechanisms proposed:**

1. **Service-based**: Optional flag when rescheduling an overdue chore via service
2. **Overdue Handling Option A**: "Mark as Missed until Approval Reset (Prevents Claims)" - visible state change
3. **Overdue Handling Option B**: "Overdue Until Approval Reset (Mark as Missed)" - stats-only tracking

### 1.2 Opportunity Analysis ✅

| Opportunity                                           | How to Leverage                                                             | Benefit                                               |
| ----------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Statistics Engine already tracks "overdue" counts** | Add parallel `missed` metric alongside existing `overdue` in period buckets | Minimal schema change                                 |
| **Signal infrastructure exists**                      | Add `SIGNAL_SUFFIX_CHORE_MISSED` to existing event catalog                  | GamificationManager can listen for badges             |
| **Period bucket structure**                           | `DATA_KID_CHORE_DATA_PERIOD_MISSED` follows existing pattern                | Consistent with `approved`, `claimed`, `overdue` etc. |
| **`_process_overdue()` already scans chores**         | Extend to handle new overdue handling types                                 | Single touch point for new logic                      |
| **Due date local time conversion exists**             | `as_local(due_date)` pattern already used for stats bucketing               | Correct daily period assignment                       |

### 1.3 Complexity Analysis ⚠️

| Complexity                               | Description                                                                                     | Mitigation                                                                                          |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Overdue handling option validation**   | New options only valid with certain combinations (like existing `OVERDUE_UNTIL_APPROVAL_RESET`) | Extend `_validate_overdue_handling_compatibility()` in flow_helpers.py                              |
| **State vs. Stats distinction**          | Option A changes visible state; Option B is stats-only                                          | Clear naming: `OVERDUE_HANDLING_MISSED_UNTIL_RESET` vs. `OVERDUE_HANDLING_AT_DUE_DATE_TRACK_MISSED` |
| **Can a missed chore still be claimed?** | Option A says "Prevents Claims" - need new state                                                | Add `CHORE_STATE_MISSED` to FSM with transitions only to `PENDING` (on approval reset)              |
| **Service reschedule with missed flag**  | Need to record stat BEFORE rescheduling (due date determines bucket)                            | Extract due date, call `record_missed()`, THEN reschedule                                           |

### 1.4 Trap Analysis 🚨

| Trap                                             | Why It's Dangerous                                                                              | Prevention                                                                                                                          |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **"Missed" as a state vs. "Missed" as an event** | Conflating these leads to confusion. State = visible. Event = happened once, recorded in stats. | Document clearly: `CHORE_STATE_MISSED` is a blocking state; `chore_missed` is an event that increments stats                        |
| **Timezone for stats bucket**                    | If `record_missed()` uses UTC date, chore due at 11PM local might record to wrong day           | ALWAYS use `as_local(due_date_utc).date()` for period key generation                                                                |
| **Double-counting**                              | If Option A (state-based) also emits event, and listener already counted...                     | Emit `SIGNAL_SUFFIX_CHORE_MISSED` exactly ONCE per miss occurrence                                                                  |
| **Shared chore missed by whom?**                 | SHARED chore has one due date but multiple kids                                                 | For SHARED: record missed for ALL assigned kids who haven't completed. For SHARED_FIRST: record only for "next in rotation" or all? |

### 1.5 Schema Impact

```python
# New constants needed:
CHORE_STATE_MISSED = "missed"  # New FSM state (Option A only)
SIGNAL_SUFFIX_CHORE_MISSED = "chore_missed"  # Event signal

# New overdue handling types:
OVERDUE_HANDLING_MISSED_UNTIL_RESET = "missed_until_approval_reset"  # Option A
OVERDUE_HANDLING_AT_DUE_DATE_TRACK_MISSED = "at_due_date_track_missed"  # Option B

# New period metric:
DATA_KID_CHORE_DATA_PERIOD_MISSED = "missed"

# Service field:
SERVICE_FIELD_CHORE_RESCHEDULE_MARK_AS_MISSED = "mark_as_missed"  # Boolean

# Validation: These new options require same validation as existing AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
```

### 1.6 Affected Files

| File                             | Changes                                                              |
| -------------------------------- | -------------------------------------------------------------------- |
| `const.py`                       | New constants (state, signal, overdue handling types, period metric) |
| `engines/chore_engine.py`        | Add `CHORE_STATE_MISSED` to `VALID_TRANSITIONS`                      |
| `managers/chore_manager.py`      | Extend `_process_overdue()`, add `record_missed()`                   |
| `managers/statistics_manager.py` | Listen for `SIGNAL_SUFFIX_CHORE_MISSED`, increment period bucket     |
| `services.py`                    | Add optional `mark_as_missed` field to reschedule service            |
| `helpers/flow_helpers.py`        | Extend `_validate_overdue_handling_compatibility()`                  |
| `translations/en.json`           | Labels for new options                                               |

### 1.7 Recommendation

**Implementation Approach**: "Stats-only by default" pattern

- Start with Option B (event/stat tracking) which has lowest risk
- Option A (state-based blocking) can be added later if needed
- Service flag is orthogonal and easy to add

**Estimated Effort**: Medium (15-20 hours)

- Constants + FSM update: 2h
- Statistics tracking: 4h
- Overdue handling logic: 4h
- Service integration: 2h
- Testing: 4h
- Documentation: 2h

---

## Feature 2: Due Window Claim Restrictions (Reset Timing Options)

### 2.1 Concept Summary

Add two new "Completions Allowed - Reset Timing" options that restrict when a chore can be claimed based on the due window:

1. **"Once in or after Due Window - Resets at midnight"** - Chore unavailable until due window opens; resets at midnight
2. **"Once in Due Window - Resets at due date"** - Chore unavailable until due window; unavailable again after due passes; resets at due date

### 2.2 Current State Review

**Existing Options** (`DATA_CHORE_APPROVAL_RESET_TYPE`):

- `at_midnight_once` - Claimable anytime, single claim per day
- `at_midnight_multi` - Claimable anytime, multiple claims per day
- `at_due_date_once` - Claimable anytime, resets when due passes
- `at_due_date_multi` - Claimable anytime, resets when due passes
- `upon_completion` - Immediate reset after approval

**Key Insight**: Current options control WHEN reset happens, not WHEN claim is allowed. The new feature adds a "when can claim" dimension.

### 2.3 Opportunity Analysis ✅

| Opportunity                       | How to Leverage                                                          | Benefit                               |
| --------------------------------- | ------------------------------------------------------------------------ | ------------------------------------- |
| **Due window already exists**     | `DATA_CHORE_DUE_WINDOW_OFFSET` defines window start relative to due date | No new concept to introduce           |
| **`can_claim` logic centralized** | `ChoreEngine.can_claim()` or similar validation point                    | Single place to add window check      |
| **`CHORE_STATE_DUE` exists**      | Already have "in due window" state concept                               | Visual feedback infrastructure exists |
| **`_process_due_window()` timer** | Already runs 5-minute checks on due window                               | Can update state when window opens    |

### 2.4 Complexity Analysis ⚠️

| Complexity                           | Description                                                       | Mitigation                                                                              |
| ------------------------------------ | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Unavailable vs. Pending**          | Need clear distinction - chore exists but can't be claimed yet    | Either: (a) new state `UNAVAILABLE`, or (b) keep `PENDING` but enforce in `can_claim()` |
| **Validation: requires due_window**  | These options only make sense with a due window offset configured | Flow validation: error if `due_window_offset` is null/0 when these selected             |
| **"After due window"**               | Option 1 allows claims after due too; Option 2 doesn't            | Different implementations needed                                                        |
| **What happens to existing chores?** | Migration consideration if changing option                        | Default to no-change (existing behavior preserved)                                      |

### 2.5 Trap Analysis 🚨

| Trap                             | Why It's Dangerous                                                   | Prevention                                                                            |
| -------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **Confusing option names**       | Long names are hard to translate/display                             | Consider UX: group as "Claim Window: Always / Due Window Only / Due Window Strict"    |
| **INDEPENDENT vs SHARED timing** | INDEPENDENT chores have per-kid due dates; which due window applies? | For INDEPENDENT: each kid's due window. For SHARED: chore-level due window.           |
| **State proliferation**          | Adding `UNAVAILABLE` state means more FSM transitions to manage      | Alternative: Soft enforcement via `can_claim()` returning False, keep `PENDING` state |
| **UI feedback gap**              | If chore is `PENDING` but can't claim, user is confused              | Dashboard needs to show "Available in X hours" - requires UI helper changes           |
| **Timer race condition**         | What if user tries to claim right as window opens?                   | `can_claim()` must be the source of truth, not state                                  |

### 2.6 Design Decision: State vs. Soft Enforcement

**Option A: New `CHORE_STATE_UNAVAILABLE`**

- Pros: Clear state machine, visible in UI, consistent pattern
- Cons: FSM complexity, migration risk, more transitions to test

**Option B: Soft enforcement via `can_claim()` only**

- Pros: Simpler, no FSM changes, backward compatible
- Cons: State doesn't reflect claimability, dashboard must derive

**Recommendation**: **Option B (Soft Enforcement)** with enhanced `can_claim()` that returns a structured result:

```python
@dataclass
class ClaimEligibility:
    can_claim: bool
    reason: str  # "ok", "not_in_due_window", "already_claimed", etc.
    available_at: datetime | None  # When claim becomes available
```

### 2.7 Schema Impact

```python
# New approval reset types (extend existing list):
APPROVAL_RESET_IN_DUE_WINDOW_MIDNIGHT = "in_due_window_at_midnight"
APPROVAL_RESET_IN_DUE_WINDOW_AT_DUE_DATE = "in_due_window_at_due_date"

# Validation helper constant:
APPROVAL_RESET_TYPES_REQUIRING_DUE_WINDOW = [
    APPROVAL_RESET_IN_DUE_WINDOW_MIDNIGHT,
    APPROVAL_RESET_IN_DUE_WINDOW_AT_DUE_DATE,
]
```

### 2.8 Affected Files

| File                        | Changes                                                   |
| --------------------------- | --------------------------------------------------------- |
| `const.py`                  | New approval reset type constants                         |
| `engines/chore_engine.py`   | Enhance `can_claim()` to check due window when applicable |
| `managers/chore_manager.py` | Use enhanced claim eligibility in claim operations        |
| `helpers/flow_helpers.py`   | Validation: require due_window_offset for new options     |
| `managers/ui_manager.py`    | Add `available_at` to chore data for dashboard            |
| `translations/en.json`      | Option labels                                             |

### 2.9 Recommendation

**Implementation Approach**: Soft enforcement with enhanced claim eligibility

- Avoid new state to minimize FSM complexity
- Return structured result from `can_claim()` including availability timing
- Dashboard helper exposes `available_at` for UI countdown

**Estimated Effort**: Medium (12-16 hours)

- Constants + validation: 2h
- `can_claim()` enhancement: 4h
- Dashboard helper: 2h
- Timer integration: 2h
- Testing: 4h
- Documentation: 2h

---

## Feature 3: Rotation-Based Shared Chores

### 3.1 Concept Summary

Add rotation-based completion criteria for shared chores where kids take turns:

1. **Simple Rotation** - Index-based rotation through assigned kids
2. **Simple Rotation + Steal at Overdue** - Same, but becomes open when overdue
3. **Smart Rotation** - Least completions gets assignment (future)

### 3.2 Current State Review

**Existing Completion Criteria** (`DATA_CHORE_COMPLETION_CRITERIA`):

- `independent` - Each kid has their own instance
- `shared_all` - All kids must complete
- `shared_first` - First claimer wins

**Key Insight**: Rotation is similar to `shared_first` but with a predetermined order instead of first-come-first-served.

### 3.3 Opportunity Analysis ✅

| Opportunity                                    | How to Leverage                                   | Benefit                                  |
| ---------------------------------------------- | ------------------------------------------------- | ---------------------------------------- |
| **`shared_first` logic exists**                | Rotation is similar: one kid claims, others can't | Start from `shared_first` implementation |
| **`DATA_CHORE_CLAIMED_BY` / `COMPLETED_BY`**   | Already track who claimed/completed               | Can be reused for rotation               |
| **Per-kid chore data**                         | `chore_data[chore_id]` exists for each kid        | Track rotation index per kid             |
| **`_handle_completion_criteria()` dispatches** | Centralized criteria handling                     | Add rotation cases                       |

### 3.4 Complexity Analysis ⚠️

| Complexity                              | Description                                                  | Mitigation                                                             |
| --------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **Rotation index storage**              | Need to track "whose turn" persistently                      | Store `rotation_index` on chore (not kid)                              |
| **Order matters**                       | `assigned_kids` order defines rotation                       | Document that array order = rotation order                             |
| **Kid addition/removal**                | What if kid is unassigned mid-rotation?                      | On assignment change: reset index or adjust                            |
| **"Steal" semantics**                   | When overdue, who gets credit? Original assignee or stealer? | Only original assignee gets overdue stat; stealer gets completion stat |
| **Unavailable state for non-turn kids** | Should chore show as unavailable or just unclaimed?          | Similar to Feature 2: soft enforcement via `can_claim()`               |

### 3.5 Trap Analysis 🚨

| Trap                          | Why It's Dangerous                                                | Prevention                                                                  |
| ----------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Index drift**               | If `assigned_kids` array is reordered, index points to wrong kid  | Store kid_id not just index; recalculate index from kid_id if array changes |
| **Atomic rotation advance**   | Must advance index only after approval, not claim                 | Advance on `SIGNAL_SUFFIX_CHORE_APPROVED`, not claimed                      |
| **Steal window timing**       | "At overdue" - what if overdue check runs before kid could claim? | Grace period consideration, or make it "X hours after overdue"              |
| **Dashboard confusion**       | Kid sees chore but can't claim - why?                             | Clear UI indicator: "Sarah's turn" / "Available (overdue)"                  |
| **Smart rotation complexity** | "Least completions" requires aggregation query                    | Defer to v0.5.2; start with simple index rotation                           |

### 3.6 Proposed Data Model

```python
# New completion criteria values:
COMPLETION_CRITERIA_ROTATION = "rotation"
COMPLETION_CRITERIA_ROTATION_STEAL = "rotation_steal"
# Future: COMPLETION_CRITERIA_ROTATION_SMART = "rotation_smart"

# Chore-level rotation tracking:
DATA_CHORE_ROTATION_CURRENT_KID_ID = "rotation_current_kid_id"  # Who's turn
DATA_CHORE_ROTATION_INDEX = "rotation_index"  # Position in assigned_kids (backup)

# Per-kid tracking for rotation (in kid's chore_data):
DATA_KID_CHORE_DATA_ROTATION_COMPLETIONS = "rotation_completions"  # For smart rotation future
```

### 3.7 State/Visibility Model

| Scenario                       | State for Turn Kid | State for Other Kids          | Can Claim?    |
| ------------------------------ | ------------------ | ----------------------------- | ------------- |
| Rotation, pending, not overdue | `PENDING`          | `PENDING`                     | Turn kid only |
| Rotation, claimed              | `CLAIMED`          | `COMPLETED_BY_OTHER`          | No            |
| Rotation, approved             | `APPROVED`         | `COMPLETED_BY_OTHER`          | No            |
| Rotation+Steal, overdue        | `OVERDUE`          | `PENDING` (becomes claimable) | All kids      |

### 3.8 Affected Files

| File                        | Changes                                                                   |
| --------------------------- | ------------------------------------------------------------------------- |
| `const.py`                  | New completion criteria constants, rotation data keys                     |
| `engines/chore_engine.py`   | Add rotation criteria handling in `calculate_transition()`, `can_claim()` |
| `managers/chore_manager.py` | Rotation index management, advance on approval                            |
| `data_builders.py`          | Default rotation fields on chore creation                                 |
| `helpers/flow_helpers.py`   | Validation for rotation criteria                                          |
| `managers/ui_manager.py`    | "Whose turn" indicator for dashboard                                      |
| `translations/en.json`      | Labels                                                                    |
| `migration_pre_v50.py`      | Migration for existing chores if changing criteria                        |

### 3.9 Recommendation

**Implementation Approach**: Start simple, expand later

- Phase 3a: Simple Rotation only (`rotation`)
- Phase 3b: Add Steal at Overdue (`rotation_steal`)
- Phase 3c (v0.5.2+): Smart Rotation (least completions)

**Estimated Effort**: High (25-35 hours)

- Simple rotation: 15h
- Steal at overdue: 8h
- Testing: 8h
- Documentation: 4h

---

## Strategic Recommendations

### Priority Order

1. **Feature 1 (Missed State)** - Low risk, high value, builds on existing patterns
2. **Feature 2 (Due Window Lock)** - Medium risk, medium complexity
3. **Feature 3 (Rotation)** - Highest complexity, can be phased

### Schema Version Strategy

**Recommend**: Single schema bump (v44) for all three features

- Reduces migration overhead
- Features are additive (no breaking changes to existing data)
- New fields default to null/empty (backward compatible)

### Testing Strategy

All features should use existing test patterns:

- **Scenario fixtures**: `scenario_medium` for basic tests, `scenario_full` for complex
- **Service-based tests**: Test through services rather than direct manager calls
- **State matrix tests**: Extend `test_chore_state_matrix.py` for new states/transitions

### Dashboard Impact

All three features require dashboard helper changes:

- Feature 1: Add `missed_count` to stats
- Feature 2: Add `available_at` timestamp
- Feature 3: Add `rotation_turn_kid` indicator

**Recommend**: Create supporting document for dashboard changes.

---

## Decision Points Required

Before implementation begins, confirm:

1. **Feature 1**: Should `CHORE_STATE_MISSED` be a full FSM state (blocking claims) or stats-only?
2. **Feature 2**: Soft enforcement vs. new `UNAVAILABLE` state?
3. **Feature 2**: Option naming preferences for UI?
4. **Feature 3**: Start with simple rotation only, or include steal from day 1?
5. **Feature 3**: Smart rotation deferred to v0.5.2?
6. **All**: Single schema bump or incremental?

---

## Notes & follow-up

- This analysis document serves as the foundation for implementation plans
- Each feature should have its own detailed implementation plan created from this analysis
- Consider creating `CHORE_MISSED_STATE_IN-PROCESS.md`, `CHORE_DUE_WINDOW_LOCK_IN-PROCESS.md`, `CHORE_ROTATION_IN-PROCESS.md` as separate implementation plans

> **Analysis Status**: Complete. Ready for review and decision on implementation priority.
