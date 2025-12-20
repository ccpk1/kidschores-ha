# Badge Assignment Consistency Refactor

## Initiative snapshot

- **Name / Code**: Badge Assignment Consistency Refactor (BAC-2025-12)
- **Target release / milestone**: v0.4.0 (schema v42)
- **Owner / driver(s)**: Development Team
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                           | Description                                                                 | % complete | Quick notes                                                                  |
| -------------------------------------- | --------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------- |
| Phase 1 – Analysis & Testing Design    | Impact analysis, testing strategy, migration/normal use validation coverage | 100%       | ✅ COMPLETE - Baseline tests created, migration tested                       |
| Phase 2 – Core Logic Updates           | Update badge assignment logic, add config/options flow validation           | 100%       | ✅ COMPLETE - Coordinator logic + flow validation + translations implemented |
| Phase 3 – Testing Updates              | Update baseline tests to reflect new explicit assignment behavior           | 100%       | ✅ COMPLETE - All 11 baseline tests pass with Phase 2 changes                |
| Phase 4 – Dashboard Helper Enhancement | Leverage new assignment logic to show all assigned badges in helper         | 0%         | Ready to start - Core feature change complete                                |

### 1. Key objective

Refactor badge assignment behavior to require explicit kid assignment (like chores), eliminating automatic "apply to all kids" when no kids are assigned. This improves consistency across the system and gives parents more granular control.

**Current behavior:**

- Badge with empty `assigned_to` → automatically applies to all kids
- Badge with one/multiple kids in `assigned_to` → applies only to those kids

**Target behavior:**

- Badge with empty `assigned_to` → does not apply to any kids
- Badge with one/multiple kids in `assigned_to` → applies only to those kids

### 2. Summary of recent work

**Phase 1 (COMPLETE ✅):**

- Created 4 baseline test files validating current behavior
- 11 tests for migration, assignment, and validation scenarios
- Confirmed old auto-assign behavior with intentional failure test

**Phase 2 (COMPLETE ✅):**

- Updated coordinator badge assignment logic (2 locations: cumulative + non-cumulative)
- Added flow_helpers.py validation requiring at least one kid assigned
- Added TRANS_KEY_CFOF_BADGE_REQUIRES_ASSIGNMENT constant
- Added English translations in both config flow and options flow error sections
- All linting passed

**Phase 3 (COMPLETE ✅):**

- Updated 4 baseline tests to use explicit kid assignments
- Changed test documentation to reflect "Feature Change v4.2"
- All 11 baseline tests now pass (was 7 pass, 4 fail → now 11 pass)
- All linting checks passed

### 3. Next steps (short term)

1. ✅ Update baseline tests to use explicit kid assignments - COMPLETE
2. Run full integration test suite to verify no regressions
3. Phase 4: Dashboard helper enhancement to show all assigned badges
4. Document feature change in release notes
5. Consider user migration guide for existing badge data

### 4. Risks / blockers

- **Data Loss Risk**: Migration must correctly assign existing badges with empty `assigned_to` to prevent losing badge progress data
- **User Communication**: Clear migration messaging required so parents understand the behavior change
- **Dashboard Rendering**: Dashboard filters need updates to reflect new filtering logic
- **Backward Compatibility**: Consider impact on users upgrading from older versions
- **Existing Integrations**: Test impact on badge sensors and coordinator logic

### 5. References

