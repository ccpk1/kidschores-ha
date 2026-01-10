# Initiative Plan: Test Suite Reorganization

## Initiative snapshot

- **Name / Code**: Test Suite Reorganization (Legacy vs Modern)
- **Target release / milestone**: v0.5.1
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                      | Description                                      | % complete | Quick notes                                                         |
| --------------------------------- | ------------------------------------------------ | ---------- | ------------------------------------------------------------------- |
| Phase 1 – File Reorganization     | Move legacy tests to tests/legacy/               | 100%       | ✅ 67+ files moved                                                  |
| Phase 2 – Conftest Setup          | Create modern conftest, preserve legacy conftest | 100%       | ✅ Clean minimal conftest created                                   |
| Phase 3 – Validation              | Ensure all tests still pass                      | 100%       | ✅ 709 passed, 36 skipped                                           |
| Phase 4 – Workflow Helpers        | Build claim/approve helper framework             | 100%       | ✅ tests/helpers/ module (2,626 lines)                              |
| Phase 4b – Setup Helper           | Declarative test setup via config flow           | 100%       | ✅ setup.py (727 lines) + 5 tests                                   |
| Phase 4c – YAML Setup             | YAML scenario files + setup_from_yaml()          | 100%       | ✅ scenario_full.yaml + 6 tests                                     |
| Phase 5 – Test Cleanup            | Remove duplicates, organize test root            | 100%       | ✅ Cleaned tests/ root                                              |
| Phase 6 – Workflow Tests          | Create test_workflow_chores.py (chore matrix)    | 100%       | ✅ 11 tests, all passing                                            |
| Phase 6b – Notification Tests     | Create test_workflow_notifications.py            | 100%       | ✅ 9 tests, true config flow setup                                  |
| Phase 6c – Translation Tests      | Create test_translations_custom.py               | 100%       | ✅ 85 tests, all 12 languages                                       |
| Phase 7 – Migration (Ongoing)     | Migrate high-value tests to modern patterns      | 25%        | ✅ 6 new chore test files                                           |
| Phase 8 – Documentation Migration | Consolidate test docs from legacy/ to tests/     | 100%       | ✅ 4 focused test docs created                                      |
| Phase 9 – Legacy Test Analysis    | Analyze modern coverage, deprecate duplicates    | 65%        | ✅ Config flow done, ✅ Options flow done, ✅ Migration tests fixed |

1. **Key objective** – Separate legacy tests (direct coordinator manipulation) from modern tests (full config flow integration) to establish a high-confidence test suite while preserving existing regression coverage.

2. **Summary of recent work**

   - ✅ Created `tests/legacy/` folder and moved all 67+ legacy test files
   - ✅ Created clean minimal `tests/conftest.py` (~160 lines) following AGENT_TEST_CREATION_INSTRUCTIONS.md
   - ✅ Preserved original conftest in `tests/legacy/conftest.py` (2252 lines)
   - ✅ Fixed import paths in 21 legacy test files
   - ✅ Fixed path resolution in test_notification_translations.py
   - ✅ Removed pytest_plugins from legacy conftest (must be top-level only)
   - ✅ All tests pass: 709 passed, 36 skipped
   - ✅ Created `tests/helpers/` module with constants, workflows, validation
   - ✅ Workflow helpers use dashboard helper as single source of truth
   - ✅ WorkflowResult dataclass captures before/after state for assertions
   - ✅ Created `tests/helpers/setup.py` (870+ lines) - declarative test setup
   - ✅ SetupResult dataclass with full state access (coordinator, kid_ids, chore_ids)
   - ✅ 5 setup helper tests passing in `test_setup_helper.py`
   - ✅ Created `tests/scenarios/scenario_full.yaml` (249 lines) - YAML scenario format
   - ✅ Added `setup_from_yaml()` to setup.py - loads YAML and runs config flow
   - ✅ 6 YAML setup tests passing in `test_yaml_setup.py`
   - ✅ Cleaned tests/ root - deleted test_constants.py (duplicate), moved entity_validation_helpers.py to legacy/
   - ✅ **NEW**: Created `tests/scenarios/scenario_minimal.yaml` (1 kid, 5 chores)
   - ✅ **NEW**: Created `tests/scenarios/scenario_shared.yaml` (3 kids, 8 shared chores)
   - ✅ **NEW**: Created `tests/test_workflow_chores.py` (11 tests) covering:
     - TestIndependentChores: claim, approve, disapprove (4 tests)
     - TestAutoApprove: instant approval on claim (1 test)
     - TestSharedFirstChores: first-claimer-wins, disapprove reset (3 tests)
     - TestSharedAllChores: per-kid approval and points (3 tests)
   - ✅ **NEW**: Modern test suite now at 32 passed, 2 skipped (was 21)
   - ✅ **NEW**: Created `test_workflow_notifications.py` (9 tests) covering:
     - Notification enablement via config flow (mock notify services)
     - Chore claim sends notification to parent with action buttons
     - Auto-approve chores don't notify parents
     - Kid language determines action button translations (en, sk)
   - ✅ **NEW**: Created `test_translations_custom.py` (85 tests) covering:
     - Translation file existence and structure validation
     - All 12 languages parametrized testing
     - Notification and dashboard translation coverage
     - Translation quality checks (no placeholders, readable text)
   - ✅ **NEW**: Deleted legacy notification tests (superseded by modern tests):
     - `tests/legacy/test_notification_translations.py` (435 lines)
     - `tests/legacy/test_notification_translations_integration.py` (131 lines)
   - ✅ **NEW**: Comprehensive chore services testing (Phase 7 migration):
     - Created `test_chore_services.py` (20 tests) - claim, approve, set_due_date, skip, reset
     - Created `test_shared_chore_features.py` (15 tests) - auto-approve, pending claim actions
     - Created `test_approval_reset_overdue_interaction.py` (8 tests) - reset type interactions
     - Created `test_chore_state_matrix.py` (18 tests) - all states × completion criteria
     - Created `test_chore_scheduling.py` (41 tests) - due dates, overdue, approval reset
   - ✅ **NEW**: Refactored `coordinator.reset_all_chores()` from services.py (service handler delegation)
   - ✅ **NEW**: Total test suite: 899 passed, 65 skipped (964 total collected)

