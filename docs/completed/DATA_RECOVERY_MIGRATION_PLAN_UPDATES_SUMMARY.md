# Initiative Plans Update Summary (Dec 18, 2025)

## What Was Updated

Three documents were updated/created to establish a comprehensive, coordinated testing strategy:

1. **DATA_RECOVERY_BACKUP_PLAN_IN-PROCESS.md** - Updated with Phase 4.5 completion and new Phase 5-6
2. **MIGRATION_TESTING_PLAN_IN-PROCESS.md** - Updated with Phase 1.5 and coordination strategy
3. **UNIFIED_TESTING_STRATEGY_IN-PROCESS.md** - NEW comprehensive testing coordination document

---

## Key Changes by Document

### 1. Data Recovery Backup Plan

**New Phase Structure**:
- Phase 0-4: Complete (100%)
- **Phase 4.5**: Config flow restore fixes (100%) - **NEW**
- **Phase 5**: Entity validation & production JSON testing (0%) - **REDEFINED**
- **Phase 6**: Documentation & release polish (0%) - **RENUMBERED**

**Phase 4.5 Details** (100% complete):
- **Root cause documented**: `_handle_restore_backup` created storage_manager too early, causing wrong path construction with test mocking
- **Solution documented**: Changed to direct `hass.config.path(".storage", const.STORAGE_KEY)` construction; only create storage_manager when needed
- **Test results**: All 5 restore tests now passing (was 0/5):
  - test_restore_from_backup_creates_entry_immediately ✅
  - test_restore_from_backup_validates_backup_file ✅
  - test_restore_handles_missing_backup_file ✅
  - test_restore_v41_backup_migrates_to_v42 ✅
  - test_restore_v42_backup_no_migration_needed ✅
- **Technical fixes**: 13 path mocking patterns corrected, discover_backups mocks added, timestamp formats fixed, assertion adjustments

**Phase 5 Redefined** (0% complete):
- **Focus shifted**: From documentation to entity creation validation + production JSON testing
- **Requirements**:
  - Character encoding validation for production JSON (UTF-8: Zoë, cåts, plänts, wåter)
  - Entity creation verification (sensors, buttons, calendar, select)
  - Production JSON testing through paste JSON flow
  - Production JSON testing through restore backup flow
  - Entity count validation: ~150+ sensors, ~50+ buttons, 3 calendars, 3 selects
- **Coordination**: Integrated with Migration Testing Phase 1.5/2 via shared entity validation framework

**Phase 6 Renumbered** (0% complete):
- Moved from Phase 5 to Phase 6
- Focus remains: Manual testing scenarios, release notes, architecture docs

---

### 2. Migration Testing Plan

**New Phase Structure**:
- Phase 1: Legacy sample validation (65% - badge migration blocking)
- **Phase 1.5**: Production JSON sample validation (0%) - **NEW**
- **Phase 2**: Migration fixes & entity validation (35%) - **ENHANCED**
- Phase 3: Regression proofs & documentation (15%)

**Phase 1.5 Details** (0% complete):
- **Purpose**: Validate real production data sample, integrate with data recovery testing
- **Steps**:
  1. Character encoding validation (Zoë, cåts, plänts, wåter)
  2. Data structure validation (3 kids, 7 chores, 1 badge, 5 rewards, etc.)
  3. Integration with Data Recovery Phase 5 (shared test suite)
  4. Comprehensive entity validation framework
- **Test patterns to create**:
  - test_production_json_paste_creates_entities
  - test_production_json_restore_creates_entities
  - test_production_json_migration_v42_to_v42
  - test_production_json_character_encoding
- **Key issues**: Character encoding may be corrupted; entity tests overlap with Data Recovery (coordination required)

**Phase 2 Enhanced**:
- Added entity creation validation (Step 4)
- Added test migration + entity creation together (Step 5)
- Storage wipe bug marked as fixed (✅ done Dec 18)
- Integration with Data Recovery Phase 5 for shared entity validation framework

**Coordination Section Added**:
- Phase alignment with Data Recovery plan documented
- Shared entity validation framework location specified
- Production JSON sample shared between both plans
- Testing sequence defined: Character validation → Data structure → Entity creation
- Expected entity counts baseline established

---

### 3. Unified Testing Strategy (NEW)

**Purpose**: Coordinate entity validation testing across both initiatives to avoid duplication

**Key Sections**:

