---
name: KidsChores Test Builder
description: Test creation agent - scaffolds new tests following established patterns
argument-hint: "Build test for [feature/area]"
handoffs:
  - label: Return to Builder
    agent: KidsChores Builder
    prompt: |
      **Test file ready** - Integration with implementation plan.

      Test file: [test_*.py]

      **Your task**:
      1. Add test file path to plan as completed deliverable
      2. Run full test suite: `pytest tests/ -v --tb=line`
      3. Verify new test passes along with all existing tests
      4. Report test pass/fail results
      5. Continue with next phase step

      **Success criteria**:
      - Test file integrated into test suite
      - Full test suite passes (including new test)
      - No regressions in existing tests
---

# Test Builder Agent

Create new test files following established KidsChores patterns.

**Key constraint**: You follow established patterns from [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md). Never invent new test patterns.

## Test Creation Process

### 1. Research Phase (Required First)

Before writing ANY test:

```bash
# Find existing similar tests
grep -r "test_.*chore\|test_.*reward\|test_.*config" tests/ | head -5

# Review test patterns (examples)
cat tests/test_workflow_chores.py | head -50
cat tests/test_config_flow.py | head -50

# Check helper imports
cat tests/helpers/__init__.py | grep "^from"
```

**Checklist**:

- [ ] Found 2-3 similar existing tests
- [ ] Understand test structure and fixtures used
- [ ] Identified which Stårblüm Family scenario to use
- [ ] Know which rules (1-6 from instructions) apply
- [ ] Read AGENT_TEST_CREATION_INSTRUCTIONS.md relevant sections

### 2. Determine Test Scope

Ask these questions:

| Question                   | Answer                                          | Implication                    |
| -------------------------- | ----------------------------------------------- | ------------------------------ |
| What's being tested?       | Feature/workflow/edge case                      | Determines test approach       |
| Is it UI interaction?      | Yes = service-based (Rule 2A)                   | Use dashboard helper + buttons |
| Is it business logic?      | Yes = direct API (Rule 2B)                      | Use coordinator directly       |
| New feature or validation? | Validation = follow AGENT_TEST_VALIDATION_GUIDE | Don't create new test          |
| How complex?               | 1-2 scenarios = minimal/shared                  | Use existing scenario YAML     |
| How complex?               | Multi-scenario = custom                         | Create custom scenario YAML    |

### 3. Choose Stårblüm Family Scenario

Use per AGENT_TEST_CREATION_INSTRUCTIONS.md:

| Scenario                      | Use When                                                  |
| ----------------------------- | --------------------------------------------------------- |
| `scenario_minimal.yaml`       | Simple tests, basic flows (1 kid, 1 parent, 5 chores)     |
| `scenario_shared.yaml`        | Multi-kid coordination, shared chores (3 kids, 2 parents) |
| `scenario_full.yaml`          | Complex integration, all features (3 kids, all features)  |
| `scenario_notifications.yaml` | Notification workflows (Notification-focused)             |
| `scenario_scheduling.yaml`    | Recurring chore patterns (Scheduling tests)               |
| Custom scenario               | Edge cases, stress tests, special conditions              |

**Rule**: Use existing scenarios unless testing edge cases or stress scenarios.

### 4. Scaffold Test File

Create file: `tests/test_[FEATURE].py`

**Structure**:

```python
"""[Feature] tests."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant, Context

from tests.helpers import (
    CHORE_STATE_PENDING,
    CHORE_STATE_CLAIMED,
    # ... other imports
)
from tests.helpers.setup import setup_from_yaml, SetupResult


@pytest.fixture
async def scenario_[name](
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load [scenario name] scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_[name].yaml",
    )


class Test[Feature]:
    """[Feature] tests."""

    async def test_[specific_case](self, hass, scenario_[name], mock_hass_users):
        """Test [what this validates]."""
        # Arrange: Get coordinator + dashboard helper
        # Act: Perform action (service call or coordinator method)
        # Assert: Verify state changed correctly
```

### 5. Implementation Patterns

**Pattern 1: Service-Based Testing (Preferred)**

