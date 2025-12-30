# Chore Enhancements Plan – Simplified (Phases 1-4 Summary + Phase 5 Details)

## Summary table

| Phase | Feature               | Status         | Tests | Date   |
| ----- | --------------------- | -------------- | ----- | ------ |
| 1     | Show on Calendar      | ✅ COMPLETE    | 3/3   | Dec 20 |
| 2     | Auto Approve          | ✅ COMPLETE    | 9/9   | Dec 27 |
| 3     | Completion Criteria   | ✅ COMPLETE    | 18/18 | Dec 29 |
| 4     | Approval Reset Timing | ✅ COMPLETE    | 39/39 | Dec 30 |
| 5     | Overdue Handling      | 🔄 IN PROGRESS | -     | Dec 29 |
| 6     | Multiple Time Slots   | 📋 FUTURE      | -     | Future |

---

## Phases 1-4: Completed Work

### Phase 1 – Show on Calendar ✅

**Implemented**: Calendar visibility toggle for each chore

- ✅ 3 constants (`DATA_CHORE_SHOW_ON_CALENDAR`, `CONF_CHORE_SHOW_ON_CALENDAR`, translation key)
- ✅ UI checkbox field in config/options flow
- ✅ Calendar filtering logic (only shows chores with `show_on_calendar=True`)
- ✅ Migration (sets field=True for all existing chores)
- ✅ Test suite: 3 tests covering basic functionality, backward compatibility, migration
- **Validation**: Linting 10.00/10, all project tests passing (563/573)

---

### Phase 2 – Auto Approve ✅

**Implemented**: Automatic approval when chores are claimed

- ✅ 2 constants (`DATA_CHORE_AUTO_APPROVE`, `CONF_CHORE_AUTO_APPROVE`)
- ✅ UI checkbox field in config/options flow
- ✅ Core logic: Auto-approval on claim if `auto_approve=True`
- ✅ Migration (sets field=False for all existing chores)
- ✅ Notifications for auto-approved vs manually approved chores
- ✅ Parent override: Can disapprove auto-approved chores
- ✅ Test suite: 9 tests covering approval modes, notifications, edge cases, migration
- **Validation**: Linting 9.90/10, all project tests passing (572/572)

---

### Phase 3 – Completion Criteria ✅

**Implemented**: Fixed INDEPENDENT mode bugs + added SHARED_FIRST mode

**Sprint 1 Fixes**:

- ✅ Fixed overdue checking to use per-kid due dates (not chore-level)
- ✅ Added per-kid due date configuration in config/options flow
- ✅ Migration: Copy chore-level due dates to all kids

**Sprint 3 Additions**:

- ✅ Replaced `shared_chore` boolean with `completion_criteria` enum (3 modes: INDEPENDENT, SHARED_ALL, SHARED_FIRST)
- ✅ Implemented SHARED_FIRST mode: first kid to complete marks chore done for others
- ✅ Dashboard shows `completed_by_other` state for SHARED_FIRST
- ✅ Updated 11 coordinator references to use enum

**Deliverables**:

- ✅ 8 constants for enum values, default, config keys, translation keys
- ✅ UI dropdown field in config/options flow
- ✅ 3 modes fully implemented in coordinator (claim, approval, state logic)
- ✅ Migration (boolean→enum + per-kid due dates)
- ✅ Test suite: 18 tests covering all 3 modes, interactions, edge cases

**Note**: Sprint 4 (ALTERNATING mode) deferred pending user feedback

- **Validation**: Linting 10.00/10, all project tests passing (630/630)

---

### Phase 4 – Approval Reset Timing ✅

**Implemented**: 5 reset modes controlling when/how often chores can be reclaimed

**5 Modes**:

- `AT_MIDNIGHT_ONCE`: One claim per day, reset at midnight
- `AT_MIDNIGHT_MULTI`: Multiple claims per day, reset at midnight
- `AT_DUE_DATE_ONCE`: One claim per cycle, reset at due date
- `AT_DUE_DATE_MULTI`: Multiple claims per cycle, reset at due date
- `UPON_COMPLETION`: Unlimited claims (no reset gate)

**Deliverables**:

- ✅ 11 constants (5 enum values, OPTIONS list, DEFAULT, config keys, translation keys)
- ✅ Core logic: Period tracking with timestamps, `is_approved_in_current_period()`, `_can_claim_chore()`, `_can_approve_chore()`
- ✅ UI dropdown field in config/options flow
- ✅ Migration (deprecated `allow_multiple_claims_per_day` boolean→enum)
- ✅ Translations: All 5 option labels in en.json
- ✅ Sensor attributes: `approval_reset_type`, `next_approval_allowed`, `can_claim_now`
- ✅ Test suite: 39 tests covering all 5 modes, time boundaries, edge cases, backward compatibility

- **Validation**: Linting 10.00/10, all project tests passing (669/669)

---

## Phase 5: Overdue Handling (DESIGN COMPLETE)

**Goal**: Implement flexible overdue handling with 2 independent configuration fields

### Design Complete (Dec 29, 2025)

**Two new fields for chore configuration:**

