# Services.py Code Quality Improvement Plan

**Created:** December 18, 2025
**Current Branch:** 2025-12-12-RefactorConfigStorage
**Files in Scope:**

- `custom_components/kidschores/services.py` (1290 lines)
- `custom_components/kidschores/services.yaml` (395 lines)
- `custom_components/kidschores/const.py` (translation keys)

---

## Executive Summary

Comprehensive code review of services.py identified **26 actionable issues** across 4 severity levels:

- **2 Critical**: Missing type hints (mandatory standard), bare exception catch
- **6 High**: Duplicate code (200+ lines), inconsistent patterns, missing validation
- **12 Medium**: Hardcoded strings, documentation gaps, minor inconsistencies
- **6 Low**: Style variations, minor improvements

**Current Code Quality:** 7.5/10
**Target Quality:** 9.5/10
**Estimated Effort:** 4-6 hours across 4 phases

---

## Authorization Design Decision

### **INTENTIONAL: Services Operate Without User Authorization**

**Context:** Home Assistant's impersonation model and service call architecture create challenges for authorization enforcement in services.

**Issues with Authorization in Services:**

1. **Automation/Script Execution**: When services are called from automations or scripts, `call.context.user_id` is `None`
2. **Service Impersonation**: HA's impersonation system doesn't reliably propagate user context through service calls
3. **Dashboard Button Limitations**: UI button presses may not consistently pass user context
4. **API Calls**: REST API and webhook triggers often lack user context

**Design Decision:**

