# Phase 2B Implementation Plan: Entity Lookup Helpers

**Status**: 🔄 IN PROGRESS
**Created**: December 18, 2025
**Branch**: 2025-12-12-RefactorConfigStorage
**Related**: SERVICES_IMPROVEMENT_PLAN.md (Phase 2B)

---

## Executive Summary

Implement 6 new helper functions in `kc_helpers.py` to eliminate ~200 lines of duplicate entity lookup code across 40+ call sites in `services.py`. This refactoring reduces code duplication, improves maintainability, and follows Home Assistant core patterns.

**Impact**:

- **Reduction**: ~120 net lines removed from services.py (1290 → ~1170 lines)
- **Addition**: ~150 lines added to kc_helpers.py (1553 → ~1703 lines)
- **Net Benefit**: Eliminating 200+ lines of duplicate patterns

---

## Implementation Steps

### Step 1: Add Import to kc_helpers.py

**File**: `custom_components/kidschores/kc_helpers.py`
**Line**: 14 (in import section)

**Change**:

```python
from homeassistant.exceptions import HomeAssistantError
```

**Context**:

```python
from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError  # ← ADD THIS
from homeassistant.helpers.label_registry import async_get as async_get_label_registry

from . import const
```

---

### Step 2: Add Section Separator and Helper Functions

**File**: `custom_components/kidschores/kc_helpers.py`
**Location**: After line 243 (after `get_friendly_label()` function)

**Add Section Separator**:

```python


# ────────────────────────────────────────────────────────────────
# 🔍 Entity Lookup Helpers with Error Raising
# These helpers wrap the get_*_id_by_name() functions and raise
# HomeAssistantError if the entity is not found. Used primarily by
# services.py to eliminate duplicate lookup+validation patterns.
# ────────────────────────────────────────────────────────────────
```

**Add 6 Helper Functions**:

```python
def get_kid_id_or_raise(
    coordinator: KidsChoresDataCoordinator, kid_name: str, action: str
) -> str:
    """Get kid ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        kid_name: Name of the kid to look up
        action: Description of the action for error context (e.g., "Claim Chore")

    Returns:
        The kid's internal_id

    Raises:
        HomeAssistantError: If kid not found

    Example:
        kid_id = get_kid_id_or_raise(coordinator, "Sarah", "Claim Chore")
    """
    kid_id = get_kid_id_by_name(coordinator, kid_name)
    if not kid_id:
        const.LOGGER.warning("WARNING: %s: Kid not found: %s", action, kid_name)
        raise HomeAssistantError(f"Kid '{kid_name}' not found")
    return kid_id


def get_chore_id_or_raise(
    coordinator: KidsChoresDataCoordinator, chore_name: str, action: str
) -> str:
    """Get chore ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        chore_name: Name of the chore to look up
        action: Description of the action for error context

    Returns:
        The chore's internal_id

    Raises:
        HomeAssistantError: If chore not found
    """
    chore_id = get_chore_id_by_name(coordinator, chore_name)
    if not chore_id:
        const.LOGGER.warning("WARNING: %s: Chore not found: %s", action, chore_name)
        raise HomeAssistantError(f"Chore '{chore_name}' not found")
    return chore_id


def get_reward_id_or_raise(
    coordinator: KidsChoresDataCoordinator, reward_name: str, action: str
) -> str:
    """Get reward ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        reward_name: Name of the reward to look up
        action: Description of the action for error context

    Returns:
        The reward's internal_id

    Raises:
        HomeAssistantError: If reward not found
    """
    reward_id = get_reward_id_by_name(coordinator, reward_name)
    if not reward_id:
        const.LOGGER.warning("WARNING: %s: Reward not found: %s", action, reward_name)
        raise HomeAssistantError(f"Reward '{reward_name}' not found")
    return reward_id


def get_penalty_id_or_raise(
    coordinator: KidsChoresDataCoordinator, penalty_name: str, action: str
) -> str:
    """Get penalty ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        penalty_name: Name of the penalty to look up
        action: Description of the action for error context

    Returns:
        The penalty's internal_id

    Raises:
        HomeAssistantError: If penalty not found
    """
    penalty_id = get_penalty_id_by_name(coordinator, penalty_name)
    if not penalty_id:
        const.LOGGER.warning("WARNING: %s: Penalty not found: %s", action, penalty_name)
        raise HomeAssistantError(f"Penalty '{penalty_name}' not found")
    return penalty_id


def get_bonus_id_or_raise(
    coordinator: KidsChoresDataCoordinator, bonus_name: str, action: str
) -> str:
    """Get bonus ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        bonus_name: Name of the bonus to look up
        action: Description of the action for error context

    Returns:
        The bonus's internal_id

    Raises:
        HomeAssistantError: If bonus not found
    """
    bonus_id = get_bonus_id_by_name(coordinator, bonus_name)
    if not bonus_id:
        const.LOGGER.warning("WARNING: %s: Bonus not found: %s", action, bonus_name)
        raise HomeAssistantError(f"Bonus '{bonus_name}' not found")
    return bonus_id


def get_badge_id_or_raise(
    coordinator: KidsChoresDataCoordinator, badge_name: str, action: str
) -> str:
    """Get badge ID by name or raise HomeAssistantError if not found.

    Args:
        coordinator: The KidsChores data coordinator
        badge_name: Name of the badge to look up
        action: Description of the action for error context

    Returns:
        The badge's internal_id

    Raises:
        HomeAssistantError: If badge not found
    """
    badge_id = get_badge_id_by_name(coordinator, badge_name)
    if not badge_id:
        const.LOGGER.warning("WARNING: %s: Badge not found: %s", action, badge_name)
        raise HomeAssistantError(f"Badge '{badge_name}' not found")
    return badge_id
```

