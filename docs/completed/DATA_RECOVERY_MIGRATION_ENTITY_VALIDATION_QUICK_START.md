# Quick Start: Entity Validation Testing

**Purpose**: Fast-track guide to start entity validation testing (Data Recovery Phase 5 + Migration Phase 1.5/2)

**Total Time**: ~3 hours for critical path

---

## ⚡ Step 1: Character Validation (5 minutes) - START HERE

### Commands:
```bash
cd /workspaces/kidschores-ha
code tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json
```

### Search for these 4 patterns (Ctrl+F):
1. `"Zoë"` - Kid name with diaeresis
2. `"cåts"` - Chore name with ring above
3. `"plänts"` - Chore name with diaeresis
4. `"wåter"` - Chore name with ring above

### Expected Results:
✅ All 4 patterns found
✅ Characters display correctly (not ?, �, or blank)
✅ No "corrupted file" warnings

### If Issues Found:
❌ STOP - Production JSON corrupted
❌ Request clean sample from user
❌ Document corruption in GitHub issue

### If Valid:
✅ Proceed to Step 2
✅ Document validation in plan update

---

## ⚡ Step 2: Create Entity Validation Framework (30 minutes)

### Commands:
```bash
cd /workspaces/kidschores-ha/tests
touch entity_validation_helpers.py
```

### Copy This Code:
Open `/workspaces/kidschores-ha/docs/in-process/UNIFIED_TESTING_STRATEGY_IN-PROCESS.md`
- Go to section: "Shared Entity Validation Framework"
- Copy entire Python code block (lines ~150-350)
- Paste into `tests/entity_validation_helpers.py`

### Verify:
```bash
cd /workspaces/kidschores-ha
./utils/quick_lint.sh --fix
```

Expected: No errors, 9.60/10 rating maintained

---

## ⚡ Step 3: Data Recovery Phase 5 Tests (2 hours)

### File to Edit:
`tests/test_config_flow_data_recovery.py`

### Add Test 3.1 (at end of file, before template notice):

Copy from UNIFIED_TESTING_STRATEGY.md:
- Section: "Test 3.1: Production JSON Paste Creates Entities"
- Lines ~420-520
- Full test function with docstring

### Add Test 3.2 (after Test 3.1):

Copy from UNIFIED_TESTING_STRATEGY.md:
- Section: "Test 3.2: Production JSON Restore Creates Entities"
- Lines ~530-600
- Full test function with docstring

### Run Tests:
```bash
cd /workspaces/kidschores-ha
python -m pytest tests/test_config_flow_data_recovery.py -v
```

### Expected Results:
- Total: 18 tests
- Passing: 18 (was 16, added 2 new)
- Duration: ~5-10 seconds
- Failures: 0

### Key Validations:
✅ Production JSON paste creates config entry
✅ Production JSON restore creates config entry
✅ Entity counts: ≥150 sensors, ≥50 buttons, 3 calendars, 3 selects
✅ Special characters preserved: Zoë → kc_zoe_* entity IDs
✅ Chore names preserved: "cåts" in entity attributes

---

## ⚡ Step 4: Migration Phase 1.5 Tests (1.5 hours) - OPTIONAL PARALLEL

### Create New File:
```bash
cd /workspaces/kidschores-ha/tests
touch test_migration_production_sample.py
```

### Copy Test Templates:
From UNIFIED_TESTING_STRATEGY.md:
- Test 4.1: Character encoding validation (lines ~650-680)
- Test 4.2: v42 no migration needed (lines ~690-750)

### Add Standard Imports (at top of file):
```python
"""Tests for production JSON sample validation."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import DOMAIN

# Add more imports as needed per test
```

### Run Tests:
```bash
python -m pytest tests/test_migration_production_sample.py -v
```

Expected: 2/2 passing

---

## Quick Checklist

### Prerequisites:
- [ ] Backup restore fixes complete (Phase 4.5) ✅ Done Dec 18
- [ ] Production JSON sample available ✅ In migration_samples/
- [ ] Test framework at 16/16 passing ✅ Verified Dec 18

### Step 1 Complete When:
- [ ] All 4 special characters found and valid
- [ ] No corruption warnings
- [ ] Documented in plan

### Step 2 Complete When:
- [ ] entity_validation_helpers.py created
- [ ] All 5 helper functions present
- [ ] Linting passes (no errors)
- [ ] File committed to git

### Step 3 Complete When:
- [ ] Test 3.1 added and passing
- [ ] Test 3.2 added and passing
- [ ] Total 18/18 tests passing
- [ ] Entity counts validated
- [ ] Special characters verified

