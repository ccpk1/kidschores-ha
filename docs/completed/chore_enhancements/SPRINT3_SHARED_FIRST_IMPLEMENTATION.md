# Sprint 3: SHARED_FIRST Mode Implementation

**Created**: December 29, 2025
**Status**: ✅ COMPLETE
**Completed**: December 29, 2025
**Branch**: 2025-12-12-RefactorConfigStorage

---

## Design Decisions (Confirmed)

| Question | Decision |
|----------|----------|
| **Q1: Points Distribution** | A - Only first kid gets points |
| **Q2: Block Timing** | A - Block claims after first claim (no one else can claim) |
| **Q3: Existing Claims** | D - Return error message when blocked kid tries to claim |
| **Q4: Dashboard Display** | Use `completed_by_other` state for other kids; global state follows normal shared pattern |
| **Q5: Reset Behavior** | Same as SHARED_ALL - resets for all kids |

---

## State Machine

### Happy Path
```
INITIAL:
  Global:  pending
  Kid A:   pending
  Kid B:   pending

KID A CLAIMS:
  Global:  claimed
  Kid A:   claimed
  Kid B:   completed_by_other (attr: claimed_by="Kid A")

PARENT APPROVES:
  Global:  approved
  Kid A:   approved
  Kid B:   completed_by_other (attr: completed_by="Kid A")
```

### Rejection Path
```
KID A CLAIMS:
  Global:  claimed
  Kid A:   claimed
  Kid B:   completed_by_other

PARENT DISAPPROVES:
  Global:  pending
  Kid A:   pending
  Kid B:   pending  ← All reset, everyone can try again
```

---

## Implementation Progress

| # | Component | Status | Notes |
|---|-----------|--------|-------|
| 1 | Add `COMPLETION_CRITERIA_SHARED_FIRST` constant | ✅ | const.py line ~1011 |
| 2 | Add `CHORE_STATE_COMPLETED_BY_OTHER` constant | ✅ | const.py line ~1294 |
| 3 | Add `TRANS_KEY_ERROR_CHORE_ALREADY_CLAIMED` constant | ✅ | const.py line ~1873 |
| 4 | Update `COMPLETION_CRITERIA_OPTIONS` list | ✅ | const.py includes shared_first |
| 5 | Add translations to en.json | ✅ | completion_criteria + exception |
| 6 | Modify `claim_chore()` for SHARED_FIRST blocking | ✅ | coordinator.py - block after first claim |
| 7 | Modify `approve_chore()` for SHARED_FIRST logic | ✅ | coordinator.py - completed_by attr |
| 8 | Modify `disapprove_chore()` for reset logic | ✅ | coordinator.py - reset ALL kids |
| 9 | Update `_process_chore_state()` for new state | ✅ | coordinator.py - COMPLETED_BY_OTHER handling |
| 9b | Add `DATA_KID_COMPLETED_BY_OTHER_CHORES` constant | ✅ | const.py line ~694 |
| 9c | Update global state computation for SHARED_FIRST | ✅ | coordinator.py lines ~3105-3130 |
| 10 | Update dashboard helper for new state | ✅ | sensor.py - completed_by_other handling |
| 11 | Create test file | ✅ | test_shared_first_completion.py - 9 test cases |
| 12 | Run full test suite | ✅ | 630 passed, 16 skipped - no regressions |

---

## Phase 1: Constants & Translations (Steps 1-5)

### Step 1-4: const.py Changes

**Location**: `custom_components/kidschores/const.py`

Add after existing completion criteria constants (~line 1010):
```python
COMPLETION_CRITERIA_SHARED_FIRST = "shared_first"
```

Add to `COMPLETION_CRITERIA_OPTIONS` list:
```python
COMPLETION_CRITERIA_OPTIONS = [
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED_FIRST,  # NEW
]
```

Add new chore state (~line with other CHORE_STATE_*):
```python
CHORE_STATE_COMPLETED_BY_OTHER = "completed_by_other"
```

Add error translation key:
```python
TRANS_KEY_ERROR_CHORE_ALREADY_CLAIMED = "chore_already_claimed"
```

### Step 5: en.json Translations

Add to `exceptions` section:
```json
"chore_already_claimed": {
  "message": "This chore has already been claimed by {claimed_by}"
}
```

Add to completion criteria options (if selector uses translations):
```json
"shared_first": "Shared (first to complete)"
```

---

## Phase 2: Coordinator Logic (Steps 6-9)

### Step 6: claim_chore() Modifications

**Logic**:
1. Check if chore has `completion_criteria == "shared_first"`
2. If yes, check if any other kid has already claimed
3. If already claimed, raise `HomeAssistantError` with translation key
4. If first to claim, set all other kids to `completed_by_other`

### Step 7: approve_chore() Modifications

**Logic**:
1. For SHARED_FIRST chores, only the claiming kid gets points
2. Other kids remain in `completed_by_other` state
3. Update `completed_by` attribute from `claimed_by` to show who completed

### Step 8: disapprove_chore() Modifications

**Logic**:
1. Reset ALL kids to `pending` state (same as SHARED_ALL)
2. Clear `claimed_by`/`completed_by` attributes
3. Everyone gets a fresh opportunity

### Step 9: _process_chore_state() Updates

**Logic**:
1. Handle `completed_by_other` as a valid state
2. Include in state transitions appropriately

---

## Phase 3: Dashboard & Sensors (Step 10)

### Step 10: Dashboard Helper Updates

**Location**: `sensor.py` - `KidDashboardHelperSensor`

1. Include `completed_by_other` in chore categorization
2. Show `completed_by` attribution in attributes
3. Ensure button is hidden/disabled for these chores

---

## Phase 4: Testing (Steps 11-12)

### Step 11: Test File Creation

**File**: `tests/test_shared_first_completion.py`

Test cases:
1. First kid claims successfully
2. Second kid blocked after first claims
3. Approval gives points only to first kid
4. Disapproval resets all kids
5. Re-claim after disapproval works
6. Daily reset clears all states

### Step 12: Full Test Suite

```bash
python -m pytest tests/ -v --tb=line
```

---

## Validation Checklist

- [x] All constants added to const.py
- [x] Translations added to en.json
- [x] claim_chore() blocks correctly
- [x] approve_chore() awards points to first kid only
- [x] disapprove_chore() resets all kids
- [x] Dashboard shows completed_by_other correctly
- [x] All existing tests pass (630 passed, 16 skipped)
- [x] New tests pass (9 test cases in test_shared_first_completion.py)
- [x] Linting passes: `./utils/quick_lint.sh --fix`

---

## Files Modified

| File | Changes |
|------|---------|
| `const.py` | +4 constants |
| `translations/en.json` | +2 translation entries |
| `coordinator.py` | Modified claim_chore, approve_chore, disapprove_chore, _process_chore_state |
| `sensor.py` | Dashboard helper updates |
| `tests/test_shared_first_completion.py` | New test file |