**Total Lines Added**: ~150 (6 lines separator + ~24 lines per function × 6 functions)

---

### Step 3: Update services.py Call Sites

**File**: `custom_components/kidschores/services.py`
**Changes**: 40+ replacements across 15 handlers

#### Replacement Pattern

**OLD PATTERN** (4 lines):

```python
entity_id = kh.get_entity_id_by_name(coordinator, entity_name)
if not entity_id:
    const.LOGGER.warning("WARNING: <Action>: Entity not found: %s", entity_name)
    raise HomeAssistantError(f"Entity '{entity_name}' not found")
```

**NEW PATTERN** (1 line):

```python
entity_id = kh.get_entity_id_or_raise(coordinator, entity_name, "<Action>")
```

#### Handler-by-Handler Changes

**1. handle_claim_chore** (Lines ~162-177)

- Replace kid lookup (4 lines → 1 line): `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Claim Chore")`
- Replace chore lookup (4 lines → 1 line): `chore_id = kh.get_chore_id_or_raise(coordinator, chore_name, "Claim Chore")`

**2. handle_approve_chore** (Lines ~231-246)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Approve Chore")`
- Replace chore lookup: `chore_id = kh.get_chore_id_or_raise(coordinator, chore_name, "Approve Chore")`

**3. handle_disapprove_chore** (Lines ~309-324)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Disapprove Chore")`
- Replace chore lookup: `chore_id = kh.get_chore_id_or_raise(coordinator, chore_name, "Disapprove Chore")`

**4. handle_redeem_reward** (Lines ~380-395)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Redeem Reward")`
- Replace reward lookup: `reward_id = kh.get_reward_id_or_raise(coordinator, reward_name, "Redeem Reward")`

**5. handle_approve_reward** (Lines ~452-467)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Approve Reward")`
- Replace reward lookup: `reward_id = kh.get_reward_id_or_raise(coordinator, reward_name, "Approve Reward")`

**6. handle_disapprove_reward** (Lines ~521-536)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Disapprove Reward")`
- Replace reward lookup: `reward_id = kh.get_reward_id_or_raise(coordinator, reward_name, "Disapprove Reward")`

**7. handle_apply_penalty** (Lines ~575-590)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Apply Penalty")`
- Replace penalty lookup: `penalty_id = kh.get_penalty_id_or_raise(coordinator, penalty_name, "Apply Penalty")`

**8. handle_reset_penalties** (Line ~648)

- Replace penalty lookup (if not None): `penalty_id = kh.get_penalty_id_or_raise(coordinator, penalty_name, "Reset Penalties")`

**9. handle_reset_bonuses** (Line ~713)

- Replace bonus lookup (if not None): `bonus_id = kh.get_bonus_id_or_raise(coordinator, bonus_name, "Reset Bonuses")`

**10. handle_reset_rewards** (Lines ~778-794)

- Replace kid lookup (if not None): `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Reset Rewards")`
- Replace reward lookup (if not None): `reward_id = kh.get_reward_id_or_raise(coordinator, reward_name, "Reset Rewards")`

**11. handle_remove_awarded_badges** (Lines ~814-829)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Remove Awarded Badges")`
- Replace badge lookup: `badge_id = kh.get_badge_id_or_raise(coordinator, badge_name, "Remove Awarded Badges")`