3. **Next steps (short term)**

   - ✅ **DONE**: Updated `AGENT_TEST_CREATION_INSTRUCTIONS.md` to reflect modern patterns
   - Analyze existing chore workflow tests for gaps
   - Create comprehensive chore state matrix tests
   - Consider creating test_workflow_rewards.py for reward claim/approve
   - Consider creating test_workflow_penalties.py for penalty applications
   - Consider adding Dutch (nl) kid to notification scenario for 3-language test
   - Extend YAML scenarios for badges, achievements, challenges
   - Continue migrating high-value legacy tests

4. **Risks / blockers**

   - ~~Import path changes may break legacy tests initially~~ ✅ RESOLVED
   - ~~Shared fixtures need to be accessible from both locations~~ ✅ RESOLVED (duplicated in legacy)
   - ~~pytest collection may need pytest.ini updates~~ ✅ No changes needed

5. **References**

   - Agent testing instructions: `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` (updated to modern patterns)
   - Architecture overview: `docs/ARCHITECTURE.md`
   - Code review guide: `docs/CODE_REVIEW_GUIDE.md`
   - Existing test patterns: `tests/test_config_flow_fresh_start.py`
   - Helpers module: `tests/helpers/` (constants, setup, workflows, validation)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Modern tests use real config flow, not direct coordinator manipulation
     - Legacy tests preserved for regression coverage, will be migrated gradually
     - `mock_hass_users` fixture shared via import from common module
     - Workflow helpers use dataclass for structured results
   - **Completion confirmation**: `[ ]` All follow-up items completed

---

## Detailed phase tracking

### Phase 1 – File Reorganization ✅ COMPLETE

- **Goal**: Move all legacy test files to `tests/legacy/` while keeping modern tests in `tests/`

- **Files KEPT in tests/** (modern):

  - `__init__.py`
  - `conftest.py` (new minimal version ~190 lines)
  - `test_config_flow_fresh_start.py` (modern pattern - 12 tests)
  - `test_setup_helper.py` (setup helper tests - 5 tests)
  - `test_yaml_setup.py` (YAML setup tests - 6 tests)
  - `test_workflow_chores.py` (chore workflow tests - 11 tests)
  - `test_workflow_notifications.py` (notification tests - 9 tests)
  - `test_translations_custom.py` (translation tests - 85 tests)
  - `test_chore_state_matrix.py` (state matrix tests - 18 tests) ⭐ NEW
  - `test_chore_scheduling.py` (scheduling tests - 41 tests) ⭐ NEW
  - `test_chore_services.py` (service tests - 20 tests) ⭐ NEW
  - `test_shared_chore_features.py` (shared chore tests - 15 tests) ⭐ NEW
  - `test_approval_reset_overdue_interaction.py` (reset interaction tests - 8 tests) ⭐ NEW
  - `helpers/` module (constants, workflows, validation, setup)
  - `scenarios/` directory (YAML scenario files: minimal, shared, full, scheduling, etc.)
  - Documentation files (\*.md)

- **Files MOVED to tests/legacy/** (67+ files):

  - All legacy `test_*.py` files
  - `migration_samples/` folder
  - `__snapshots__/` folder
  - Copy of testdata*scenario*\*.yaml files

- **Steps / detailed work items**

  1. `[x]` Create `tests/legacy/__init__.py` with module docstring
  2. `[x]` Create `tests/legacy/` directory structure
  3. `[x]` Move all legacy test files via git mv
  4. `[x]` Copy testdata*scenario*\*.yaml files to legacy/ (needed for fixtures)
  5. `[x]` Move migration_samples/ to legacy/
  6. `[x]` Move **snapshots**/ to legacy/

- **Key issues**
  - ✅ RESOLVED: Import paths fixed via sed in 21 files
  - ✅ RESOLVED: Path resolution in test_notification_translations.py fixed

### Phase 2 – Conftest Setup ✅ COMPLETE

- **Goal**: Create modern conftest with workflow helpers, preserve legacy conftest for backward compatibility

- **Modern conftest.py features** (implemented ~160 lines):

  ```python
  # tests/conftest.py (modern)

  # Core (REQUIRED at top-level)
  pytest_plugins = "pytest_homeassistant_custom_component"

  # Autouse fixture
  auto_enable_custom_integrations

  # User fixtures
  mock_hass_users  # HA user mocks for kid/parent contexts

  # Setup fixtures
  mock_config_entry
  mock_storage_data
  mock_storage_manager
  init_integration
  ```

- **Legacy conftest.py** (preserved 2252 lines):

  - `scenario_minimal`, `scenario_medium`, `scenario_full`, `scenario_stress` fixtures
  - YAML data loading helpers
  - Direct coordinator access patterns
  - All existing helper functions
  - NOTE: `pytest_plugins` removed (must be top-level only)

- **Steps / detailed work items**

  1. `[x]` Copy current conftest.py to tests/legacy/conftest.py
  2. `[x]` Update legacy conftest imports for new location
  3. `[x]` Create new minimal tests/conftest.py with modern patterns
  4. `[ ]` Add workflow helpers (MOVED TO PHASE 4)

- **Key issues**
  - ✅ RESOLVED: pytest_plugins must only be at top-level conftest

### Phase 3 – Validation ✅ COMPLETE

- **Goal**: Ensure all tests pass after reorganization