1. **Executive Summary**
   - Explains why unified strategy needed (both plans reached entity validation stage)
   - Identifies shared integration points
   - Establishes production baseline (3 kids, 7 chores = ~150+ sensors, ~50+ buttons, 3 calendars, 3 selects)

2. **Phase Alignment Matrix**
   - Visual mapping of how Data Recovery Phase 5 aligns with Migration Phase 1.5/2
   - Shows dependencies and critical path
   - Makes coordination explicit

3. **Shared Entity Validation Framework** (MOST IMPORTANT)
   - Complete Python code for `tests/entity_validation_helpers.py`
   - 5 helper functions:
     - `count_entities_by_platform()` - Count entities by platform type
     - `get_kid_entity_prefix()` - Generate expected entity ID prefix
     - `verify_kid_entities()` - Comprehensive per-kid entity validation
     - `verify_entity_state()` - Check entity state and attributes
     - `get_entity_counts_summary()` - Summary of all entities
   - Ready to copy/paste into codebase

4. **Production JSON Sample Specification**
   - Data inventory (3 kids, 7 chores, etc.)
   - Special character table with Unicode codes
   - Validation steps for character encoding
   - Expected entity count calculations with thresholds

5. **Testing Sequence & Execution Plan** (5 STEPS)
   - **Step 1**: Character encoding validation (5 min, manual)
   - **Step 2**: Create shared validation framework (30 min)
   - **Step 3**: Data Recovery Phase 5 tests (2 hours, 2 tests)
   - **Step 4**: Migration Phase 1.5 tests (1.5 hours, 2 tests)
   - **Step 5**: Migration Phase 2 tests (2 hours, 4 tests, blocked by badge fixes)

6. **Complete Test Templates**
   - Test 3.1: `test_production_json_paste_creates_entities` (full code)
   - Test 3.2: `test_production_json_restore_creates_entities` (full code)
   - Test 4.1: `test_production_json_character_encoding` (full code)
   - Test 4.2: `test_production_json_v42_no_migration_needed` (full code)
   - Test 5.1-5.3: Legacy migration + entity validation (pattern)
   - Test 5.4: Production sample + entity validation (pattern)

7. **Success Criteria & Completion Checklist**
   - Data Recovery Phase 5 criteria (5 items)
   - Migration Phase 1.5 criteria (3 items)
   - Migration Phase 2 criteria (4 items)
   - Overall strategy criteria (7 items)

8. **Timeline Estimate**
   - Critical path: 3 hours (Steps 1-3)
   - Parallel path: 1.5 hours (Step 4 alongside Step 3)
   - Total: 6 hours (excluding badge migration fixes)

---

## Critical Path Forward

### Immediate Next Steps (Today/Tomorrow):

1. **Step 1: Validate production JSON** (5 minutes) ⚡ **START HERE**
   - Open `tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`
   - Search for: `Zoë`, `cåts`, `plänts`, `wåter`
   - Confirm no corruption (?, �, or blanks)
   - If corruption found: STOP and request clean sample
   - If valid: Proceed to Step 2

2. **Step 2: Create entity validation framework** (30 minutes)
   - Copy code from UNIFIED_TESTING_STRATEGY section "Shared Entity Validation Framework"
   - Create file: `tests/entity_validation_helpers.py`
   - Run linting: `./utils/quick_lint.sh --fix`
   - Verify no errors

3. **Step 3: Implement Data Recovery tests** (2 hours)
   - Add Test 3.1 to `tests/test_config_flow_data_recovery.py` (paste creates entities)
   - Add Test 3.2 to `tests/test_config_flow_data_recovery.py` (restore creates entities)
   - Run: `python -m pytest tests/test_config_flow_data_recovery.py -v`
   - Verify: 18/18 tests passing (was 16/16)

4. **Update Data Recovery Plan** (5 minutes)
   - Mark Phase 5 as 100% complete
   - Document entity validation results
   - Note entity counts achieved

### Short-Term (This Week):

5. **Step 4: Implement Migration Phase 1.5 tests** (1.5 hours)
   - Create `tests/test_migration_production_sample.py`
   - Add Test 4.1 (character encoding)
   - Add Test 4.2 (v42 no migration)
   - Run and verify 2/2 passing

6. **Update Migration Plan** (5 minutes)
   - Mark Phase 1.5 as 100% complete
   - Document production JSON validation results

### Medium-Term (After Badge Fixes):