- Services.py handlers **do NOT enforce authorization checks**
- Authorization enforcement happens at **UI layer** (button entities, dashboard cards)
- **Rationale**: Services must be callable from automations/scripts/API without user context
- **Security Model**: Trust the caller (automation, dashboard, parent's device) rather than the service layer

**Current Implementation Pattern:**

```python
# Pattern in 13 handlers (lines 171-177, 240-246, 318-324, etc.)
user_id = call.context.user_id
if user_id and not await kh.is_user_authorized_for_kid(hass, user_id, kid_id):
    const.LOGGER.warning("WARNING: Claim Chore: User not authorized")
    raise HomeAssistantError("User not authorized for this kid")
# IF user_id is None (automation), authorization is SKIPPED
```

**Affected Handlers:**

1. `handle_claim_chore` - kid-level auth check (Lines 171-177)
2. `handle_approve_chore` - global auth check (Lines 240-246)
3. `handle_disapprove_chore` - global auth check (Lines 318-324)
4. `handle_redeem_reward` - kid-level auth check (Lines 389-395)
5. `handle_approve_reward` - global auth check (Lines 461-467)
6. `handle_disapprove_reward` - global auth check (Lines 530-536)
7. `handle_apply_penalty` - global auth check (Lines 584-590)
8. `handle_reset_penalties` - global auth check (Lines 658-664)
9. `handle_reset_bonuses` - global auth check (Lines 723-729)
10. `handle_reset_rewards` - global auth check (Lines 788-794)
11. `handle_remove_awarded_badges` - global auth check (Lines 823-829)
12. `handle_apply_bonus` - global auth check (Lines 884-890)
13. `handle_set_chore_due_date` - NO CHECK (Lines 1074-1128)

**Handlers WITHOUT Auth Checks (Intentional):**

- `handle_reset_all_data` - Factory reset, admin-only operation (dashboard access control)
- `handle_reset_all_chores` - Bulk reset, admin-only operation
- `handle_reset_overdue_chores` - Automation-triggered cleanup
- `handle_skip_chore_due_date` - Automation-triggered scheduling

**Action Items:**

1. ✅ **Phase 1**: Document this decision in services.py with explanatory comment
2. ✅ **Phase 1**: Add comment to each auth check explaining bypass behavior
3. ✅ **Deferred**: Review UI layer authorization (button entities, dashboard cards) - separate task

---

## Test Coverage Assessment

### **Current State: INADEQUATE** ❌

**Existing Test File**: `tests/test_services.py` (182 lines, 3 tests only)

**Services WITH Tests** (3 out of 17):

- ✅ `claim_chore` - Tests name resolution and workflow
- ✅ `approve_chore` - Tests approval workflow and points award
- ✅ `apply_bonus` / `apply_penalty` - Tests both in single test

**Services WITHOUT Tests** (14 out of 17):

- ❌ `disapprove_chore`
- ❌ `redeem_reward`
- ❌ `approve_reward`
- ❌ `disapprove_reward`
- ❌ `reset_all_data`
- ❌ `reset_all_chores`
- ❌ `reset_overdue_chores`
- ❌ `reset_penalties`
- ❌ `reset_bonuses`
- ❌ `reset_rewards`
- ❌ `remove_awarded_badges`
- ❌ `set_chore_due_date`
- ❌ `skip_chore_due_date`

### **CRITICAL GAP: Zero Error Case Testing** 🚨

**None of the existing tests verify**:

- ❌ Invalid kid name → should raise `HomeAssistantError`
- ❌ Invalid chore name → should raise `HomeAssistantError`
- ❌ Invalid reward/penalty/bonus/badge name → should raise errors
- ❌ Error message content/format
- ❌ Log message validation (WARNING level, correct context)

**Impact on Phase 2B Refactoring**:

- **Risk**: Cannot validate that helper refactoring maintains identical error behavior
- **Requirement**: MUST add error tests BEFORE implementing helpers
- **Reason**: Establish baseline behavior to prevent regressions

**Recommended Action**:

1. ✅ Add 3 minimal error tests (Phase 2B-Pre)
2. ✅ Verify current error handling works
3. ✅ Then proceed with helper refactoring
4. ✅ Verify tests still pass after refactoring

---

## Issues Inventory

### **REVISED Critical Issues (2)**

**C1. Missing Return Type Hints (15 handlers)**

- **Severity:** Critical - Violates mandatory coding standard
- **Location:** Lines 145, 194, 267, 327, 411, 480, 540, 607, 672, 733, 794, 839, 906, 970, 1055
- **Impact:** Type checkers cannot validate, fails mypy/pylint strict mode
- **Fix:** Add `-> None` to all handler signatures
- **Effort:** 5 minutes (simple find/replace pattern)

**C2. Bare Exception Catch in Backup Code**

- **Severity:** Critical - Could mask serious errors
- **Location:** Line 936-941 (`handle_reset_all_data` backup creation)
- **Code:**
  ```python
  except Exception as err:  # pylint: disable=broad-exception-caught
      const.LOGGER.warning("WARNING: Failed to create pre-reset backup: %s", err)
  ```
- **Impact:** Catches `KeyboardInterrupt`, `SystemExit`, memory errors
- **Fix:** Replace with specific exceptions: `OSError`, `IOError`, `PermissionError`, `shutil.Error`
- **Effort:** 2 minutes

~~**C3-C6. Missing Authorization Checks**~~

- **Status:** ❌ **REMOVED** - Authorization bypass is intentional design decision
- **Action:** Document, don't fix

---

### **High Priority Issues (6)**

**H1. Logging Inconsistency - Wrong Level for Errors**

- **Severity:** High
- **Location:** Lines 263, 472, 605, 909
- **Current:** `const.LOGGER.info("ERROR: Approve Chore: %s", e)`
- **Fix:** `const.LOGGER.error("Approve Chore: %s", e)` (no prefix, correct level)
- **Impact:** Errors don't appear in error-level logs, misleading log analysis
- **Affected Handlers:**
  - Line 263: `handle_approve_chore`
  - Line 472: `handle_approve_reward`
  - Line 605: `handle_apply_penalty`
  - Line 909: `handle_apply_bonus`
- **Effort:** 5 minutes (4 changes)

**H2. Duplicate Code - Entity Lookup Pattern**

- **Severity:** High
- **Location:** All 17 handlers, 200+ lines total
- **Pattern:** Same 4-line sequence repeated 40+ times:
  ```python
  kid_id = kh.get_kid_id_by_name(coordinator, kid_name)
  if not kid_id:
      const.LOGGER.warning("WARNING: <Action>: Kid '%s' not found", kid_name)
      raise HomeAssistantError(f"Kid '{kid_name}' not found")
  ```
- **Occurrences:**
  - Kid lookups: 8 handlers
  - Chore lookups: 7 handlers
  - Reward lookups: 4 handlers
  - Penalty lookups: 3 handlers
  - Bonus lookups: 2 handlers
  - Badge lookups: 2 handlers
- **Impact:** Maintenance burden, inconsistent error messages, code bloat (~200+ lines)
- **Fix:** Create 6 helper functions in kc_helpers.py (see Phase 2B below)
- **Effort:** 45 minutes (create helpers, update 40+ call sites, test)
- **Status:** 🔄 **IN PROGRESS** - Implementation approved for Phase 2B

**H3. Inconsistent Error Handling Patterns**

- **Severity:** High
- **Location:** All handlers
- **Issue:** Three different patterns used inconsistently:
  - **Pattern A**: Try/except with specific exceptions (5 handlers)
  - **Pattern B**: No try/except (12 handlers)
  - **Pattern C**: Data processing outside try block (mixed)
- **Impact:** Unclear which coordinator methods can fail, inconsistent error reporting
- **Questions to Answer:**
  1. Which coordinator methods can raise exceptions?
  2. Should all handlers use try/except?
  3. What's the standard pattern?
- **Fix:**
  1. Document coordinator exception behavior
  2. Choose standard pattern (recommend Pattern A)
  3. Apply consistently
- **Effort:** 45 minutes (research + 17 handler updates)

**H4. Missing Validation - handle_skip_chore_due_date**

- **Severity:** High
- **Location:** Lines 1130-1169
- **Issue:** Doesn't verify chore is recurring before calling `coordinator.skip_chore_due_date()`
- **Impact:** Service fails at coordinator level with unclear error
- **Fix:** Add pre-check:
  ```python
  chore_info = coordinator.chores_data.get(chore_id)
  if not chore_info:
      raise HomeAssistantError("Chore not found")
  if not chore_info.get(const.DATA_CHORE_RECURRENCE_FREQUENCY):
      raise HomeAssistantError("Cannot skip due date for non-recurring chore")
  ```
- **Effort:** 5 minutes

**H5. Missing Log Prefix - handle_disapprove_reward**

- **Severity:** High (consistency)
- **Location:** Line 524
- **Current:** `const.LOGGER.warning("Disapprove Reward: Reward '%s' not found", reward_name)`
- **Fix:** `const.LOGGER.warning("WARNING: Disapprove Reward: Reward '%s' not found", reward_name)`
- **Impact:** Inconsistent with all other handlers
- **Effort:** 1 minute

**H6. handle_remove_awarded_badges Passes Names Instead of IDs**

- **Severity:** High (architectural inconsistency)
- **Location:** Lines 846-848
- **Issue:** Unlike ALL other handlers, passes raw `kid_name` and `badge_name` to coordinator
- **Current:**
  ```python
  coordinator.remove_awarded_badges(kid_name=kid_name, badge_name=badge_name)
  ```
- **Pattern Violation:** All other handlers resolve names to IDs first, pass IDs to coordinator
- **Impact:** Coordinator must handle name resolution, violates separation of concerns
- **Fix:** Resolve to IDs before calling coordinator (requires coordinator method signature change)
- **Effort:** 10 minutes (handler + coordinator method)

---

### **Medium Priority Issues (12)**

**M1. Missing Return Type Hint - async_setup_services**

- **Severity:** Medium
- **Location:** Line 142
- **Current:** `def async_setup_services(hass: HomeAssistant):`
- **Fix:** `def async_setup_services(hass: HomeAssistant) -> None:`
- **Effort:** 1 minute

**M2. Minimal Docstring - async_setup_services**

- **Severity:** Medium
- **Location:** Line 142
- **Current:** `"""Register KidsChores services."""`
- **Fix:** Expand to document:
  - Which services are registered (17 total)
  - Authorization model (bypass when user_id is None)
  - Entry ID behavior (uses first entry)
- **Effort:** 5 minutes

**M3. Hardcoded Error Messages - Not Translatable**

- **Severity:** Medium
- **Location:** 30+ occurrences throughout file
- **Issue:** Violates coding standard: "Never hardcode user-facing strings"
- **Examples:**
  - "Kid '{kid_name}' not found" (8 occurrences)
  - "Chore '{chore_name}' not found" (6 occurrences)
  - "Reward '{reward_name}' not found" (4 occurrences)
  - "Failed to approve/apply/claim..." (6 occurrences)
- **Current Pattern:**
  ```python
  raise HomeAssistantError(f"Kid '{kid_name}' not found")
  ```
- **Target Pattern:**
  ```python
  raise HomeAssistantError(
      translation_domain=const.DOMAIN,
      translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND,
      translation_placeholders={"kid_name": kid_name}
  )
  ```
- **Note:** Some handlers already use translation keys correctly (Lines 247-250, 451-454)
- **Fix:**
  1. Add translation keys to const.py
  2. Add translations to strings.json
  3. Update 30+ raise statements
- **Effort:** 60 minutes (15 min keys, 15 min strings, 30 min updates)

**M4. Inconsistent Points Validation**

- **Severity:** Medium
- **Location:** Lines 385-396 (`handle_redeem_reward`)
- **Issue:** Only `handle_redeem_reward` checks if kid has enough points
- **Question:** Should `handle_approve_reward` also check points? It deducts but doesn't verify sufficiency.
- **Fix:** Research coordinator behavior, document/standardize
- **Effort:** 15 minutes

**M5. Duplicate Conditional Logic - Reset Handlers**

- **Severity:** Medium
- **Location:** Lines 643-676, 708-741, 773-806
- **Issue:** Three reset handlers have identical 4-branch conditional logging
- **Pattern:**
  ```python
  if kid_id is None and penalty_id is None:
      const.LOGGER.info("INFO: Resetting all penalties for all kids.")
  elif kid_id is None:
      const.LOGGER.info("INFO: Resetting penalty '%s' for all kids.", penalty_name)
  elif penalty_id is None:
      const.LOGGER.info("INFO: Resetting all penalties for kid '%s'.", kid_name)
  else:
      const.LOGGER.info("INFO: Resetting penalty '%s' for kid '%s'.", penalty_name, kid_name)
  ```
- **Fix:** ~~Create `_log_reset_action()` helper~~ **DEFERRED** - Pending coordinator review
- **Effort:** ~~10 minutes~~ **DEFERRED**

**M6. Date Parsing Uses Generic Exception**

- **Severity:** Medium
- **Location:** Lines 1102-1118 (`handle_set_chore_due_date`)
- **Current:** `except Exception as err:`
- **Fix:** Catch specific exceptions: `ValueError`, `TypeError`, `AttributeError`
- **Effort:** 3 minutes

**M7. Missing Service Implementation - adjust_points**

- **Severity:** Medium (potential dead code)
- **Location:** const.py Lines 1495, 1572
- **Issue:** Constants define `SERVICE_ADJUST_POINTS` but no handler exists
- **Investigation Needed:**
  1. Was this service removed?
  2. Is it pending implementation?
  3. Should constants be removed?
- **Fix:** Research history, either implement or remove constants
- **Effort:** 30 minutes (research) or 2 minutes (delete constants)

**M8. Service Registration Order**

- **Severity:** Medium (maintainability)
- **Location:** Lines 1172-1259
- **Issue:** Services registered in mixed order (not alphabetical, not functional groups)
- **Current Order:** claim_chore, approve_chore, disapprove_chore, redeem_reward, approve_reward, disapprove_reward, apply_penalty, reset_all_data, reset_all_chores, reset_overdue_chores, reset_penalties, reset_bonuses, reset_rewards, remove_awarded_badges, set_chore_due_date, skip_chore_due_date, apply_bonus
- **Recommendation:** Group by function:
  1. Chore lifecycle (3 services)
  2. Reward lifecycle (3 services)
  3. Point adjustments (2 services)
  4. Reset operations (7 services)
  5. Date management (2 services)
- **Effort:** 10 minutes (reorder with comments)

**M9-M12. Schema Organization, Import Style, etc.**

- **Severity:** Medium/Low
- **Status:** Acceptable as-is, cosmetic improvements
- **Effort:** 10 minutes each if pursued

---

### **Low Priority Issues (6)**

**L1-L6. Comment Style, Magic Numbers, Brief Docstrings**

- **Severity:** Low
- **Status:** Acceptable as-is, minor polish
- **Effort:** 5 minutes each if pursued

---

## Phased Implementation Plan

### **Phase 1: Critical Fixes + Documentation** ✅ PRIORITY

**Goal:** Mandatory compliance, document design decisions
**Estimated Time:** 30 minutes
**Testing:** Quick lint check, no full test suite needed

**Tasks:**

1. ✅ Add `-> None` return type hints to all 15 handlers missing them
2. ✅ Add `-> None` to `async_setup_services()`
3. ✅ Replace bare `except Exception:` with specific exceptions in backup code (Line 936)
4. ✅ Add authorization design documentation comment at top of `async_setup_services()`
5. ✅ Add brief comments to 13 handlers explaining authorization bypass behavior

**Changes:**

- File: `services.py`
- Lines affected: 142, 145, 194, 267, 327, 411, 480, 540, 607, 672, 733, 794, 839, 906, 936-941, 970, 1055

**Validation:**

```bash
# Type checking
python -m mypy custom_components/kidschores/services.py

# Quick lint
python -m pylint custom_components/kidschores/services.py --disable=all --enable=E0601,E0602,E1101
```

---

### **Phase 2: Logging and Validation Fixes** ⏭️ HIGH PRIORITY

**Goal:** Fix error reporting, add missing validation
**Estimated Time:** 20 minutes
**Testing:** Quick lint check, focused tests on affected handlers

**Tasks:**

1. ✅ Fix 4 instances of `LOGGER.info("ERROR:...")` → `LOGGER.error(...)`
2. ✅ Add missing `WARNING:` prefix to `handle_disapprove_reward` (Line 524)
3. ✅ Add recurring chore validation to `handle_skip_chore_due_date`
4. ✅ Fix `handle_remove_awarded_badges` to resolve names to IDs (requires coordinator change)

**Changes:**

- File: `services.py`
- Lines affected: 263, 472, 524, 605, 846-848, 909, 1130-1169

**Validation:**

```bash
# Lint check
./utils/quick_lint.sh custom_components/kidschores/services.py

# Focused tests
python -m pytest tests/test_services.py::test_skip_chore_due_date -v
python -m pytest tests/test_services.py::test_remove_awarded_badges -v
```

---

### **Phase 2B-Pre: Add Error Case Tests** ⚠️ REQUIRED BEFORE REFACTORING

**Goal:** Establish baseline error handling behavior before code changes
**Estimated Time:** 15 minutes
**Priority:** 🚨 BLOCKING - Must complete before Phase 2B implementation

**Rationale:**

- Current tests only verify success paths (3 tests, 0 error cases) - see Test Coverage Assessment above
- Helper refactoring changes 40+ call sites with NO validation
- Need baseline to prove helpers maintain identical error behavior
- Error tests catch regressions during refactoring

**Tasks:**

1. ✅ Add `test_service_claim_chore_invalid_kid_name` to test_services.py
2. ✅ Add `test_service_claim_chore_invalid_chore_name` to test_services.py
3. ✅ Add `test_service_apply_penalty_invalid_penalty_name` to test_services.py

**Test Pattern:**

```python
async def test_service_claim_chore_invalid_kid_name(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test claim_chore service with invalid kid name."""
    with pytest.raises(HomeAssistantError, match=\"Kid 'NonExistent' not found\"):
        await hass.services.async_call(
            DOMAIN, SERVICE_CLAIM_CHORE,
            {ATTR_KID_NAME: \"NonExistent\", ATTR_CHORE_NAME: \"Feed Cats\"},
            blocking=True
        )
```

**Validation:**

```bash
# Run new error tests (should PASS with current code)
python -m pytest tests/test_services.py::test_service_claim_chore_invalid_kid_name -v
python -m pytest tests/test_services.py::test_service_claim_chore_invalid_chore_name -v
python -m pytest tests/test_services.py::test_service_apply_penalty_invalid_penalty_name -v

# Verify all tests still pass (baseline: 349 total, 6 service tests)
python -m pytest tests/test_services.py -v
```

**Success Criteria:**

- ✅ 3 new error tests added to test_services.py
- ✅ All 6 service tests pass (3 existing success + 3 new error cases)
- ✅ Baseline error behavior documented and validated
- ✅ Test file expanded from 182 → ~270 lines
- ✅ Ready to proceed with Phase 2B implementation

**🚨 BLOCKER**: Phase 2B implementation cannot proceed until these tests exist and pass.

---

### **Phase 2B: Code Deduplication - Entity Lookup Helpers** 🔄 READY TO START

**Goal:** Eliminate 200+ lines of duplicate entity lookup code
**Estimated Time:** 45 minutes
**Prerequisites:** ✅ Phase 2B-Pre complete (error tests added and passing)
**Testing:** Full test suite (352 tests) + 3 error tests from Phase 2B-Pre validate refactoring

**Implementation Approach:**
Create 6 new helper functions in kc*helpers.py that wrap existing `get*\*\_id_by_name()`functions and raise`HomeAssistantError` if entity not found.

**Tasks:**

1. ✅ **Add Import to kc_helpers.py** (Line 14)

   ```python
   from homeassistant.exceptions import HomeAssistantError
   ```

2. ✅ **Add 6 Helper Functions** (After line 243, after `get_friendly_label()`)

   Add section separator:

   ```python
   # ────────────────────────────────────────────────────────────────
   # 🔍 Entity Lookup Helpers with Error Raising
   # These helpers wrap the get_*_id_by_name() functions and raise
   # HomeAssistantError if the entity is not found. Used primarily by
   # services.py to eliminate duplicate lookup+validation patterns.
   # ────────────────────────────────────────────────────────────────
   ```

   Add 6 functions following this pattern:

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
       """
       kid_id = get_kid_id_by_name(coordinator, kid_name)
       if not kid_id:
           const.LOGGER.warning("WARNING: %s: Kid not found: %s", action, kid_name)
           raise HomeAssistantError(f"Kid '{kid_name}' not found")
       return kid_id
   ```

   Create similar functions for:

   - `get_chore_id_or_raise(coordinator, chore_name, action) -> str`
   - `get_reward_id_or_raise(coordinator, reward_name, action) -> str`
   - `get_penalty_id_or_raise(coordinator, penalty_name, action) -> str`
   - `get_bonus_id_or_raise(coordinator, bonus_name, action) -> str`
   - `get_badge_id_or_raise(coordinator, badge_name, action) -> str`

3. ✅ **Update services.py Call Sites** (40+ occurrences)

   Replace this 4-line pattern:

   ```python
   kid_id = kh.get_kid_id_by_name(coordinator, kid_name)
   if not kid_id:
       const.LOGGER.warning("WARNING: Claim Chore: Kid not found: %s", kid_name)
       raise HomeAssistantError(f"Kid '{kid_name}' not found")
   ```

   With this 1-line call:

   ```python
   kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Claim Chore")
   ```

   **Affected Handlers (40+ call sites):**

   - `handle_claim_chore` - kid + chore lookups (Lines ~162-177)
   - `handle_approve_chore` - kid + chore lookups (Lines ~231-246)
   - `handle_disapprove_chore` - kid + chore lookups (Lines ~309-324)
   - `handle_redeem_reward` - kid + reward lookups (Lines ~380-395)
   - `handle_approve_reward` - kid + reward lookups (Lines ~452-467)
   - `handle_disapprove_reward` - kid + reward lookups (Lines ~521-536)
   - `handle_apply_penalty` - kid + penalty lookups (Lines ~575-590)
   - `handle_reset_penalties` - penalty lookup (Line ~648)
   - `handle_reset_bonuses` - bonus lookup (Line ~713)
   - `handle_reset_rewards` - kid + reward lookups (Lines ~778-794)
   - `handle_remove_awarded_badges` - kid + badge lookups (Lines ~814-829)
   - `handle_apply_bonus` - kid + bonus lookups (Lines ~875-890)
   - `handle_reset_overdue_chores` - kid lookup (Line ~941)
   - `handle_set_chore_due_date` - kid + chore lookups (Lines ~1074-1089)
   - `handle_skip_chore_due_date` - kid + chore lookups (Lines ~1130-1145)

**Changes Summary:**

- File: `kc_helpers.py`

  - Add import: 1 line (line 14)
  - Add section separator: 6 lines (after line 243)
  - Add 6 helper functions: ~24 lines each = ~144 lines total
  - Total additions: ~150 lines (final: ~1703 lines)

- File: `services.py`
  - Replace 40+ occurrences of 4-line pattern with 1-line call
  - Net reduction: ~120 lines (1290 → ~1170 lines)

**Validation:**

```bash
# Quick lint for both files
./utils/quick_lint.sh custom_components/kidschores/kc_helpers.py
./utils/quick_lint.sh custom_components/kidschores/services.py

# Test helpers work correctly
python -m pytest tests/test_services.py -v --tb=short

# Full test suite
python -m pytest tests/ -v --tb=short
```

**Design Rationale:**

- **Location Choice**: Added to kc_helpers.py (not new service_helpers.py)

  - Follows existing pattern (kc*helpers already has `get*\*\_id_by_name()` functions)
  - Avoids file proliferation
  - File split decision deferred until coordinator review

- **Pattern Precedent**: Follows Home Assistant core pattern

  - Similar to `device_automation.__init__.py:async_get_entity_registry_entry_or_raise()`
  - Common pattern in camera/helper.py and other core integrations

- **Error Messages**: Keep current format for consistency
  - Maintains existing user-facing error messages
  - Translation key migration deferred to Phase 4
  - Action parameter provides context for logging

**Success Criteria:**

- ✅ All 6 helper functions added to kc_helpers.py
- ✅ All 40+ call sites updated in services.py
- ✅ No pylint/type errors in either file
- ✅ All 349 tests pass
- ✅ Net code reduction of ~120 lines (after adding helpers)

---

### **Phase 3: Error Handling Standardization** ⏭️ MEDIUM PRIORITY

**Goal:** Consistent error handling across all handlers
**Estimated Time:** 60 minutes
**Testing:** Full test suite required

**Tasks:**

1. ✅ Document which coordinator methods can raise exceptions
2. ✅ Choose standard error handling pattern (Pattern A recommended)
3. ✅ Apply pattern to all 17 handlers
4. ✅ Research/fix inconsistent points validation logic
5. ✅ Fix date parsing to use specific exceptions (Line 1102)

**Changes:**

- File: `services.py`
- Lines affected: All 17 handlers (144-1169)
- Requires understanding coordinator exception behavior

**Validation:**

```bash
# Full test suite
python -m pytest tests/test_services.py -v --tb=short
python -m pytest tests/ -v --tb=short
```

---

### **Phase 4: Translation Keys and Polish** ⏭️ MEDIUM PRIORITY

**Goal:** Internationalization support, code maintainability
**Estimated Time:** 90 minutes
**Testing:** Full test suite + translation validation

**Tasks:**

1. ✅ Add 15+ translation keys to `const.py`
2. ✅ Add translations to `strings.json` (English + existing languages)
3. ✅ Update 30+ hardcoded error messages to use translation keys
4. ✅ Expand `async_setup_services()` docstring
5. ✅ Reorder service registration by functional groups
6. ✅ Research/resolve missing `adjust_points` service

**Changes:**

- File: `services.py` (30+ changes)
- File: `const.py` (15+ new constants)
- File: `strings.json` (15+ new entries)

**Validation:**

```bash
# Full test suite
python -m pytest tests/ -v --tb=short

# Translation validation
python -m script.translations develop --all

# Hassfest validation
python -m script.hassfest
```

---

### **DEFERRED: Additional Code Deduplication** 🔄 PENDING COORDINATOR REVIEW

**Goal:** Further reduce code duplication beyond Phase 2B entity lookups
**Estimated Time:** TBD after coordinator review
**Reason for Deferral:** User wants to review coordinator patterns first

**Deferred Tasks:**

1. ✅ ~~Create helper functions for entity lookup patterns~~ - **COMPLETED IN PHASE 2B**
2. 🔄 Create `_log_reset_action()` helper for reset handlers (duplicate logging pattern)
3. 🔄 Evaluate need for service_helpers.py file (may split during coordinator review)

**Will Revisit After:**

- Coordinator code review
- Understanding coordinator exception patterns
- Identifying additional service-specific vs general helper patterns
- Evaluating if kc_helpers.py should be split into multiple files

---

## Testing Strategy

### **Phase 1 (Critical)**

- ✅ Type checking with mypy
- ✅ Pylint critical errors only
- ⏭️ No functional tests needed (type hints are compile-time)

### **Phase 2 (Logging/Validation)**

- ✅ Lint checks
- ✅ Focused tests on 2 modified handlers
- ✅ Log message validation (check for ERROR level)

### **Phase 3 (Error Handling)**

- ✅ Full test suite (349 tests)
- ✅ Test error paths for all 17 handlers
- ✅ Verify exception types and messages

### **Phase 4 (Translations)**

- ✅ Full test suite
- ✅ Translation script validation
- ✅ Hassfest integration check
- ✅ Manual verification of translated error messages

---

## Success Criteria

### **Phase 1 Complete When:**

- ✅ Mypy passes with no errors in services.py
- ✅ All handlers have return type hints
- ✅ Authorization design decision is documented
- ✅ Bare exception catch replaced with specific exceptions

### **Phase 2 Complete When:**

- ✅ All log messages use correct level (no `info("ERROR:...")`)
- ✅ `handle_skip_chore_due_date` validates recurring chores
- ✅ `handle_remove_awarded_badges` consistent with other handlers
- ✅ Pylint rating maintains 9.8+/10

### **Phase 3 Complete When:**

- ✅ Coordinator exception behavior documented
- ✅ All 17 handlers use consistent error handling pattern
- ✅ 349 tests pass
- ✅ Test coverage maintained at 56%+

### **Phase 4 Complete When:**

- ✅ Zero hardcoded user-facing strings remain
- ✅ All error messages use translation keys
- ✅ Translation script validates successfully
- ✅ Hassfest passes
- ✅ Services registered in logical order with group comments

### **Final Target:**

- **Code Quality Score:** 9.5/10 (up from 7.5/10)
- **Type Hint Coverage:** 100%
- **Logging Consistency:** 100%
- **Error Handling Consistency:** 100%
- **Translation Coverage:** 100% (user-facing strings)

---

## Risk Assessment

### **Low Risk**

- Phase 1 (type hints, documentation)
- Phase 2 (logging fixes, validation)
- All changes are non-functional or add safety checks

### **Medium Risk**

- Phase 3 (error handling changes)
- Changes to exception catching could alter error reporting
- Mitigation: Comprehensive testing of error paths

### **Low Risk**

- Phase 4 (translation keys)
- Changes error message format but not behavior
- Mitigation: Verify all translation keys exist before rollout

---

## Notes for Future Work

### **Coordinator Review (Next Session)**

When reviewing coordinator.py, consider:

1. Which methods can raise exceptions?
2. What's the standard exception pattern?
3. Are there common patterns suitable for helper abstraction?
4. Should coordinator do entity resolution or services.py?

### **Service Helper Decision (Pending)**

After coordinator review, decide:

1. Location: kc_helpers.py vs new service_helpers.py
2. Scope: Entity lookup only or broader service patterns?
3. Signatures: Error handling in helper or caller?

### **UI Authorization Review (Separate Task)**

Document and verify authorization at UI layer:

1. Button entities - who can press?
2. Dashboard cards - access control?
3. Service calls from UI - user context propagation?

---

## Appendix: Issue Reference

### **Full Issue List (26 issues)**

**Implemented/To Be Implemented:**

- C1: Missing return type hints (15 handlers) - Phase 1 ✅
- C2: Bare exception catch - Phase 1 ✅
- H1: Logging inconsistency (4 instances) - Phase 2 ✅
- H2: Duplicate code (200+ lines) - DEFERRED 🔄
- H3: Inconsistent error handling - Phase 3 ✅
- H4: Missing validation (skip_chore_due_date) - Phase 2 ✅
- H5: Missing log prefix (disapprove_reward) - Phase 2 ✅
- H6: remove_awarded_badges name resolution - Phase 2 ✅
- M1: async_setup_services return type - Phase 1 ✅
- M2: async_setup_services docstring - Phase 4 ✅
- M3: Hardcoded error messages (30+) - Phase 4 ✅
- M4: Inconsistent points validation - Phase 3 ✅
- M5: Duplicate reset logging - DEFERRED 🔄
- M6: Generic exception in date parsing - Phase 3 ✅
- M7: Missing adjust_points service - Phase 4 ✅
- M8: Service registration order - Phase 4 ✅

**Won't Fix (Intentional Design):**

- C3: Missing auth check (reset_all_data) - DOCUMENTED ✅
- C4: Missing auth check (reset_all_chores) - DOCUMENTED ✅
- H7: Missing auth check (reset_overdue_chores) - DOCUMENTED ✅
- H8: Missing auth check (set_chore_due_date) - DOCUMENTED ✅

**Low Priority (Acceptable As-Is):**

- M9-M12: Schema organization, imports, etc. - Optional polish
- L1-L6: Comment style, magic numbers, etc. - Optional polish

---

**End of Plan**