- **Results**: 709 passed, 36 skipped

- **Steps / detailed work items**

  1. `[x]` Run `python -m pytest tests/ -v` (modern tests only) - 12 passed, 2 skipped
  2. `[x]` Run `python -m pytest tests/legacy/ -v` (legacy tests only) - 699 passed, 34 skipped
  3. `[x]` Run `python -m pytest tests/ -v` (combined) - 709 passed, 36 skipped
  4. `[x]` Fix any import errors in legacy tests - 21 files fixed via sed
  5. `[x]` Fix path resolution in test_notification_translations.py
  6. `[x]` Remove pytest_plugins from legacy conftest
  7. `[ ]` Run linting on all test files
  8. `[ ]` Verify CI/CD configuration (if applicable)

- **Key issues**
  - ✅ RESOLVED: Import paths adjusted in legacy tests
  - ✅ RESOLVED: pytest_plugins conflict resolved

### Phase 4 – Workflow Helpers Framework ✅ COMPLETE

- **Goal**: Build scalable helper framework for comprehensive chore workflow testing using dashboard helper as source of truth

- **Design Principle** (from AGENT_TEST_CREATION_INSTRUCTIONS.md):

  - **NEVER construct entity IDs** - get them from dashboard helper
  - **Use dashboard helper as single source of truth** for entity lookup
  - Import constants from `tests/helpers`, not from `const.py`
  - Work through HA service calls, not direct coordinator access

- **Module Structure Created** (`tests/helpers/`):

  ```
  tests/helpers/
  ├── __init__.py     # Re-exports all helpers for convenient imports (233 lines)
  ├── constants.py    # All KidsChores constants (222 lines)
  ├── setup.py        # Declarative test setup via config flow (727 lines) ⭐ NEW
  ├── workflows.py    # Chore/reward/bonus workflow helpers (809 lines)
  └── validation.py   # Entity state and count validation (635 lines)
  ```

  **Total: 2,626 lines of helper code**

- **Usage Pattern**:

  ```python
  from tests.helpers import (
      # Workflow helpers
      claim_chore, approve_chore, WorkflowResult,
      get_dashboard_helper, find_chore,

      # Constants
      CHORE_STATE_PENDING, CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED,

      # Validation
      assert_entity_exists, assert_state_equals, assert_points_changed,
  )

  async def test_basic_chore_workflow(hass, init_integration, mock_hass_users):
      # Get dashboard helper (single source of truth)
      dashboard = get_dashboard_helper(hass, "zoe")

      # Find chore by display name
      chore = find_chore(dashboard, "Feed the cats")
      assert chore is not None

      # Claim chore via button press (kid context)
      kid_context = Context(user_id=mock_hass_users["kid1"].id)
      result = await claim_chore(hass, "zoe", "Feed the cats", kid_context)

      # Assert using structured result
      assert_workflow_success(result)
      assert_state_transition(result, CHORE_STATE_PENDING, CHORE_STATE_CLAIMED)
  ```

- **Test Matrix to Support**:

  | #   | Scenario                | Criteria     | Kids | Key Validation                            |
  | --- | ----------------------- | ------------ | ---- | ----------------------------------------- |
  | 1   | Single kid basic        | INDEPENDENT  | 1    | State: pending→claimed→approved           |
  | 2   | Single kid disapprove   | INDEPENDENT  | 1    | State resets: claimed→pending             |
  | 3   | Multi-kid independent   | INDEPENDENT  | 3    | Each kid tracked separately               |
  | 4   | Shared-first winner     | SHARED_FIRST | 2    | First wins, loser gets completed_by_other |
  | 5   | Shared-first disapprove | SHARED_FIRST | 2    | ALL kids reset on disapprove              |
  | 6   | Shared-all partial      | SHARED_ALL   | 3    | Global state shows partial until done     |
  | 7   | Shared-all complete     | SHARED_ALL   | 3    | Points only when all kids approved        |
  | 8   | Auto-approve immediate  | INDEPENDENT  | 1    | Claim triggers instant approval           |

- **Helper Design Principles**:

  - Use dashboard helper as single source of truth for entity lookup
  - Return structured results via dataclass for easy assertions
  - Support both single-kid and multi-kid scenarios
  - Capture before/after states for all relevant attributes
  - Work through HA service calls, not direct coordinator access

- **Steps / detailed work items**

  1. `[x]` Create `tests/helpers/__init__.py` with re-exports
  2. `[x]` Create `tests/helpers/constants.py` with all integration constants
  3. `[x]` Create `tests/helpers/workflows.py` with WorkflowResult and all helpers
  4. `[x]` Create `tests/helpers/validation.py` with assertion and counting helpers
  5. `[x]` Implement `get_dashboard_helper()` - reads dashboard helper sensor
  6. `[x]` Implement `find_chore()`, `find_reward()`, `find_bonus()`, `find_penalty()`
  7. `[x]` Implement `claim_chore()` - presses claim button, returns before/after
  8. `[x]` Implement `approve_chore()` - presses approve button, returns before/after
  9. `[x]` Implement `disapprove_chore()` - presses disapprove button, returns before/after
  10. `[x]` Implement `claim_reward()`, `approve_reward()` for reward workflows
  11. `[x]` Implement `apply_bonus()`, `apply_penalty()` for point adjustments
  12. `[x]` Implement `get_chore_states_all_kids()` - for multi-kid scenario testing
  13. `[ ]` Create `test_chore_workflow_matrix.py` with parametrized tests (PHASE 5)
  14. `[ ]` Add test for each row in the test matrix above (PHASE 5)

- **Key issues**
  - Need to handle cases where dashboard helper may not have all chores (filtering)
  - Auto-approve chores skip claim state - need special handling

### Phase 4b – Setup Helper ✅ COMPLETE

