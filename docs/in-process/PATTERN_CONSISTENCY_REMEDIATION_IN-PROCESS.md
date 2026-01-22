# Pattern Consistency Audit - CORRECTED STATUS

**Date**: 2026-01-21
**Status**: � **IN PROGRESS - Phase A Complete**

---

## Executive Summary

**Previous claim**: "All Phases 1-4 entities are consistent"
**Reality**: Only 4 of 8 entity types were fully migrated. Chores migration is now complete. Badges still have legacy `build_badge_common_data()` function.

---

## Actual Implementation Status (CORRECTED)

| Entity        | `validate_X_inputs()` in FH         | `build_X()` in EH             | Legacy `build_X_data()` in FH             | Status                   |
| ------------- | ----------------------------------- | ----------------------------- | ----------------------------------------- | ------------------------ |
| **Kids**      | ✅ `validate_kids_inputs()`         | ✅ `build_kid()`              | ❌ Removed                                | ✅ **DONE**              |
| **Parents**   | ✅ `validate_parents_inputs()`      | ✅ `build_parent()`           | ❌ Removed                                | ✅ **DONE**              |
| **Rewards**   | ✅ `validate_rewards_inputs()`      | ✅ `build_reward()`           | ❌ Never existed                          | ✅ **DONE**              |
| **Bonuses**   | ✅ `validate_bonuses_inputs()`      | ✅ `build_bonus_or_penalty()` | ❌ Removed                                | ✅ **DONE**              |
| **Penalties** | ✅ `validate_penalties_inputs()`    | ✅ `build_bonus_or_penalty()` | ❌ Removed                                | ✅ **DONE**              |
| **Chores**    | ✅ `validate_chores_inputs()`       | ✅ `build_chore()`            | ✅ **Removed**                            | ✅ **DONE**              |
| **Badges**    | ✅ `validate_badge_common_inputs()` | ✅ `build_badge()`            | ⚠️ **`build_badge_common_data()` EXISTS** | 🔴 **NOT DONE**          |
| **Points**    | ✅ `validate_points_inputs()`       | N/A (system config)           | ✅ `build_points_data()` (intentional)    | ⚠️ Intentional exception |

---

## What Was Actually Completed

1. ✅ Removed `build_kids_data()` from flow_helpers
2. ✅ Removed `build_parents_data()` from flow_helpers
3. ✅ Removed `build_bonuses_data()` from flow_helpers
4. ✅ Removed `build_penalties_data()` from flow_helpers
5. ✅ Removed `build_shadow_kid_data()` from flow_helpers
6. ✅ Created `validate_chores_inputs()` in flow_helpers
7. ✅ Updated `test_kids_helpers.py` to use entity_helpers
8. ✅ Updated `test_parents_helpers.py` to use entity_helpers
9. ✅ Updated `config_flow.py` bonuses/penalties to use entity_helpers

### Phase A Completion (2026-01-21)

10. ✅ Created `transform_chore_cfof_to_data()` in flow_helpers (~120 lines)
11. ✅ Updated `async_step_add_chore()` to use three-function pattern
12. ✅ Updated `async_step_edit_chore()` to use three-function pattern
13. ✅ Updated `async_step_chores()` in config_flow.py
14. ✅ Removed `build_chores_data()` from flow_helpers (~318 lines deleted)
15. ✅ Updated 8 tests in `test_frequency_validation.py` and `test_approval_reset_overdue_interaction.py`
16. ✅ All 882 tests passing
17. ✅ Lint/mypy validation passing

---

## What Was NOT Completed (Remaining Work)

### ✅ COMPLETED: Chores - `build_chores_data()` Removed

**Previously ~318 lines at flow_helpers.py lines 1033-1350**

**Migration Pattern Used**:

```python
# New three-function pattern:
errors, due_date_str = fh.validate_chores_inputs(user_input, kids_dict, existing)
if not errors:
    transformed = fh.transform_chore_cfof_to_data(user_input, kids_dict, due_date_str)
    chore = eh.build_chore(transformed)  # or eh.build_chore(transformed, existing=old)
```

### 🔴 Issue 2: Badges - `build_badge_common_data()` Still Exists and Is Used

**Location**: `flow_helpers.py` lines 2085-2640 (~555 lines!)

**Currently Used By**:

```
options_flow.py:2190 - async_step_badge_attributes_cumulative()
options_flow.py:2290 - async_step_badge_attributes_daily()
options_flow.py:2391 - async_step_badge_attributes_periodic()
options_flow.py:2490 - async_step_badge_attributes_special_occasion()
options_flow.py:2591 - async_step_badge_attributes_achievement_linked()
options_flow.py:2691 - async_step_badge_attributes_challenge_linked()
options_flow.py:2868 - async_step_edit_badge_attributes_cumulative()
options_flow.py:2962 - async_step_edit_badge_attributes_daily()
... (many more)
```

**Problem**:

- Returns simple dict (not tuple) but still mixes concerns
- `entity_helpers.build_badge()` exists but NOT used by flows
- Duplicates badge-building logic across two files

---

## Remediation Plan