7. **Step 5: Implement Migration Phase 2 tests** (2 hours)
   - Add Test 5.1-5.3 to `tests/test_migration_samples_validation.py` (legacy + entities)
   - Add Test 5.4 (production + entities)
   - Run and verify 34/34 passing (30 existing + 4 new)

8. **Update Migration Plan** (5 minutes)
   - Mark Phase 2 as 100% complete
   - Document entity validation integration

9. **Mark Both Initiatives Complete**
   - Data Recovery: Phase 5 → Phase 6 (documentation)
   - Migration: Phase 2 → Phase 3 (regression proofs)

---

## What Problems This Solves

### Before Updates:
- ❌ Two separate plans reaching entity validation independently
- ❌ Risk of duplicating test code between initiatives
- ❌ No clear coordination strategy
- ❌ Production JSON sample not integrated into testing
- ❌ Entity validation requirements not specified
- ❌ No shared helper framework planned
- ❌ Unclear which initiative owns which tests

### After Updates:
- ✅ Single unified testing strategy coordinating both initiatives
- ✅ Shared entity validation framework (no duplication)
- ✅ Clear phase alignment matrix showing dependencies
- ✅ Production JSON sample fully integrated with validation steps
- ✅ Entity validation requirements explicit (counts, naming, special chars)
- ✅ Complete test templates ready to implement
- ✅ Clear ownership: Data Recovery tests paste/restore, Migration tests v30/v31/v40beta1/v42
- ✅ Timeline with critical path identified (3 hours)
- ✅ Success criteria clearly defined for each phase

---

## Key Deliverables

### 1. Entity Validation Framework
**File**: `tests/entity_validation_helpers.py` (ready to create)
- 5 helper functions with full docstrings
- Reusable across all entity validation tests
- Handles kid entity verification, platform counting, state checking

### 2. Test Templates (6 Complete Tests)
**Files**: 
- `tests/test_config_flow_data_recovery.py` (add 2 tests)
- `tests/test_migration_production_sample.py` (create new, 2 tests)
- `tests/test_migration_samples_validation.py` (add 4 tests later)

**Coverage**:
- Data Recovery: Production JSON paste + restore with entity validation
- Migration 1.5: Character encoding + v42 no-migration
- Migration 2: Legacy samples + production with entity validation

### 3. Production JSON Baseline
**Expectations**:
- 3 kids (Zoë, Max!, Lila)
- 7 chores with special characters (cåts, plänts, wåter)
- Expected entities: ≥150 sensors, ≥50 buttons, 3 calendars, 3 selects
- Character encoding: UTF-8 validated before use

---

## Questions to Consider

1. **Character Encoding**: Has the production JSON been validated yet? (Step 1 prerequisite)
2. **Badge Migration**: When will badge fixes land? (blocks Migration Phase 2)
3. **Timeline**: Is 6-hour estimate for Steps 1-4 realistic for current sprint?
4. **Manual Testing**: Should manual testing scenarios (11 documented) be executed before or after Phase 5 completion?

---

## Summary

**What Changed**:
- Data Recovery Plan: Added Phase 4.5 (restore fixes complete), redefined Phase 5 (entity validation)
- Migration Plan: Added Phase 1.5 (production JSON), enhanced Phase 2 (entity validation)
- Unified Strategy: NEW document coordinating both initiatives with shared framework

**Critical Path**:
1. Validate production JSON character encoding (5 min)
2. Create entity validation framework (30 min)
3. Implement Data Recovery Phase 5 tests (2 hours)
4. Mark Data Recovery complete, proceed to Migration Phase 1.5

**Total Effort**:
- Data Recovery Phase 5: ~3 hours (Steps 1-3)
- Migration Phase 1.5: ~1.5 hours (Step 4)
- Migration Phase 2: ~2 hours (Step 5, blocked by badge fixes)
- **Total**: 6.5 hours

**Files to Create**:
1. `tests/entity_validation_helpers.py` - Shared framework (30 min)
2. Add 2 tests to `tests/test_config_flow_data_recovery.py` (2 hours)
3. Create `tests/test_migration_production_sample.py` with 2 tests (1.5 hours)
4. Add 4 tests to `tests/test_migration_samples_validation.py` (2 hours later)

**Next Action**: Start with Step 1 (5 min character validation) ⚡

---

**Document Created**: Dec 18, 2025  
**Purpose**: Provide executive summary of plan updates and next steps