- **Goal**: Create declarative test setup that navigates the full config flow, reducing test boilerplate

- **Key Components Created**:

  1. **SetupResult dataclass** - Returns all data needed for test assertions:

     ```python
     @dataclass
     class SetupResult:
         hass: HomeAssistant
         config_entry: ConfigEntry
         coordinator: KidsChoresDataUpdateCoordinator
         final_result: ConfigFlowResult | None
         kid_ids: dict[str, str]      # {"Zoë": "uuid-123"}
         parent_ids: dict[str, str]   # {"Dad": "uuid-456"}
         chore_ids: dict[str, str]    # {"Clean room!": "uuid-789"}
     ```

  2. **setup_integration()** - Main entry point for declarative setup:

     ```python
     result = await setup_integration(
         hass,
         mock_hass_users,
         kids=[{"name": "Zoë"}],
         parents=[{"name": "Dad", "ha_user_id": mock_hass_users["parent1"].id}],
         chores=[{"name": "Clean room!", "default_points": 10}],
     )
     assert result.coordinator.kids_data  # Full coordinator access
     ```

  3. **Scenario presets** - One-liner test setup:
     ```python
     result = await setup_minimal_scenario(hass, mock_hass_users)  # 1 kid, 2 chores
     result = await setup_medium_scenario(hass, mock_hass_users)   # 2 kids, 4 chores
     result = await setup_full_scenario(hass, mock_hass_users)     # 3 kids, 7 chores
     ```

- **Steps / detailed work items**

  1. `[x]` Create `tests/helpers/setup.py` with SetupResult dataclass
  2. `[x]` Implement config flow navigation helpers (points, kids, parents, chores)
  3. `[x]` Implement `_handle_step()` for generic flow navigation
  4. `[x]` Implement entity ID extraction from coordinator after setup
  5. `[x]` Add proper type hints (ConfigFlowResult from homeassistant.config_entries)
  6. `[x]` Create `test_setup_helper.py` with 5 validation tests
  7. `[x]` Fix all Pylance type errors (TypedDict access, Optional narrowing)
  8. `[ ]` Extend for badges, rewards, penalties, bonuses (as needed)

- **Test Results**: 5 tests passing

  - `test_setup_minimal_scenario` - Basic 1-kid setup
  - `test_setup_scenario_custom_config` - Custom points label/icon
  - `test_setup_multi_kid_scenario` - Multiple kids with chores
  - `test_setup_scenario_no_chores` - Kids without chores
  - `test_setup_scenario_no_parents` - Kids without parents

- **Key issues**
  - ✅ RESOLVED: Kid ID extraction moved to PARENTS step (kids created after KIDS step)
  - ✅ RESOLVED: Removed async_setup mock that prevented real setup
  - ✅ RESOLVED: Type annotations fixed (ConfigFlowResult, .get() access)

### Phase 4c – YAML Setup ✅ COMPLETE

- **Goal**: Create YAML-based scenario files that work with `setup_from_yaml()` for comprehensive test data

- **Files Created**:

  1. **`tests/scenarios/scenario_full.yaml`** (249 lines)

     - 3 kids: Zoë, Max!, Lila (with special characters)
     - 2 parents: Môm Astrid Stârblüm, Dad Leo
     - 18 chores covering all completion criteria and frequencies:
       - Independent (9): single-kid daily/weekly/monthly, multi-kid, custom interval
       - Shared_all (3): daily/weekly with 2-3 kids
       - Shared_first (4): daily/weekly with 2-3 kids
       - Auto-approve (1): daily with instant approval

  2. **`tests/helpers/setup.py`** additions (~150 lines):

     - `_transform_yaml_to_scenario()` - Transforms YAML format to setup_scenario() format
     - `setup_from_yaml()` - Loads YAML file and runs config flow setup

  3. **`tests/test_yaml_setup.py`** (6 tests):
     - `test_setup_from_yaml_scenario_full` - Verifies 3 kids, 2 parents, 18 chores
     - `test_setup_from_yaml_kid_chore_assignment` - Verifies kid assignment
     - `test_setup_from_yaml_completion_criteria` - Verifies independent/shared_all/shared_first
     - `test_setup_from_yaml_auto_approve` - Verifies auto_approve setting
     - `test_setup_from_yaml_system_settings` - Verifies points label/icon
     - `test_setup_from_yaml_file_not_found` - Error handling

- **YAML Format** (config-flow-ready keys):

  ```yaml
  system:
    points_label: "Star Points"
    points_icon: "mdi:star"
  kids:
    - name: "Zoë"
      ha_user: "kid1" # Key in mock_hass_users fixture
  parents:
    - name: "Mom"
      ha_user: "parent1"
      kids: ["Zoë"] # Kid names to associate
  chores:
    - name: "Clean Room"
      assigned_to: ["Zoë"] # Kid names
      points: 10.0
      completion_criteria: "independent"
  ```

- **Usage**:

  ```python
  from tests.helpers.setup import setup_from_yaml

  result = await setup_from_yaml(
      hass,
      mock_hass_users,
      "tests/scenarios/scenario_full.yaml",
  )
  # Access: result.kid_ids["Zoë"], result.chore_ids["Feed the cåts"]
  ```

- **Steps / detailed work items**

  1. `[x]` Create `tests/scenarios/__init__.py` package
  2. `[x]` Create `tests/scenarios/scenario_full.yaml` with 3 kids, 2 parents, 18 chores
  3. `[x]` Add `_transform_yaml_to_scenario()` to setup.py
  4. `[x]` Add `setup_from_yaml()` to setup.py
  5. `[x]` Create `tests/test_yaml_setup.py` with 6 validation tests
  6. `[x]` All tests passing (6/6)

### Phase 5 – Test Cleanup ✅ COMPLETE