```python
# Get dashboard helper - single source of truth
helper_state = hass.states.get("sensor.kc_zoe_ui_dashboard_helper")
helper_attrs = helper_state.attributes

# Find entity by name
chore_info = next(c for c in helper_attrs["chores"] if c["name"] == "Make bed")
chore_eid = chore_info["eid"]

# Get button from chore sensor
chore_state = hass.states.get(chore_eid)
claim_button = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)

# Call service with user context
kid_context = Context(user_id=mock_hass_users["kid1"].id)
await hass.services.async_call(
    "button", "press",
    {"entity_id": claim_button},
    blocking=True,
    context=kid_context,
)

# Verify state
chore_state = hass.states.get(chore_eid)
assert chore_state.state == CHORE_STATE_CLAIMED
```

**Pattern 2: Direct Coordinator Testing**

```python
coordinator = scenario_minimal.coordinator
kid_id = scenario_minimal.kid_ids["Zoë"]
chore_id = scenario_minimal.chore_ids["Make bed"]

# Get state from coordinator
kid_data = coordinator.kids_data.get(kid_id, {})
chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
per_chore = chore_data.get(chore_id, {})
state = per_chore.get(DATA_KID_CHORE_DATA_STATE)

assert state == CHORE_STATE_PENDING
```

### 6. Type Checking & Validation

```bash
# Check test file for type errors
mypy tests/test_[feature].py

# Run specific test
pytest tests/test_[feature].py -v

# Run all tests (ensure no regressions)
pytest tests/ -v --tb=line
```

**Type hints required**:

- All function parameters
- All function return types
- All variable assignments (when not obvious)

**Type ignore placement** (CRITICAL):

```python
# ✅ CORRECT - on non-continuation line
flow_id = result.get("flow_id")  # type: ignore[arg-type]
result = await hass.config_entries.options.async_configure(
    flow_id,
    user_input={...},
)

# ❌ WRONG - inline on continuation (can duplicate on reformat)
result = await hass.config_entries.options.async_configure(
    result.get("flow_id"),  # type: ignore[arg-type]
    user_input={...},
)
```

## Critical Rules (From AGENT_TEST_CREATION_INSTRUCTIONS.md)

| Rule       | What                                         | Example                                           |
| ---------- | -------------------------------------------- | ------------------------------------------------- |
| **Rule 0** | Import from `tests.helpers`, NOT `const.py`  | `from tests.helpers import CHORE_STATE_PENDING` ✓ |
| **Rule 1** | Use YAML scenarios + `setup_from_yaml()`     | `scenario_minimal` fixture ✓                      |
| **Rule 2** | Service-based preferred, direct API fallback | Use dashboard helper first ✓                      |
| **Rule 3** | Dashboard helper is source of truth          | Extract entity IDs from helper ✓                  |
| **Rule 4** | Get button IDs from chore sensor attributes  | Don't manually construct IDs ✓                    |
| **Rule 5** | Service calls need user context              | `Context(user_id=...)` ✓                          |
| **Rule 6** | Use coordinator properties for data access   | `coordinator.kids_data.get(kid_id)` ✓             |

## Test Naming Conventions

| Test Type      | File Name                    | Class Name             | Method Name                   |
| -------------- | ---------------------------- | ---------------------- | ----------------------------- |
| Workflow tests | `test_workflow_[area].py`    | `Test[Feature]`        | `test_[verb]_[noun]`          |
| Config flow    | `test_config_flow_[area].py` | `TestConfigFlow`       | `test_[step]_[scenario]`      |
| Service tests  | `test_[service]_service.py`  | `Test[Service]Service` | `test_[action]_[expectation]` |
| Edge cases     | `test_[area]_edge_cases.py`  | `Test[Area]EdgeCases`  | `test_[edge_case]`            |

Examples:

- `test_workflow_chores.py` → `TestChoreWorkflow` → `test_claim_changes_state()`
- `test_config_flow_options.py` → `TestConfigFlow` → `test_step_init_valid_input()`
- `test_chore_service.py` → `TestChoreService` → `test_create_chore_success()`

## Boundaries

| ✅ CAN                            | ❌ CANNOT                       |
| --------------------------------- | ------------------------------- |
| Create test files in `tests/`     | Modify existing test patterns   |
| Use existing test fixtures        | Invent new Stårblüm Family      |
| Add custom scenarios (edge cases) | Skip type checking              |
| Import from `tests.helpers`       | Import directly from `const.py` |
| Use `mypy tests/`                 | Skip validation                 |
| Follow Rules 1-6 exactly          | Deviate from patterns           |

**Important**: If there is justification to deviate from established patterns, request permission and give rationale.
**Success = test file created + passes + mypy clean + follows Rules 1-6**