### Data Recovery Phase 5 Complete When:
- [ ] Steps 1-3 all complete
- [ ] Entity validation framework reusable
- [ ] Production JSON tested in paste flow
- [ ] Production JSON tested in restore flow
- [ ] Plan updated to 100%

---

## Common Issues & Fixes

### Issue: Production JSON not found
**Fix**: Check path: `tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`

### Issue: Import error in entity_validation_helpers
**Fix**: Add to tests/conftest.py:
```python
import sys
sys.path.insert(0, str(Path(__file__).parent))
```

### Issue: Entity counts lower than expected
**Fix**: 
1. Check if setup completed: `await hass.async_block_till_done()`
2. Reload platforms if needed
3. Verify production JSON has expected data (3 kids, 7 chores)

### Issue: Special characters not preserved
**Fix**:
1. Verify Step 1 validation passed
2. Check file encoding: `file -i config_entry-kidschores-*.json`
3. Should show: `charset=utf-8`

---

## File Locations Reference

### Documents:
- Plan updates: `/workspaces/kidschores-ha/docs/in-process/PLAN_UPDATES_SUMMARY.md`
- Unified strategy: `/workspaces/kidschores-ha/docs/in-process/UNIFIED_TESTING_STRATEGY_IN-PROCESS.md`
- Data recovery plan: `/workspaces/kidschores-ha/docs/in-process/DATA_RECOVERY_BACKUP_PLAN_IN-PROCESS.md`
- Migration plan: `/workspaces/kidschores-ha/docs/in-process/MIGRATION_TESTING_PLAN_IN-PROCESS.md`

### Test Files:
- Entity helpers: `/workspaces/kidschores-ha/tests/entity_validation_helpers.py` (CREATE)
- Data recovery: `/workspaces/kidschores-ha/tests/test_config_flow_data_recovery.py` (EDIT)
- Migration prod: `/workspaces/kidschores-ha/tests/test_migration_production_sample.py` (CREATE)
- Migration legacy: `/workspaces/kidschores-ha/tests/test_migration_samples_validation.py` (EDIT LATER)

### Production Sample:
- JSON: `/workspaces/kidschores-ha/tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`

---

## Timeline

| Step | Duration | Can Parallel? | Blocker? |
|------|----------|---------------|----------|
| Step 1: Character validation | 5 min | No | No |
| Step 2: Entity framework | 30 min | No | Step 1 |
| Step 3: Data Recovery tests | 2 hours | With Step 4 | Step 2 |
| Step 4: Migration Phase 1.5 | 1.5 hours | With Step 3 | Step 1 |

**Critical Path**: Step 1 → Step 2 → Step 3 = **~3 hours**

**Parallel Option**: Run Step 4 during Step 3 (saves 1.5 hours)

---

## Success Output

After Step 3 complete, you should see:

```bash
$ python -m pytest tests/test_config_flow_data_recovery.py -v

test_config_flow_data_recovery.py::test_restore_from_backup_creates_entry_immediately PASSED
test_config_flow_data_recovery.py::test_restore_from_backup_validates_backup_file PASSED
test_config_flow_data_recovery.py::test_restore_handles_missing_backup_file PASSED
test_config_flow_data_recovery.py::test_restore_v41_backup_migrates_to_v42 PASSED
test_config_flow_data_recovery.py::test_restore_v42_backup_no_migration_needed PASSED
test_config_flow_data_recovery.py::test_paste_json_with_wrapped_v42_data PASSED
test_config_flow_data_recovery.py::test_paste_json_with_raw_v41_data PASSED
# ... 11 more existing tests ...
test_config_flow_data_recovery.py::test_production_json_paste_creates_entities PASSED
test_config_flow_data_recovery.py::test_production_json_restore_creates_entities PASSED

======================== 18 passed in 7.2s ========================
```

Key indicators:
✅ All 18 tests passing
✅ New tests show entity counts validated
✅ Duration under 10 seconds
✅ No warnings about special characters

---

## What's Next After Step 3?

1. **Update Data Recovery Plan** (5 minutes)
   - Mark Phase 5 as 100% complete
   - Document entity counts achieved
   - Note special character validation passed

2. **Optional: Complete Migration Phase 1.5** (1.5 hours)
   - Execute Step 4 if not done in parallel
   - Creates 2 more tests in new file
   - Validates production JSON from migration perspective

3. **Wait for Badge Fixes** (blocks Migration Phase 2)
   - Migration Phase 2 requires badge migration working
   - Step 5 can't proceed until 11 badge tests pass

4. **Manual Testing** (when ready)
   - Execute 11 manual testing scenarios
   - Validate UI behavior with production data
   - Confirm dashboard displays correctly

---

**Last Updated**: Dec 18, 2025  
**Status**: Ready to execute - start with Step 1 (5 minutes)