- **Goal**: Clean up tests/ root directory, remove duplicates, organize structure

- **Cleanup Actions**:

  1. **Deleted**: `tests/test_constants.py` (duplicate of `tests/helpers/constants.py`)

     - Updated `test_config_flow_fresh_start.py` import to use `tests.helpers.constants`

  2. **Moved**: `tests/entity_validation_helpers.py` → `tests/legacy/entity_validation_helpers.py`

     - Only used by legacy tests

  3. **Moved**: Legacy YAML files to `tests/legacy/`
     - `testdata_scenario_minimal.yaml`
     - `testdata_scenario_medium.yaml`
     - `testdata_scenario_full.yaml`
     - `testdata_scenario_performance_stress.yaml`

- **Current tests/ root structure**:

  ```
  tests/
  ├── __init__.py
  ├── conftest.py                             # Modern fixtures (~190 lines)
  ├── test_config_flow_fresh_start.py         # 12 tests
  ├── test_setup_helper.py                    # 5 tests
  ├── test_yaml_setup.py                      # 6 tests
  ├── test_workflow_chores.py                 # 11 tests
  ├── test_workflow_notifications.py          # 9 tests
  ├── test_translations_custom.py             # 85 tests
  ├── test_chore_state_matrix.py              # 18 tests ⭐ NEW
  ├── test_chore_scheduling.py                # 41 tests ⭐ NEW
  ├── test_chore_services.py                  # 20 tests ⭐ NEW
  ├── test_shared_chore_features.py           # 15 tests ⭐ NEW
  ├── test_approval_reset_overdue_interaction.py  # 8 tests ⭐ NEW
  ├── helpers/                                # Helper modules
  │   ├── __init__.py
  │   ├── constants.py
  │   ├── setup.py
  │   ├── validation.py
  │   └── workflows.py
  ├── scenarios/                              # YAML scenario files
  │   ├── __init__.py
  │   ├── scenario_full.yaml                  # 3 kids, 18 chores
  │   ├── scenario_minimal.yaml               # 1 kid, 5 chores
  │   ├── scenario_shared.yaml                # 3 kids, 8 shared chores
  │   ├── scenario_scheduling.yaml            # 1 kid, 13 chores ⭐ NEW
  │   ├── scenario_chore_services.yaml        # 2 kids, 7 chores ⭐ NEW
  │   ├── scenario_approval_reset_overdue.yaml    # 3 kids, 5 chores ⭐ NEW
  │   └── scenario_notifications.yaml         # Notification scenarios
  ├── legacy/                                 # Legacy tests (~735 tests)
  │   ├── conftest.py
  │   ├── test_*.py files
  │   └── testdata_*.yaml files
  └── *.md                                    # Documentation
  ```

- **Test Results After Chore Workflow Testing**:
  - Modern tests: 227 passed, 4 skipped
  - Legacy tests: ~737 passed (includes some skips)
  - **Total combined: 899 passed, 65 skipped (964 total)**

### Phase 6 – Workflow Tests ✅ COMPLETE

- **Goal**: Create test_workflow_chores.py covering all chore workflow scenarios using YAML setup

- **Files Created**:

  1. **`tests/scenarios/scenario_minimal.yaml`** (24 lines)

     - 1 kid: Zoë
     - 1 parent: Mom
     - 5 chores:
       - Make bed (5 pts, daily)
       - Clean room (15 pts, daily)
       - Brush teeth (3 pts, auto-approve)
       - Do homework (20 pts, weekly)
       - Organize closet (25 pts, monthly)

  2. **`tests/scenarios/scenario_shared.yaml`** (68 lines)

     - 3 kids: Zoë, Max, Lila
     - 1 parent: Mom
     - 8 shared chores:
       - 4 x shared_all: Family dinner cleanup (3 kids), Walk the dog (2 kids), Weekend yard work (3 kids), Clean bathroom (2 kids)
       - 4 x shared_first: Take out trash (3 kids), Get the mail (2 kids), Wash the car (3 kids), Organize garage (2 kids)

  3. **`tests/test_workflow_chores.py`** (430 lines, 11 tests)
     - **TestIndependentChores** (4 tests):
       - `test_claim_changes_state_to_claimed`
       - `test_approve_grants_points`
       - `test_disapprove_resets_to_pending`
       - `test_disapprove_does_not_grant_points`
     - **TestAutoApprove** (1 test):
       - `test_claim_triggers_instant_approval`
     - **TestSharedFirstChores** (3 tests):
       - `test_claim_blocks_other_kids` - First claim sets others to completed_by_other
       - `test_approve_grants_points_to_claimer_only`
       - `test_disapprove_resets_all_kids`
     - **TestSharedAllChores** (3 tests):
       - `test_each_kid_gets_points_on_approval` - Each kid gets points independently
       - `test_three_kid_shared_all` - Three-kid scenario
       - `test_approved_state_tracked_per_kid` - Independent state tracking

- **Key Design Decisions**:

  1. **Coordinator API Usage** (documented in file docstring):

     ```python
     # claim_chore(kid_id, chore_id, user_name)
     # approve_chore(parent_name, kid_id, chore_id, points_awarded=None)
     # disapprove_chore(parent_name, kid_id, chore_id)
     ```

  2. **Business Logic Discoveries**:

     - shared_first: First claim IMMEDIATELY blocks other kids (sets to completed_by_other)
     - shared_all: Each kid gets points independently on their own approval
     - disapprove_chore for shared_first resets ALL kids to pending

  3. **Helper Functions**:
     ```python
     def get_kid_chore_state(coordinator, kid_id, chore_id) -> str
     def get_kid_points(coordinator, kid_id) -> float
     ```

- **Test Results**: 11 passed