**12. handle_apply_bonus** (Lines ~875-890)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Apply Bonus")`
- Replace bonus lookup: `bonus_id = kh.get_bonus_id_or_raise(coordinator, bonus_name, "Apply Bonus")`

**13. handle_reset_overdue_chores** (Line ~941)

- Replace kid lookup (if not None): `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Reset Overdue Chores")`

**14. handle_set_chore_due_date** (Lines ~1074-1089)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Set Chore Due Date")`
- Replace chore lookup: `chore_id = kh.get_chore_id_or_raise(coordinator, chore_name, "Set Chore Due Date")`

**15. handle_skip_chore_due_date** (Lines ~1130-1145)

- Replace kid lookup: `kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Skip Chore Due Date")`
- Replace chore lookup: `chore_id = kh.get_chore_id_or_raise(coordinator, chore_name, "Skip Chore Due Date")`

**Total Replacements**: 40+ occurrences (160 lines → 40 lines = 120 line reduction)

---

## Testing Strategy

### Phase 1: Lint Validation

```bash
# Lint kc_helpers.py (verify no errors after adding helpers)
./utils/quick_lint.sh custom_components/kidschores/kc_helpers.py

# Lint services.py (verify no errors after replacing call sites)
./utils/quick_lint.sh custom_components/kidschores/services.py
```

**Expected**: No pylint/mypy/type errors, all formatting correct

### Phase 2: Unit Tests

```bash
# Test services handlers (all 17 handlers)
python -m pytest tests/test_services.py -v --tb=short

# Test helper functions work correctly with coordinator
python -m pytest tests/test_kc_helpers.py -v --tb=short
```

**Expected**: All service handler tests pass (baseline: 349 total tests)

### Phase 3: Integration Tests

```bash
# Full test suite (verify no regressions)
python -m pytest tests/ -v --tb=short
```

**Expected**: 349/349 tests pass (no regressions)

### Phase 4: Manual Validation

1. **Test Error Handling**:

   - Call service with invalid kid name → verify error message correct
   - Call service with invalid chore name → verify error message correct
   - Verify log messages contain action context

2. **Test Normal Operations**:
   - Claim chore with valid names → verify works
   - Apply penalty with valid names → verify works
   - Reset operations with optional entities → verify works

---

## Success Criteria

### Code Quality

- ✅ All 6 helper functions added to kc_helpers.py
- ✅ All 40+ call sites updated in services.py
- ✅ No pylint errors (maintain 9.8+/10 rating)
- ✅ No mypy/type errors
- ✅ All docstrings complete with examples

### Testing

- ✅ 349/349 tests pass
- ✅ No test coverage regression (maintain 56%+)
- ✅ All service handlers tested with valid/invalid inputs

### Code Metrics

- ✅ services.py reduced from 1290 → ~1170 lines (-120 lines)
- ✅ kc_helpers.py increased from 1553 → ~1703 lines (+150 lines)
- ✅ Net duplication elimination: ~200 lines of identical patterns removed

### Documentation

- ✅ SERVICES_IMPROVEMENT_PLAN.md updated (Phase 2B marked complete)
- ✅ ARCHITECTURE.md updated (Entity Lookup Helper Pattern section added)
- ✅ This implementation plan created and tracked

---

## Rollback Plan

If implementation causes issues:

1. **Revert services.py changes**:

   ```bash
   git checkout HEAD -- custom_components/kidschores/services.py
   ```

2. **Revert kc_helpers.py changes**:

   ```bash
   git checkout HEAD -- custom_components/kidschores/kc_helpers.py
   ```

3. **Run tests to verify baseline**:
   ```bash
   python -m pytest tests/ -v --tb=short
   ```

**Recovery Time**: < 5 minutes

---

## Next Steps After Completion

1. **Mark Phase 2B Complete** in SERVICES_IMPROVEMENT_PLAN.md
2. **Update Documentation** (this plan and ARCHITECTURE.md already done)
3. **Consider Phase 3** (Error Handling Standardization)
4. **Evaluate File Split** during coordinator review (defer for now)

---

## References

- **SERVICES_IMPROVEMENT_PLAN.md**: Full services.py improvement roadmap
- **ARCHITECTURE.md**: Entity Lookup Helper Pattern section (lines 1096-1157)
- **HA Core Precedent**: `device_automation/__init__.py:async_get_entity_registry_entry_or_raise()`
- **Related Issue**: H2 in SERVICES_IMPROVEMENT_PLAN.md (Duplicate Code - Entity Lookup Pattern)

---

**Document Version**: 1.0
**Status**: Ready for implementation
**Estimated Time**: 45 minutes (15 min helpers, 30 min services updates)