#### Field 1: `overdue_handling_type` (3 modes)

| Value                    | User Label                             | Behavior                                  |
| ------------------------ | -------------------------------------- | ----------------------------------------- |
| `AT_DUE_DATE`            | "Overdue until complete"               | Shows overdue, stays until kid completes  |
| `NEVER_OVERDUE`          | "Never overdue"                        | Never shows overdue, reschedules silently |
| `AT_DUE_DATE_THEN_RESET` | "Overdue until complete or next reset" | Shows overdue, clears at next reset       |

**Default**: `AT_DUE_DATE` (current behavior)

#### Field 2: `approval_reset_pending_claim_action` (3 modes)

| Value                  | User Label               | Behavior at Reset                         |
| ---------------------- | ------------------------ | ----------------------------------------- |
| `HOLD_PENDING`         | "Hold for parent review" | Pending claim persists, blocks new claims |
| `CLEAR_PENDING`        | "Clear and start fresh"  | Pending claim dropped, new instance       |
| `AUTO_APPROVE_PENDING` | "Auto-approve at reset"  | System approves, then new instance        |

**Default**: `CLEAR_PENDING` (current behavior)

### Key Design Decisions

- ✅ Reset timing follows `approval_reset_type` from Phase 4
- ✅ Notify once when becomes overdue (not repeated reminders)
- ✅ Shared chores: All kids get fresh instance at reset
- ✅ Overdue state calculated real-time (no storage field)
- ✅ No automatic points penalty (use existing bonus/penalty system)
- ✅ Dashboard attributes: `is_overdue`, `days_overdue`, `overdue_handling_type`, `next_reset_time`, `pending_claim_action`

### Shared Chore Behavior

- **SHARED_ALL** + reset: All kids get fresh instance regardless of who completed
- **SHARED_FIRST** + reset: All kids get fresh instance
- **Pending claims**: Evaluated per-kid (one kid's pending doesn't affect others)

**Per-Kid vs Per-Chore Application**:

- `overdue_handling_type`: Stored at CHORE level, affects all assigned kids
- `approval_reset_pending_claim_action`: Stored at CHORE level, but evaluated PER-KID at reset

### Implementation Steps (6 Steps)

| Step | Task             | Status  | Details                                                                                                                                         |
| ---- | ---------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | **Constants**    | ✅ DONE | Added 15 constants to const.py (enums, options, defaults, keys)                                                                                 |
| 2    | **Translations** | ✅ DONE | Added user labels to en.json for both dropdowns                                                                                                 |
| 3    | **Core Logic**   | ✅ DONE | Modified coordinator.py: `_check_overdue_independent`, `_check_overdue_shared`, `_reset_shared_chore_status`, `_reset_independent_chore_status` |
| 4    | **UI Fields**    | ⬜      | Add 2 dropdowns to chore create/edit in flow_helpers.py                                                                                         |
| 5    | **Migration**    | ⬜      | Set defaults for existing chores (AT_DUE_DATE, CLEAR_PENDING)                                                                                   |
| 6    | **Tests**        | ⬜      | 12+ scenarios covering all mode combinations                                                                                                    |

**Estimated effort**: ~8 hours remaining (Steps 4-6)

See **[PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md)** for full design document.

---

## Phase 6: Multiple Time Slots (FUTURE)

**Goal**: Schedule same chore at multiple times per day with independent tracking

**Status**: Deferred to future phase

**Estimated effort**: 14-18 hours

---

## Summary: Why Phases 1-4 Complete

| Phase       | Why Complete                        | Evidence                            |
| ----------- | ----------------------------------- | ----------------------------------- |
| 1           | All features implemented, tested    | 3/3 tests ✅, 10.00/10 linting ✅   |
| 2           | All features implemented, tested    | 9/9 tests ✅, 9.90/10 linting ✅    |
| 3           | Bugs fixed + new mode added, tested | 18/18 tests ✅, 10.00/10 linting ✅ |
| 4           | All 5 modes implemented, tested     | 39/39 tests ✅, 10.00/10 linting ✅ |
| 5           | Design complete, ready for impl     | Design approved Dec 29, 2025        |
| **Project** | **Zero regressions**                | **669/669 tests passing** ✅        |

---

## Phase 5 Design Rationale

**Key design decisions for v0.4.0 schema v42:**

1. **Two independent fields** instead of complex multi-option framework:

   - `overdue_handling_type`: Controls if/when chore shows overdue
   - `approval_reset_pending_claim_action`: Controls what happens to pending claims at reset

2. **Separation of concerns**: Pending claim behavior is separate from overdue handling because a kid might claim on time but parent doesn't approve before reset - that's an approval workflow issue, not the kid being late.

3. **Shared chore simplicity**: At reset, all kids get fresh instance (no complex partial-completion logic).

4. **Reuse Phase 4 timing**: Reset follows `approval_reset_type` boundaries (no third timing concept).

See [PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md) for full design document with implementation plan.

---

## Key Documentation

- [PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md) - Complete design decisions and implementation plan
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage schema v42, migration patterns
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Quality standards, testing patterns