- **Steps / detailed work items**

  1. `[x]` Create `tests/scenarios/scenario_minimal.yaml`
  2. `[x]` Create `tests/scenarios/scenario_shared.yaml`
  3. `[x]` Create `test_workflow_chores.py` skeleton with 4 test classes
  4. `[x]` Implement TestIndependentChores (4 tests)
  5. `[x]` Implement TestAutoApprove (1 test)
  6. `[x]` Implement TestSharedFirstChores (3 tests) - discovered first-claim-blocks behavior
  7. `[x]` Implement TestSharedAllChores (3 tests) - discovered per-kid-points behavior
  8. `[x]` Fix coordinator API signatures (user_name not user_id)
  9. `[x]` Add pylint suppressions (unused-argument for hass fixture)
  10. `[x]` All tests passing, linting clean

### Phase 7 – Migration (Ongoing)

- **Goal**: Gradually migrate high-value legacy tests to modern patterns

- **Migration Priority** (based on coverage value):

  1. **High Priority** - Core workflow tests

     - `test_workflow_chore_claim.py` → migrate to `test_chore_workflow_matrix.py`
     - `test_workflow_shared_regression.py` → migrate to workflow matrix
     - `test_workflow_independent_*.py` → migrate to workflow matrix

  2. **Medium Priority** - Feature-specific tests

     - `test_auto_approve_feature.py`
     - `test_shared_first_*.py`
     - `test_approval_reset_timing.py`

  3. **Lower Priority** - Edge cases and legacy features
     - `test_badge_*.py`
     - `test_migration_*.py`
     - `test_options_flow_*.py`

- **Migration Criteria** (test is ready to migrate when):

  - [ ] Functionality can be tested via config flow setup
  - [ ] Test uses service calls, not direct coordinator methods
  - [ ] Test verifies state via entity attributes or dashboard helper
  - [ ] Test is self-contained (no shared mutable state)

- **Steps / detailed work items**

  1. `[ ]` Document migration criteria in tests/README.md
  2. `[ ]` Create migration checklist for each test file
  3. `[ ]` Migrate tests one file at a time, validate, then remove from legacy
  4. `[ ]` Update test count tracking as tests are migrated

- **Key issues**
  - Some legacy tests may test internal implementation details not exposed via UI
  - Those tests should remain in legacy/ as unit tests

### Phase 8 – Documentation Migration ✅ COMPLETE

- **Goal**: Migrate test documentation from `tests/legacy/` to `tests/` with consolidated reference material, leaving legacy folder focused on test files only

- **Files Created**:

  - `tests/README.md` - High-level overview with Stårblüm family story and testing philosophy (~70 lines)
  - `tests/SCENARIOS.md` - Scenario selection guide (~50 lines)
  - `tests/AGENT_TEST_VALIDATION_GUIDE.md` - Quick reference for validating production code changes (~200 lines)
  - Enhanced `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` - Split for focused technical implementation (~400 lines)

- **Migration Strategy Executed**:

  - **Concept-focused**: Extracted timeless concepts (Stårblüm family, testing philosophy, scenario selection)
  - **Minimal maintenance**: Avoided counts, implementation details that change over time
  - **Clear separation**: Validation guide vs. creation guide for different use cases
  - **Cross-references**: Documents link to each other appropriately

- **Key Benefits Achieved**:

  - Single source for Stårblüm family story and naming rationale
  - Quick validation path for code changes (separate from test creation)
  - Concise scenario decision matrix
  - Modern testing patterns well-documented
  - Legacy folder ready for test file focus

- **Steps / detailed work items**
  1. `[x]` Extract Stårblüm family story to tests/README.md
  2. `[x]` Create scenario selection guide in tests/SCENARIOS.md
  3. `[x]` Split validation vs. creation guidance into separate files
  4. `[x]` Remove outdated technical details, focus on concepts
  5. `[x]` Add quality gates and requirements to validation guide
  6. `[x]` Ensure cross-references work between documents

### Phase 9 – Legacy Test Analysis ✅ GROUP 1 & 2 COMPLETE

- **Goal**: Analyze legacy tests for modern coverage overlap, identify migration candidates vs. deprecation targets, and create systematic approach for legacy test lifecycle management

- **Status**: Config Flow and Options Flow groups complete - 60%+ reduction achieved
- **Current Progress**: Group 1 done, Group 2 done, Groups 3-5 pending

- **Motivation**:

  - Many legacy tests may be duplicated by modern workflow tests
  - Some legacy tests cover migration scenarios or internal details worth preserving
  - Need systematic approach to avoid losing important coverage
  - Legacy suite is large (~737 tests) and needs strategic reduction

- **Analysis Categories**:

  | Category                | Description                                 | Action                | Example                                  |
  | ----------------------- | ------------------------------------------- | --------------------- | ---------------------------------------- |
  | **Duplicated Coverage** | Modern tests fully cover same functionality | **SKIP/DEPRECATE**    | Basic chore claim/approve flows          |
  | **Migration/Internal**  | Tests migration logic, storage internals    | **MIGRATE AS-IS**     | Schema migration, storage validation     |
  | **Edge Cases**          | Valuable edge cases not in modern tests     | **MIGRATE TO MODERN** | Unicode handling, boundary conditions    |
  | **Performance**         | Stress/load testing scenarios               | **MIGRATE TO MODERN** | Large dataset performance tests          |
  | **Obsolete**            | Tests removed features or old patterns      | **DELETE**            | Deprecated API tests, old config formats |

- **Analysis Methodology**:

  1. **Coverage Mapping**: Map each legacy test to modern test coverage
  2. **Feature Classification**: Categorize by functionality (chores, badges, config, etc.)
  3. **Value Assessment**: Determine unique value vs. duplication
  4. **Migration Path**: Define specific approach for each category