- **Architecture Overview**: [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- **Code Review Guide**: [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
- **Testing Instructions**: [tests/TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md)
- **Current Implementation**:
  - [coordinator.py#\_check_badges_for_kid](../../custom_components/kidschores/coordinator.py) - Badge checking logic (line ~4836)
  - [const.py#DATA_BADGE_ASSIGNED_TO](../../custom_components/kidschores/const.py) - Badge assignment constant (line ~973)
  - [flow_helpers.py](../../custom_components/kidschores/flow_helpers.py) - Config flow validation
  - [translations/en.json](../../custom_components/kidschores/translations/en.json) - User-facing text

---

## Detailed phase tracking

### Phase 1 – Analysis & Testing Design

**Goal**: Complete comprehensive impact analysis, design testing strategy for both migration scenario and normal use, establish design decisions for the refactor.

**Steps / detailed work items**

1. **Code Impact Analysis**

   - [ ] Identify all locations checking `DATA_BADGE_ASSIGNED_TO` in coordinator.py
   - [ ] Document current behavior in `_check_badges_for_kid()` (line ~4953-4954):
     ```python
     is_assigned_to = bool(
         not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
         or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
     )
     ```
   - [ ] List all affected functions:
     - `_check_badges_for_kid()` – Primary badge evaluation logic
     - `_sync_badge_progress_for_kid()` – Badge progress sync (line ~6701-6706)
     - `_build_dashboard_helper_badge_list()` – Dashboard badge filtering (line ~6476-6477)
     - `_persist_ui_helper_data()` – UI helper sensor data
     - `_check_badges_for_pending_maintenance()` – Maintenance checks (line ~6809-6810)
     - Helper sensor filtering logic
   - [ ] Check dashboard template badge filtering logic in `/workspaces/kidschores-ha-dashboard/files/kc_dashboard_all.yaml` (line ~1295)

2. **Data Migration Strategy (v4.2 - No Schema Change)**

   - [ ] **No schema version increment** (staying at v42 for current cycle)
   - [ ] Decide: How to assign orphaned badges (empty `assigned_to`)?
     - Option A: Assign to ALL existing kids (conservative, preserves behavior)
     - Option B: Assign to first kid only (requires manual reassignment)
     - Option C: Clear and require manual reassignment (most explicit but disruptive)
     - **Recommendation**: Option A – Assign to all kids to preserve earned badge history and behavior
   - [ ] Note: Data migration happens at coordinator init time if needed (soft migration)
   - [ ] Define migration logic (applied at runtime):
     ```python
     if badge_info.get(const.DATA_BADGE_ASSIGNED_TO, []) == []:
         # Assign badge to all existing kids
         badge_info[const.DATA_BADGE_ASSIGNED_TO] = list(self.kids_data.keys())
         LOGGER.info(f"Migrated badge '{badge_name}' to all kids")
     ```
   - [ ] Plan when to apply:
     - On coordinator initialization? OR
     - On first badge check for unassigned badge? OR
     - Proactively on startup?
   - [ ] **CRITICAL**: Test BOTH migration scenarios:
     - Existing installations with old data (unassigned badges)
     - Fresh installations (new data only)
   - [ ] Test with sample data including:
     - Badges with no assignment
     - Badges with single kid assignment
     - Badges with multiple kids assignment
     - Badges with earned history

3. **Coordinator Logic Changes**

   - [ ] Change assignment check from:
     ```python
     is_assigned_to = bool(
         not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])  # ← Remove this
         or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
     )
     ```
     To:
     ```python
     is_assigned_to = kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
     ```
   - [ ] Update all 4 locations where this pattern appears (lines ~4953, ~6476, ~6809, ~7198)
   - [ ] Document removed behavior clearly in comments

4. **Config & Options Flow Validation** (BOTH flows required)

   - [ ] **Config Flow Validation** (adding new badge):
     - Should require at least one kid selected
     - Return validation error if empty
     - Error message: To be added to en.json
   - [ ] **Options Flow Validation** (editing existing badge):
     - Should require at least one kid selected
     - Prevent saving with empty assignment
     - Error message: Same as config flow
   - [ ] Review `flow_helpers.py` for both flow paths
   - [ ] Plan validation message in en.json (new key needed):
     - Key: `badge_assigned_to_required` or similar
     - Text: "At least one kid must be assigned to this badge"

5. **Translation Key Changes (en.json only - v4.2)**

   - [ ] **NOTE**: Only updating en.json at this time, no other languages
   - [ ] Map existing keys that need rewording:
     - `add_badge_cumulative` → Update description text
     - `add_badge_periodic` → Update description text
     - `add_badge_achievement` → Update description text
     - `add_badge_challenge` → Update description text
     - `add_badge_special` → Update description text
   - [ ] Remove "Optional" from field labels:
     - Current: `"🧒 Assigned Kids (Optional)"`
     - New: `"🧒 Assigned Kids"` (emphasize requirement)
   - [ ] Create new validation error key in en.json:
     - Key: `badge_assigned_to_required` (or similar)
     - Text: "At least one kid must be assigned to this badge"
     - Context: Used by both config and options flow validation
   - [ ] Update data descriptions for clarity:
     - Old: "Assign this badge to specific kids for tracking."
     - New: "Assign this badge to one or more kids. Required – each badge must be explicitly assigned to track progress."

6. **Testing Coverage Strategy - Migration + Normal Use**

   - [ ] Define test scenarios for BOTH paths:
     - **Path 1: Migration** - Existing installations with unassigned badges
       - How are old badges handled?
       - Are they auto-assigned on startup?
       - Are they handled lazily on first access?
     - **Path 2: Normal Use** - v4.2 installations from start
       - New badges must require assignment
       - Validation prevents invalid creation
       - Coordinator logic correctly filters by assignment
   - [ ] Plan fixture data:
     - Pre-migration data (v4.1 style with empty assignments)
     - Post-migration data (with auto-assigned kids)
     - Fresh data (never had unassigned badges)
   - [ ] Document test execution plan:
     - Unit tests (assignment logic)
     - Integration tests (migration + normal use)
     - Config flow tests (validation)

7. **Design Decision Documentation**
   - [ ] Decide: When should migration/normalization occur?
     - Option A: On coordinator startup (proactive)
     - Option B: On first badge check (lazy)
     - Option C: On first badge creation/edit (reactive)
     - **Recommendation**: Option A (proactive, ensures clean state)
   - [ ] Decide on error handling when existing code tries to create badge without assignment
   - [ ] Plan how to handle edge case: Parent deletes all kids → badges become orphaned
     - Option: Prevent deletion if badges exist, or auto-clear badges
   - [ ] Dashboard helper sensor enhancement design:
     - **Current gap**: KidBadgeProgress only populated after badge earned
     - **Solution**: Include ALL assigned badges in dashboard helper, not just earned
     - Benefits: Can show progress for unearned badges, complete badge list visible

**Key issues**

- Migration timing (proactive vs lazy) - needs careful decision
- Error handling for edge cases during development
- Dashboard helper enhancement scope and implementation
- Testing coverage must verify both old data (migration) and new data (normal use)

---

### Phase 2 – Core Logic Updates & Validation

**Goal**: Update coordinator badge evaluation logic, implement validation in both config and options flows, handle any runtime normalization of existing data.

**STATUS: ✅ COMPLETE (100%)**

**Steps / detailed work items**

1. **Runtime Data Normalization (if needed)**

   - [x] ✅ **Decision**: No migration needed - existing badges already migrated in Phase 1c
   - [x] ✅ **Approach**: New behavior enforced immediately via coordinator logic changes
   - [x] ✅ Backward compatibility maintained - existing assigned badges work unchanged

2. **Coordinator Assignment Logic Updates**

   - [x] ✅ Updated cumulative badge check in `_check_badges_for_kid()` at line ~4951-4957
     ```python
     # Feature Change v4.2: Badges now require explicit assignment.
     # Empty assigned_to means badge is not assigned to any kid.
     assigned_to_list = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
     is_assigned_to = kid_id in assigned_to_list
     ```
   - [x] ✅ Updated non-cumulative badge check in `_update_kid_badge_progress()` at line ~6473-6479
   - [x] ✅ Both locations now use explicit assignment check (no auto-assign when empty)
   - [x] ✅ Added "Feature Change v4.2" comments documenting the behavior change
   - [x] ✅ Removed old pattern: `bool(not assigned_to or kid_id in assigned_to)`
   - [x] ✅ New pattern: `kid_id in assigned_to_list` (explicit only)

3. **Validation in Config Flow (new badge creation)**

   - [x] ✅ Updated `flow_helpers.py::validate_badge_common_inputs()` at line ~975-981
   - [x] ✅ Added validation check: `if not assigned_to or len(assigned_to) == 0`
   - [x] ✅ Returns error key: `const.TRANS_KEY_CFOF_BADGE_REQUIRES_ASSIGNMENT`
   - [x] ✅ Applies to 4 badge types that support assigned_to (cumulative, daily, periodic, special_occasion)
   - [x] ✅ Defense-in-depth validation (catches empty assignment before badge creation)

4. **Validation in Options Flow (editing existing badge)**

   - [x] ✅ Same validation function used by options flow (validate_badge_common_inputs shared)
   - [x] ✅ Prevents editing badge to remove all kid assignments
   - [x] ✅ Consistent error message across both flows

5. **Translation Keys Added**

   - [x] ✅ Added constant in const.py: `TRANS_KEY_CFOF_BADGE_REQUIRES_ASSIGNMENT = "badge_requires_assignment"`
   - [x] ✅ Added English translation in config flow errors: `"badge_requires_assignment": "At least one kid must be assigned to this badge"`
   - [x] ✅ Added English translation in options flow errors (line ~1142): Same message for consistency

6. **Testing & Validation**
   - [x] ✅ All code changes linted successfully (no errors)
   - [x] ✅ Baseline tests executed - 4 tests fail as expected (testing old auto-assign behavior)
   - [x] ✅ 7 tests pass (migration test and validation tests unaffected)
   - [ ] Update 4 failing baseline tests to use explicit kid assignments (Phase 3 task)

**Key Outcomes:**

- Feature change fully implemented at coordinator and validation levels
- Empty `assigned_to` now means "not assigned to any kid" (not "assigned to all")
- Validation prevents creating/editing badges without explicit assignment
- All changes include "Feature Change v4.2" documentation comments
- Backward compatible - existing assigned badges continue working unchanged& Options Flow Updates + English Translations
  ```

  ```

**Goal**: Update both config and options flows to enforce assignment validation, update en.json translations to reflect new

- [ ] Log warnings for any inconsistencies found
- [ ] Add to diagnostics endpoint if needed
- [ ] Log during startup if normalization was needed

6. **Backward Compatibility Handling**
   - [ ] Ensure code gracefully handles old data if encountered
   - [ ] Log info messages when normalizing old-style badges
   - [ ] Add comments in code explaining the change:
     - Old behavior: Empty assignment → applies to all kids
     - New behavior: Empty assignment → applies to no kids (now normalized)

**Key issues**

- Migration must complete successfully for all user data
- Version increment must be coordinated with manifest.json
- Backward compatibility testing critical

---

### Phase 3 – Config Flow & Translation Updates

**Goal**: Update user-facing config flow, error messages, and translations to reflect new assignment requirement.

**Steps / detailed work items**

1. **Config Flow Text Updates (en.json only)**

   - [ ] Update `translations/en.json` for all 5 badge type flows:
     - `config.step.badges` (cumulative)
     - `config.step.add_badge_periodic` (periodic)
     - `config.step.add_badge_achievement` (achievement)
     - `config.step.add_badge_challenge` (challenge)
     - `config.step.add_badge_special` (special occasion)
   - [ ] Change field label from:
     - Old: `"🧒 Assigned Kids (Optional)"`
     - New: `"🧒 Assigned Kids"` (remove "Optional")
   - [ ] Update field descriptions to reflect requirement:
     - Old: `"Assign this badge to specific kids for tracking."`
     - New: `"Assign this badge to one or more kids. Required – each badge must be explicitly assigned to track progress."`
   - [ ] Update flow step descriptions where applicable

2. **Options Flow Text Updates (en.json only)**

   - [ ] Update `translations/en.json` for options flow (editing existing badges)
   - [ ] Ensure same text as config flow for consistency
   - [ ] Same label and description changes

3. **Validation Error Messages (en.json)**

   - [ ] Add new error translation key:
     - Key: `badge_assigned_to_required` (or similar)
     - Text: `"At least one kid must be assigned to this badge."`
   - [ ] Location: Under `config.error` section in en.json
   - [ ] Used by both config and options flow validation

4. **Help Text & Data Descriptions (en.json)**

   - [ ] Update data descriptions (`data_description` section):
     - Clarify that empty assignment is no longer valid
     - Emphasize requirement in all badge type sections
   - [ ] Update descriptions for each of 5 badge types

5. **Dashboard Template Verification**

   - [ ] Review `/workspaces/kidschores-ha-dashboard/files/kc_dashboard_all.yaml` (line ~1295)
   - [ ] Current filter logic already handles explicit assignment:
     ```jinja2
     {%- set assigned = badge_attrs.get('kids_assigned') -%}
     {%- if assigned is iterable and assigned is not string and assigned | length > 0 and name not in assigned -%}
       {%- continue -%}
     {%- endif -%}
     ```
   - [ ] No dashboard template changes needed (already correct)
   - [ ] Verify dashboard correctly filters post-normalization
   - [ ] Test with sample data

6. **Localization Note**
   - [ ] **NOTE**: Only en.json updated for v4.2
   - [ ] Translations to de.json, es.json, etc. deferred to future release
   - [ ] Document this decision for future translators

**Key issues**

- Translation changes affect 5+ badge creation flows
- Dashboard filtering must work correctly post-migration
- Error messages must be clear to end users

---

### Phase 4 – Dashboard Helper Enhancement

**Goal**: Leverage explicit assignment logic to improve dashboard helper sensor data structure, resolving the KidBadgeProgress gap.

**Steps / detailed work items**

1. **Current Gap Analysis**

   - [ ] Understand current limitation:
     - KidBadgeProgress only populated AFTER badge earned
     - Dashboard sensor can't show unearned badge info
     - Can't display progress for badges not yet earned
   - [ ] Identify affected dashboard features:
     - Badge progress display
     - Badge showcase section
     - Badge list visibility

2. **Solution Design**

   - [ ] Plan new dashboard helper data structure:
     - Include ALL assigned badges (not just earned)
     - Pre-compute badge info for all assigned badges
     - Include threshold, description, target info
   - [ ] Modify `_build_dashboard_helper_badge_list()`:
     - For each kid
     - For each badge in system
     - If badge assigned to kid → include in helper
     - Include earned status + progress info
   - [ ] Enhanced helper attributes:
     ```python
     'all_assigned_badges': [
       {
         'id': 'badge_id',
         'name': 'Badge Name',
         'earned': False,
         'progress': {...},
         'threshold': {...}
       }
     ]
     ```

3. **Implementation**

   - [ ] Update `_build_dashboard_helper_badge_list()`
   - [ ] Ensure performance (don't slow down helper sensor)
   - [ ] Test with large badge counts
   - [ ] Document data structure changes

4. **Dashboard Template Updates**
   - [ ] Update kc_dashboard_all.yaml to use new helper data
   - [ ] Can now show all assigned badges (not just earned)
   - [ ] Improved badge display coverage

---

## Testing Rules & Guidelines

**Goal**: Ensure all badge assignment refactor tests follow established patterns and testing agent instructions for consistency, reliability, and maintainability.

### Critical Testing Rules

1. **Follow Testing Agent Instructions Exactly**

   - Always use terminal/console sessions for test execution (never simulate)
   - Use proper fixtures and data loading patterns
   - Follow established mock patterns for notifications and external dependencies

2. **Never Guess at Data Locations or Field Names**

   - Always examine existing code to find exact field names and constants
   - Use grep/search to find patterns before implementing
   - Reference `const.py` for all field name constants (e.g., `DATA_BADGE_ASSIGNED_TO`)
   - Never hardcode strings that should be constants

3. **Always Use Existing Working Patterns**

   - Examine working badge tests before creating new tests
   - Copy established patterns from `test_badge_creation.py`, `test_coordinator.py`, `test_workflow_parent_actions.py`
   - Use existing fixture patterns: `scenario_minimal`, `scenario_medium`, `scenario_full`
   - Follow coordinator access pattern: `coordinator._data.get(DATA_BADGES, {})`

4. **Use Precreated Test Scenarios and Sample Files**

   - Prefer `testdata_scenario_medium.yaml` and `testdata_scenario_full.yaml` for better badge representation
   - Use `scenario_minimal` only for basic testing
   - Leverage existing test data instead of creating new fixtures
   - Use `name_to_id_map` pattern for kid ID lookups

5. **Badge-Specific Testing Context**

   - **Migration Focus**: Only cumulative badges go through migration (other types introduced in current version)
   - **Badge Types**: All 5 badge types need testing but focus migration tests on cumulative
   - **Assignment Patterns**: Test empty `[]`, single kid, multiple kids scenarios
   - **Mock Pattern**: Always use `with patch.object(coordinator, "_notify_kid", new=AsyncMock())`

6. **Badge Architecture Understanding - Dual Data Structure**

   **System Badge** (Configuration Level):

   - Stored in `coordinator._data[DATA_BADGES][badge_id]`
   - Contains: name, type, assignments (`DATA_BADGE_ASSIGNED_TO`), thresholds, awards, etc.
   - This is where assignment logic is configured and checked

   **Kid Badge Data** (Individual Progress Level):

   - Stored in `coordinator.kids_data[kid_id]["badge_progress"][badge_id]`
   - Contains: progress toward earning, earned status, earn date, cycle data
   - Created when kid starts working toward badge or earns it

7. **Established Testing Patterns to Follow**

   ```python
   # Direct coordinator access pattern
   config_entry, name_to_id_map = scenario_minimal
   coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

   # System Badge data access pattern (Configuration)
   system_badges = coordinator._data.get(DATA_BADGES, {})
   system_badge = system_badges[badge_id]
   assigned_to = system_badge.get(DATA_BADGE_ASSIGNED_TO, [])

   # Kid Badge data access pattern (Progress/Earned)
   kid_id = name_to_id_map["kid:Zoë"]
   kid_data = coordinator.kids_data.get(kid_id, {})
   badge_progress = kid_data.get("badge_progress", {})
   kid_badge_data = badge_progress.get(badge_id, {})

   # Dashboard sensor badge access pattern
   dashboard_helper = f'sensor.kc_{Kid_name_normalize}_ui_dashboard_helper'
   ui_badges = state_attr(dashboard_helper, 'badges') or []

   # Notification mocking pattern
   with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
       coordinator._some_method(kid_id)

   # Badge earning test pattern (kid meets threshold)
   # 1. Set up kid with points near threshold
   coordinator.kids_data[kid_id]["points"] = threshold_value - 1
   # 2. Add points to cross threshold
   coordinator._award_points_to_kid(kid_id, 2.0)
   # 3. Verify badge was earned
   earned_badges = kid_data.get("badges_earned", [])
   assert badge_id in earned_badges
   ```

8. **Test Organization Requirements**

   - Group related tests in classes using proper naming
   - Use parametrized tests for scenario variations
   - Include proper docstrings explaining test purpose
   - Add pylint suppressions for test-specific patterns: `# pylint: disable=protected-access`

9. **Coverage Requirements - Comprehensive Badge Testing**

   - Target specific line coverage gaps identified in coordinator badge logic
   - Test **System Badge** configuration and assignment logic
   - Test **Kid Badge** progress tracking and earning scenarios
   - Test **Dashboard Sensor** badge data representation (`badges` key)
   - Test badge earning flow: kid meets threshold → badge awarded → appears in dashboard
   - Include edge cases (empty data, missing fields, invalid formats)
   - Verify error handling and validation paths

10. **Badge Earning Test Scenarios (Critical Gap)**
    - **Current Gap**: Tests may not cover actual badge earning (meeting point thresholds)
    - **Required**: Test complete badge earning workflow:
      1. System badge exists and is assigned to kid
      2. Kid accumulates points toward threshold
      3. Kid crosses threshold (via chore completion, bonus, etc.)
      4. Badge is awarded and appears in kid's badge_progress data
      5. Badge appears in dashboard sensor badges list
      6. Badge entity is created/updated in Home Assistant
    - **Entities to Verify**:
      - System badge entity (configuration)
      - Kid badge entity (once earned)
      - Dashboard sensor `badges` attribute

### Badge Testing Complexity Context

Previous tests avoided badge testing due to complexity, but several working badge tests now exist as samples:

- Badge creation flows are more complex than chore/reward flows
- Badge evaluation logic has multiple code paths
- Badge assignment logic varies by badge type
- Migration only applies to cumulative badges (historical context)

### Test Data Strategy

**Scenario Selection**:

- `scenario_minimal`: Basic testing only (1 kid: Zoë, 1 badge: Bronze Star)
- `scenario_medium`: Better badge representation (2 kids, 6 badges of various types)
- `scenario_full`: Comprehensive badge coverage (3 kids, 9+ badges, all types)

**Badge Assignment Test Cases**:

- **System Badge Level** (Configuration):
  - Empty assignment: `DATA_BADGE_ASSIGNED_TO: []` (current auto-assign behavior)
  - Single assignment: `DATA_BADGE_ASSIGNED_TO: [kid_id]`
  - Multi assignment: `DATA_BADGE_ASSIGNED_TO: [kid_id1, kid_id2]`
  - Invalid assignment: Test error handling
- **Kid Badge Level** (Progress/Earned):
  - Badge progress tracking: `coordinator.kids_data[kid_id]["badge_progress"][badge_id]`
  - Badge earning: `coordinator.kids_data[kid_id]["badges_earned"]` contains badge_id
  - Badge entity creation after earning
- **Dashboard Sensor Level** (UI Representation):
  - Dashboard helper `badges` key contains earned badges for display
  - Badge filtering works correctly with assignment logic
  - UI shows only badges assigned to and earned by specific kid

---

## Testing & Validation (Detailed Test Plan)

**Goal**: Comprehensive testing of BOTH migration scenarios AND normal use to ensure no regressions.

### Test Structure

**Critical**: Tests must cover TWO paths:

1. **Migration Path** - Existing installations upgrading to v4.2
2. **Normal Use Path** - Fresh v4.2 installations

### Steps / detailed work items

1. **Unit Tests - Assignment Logic**

   - [ ] Create test file: `test_badge_assignment_refactor.py`
   - [ ] Test NEW assignment logic (after normalization):

     ```python
     async def test_badge_only_applies_to_assigned_kids():
         """Badge should only trigger for explicitly assigned kids."""
         # Create badge assigned to kid_1 only
         # Verify badge eligibility only for kid_1
         # Verify badge NOT eligible for kid_2
         # Verify badge NOT eligible for kid_3

     async def test_unassigned_badge_does_not_apply():
         """Unassigned badge should not apply to any kid."""
         # Create badge with empty assigned_to
         # Verify badge not eligible for any kid
         # Verify badge does not trigger checks
     ```

   - [ ] Test validation logic:

     ```python
     async def test_config_flow_requires_assignment():
         """Config flow should reject badges without assignment."""
         # Attempt to create badge without kids
         # Verify validation error returned
         # Verify form not submitted

     async def test_options_flow_requires_assignment():
         """Options flow should reject empty assignment on edit."""
         # Create badge with one kid
         # Edit and remove all kids
         # Verify validation error
         # Verify change not saved
     ```

   - [ ] Test edge cases:
     - Single kid badge (only that kid)
     - Multiple kids badge (all those kids, not others)
     - Re-assign kids (from one kid to different one)

2. **Integration Tests - Normal Use Path (Fresh v4.2)**

   - [ ] Test with coordinator full lifecycle:

     ```python
     async def test_new_badge_requires_assignment():
         """New badges created in v4.2 must be assigned."""
         # Create kid
         # Create badge assigned to kid
         # Verify badge checks run
         # Verify badge progress tracked
         # Edit: assign to different kid → verify tracked for new kid only

     async def test_badge_earning_with_assignment():
         """Badge should only be earned if kid is assigned."""
         # Create kid_1, kid_2
         # Create badge assigned to kid_1 only
         # Kid_1 meets badge criteria → badge earned
         # Verify kid_2 does NOT earn badge
         # Verify notifications sent to kid_1 only
     ```

   - [ ] Test dashboard rendering with NEW data:
     - Dashboard helper sensor built correctly
     - Badge list filtered by assignment
     - Dashboard displays only assigned badges
     - Badge helper includes ALL assigned badges (even unearned)

3. **Migration Test Suite - Upgrade Path (Existing Installations)**

   - [ ] **CRITICAL**: Create fixtures for REAL old data:
     - Simulate v4.1/v4.2 early data with unassigned badges
     - Include various badge types
     - Include earned badge history
     - Include mixed assignments (some assigned, some not)
   - [ ] Test normalization/migration:

     ```python
     async def test_normalization_on_startup():
         """Startup should normalize unassigned badges."""
         # Load fixture with old-style unassigned badges
         # Initialize coordinator
         # Verify unassigned badges normalized to all kids
         # Verify normalization logged
         # Verify data persisted correctly

     async def test_normalization_preserves_earned_history():
         """Badge normalization should preserve earned history."""
         # Load fixture:
         # - Badge 1: unassigned, kid_1 earned it
         # - Badge 2: assigned to kid_2, kid_2 earned it
         # - Badge 3: unassigned, not earned
         # Run normalization
         # Verify:
         # - Badge 1 now assigned to all kids, history preserved
         # - Badge 2 unchanged, history intact
         # - Badge 3 now assigned to all kids
         # Verify kid_1 sees Badge 1 in progress
         # Verify kid_2 sees Badge 2 in progress
     ```

   - [ ] Test data persistence post-normalization:
     - Normalize data
     - Coordinator restarts
     - Verify normalized state persists
     - Verify no re-normalization occurs

4. **Backward Compatibility Tests**

   - [ ] Test upgrade scenario (v4.1→v4.2):
     ```python
     async def test_v41_data_handles_upgrade_correctly():
         """Upgrading v4.1 data should normalize correctly."""
         # Load v4.1 fixture data
         # Initialize coordinator as v4.2
         # Verify badges normalized
         # Verify no data loss
         # Verify all badge types handled correctly
     ```
   - [ ] Test downgrade scenario (v4.2→v4.1):
     ```python
     async def test_v42_data_readable_in_v41():
         """Downgrading v4.2 data should remain readable."""
         # Create v4.2 data with assignments
         # Load in v4.1 code (simulate downgrade)
         # Verify assignments ignored gracefully
         # Verify no errors
     ```

5. **Config & Options Flow Tests**

   - [ ] Test config flow (new badge):

     ```python
     async def test_all_5_badge_types_require_assignment():
         """All badge types should require assignment."""
         # Test each badge type:
         # - Cumulative
         # - Periodic
         # - Achievement-linked
         # - Challenge-linked
         # - Special occasion
         # For each:
         # - Form without kids → validation error
         # - Form with kids → success

     async def test_form_state_preserved_on_validation_error():
         """Form should preserve input on validation error."""
         # Enter badge details
         # Skip kids assignment
         # Submit → validation error
         # Verify badge name still in form
         # Verify other fields preserved
         # Assign kids → success
     ```

   - [ ] Test options flow (edit badge):
     ```python
     async def test_options_flow_validates_assignment():
         """Editing badge should validate assignment."""
         # Load existing badge with kids
         # Edit: Remove all kids
         # Submit → validation error
         # Add kids back → success
         # Submit → success
     ```

6. **Behavior Validation Tests**

   - [ ] Test each badge type independently:
     - Cumulative badge assignment logic
     - Periodic badge assignment logic
     - Achievement-linked badge assignment logic
     - Challenge-linked badge assignment logic
     - Special occasion badge assignment logic
   - [ ] Test with various chore configurations:
     - Single chore → badge
     - Multiple chores → badge
     - Shared chores → badge
   - [ ] Test notification flow:
     ```python
     async def test_badge_earned_notification_respects_assignment():
         """Badge earned notification only sent to assigned kid."""
         # Kid_1, Kid_2, Kid_3 exist
         # Badge assigned to Kid_1 only
         # Kid_1 earns badge → notification sent to Kid_1
         # Verify Kid_2, Kid_3 do NOT get notification
         # Verify parent notification mentions assignment
     ```

7. **Performance Tests**

   - [ ] Verify no regression with new logic:
     - Badge evaluation with 10+ badges
     - Multiple kids (5+)
     - Coordinator refresh timing unchanged
   - [ ] Normalization performance:
     - Normalize large dataset (50+ badges)
     - No startup timeout

8. **Dashboard Helper Tests**

   - [ ] Helper sensor data structure:
     ```python
     async def test_dashboard_helper_includes_all_assigned_badges():
         """Helper sensor should include all assigned badges."""
         # Kid_1 assigned to Badge_1, Badge_2
         # Kid_1 earned Badge_1 only
         # Helper sensor includes:
         # - Badge_1 (earned status, progress)
         # - Badge_2 (unearned status, progress)
         # - NOT Badge_3 (not assigned to Kid_1)
     ```
   - [ ] Dashboard template filtering:
     - Correct badges displayed per kid
     - Unearned badges show in dashboard
     - Progress info available

9. **Comprehensive Integration Scenarios**
   - [ ] Scenario: Multiple kids, mixed assignments (Normal Use)
     ```
     Kids: Alice, Bob, Charlie
     Badge A: Assigned to Alice, Bob → only they can earn
     Badge B: Assigned to Charlie only → only they can earn
     Badge C: Assigned to all
     Process:
     - Each kid meets criteria
     - Correct badges earned
     - Notifications sent to correct kids
     - Dashboard shows correct badges
     ```
   - [ ] Scenario: Multiple kids, mixed assignments (Migration)
     ```
     Load v4.1 data:
     - Badge A: unassigned, Alice earned it
     - Badge B: assigned to Charlie, Charlie earned it
     - Badge C: unassigned, not earned
     Upgrade to v4.2:
     - Normalization runs
     - Badge A assigned to [Alice, Bob, Charlie]
     - Badge B unchanged
     - Badge C assigned to [Alice, Bob, Charlie]
     Verify:
     - Alice sees Badge A, C in progress
     - Bob sees Badge A, C
     - Charlie sees all three
     - History preserved
     ```

**Key issues**

- Large test coverage needed for 5+ badge types
- Migration data fixtures must be comprehensive
- Dashboard rendering must be validated against new behavior

---

## Testing & validation

### Test Execution Plan

1. **Unit Tests**

   ```bash
   pytest tests/test_badge_assignment_refactor.py -v
   pytest tests/test_badge_assignment_refactor.py::test_badge_only_applies_to_assigned_kids -v
   pytest tests/test_badge_assignment_refactor.py::test_normalization_* -v
   ```

   - Assignment logic tests
   - Validation tests
   - Normalization tests

2. **Integration Tests (Normal Use)**

   ```bash
   pytest tests/test_coordinator.py -k "badge and not migration" -v
   pytest tests/test_config_flow.py -k "badge" -v
   ```

   - Coordinator lifecycle tests
   - Badge earning flow
   - Config/options flow validation

3. **Integration Tests (Migration)**

   ```bash
   pytest tests/test_badge_assignment_refactor.py::test_normalization* -v
   pytest tests/test_coordinator.py::test_upgrade_scenario -v
   ```

   - Data normalization tests
   - Upgrade scenario tests
   - Data persistence tests

4. **Regression Tests**
   ```bash
   pytest tests/ -v --durations=0
   ```
   - Full suite to ensure no regressions
   - Dashboard integration if available

### Coverage Expectations

- Target: >95% coverage for modified code
- Key files to coverage check:
  - `coordinator.py` (badge functions + normalization)
  - `flow_helpers.py` (config + options validation)
  - Core badge logic (4+ locations)
  - Test files:
    - `test_badge_assignment_refactor.py` (NEW)
    - `test_coordinator.py` (badge sections)
    - `test_config_flow.py` (all badge types)

### Outstanding Tests

- Real user acceptance testing (manual)
- Production data upgrade testing (with real customer data)
- Dashboard rendering with real data
- Performance testing with large datasets

### Test Data Fixtures

- **Fixture 1**: Fresh v4.2 data (5+ badges, various assignments)
- **Fixture 2**: Old v4.1 data with unassigned badges (for normalization testing)
- **Fixture 3**: Mixed earned/unearned badges with history
- **Fixture 4**: Edge cases (single kid, all kids, overlapping assignments)

---

## Notes & follow-up

### Architecture Considerations

1. **Storage-Only Model Compliance** (v4.2+ requirement)

   - Migration data lives in `.storage/kidschores_data`
   - Config entry contains only system settings
   - Badge assignment stored in storage only ✅

2. **Internal ID Usage**

   - Always use `internal_id` (UUID) for lookups, never entity names
   - Assignment uses kid IDs (UUIDs) not names ✅

3. **Logging Standards**

   - Use lazy logging: `LOGGER.info("Text: %s", var)` not f-strings
   - Apply to migration logging extensively

4. **Constants Pattern**
   - All strings use const.py (`DATA_BADGE_ASSIGNED_TO`, `TRANS_KEY_CFOF_BADGE_ASSIGNED_TO`)
   - No hardcoded strings

### Implementation Order (Recommended)

1. **First**: Migration logic + coordinator changes (Phases 1-2)

   - Core logic must be solid before config flow
   - Can be tested independently

2. **Second**: Config flow updates (Phase 3)

   - Depends on coordinator changes
   - Translations follow

3. **Third**: Testing suite (Phase 4)
   - Tests everything after implementation
   - Ensures no regressions

### Breaking Changes Summary

- **User-facing**: Requires explicit assignment (previously optional)
- **Existing data**: Migration assigns to all kids (preserves current behavior)
- **API**: Coordinator logic changes are internal only
- **Dashboard**: Filtering logic unchanged (already correct)

### Post-Completion Checklist

- [ ] All linting passes: `./utils/quick_lint.sh --fix`
- [ ] All tests pass: `python -m pytest tests/ -v --tb=line`
- [ ] Code coverage meets 95% threshold
- [ ] All translations updated for all supported languages
- [ ] Documentation updated in ARCHITECTURE.md if needed
- [ ] Migration tested with sample data
- [ ] Dashboard verified working with new behavior
- [ ] Release notes drafted explaining behavior change

### Decisions Captured

1. **No Schema Version Change (v4.2 current cycle)**

   - Staying at v42 for this release
   - Normalization done at runtime
   - Can be incremented in future if needed

2. **Normalization Strategy**: Assign unassigned badges to ALL kids

   - Rationale: Preserves current behavior for existing users, maintains earned badge history
   - Alternative considered: Assign to first kid only (would break expectations)
   - Timing: Proactive on startup (ensures clean state)

3. **Validation in Both Flows**: Config + Options flow validation

   - Config flow: Prevent creation without assignment
   - Options flow: Prevent editing to remove all assignments
   - Defense in depth approach

4. **Translation Scope**: English only (en.json) for v4.2

   - Other languages deferred to future release
   - Documented for future translators
   - Rationale: Allows quicker release

5. **Dashboard Helper Enhancement**: Included in Phase 4

   - Resolves KidBadgeProgress gap
   - Shows all assigned badges (not just earned)
   - Improves dashboard completeness

6. **Testing Philosophy**: Dual Path Coverage
   - Path 1: Migration testing (existing installations)
   - Path 2: Normal use testing (fresh installations)
   - Both paths equally important for quality assurance

### Dependencies & Assumptions

- **Assumption**: Users expect consistent behavior across chores and badges
- **Assumption**: Preserving existing behavior via migration is preferred over forced reassignment
- **Dependency**: Home Assistant translation system (no changes needed beyond content)
- **Dependency**: Dashboard uses badge assignment field (already does ✅)

### Future Enhancements (Out of Scope)

- Bulk assignment tools for badges
- "Clone assignment from chore X to badge Y" feature
- Badge template library with pre-assigned kids
- Assignment inheritance rules
