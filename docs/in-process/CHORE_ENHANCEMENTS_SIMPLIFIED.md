# Chore Enhancements Plan – Simplified (Phases 1-4 Summary + Phase 5 Details)

## Summary table

| Phase | Feature               | Status          | Tests | Date    |
| ----- | --------------------- | --------------- | ----- | ------- |
| 1     | Show on Calendar      | ✅ COMPLETE     | 3/3   | Dec 20  |
| 2     | Auto Approve          | ✅ COMPLETE     | 9/9   | Dec 27  |
| 3     | Completion Criteria   | ✅ COMPLETE     | 18/18 | Dec 29  |
| 4     | Approval Reset Timing | ✅ COMPLETE     | 39/39 | Dec 30  |
| 5     | Overdue Handling      | ⏳ DESIGN PHASE | -     | Pending |
| 6     | Multiple Time Slots   | 📋 FUTURE       | -     | Future  |

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

## Phase 5: Overdue Handling (DESIGN PHASE)

**Goal**: Implement 2 overdue modes controlling how overdue chores behave

### 2 Modes to Implement

**HOLD_UNTIL_COMPLETE**: Chore stays on kid's list until explicitly marked complete (can be days/weeks late)

**RESET_REGARDLESS**: Chore auto-resets at next reset period boundary regardless of completion

### Critical Design Questions (MUST ANSWER BEFORE IMPLEMENTATION)

**Before Phase 5 begins, answer these 7 questions:**

1. **RESET_REGARDLESS Auto-Reset Timing** → When/how should reset happen?

   - Option A: At approval period boundary (RECOMMENDED)
   - Option B: At chore-level due date
   - Option C: At separate "reset frequency" boundary

2. **HOLD_UNTIL_COMPLETE Notification Frequency** → How often should we notify?

   - Option A: Once when becomes overdue (RECOMMENDED)
   - Option B: Daily reminders while overdue
   - Option C: Escalating reminders (increasing over time)

3. **Multi-Kid Overdue Behavior** → For SHARED_ALL/SHARED_FIRST chores, what happens at reset?

   - Does reset affect completed kids or only uncompleted?
   - Document scenarios for SHARED_ALL and SHARED_FIRST modes

4. **Overdue State Tracking** → Where should overdue state be stored?

   - Option A: Calculated real-time (RECOMMENDED)
   - Option B: Cached in storage (per-kid field)
   - Option C: Hybrid (recalculate hourly)

5. **Points and Overdue Chores** → Should points be adjusted for late completion?

   - Option A: No penalty/bonus (RECOMMENDED)
   - Option B: Penalty based on days overdue
   - Option C: Configurable per chore
   - Option D: Refer to existing penalty/bonus system

6. **Dashboard Helper Attributes** → Which dashboard attributes are essential?

   - Select at least 5 from: `is_overdue`, `days_overdue`, `overdue_since`, `overdue_mode`, `can_reset_now`, `next_reset_time`, `notification_count`
   - Optional nice-to-haves: `overdue_reason`, `completions_while_overdue`

7. **Interaction with Phases 3 & 4** → How should overdue modes interact with completion_criteria and approval_reset_type?
   - Document behavior for complex scenarios (SHARED_FIRST+RESET_REGARDLESS+AT_DUE_DATE_ONCE, etc.)

### Design Documents

See **[PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md)** for:

- Detailed explanation of each question
- Options with pros/cons
- Specific test scenarios
- Interaction matrix with previous phases

### Implementation Steps (After Questions Answered)

1. **Update const.py** with design decisions (2-3 new constants)
2. **Design test scenarios** based on answers
3. **Implement core logic** in coordinator.py
4. **Add UI field** to flow_helpers.py (dropdown: HOLD vs RESET)
5. **Implement notifications** for overdue/reset events
6. **Add dashboard attributes** (per Question 6 selections)
7. **Comprehensive testing** (covering all interaction scenarios)

**Estimated effort after design**: 10-12 hours

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
| **Project** | **Zero regressions**                | **669/669 tests passing** ✅        |

---

## Why Phase 5 is in Design Phase

**Phase 5 has multiple valid design options that affect implementation approach:**

- **Reset timing**: When overdue chore resets (period boundary? due date? separate frequency?)
- **Multi-kid interactions**: How reset behaves for shared chores (affects all kids? only incomplete?)
- **Points strategy**: Should late completion be penalized? (affects reward system design)
- **Dashboard visibility**: What info should dashboard show about overdue chores?

**These decisions must be made BEFORE implementation** to avoid rework.

See [PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md) for complete analysis of all options.

---

## Key Documentation

- [PHASE5_DESIGN_QUESTIONS.md](PHASE5_DESIGN_QUESTIONS.md) - Design questions needing answers
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage schema v42, migration patterns
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Quality standards, testing patterns