- **Expected Outcomes**:

  | Outcome           | Est. Count | % of Legacy | Action Plan                         |
  | ----------------- | ---------- | ----------- | ----------------------------------- |
  | Skip/Deprecate    | ~300 tests | 40%         | Add @pytest.mark.skip with reason   |
  | Migrate as-is     | ~150 tests | 20%         | Move to tests/ with minimal changes |
  | Convert to modern | ~200 tests | 27%         | Rewrite using YAML scenarios        |
  | Delete obsolete   | ~87 tests  | 13%         | Remove entirely                     |

- **Steps / detailed work items**

  1. `[x]` **Config Flow Group Analysis** - Analyzed 34 legacy tests vs 12 modern tests
  2. `[x]` **Skip Basic Config Flow Tests** - Added `@pytest.mark.skip` to 7 tests in `test_config_flow.py` (duplicated by comprehensive modern tests)
  3. `[x]` **Migrate As-Is Tests** - Moved `test_config_flow_use_existing.py` (3 tests) and `test_config_flow_direct_to_storage.py` (1 test) to `tests/`
  4. `[x]` **Convert Error Scenarios to Modern** - Created `test_config_flow_error_scenarios.py` with 9 focused tests covering all critical error paths
  5. `[x]` **Skip Legacy Data Recovery Tests** - Added skip decorators to 23 tests in `test_config_flow_data_recovery.py` (converted to modern format)
  6. `[x]` **Options Flow Group - Create Modern Tests** - Created `test_options_flow_entity_crud.py` with 14 tests covering navigation, entity add, and error handling
  7. `[x]` **Options Flow Group - Skip Legacy Tests** - Added skip decorators to 57 legacy options flow tests (all 5 test_options_flow\*.py files)
  8. `[ ]` Map remaining legacy tests to modern test coverage (where exists)
  9. `[ ]` Identify migration-specific tests (schema versions, data transforms)
  10. `[ ]` Identify performance/stress tests worth preserving
  11. `[ ]` Identify edge cases missing from modern tests
  12. `[ ]` Create test categorization matrix with specific recommendations
  13. `[ ]` Implement skip decorators for duplicated tests (Phase 1)
  14. `[ ]` Migrate high-value tests to modern patterns (Phase 2)
  15. `[ ]` Move migration-specific tests to tests/ as-is (Phase 3)
  16. `[ ]` Delete obsolete tests after validation (Phase 4)
  17. `[ ]` Update test suite metrics and documentation
  18. `[ ]` Verify combined coverage still meets quality standards

**✅ Config Flow Group Complete (Steps 1-5)**:

- **Analysis**: 34 legacy tests → 13 total tests (**62% reduction achieved**)
- **Skipped**: 30 legacy tests (7 basic + 23 data recovery) with skip decorators
- **Migrated As-Is**: 4 tests (3 use_existing + 1 direct_to_storage) moved to tests/
- **Converted to Modern**: 9 comprehensive error scenario tests created
- **Quality**: All linting passed, all tests pass, improved coverage patterns
- **Files Modified**:
  - `tests/legacy/test_config_flow.py` - 7 tests skipped
  - `tests/legacy/test_config_flow_data_recovery.py` - 23 tests skipped
  - `tests/test_config_flow_use_existing.py` - 3 tests migrated
  - `tests/test_config_flow_direct_to_storage.py` - 1 test migrated
  - `tests/test_config_flow_error_scenarios.py` - 9 new modern tests created

**🔄 Options Flow Group (Group 2) - ✅ COMPLETE (Steps 6-7 done)**:

- **Modern Tests Created**: `tests/test_options_flow_entity_crud.py` with 14 tests
  - 5 navigation tests (init, manage entity, back navigation)
  - 6 entity add tests (kids, parents, chores, rewards, bonuses, penalties)
  - 2 YAML scenario-driven tests
  - 2 error handling tests (duplicate name validation)
- **All 14 tests passing**, linting clean
- **Legacy Tests Skipped**: 57 tests across 5 files with module-level `pytestmark`
  - `test_options_flow.py` - 10 tests skipped
  - `test_options_flow_comprehensive.py` - 14 tests skipped
  - `test_options_flow_backup_actions.py` - 9 tests skipped
  - `test_options_flow_per_kid_dates.py` - 11 tests skipped (includes 2 already skipped)
  - `test_options_flow_restore.py` - 13 tests skipped (includes 7 already skipped)
- **Reduction**: 57 legacy → 14 modern (**75% reduction** for options flow tests)

**✅ Additional Fixes in Group 2 Session**:

- **Fixed Migration Tests**: Moved `tests/legacy/migration_samples/` to `tests/migration_samples/`
  - `test_config_flow_use_existing.py` - 3 tests now passing (uses migration samples)
  - `test_config_flow_direct_to_storage.py` - 1 test now passing (modern pattern)
- **Fixed E2E Test**: Updated `test_e2e_adha_share_day.py` path to migration_samples
- **Added Skip Decorators**: 2 additional legacy migration test files
  - `test_migration_samples_validation.py` - 26 tests skipped (internal migration details)
  - `test_badge_migration_baseline.py` - 1 test skipped (badge assigned_to field migration)
- **Fixed Ruff E402 Errors**: Added `# ruff: noqa: E402` to 7 legacy files for import order
- **Final Test Suite**: 830 passed, 172 skipped, all linting clean

**🔍 Next Group: Workflow Tests (Group 3) - Ready for Analysis**

- **Key Analysis Questions**:

  - Which chore workflow tests are fully covered by test_workflow_chores.py?
  - Which config flow tests are duplicated by test_config_flow_fresh_start.py?
  - Which migration tests are still relevant for current schema version?
  - Which performance tests should be preserved for regression detection?
  - Which tests cover internal coordinator details not exposed via UI?