### Phase A: Chores Migration ✅ COMPLETE

**Goal**: Wire up `validate_chores_inputs()` and remove `build_chores_data()`

#### Step A1: Analyze `build_chores_data()` Logic

- [x] Read `flow_helpers.py` lines 894-1150
- [x] Document what validation it does vs what building it does
- [x] Compare with existing `validate_chores_inputs()` - identify gaps
- [x] Compare with `entity_helpers.build_chore()` - identify gaps

#### Step A2: Create `transform_chore_cfof_to_data()` Function

- [x] Created ~120 line function for CFOF→DATA key transformation
- [x] Handles kid name→UUID conversion
- [x] Builds per_kid_due_dates dict
- [x] Extracts notification selections

#### Step A3: Update `options_flow.py` Add Chore Flow

- [x] Updated `async_step_add_chore()` with new pattern
- [x] Fixed TypedDict compatibility with `dict()` casts
- [x] Handled single-kid INDEPENDENT optimization

#### Step A4: Update `options_flow.py` Edit Chore Flow

- [x] Updated `async_step_edit_chore()` with new pattern
- [x] Uses `existing=` parameter for merging

#### Step A5: Remove `build_chores_data()` from flow_helpers

- [x] Deleted function (~318 lines, lines 1033-1350)
- [x] Verified no other callers exist
- [x] Updated config_flow.py `async_step_chores()`
- [x] Updated comment references

#### Step A6: Update Tests

- [x] Updated 4 tests in `test_frequency_validation.py`
- [x] Updated 4 tests in `test_approval_reset_overdue_interaction.py`
- [x] All 882 tests passing

---

### Phase B: Badges Migration

**Goal**: Remove `build_badge_common_data()` and use `entity_helpers.build_badge()`

#### Step B1: Analyze `build_badge_common_data()` Logic

- [ ] Read `flow_helpers.py` lines 2085-2640
- [ ] Document what it does vs `entity_helpers.build_badge()`
- [ ] Identify any missing functionality in entity_helpers

#### Step B2: Enhance `entity_helpers.build_badge()` If Needed

- [ ] Ensure all badge types are supported
- [ ] Ensure all fields are handled correctly
- [ ] Handle badge-type-specific components

#### Step B3: Create `validate_badge_inputs()` If Needed

- [ ] Check if `validate_badge_common_inputs()` covers all validation
- [ ] Add any missing validation logic

#### Step B4: Update All Badge Flows in options_flow.py

**Affected Methods** (~12 methods):

- `async_step_badge_attributes_cumulative()`
- `async_step_badge_attributes_daily()`
- `async_step_badge_attributes_periodic()`
- `async_step_badge_attributes_special_occasion()`
- `async_step_badge_attributes_achievement_linked()`
- `async_step_badge_attributes_challenge_linked()`
- `async_step_edit_badge_attributes_cumulative()`
- `async_step_edit_badge_attributes_daily()`
- `async_step_edit_badge_attributes_periodic()`
- `async_step_edit_badge_attributes_special_occasion()`
- `async_step_edit_badge_attributes_achievement_linked()`
- `async_step_edit_badge_attributes_challenge_linked()`

#### Step B5: Remove `build_badge_common_data()` from flow_helpers

- [ ] Delete function (lines 2085-2640, ~555 lines)
- [ ] Verify no other callers
- [ ] Run tests

#### Step B6: Update Badge Tests

- [ ] Check for direct callers of `build_badge_common_data()`
- [ ] Update to new pattern

---

### Phase C: Validation

- [ ] Run `./utils/quick_lint.sh --fix`
- [ ] Run `mypy custom_components/kidschores/`
- [ ] Run `python -m pytest tests/ -v`
- [ ] Verify all 882+ tests pass

---

## Estimated Effort

| Phase                | Lines to Change                                | Complexity | Status      |
| -------------------- | ---------------------------------------------- | ---------- | ----------- |
| Phase A (Chores)     | Added ~120 lines transform, deleted ~318 lines | Medium     | ✅ COMPLETE |
| Phase B (Badges)     | ~200 lines in options_flow, delete ~555 lines  | High       | ⏳ Pending  |
| Phase C (Validation) | N/A                                            | Low        | ⏳ Pending  |

**Remaining**: 2-4 hours for Phase B, 30 min for Phase C

---

## Decision Required

**Before proceeding with Phase 5 (Achievements/Challenges):**

- [x] Complete Phase A (Chores) - ✅ Done
- [ ] Complete Phase B (Badges) - Required
- [ ] Or accept technical debt and document for future

**Recommendation**: Complete Phase B now. Adding achievements/challenges on top of inconsistent badge patterns will make future cleanup much harder.

---

## References

- `entity_helpers.build_chore()` - lines 672-889
- `entity_helpers.build_badge()` - lines 890-1100
- `flow_helpers.validate_chores_inputs()` - lines 408-572
- `flow_helpers.transform_chore_cfof_to_data()` - lines 893-1031 (NEW)
- `flow_helpers.build_badge_common_data()` - lines ~1700-2300 (TO BE REMOVED in Phase B)