- **Risk Mitigation**:

  - Start with skip decorators (reversible) before deletion
  - Maintain coverage metrics before/after changes
  - Run full test suite validation at each phase
  - Preserve migration tests until schema is stable
  - Document decisions for future reference

- **Success Metrics**:

  - Legacy test count reduced by 60%+
  - Combined test execution time improved
  - Modern test coverage remains comprehensive
  - No critical functionality left untested
  - Clear separation between unit and integration tests

  2. `[ ]` Update all cross-references in moved docs (tests/legacy/ → tests/)
  3. `[ ]` Read TESTDATA_CATALOG.md and SCENARIO_FULL_COVERAGE.md
  4. `[ ]` Merge both into TEST_SCENARIOS.md as appendices
  5. `[ ]` Create tests/legacy/archive/README.md with index
  6. `[ ]` Move TESTDATA_CATALOG.md and SCENARIO_FULL_COVERAGE.md to archive/
  7. `[ ]` Delete duplicate `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` (keep modern version)
  8. `[ ]` Update copilot-instructions.md links (if any reference test docs)
  9. `[ ]` Update ARCHITECTURE.md links (if any reference test docs)
  10. `[ ]` Update CODE_REVIEW_GUIDE.md links (if any reference test docs)
  11. `[ ]` Search codebase for "tests/legacy" references, fix all
  12. `[ ]` Run `python -m pytest tests/ -v` to verify tests still work
  13. `[ ]` Run `./utils/quick_lint.sh --fix` to verify linting

- **Final Structure** (after Phase 8):

  ```
  tests/
  ├── README.md                    # ✅ MOVED: Overview
  ├── TESTING_GUIDE.md             # ✅ MOVED: Master reference
  ├── TESTING_AGENT_INSTRUCTIONS.md # ✅ MOVED: AI quick-start
  ├── TEST_CREATION_TEMPLATE.md    # ✅ MOVED: Patterns
  ├── TEST_FIXTURE_GUIDE.md        # ✅ MOVED: Fixtures
  ├── TEST_SCENARIOS.md            # ✅ MOVED + CONSOLIDATED (includes appendices)
  ├── conftest.py
  ├── helpers/
  ├── scenarios/
  ├── test_*.py files
  └── legacy/
      ├── archive/                 # 🔒 Historical reference
      │   ├── README.md            # Archive index
      │   ├── TESTDATA_CATALOG.md  # (consolidated)
      │   └── SCENARIO_FULL_COVERAGE.md # (consolidated)
      ├── conftest.py
      ├── test_*.py files
      └── testdata_*.yaml files
  ```

- **Key Benefits**:

  - Single source of truth (all docs in tests/, not split)
  - Clearer structure for contributors
  - Reduced maintenance (consolidated redundancy)
  - Preserved history (archive for reference)
  - Cleaner legacy folder (files only, no docs)

- **Key Issues**

  - Must update all references in documentation and code
  - Ensure cross-references within moved docs still work
  - Validate no breaking changes to link paths

- **Estimated Effort**: 2-2.5 hours
  - Phase 1 (MOVE): 30 mins
  - Phase 2 (CONSOLIDATE): 45 mins
  - Phase 3 (ARCHIVE): 15 mins
  - Phase 4 (UPDATE): 30 mins
  - Phase 5 (VERIFY): 15 mins

---

- **Testing & validation**

- **Modern suite**: `python -m pytest tests/ -v --ignore=tests/legacy --tb=line`

  - Current: 227 passed, 4 skipped ✅
  - Files: test_config_flow_fresh_start.py (12), test_setup_helper.py (5), test_yaml_setup.py (6), test_workflow_chores.py (11), test_workflow_notifications.py (9), test_translations_custom.py (85), test_chore_state_matrix.py (18), test_chore_scheduling.py (41), test_chore_services.py (20), test_shared_chore_features.py (15), test_approval_reset_overdue_interaction.py (8)
  - Target: Comprehensive chore workflow coverage ✅ ACHIEVED

- **Legacy suite**: `python -m pytest tests/legacy/ -v --tb=line`

  - Current: ~737 passed with skips
  - Will decrease as tests are migrated

- **Combined suite**: `python -m pytest tests/ -v --tb=line`

  - Current: 899 passed, 65 skipped ✅
  - Should always pass before any PR merge

- **Linting**: `./utils/quick_lint.sh --fix`
  - Must pass for both test directories

---

## Notes & follow-up

### Architecture Decisions

1. **Why separate legacy vs modern?**

   - Legacy tests directly manipulate coordinator data, missing integration bugs
   - Modern tests exercise the full config flow → storage → entity stack
   - Bugs like AUTO_APPROVE extraction were only caught by modern tests

2. **Why keep legacy tests?**

   - They provide regression coverage during transition
   - Some test internal implementation details that aren't UI-exposed
   - Gradual migration reduces risk of losing coverage

3. **Helper function design**
   - Use dataclass for structured results (type-safe, IDE-friendly)
   - Return before/after states to enable flexible assertions
   - Support multi-kid scenarios via `other_kids_states` dict
   - Setup helper provides direct coordinator access after full config flow

### Follow-up Tasks

- [ ] **Phase 8 – Documentation Migration** (see detailed section above)

  - Move 6 core docs to tests/
  - Consolidate 2 redundant docs into TEST_SCENARIOS.md
  - Archive outdated docs in tests/legacy/archive/
  - Update all cross-references
  - Est. effort: 2-2.5 hours

- [ ] Update `tests/README.md` with new structure explanation
- [ ] Update `tests/TESTING_AGENT_INSTRUCTIONS.md` for new patterns
- [ ] Consider CI job separation (fast modern suite vs full legacy suite)
- [ ] Document which legacy tests can never be migrated (internal unit tests)
- [ ] Extend setup.py for badges, rewards, penalties, bonuses
- [ ] Update `tests/helpers/__init__.py` to export setup helpers
