# Entity Helpers Test Analysis - Supporting Document

**Parent Plan**: [ENTITY_HELPERS_REWARDS_FIRST_IN-PROCESS.md](./ENTITY_HELPERS_REWARDS_FIRST_IN-PROCESS.md)
**Created**: Phase 6 preparation
**Updated**: SERVICE*FIELD*\* constants added, testing strategy revised
**Purpose**: Analyze existing test coverage vs new tests needed

---

## Summary

✅ **Conclusion**: Service tests (E2E) are MORE valuable than `build_reward()` unit tests because they exercise the full code path:

```
Schema validation → Field mapping → build_reward() → Storage → Response
```

| Area                                 | Existing Coverage                     | New Tests Needed                   |
| ------------------------------------ | ------------------------------------- | ---------------------------------- |
| `build_reward()` (entity_helpers.py) | ❌ None                               | ⚠️ Skip - covered by service tests |
| Options Flow add_reward              | ✅ `test_options_flow_entity_crud.py` | ❌ Not needed                      |
| Options Flow edit_reward             | ⚠️ No explicit test                   | ❌ Covered by integration          |
| **create_reward service**            | ❌ None                               | ✅ **Required** - E2E coverage     |
| **update_reward service**            | ❌ None                               | ✅ **Required** - E2E coverage     |

---

## Existing Test Coverage Analysis

### 1. Options Flow - Rewards (COVERED ✅)

**File**: `tests/test_options_flow_entity_crud.py`

| Test                                         | Line | What It Tests                                                                                 |
| -------------------------------------------- | ---- | --------------------------------------------------------------------------------------------- |
| `test_options_flow_navigate_to_rewards_menu` | 157  | Navigation to rewards submenu                                                                 |
| `test_add_reward_via_options_flow`           | 306  | **Full add reward flow** - calls `async_step_add_reward()` which now uses `eh.build_reward()` |

**Code path tested**:

```
test_add_reward_via_options_flow
  → FlowTestHelper.add_entity_via_options_flow()
    → options_flow.async_step_add_reward()
      → eh.build_reward(user_input)  ← NEW CODE EXERCISED
```

**Conclusion**: Adding a reward via Options Flow **is covered**. The test exercises the new `entity_helpers.build_reward()` function indirectly.

---

### 2. Reward Services (NOT YET COVERED ⚠️)

**File**: `tests/test_reward_services.py`

| Test                                                      | Line | What It Tests                     |
| --------------------------------------------------------- | ---- | --------------------------------- |
| `test_approve_reward_lesser_cost_deducts_override_amount` | ~75  | approve_reward with cost_override |

**Missing**:

- `create_reward` service handler ← **NEED TESTS**
- `update_reward` service handler ← **NEED TESTS**

---

## Recommendation

### Phase 6 Test Implementation Priority

1. **HIGH PRIORITY** - Add service tests to `tests/test_reward_services.py`:
   - `TestCreateRewardService` (4-5 tests) - Full E2E path
   - `TestUpdateRewardService` (4-5 tests) - Full E2E path

2. **SKIP** - Unit tests for `entity_helpers.build_reward()`:
   - Covered implicitly by service tests
   - Options Flow tests already exercise the same code path
   - Lower value than E2E coverage

3. **NOT NEEDED** - Additional Options Flow tests:
   - `test_add_reward_via_options_flow` already exercises the path

---

## Test Scenarios for Test Builder

### Required: `tests/test_reward_services.py` (EXTEND EXISTING)

Add to existing file which already has `TestApproveRewardCostOverride`.

#### TestCreateRewardService (E2E)

| Scenario                                          | Priority | Description                                                   |
| ------------------------------------------------- | -------- | ------------------------------------------------------------- |
| `test_create_reward_service_success`              | HIGH     | Full path: schema → mapping → build → storage → response      |
| `test_create_reward_service_returns_reward_id`    | HIGH     | Verify response contains `reward_id`                          |
| `test_create_reward_service_duplicate_name_error` | HIGH     | Duplicate name → ServiceValidationError                       |
| `test_create_reward_service_empty_name_error`     | HIGH     | Empty name → ServiceValidationError via EntityValidationError |
| `test_create_reward_service_applies_defaults`     | MEDIUM   | Missing optional fields get defaults                          |

#### TestUpdateRewardService (E2E)

| Scenario                                           | Priority | Description                                |
| -------------------------------------------------- | -------- | ------------------------------------------ |
| `test_update_reward_service_success`               | HIGH     | Updates existing reward, returns reward_id |
| `test_update_reward_service_not_found_error`       | HIGH     | Invalid reward_id → ServiceValidationError |
| `test_update_reward_service_partial_update`        | HIGH     | Only cost provided → name preserved        |
| `test_update_reward_service_preserves_internal_id` | HIGH     | internal_id unchanged after update         |
| `test_update_reward_service_duplicate_name_error`  | MEDIUM   | Rename to existing name → error            |

---

## Test Template for Test Builder

```python
"""Tests for create_reward and update_reward services.

Add to existing tests/test_reward_services.py file.
Phase 6 of Entity Helpers Rewards First plan.

These are E2E tests exercising:
  Schema validation → Field mapping → build_reward() → Storage → Response
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.kidschores import const
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    pass


# ============================================================================
# CREATE REWARD SERVICE TESTS
# ============================================================================


class TestCreateRewardService:
    """Tests for kidschores.create_reward service."""

    @pytest.fixture
    async def scenario_medium(
        self,
        hass: HomeAssistant,
        mock_hass_users: dict[str, Any],
    ) -> SetupResult:
        """Load medium scenario: 2 kids, 1 parent, some chores/rewards."""
        return await setup_from_yaml(
            hass,
            mock_hass_users,
            "tests/scenarios/scenario_medium.yaml",
        )

    @pytest.mark.asyncio
    async def test_create_reward_service_success(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test creating reward via service call.

        Exercises full path: schema → mapping → build_reward() → storage → response
        """
        coordinator = scenario_medium.coordinator

        # Count rewards before
        rewards_before = len(coordinator.rewards_data)

        # Call service with return_response to get reward_id
        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CREATE_REWARD,
            {
                const.SERVICE_FIELD_REWARD_NAME: "New Reward",
                const.SERVICE_FIELD_REWARD_COST: 75.0,
            },
            blocking=True,
            return_response=True,
        )

        # Verify reward was created
        assert len(coordinator.rewards_data) == rewards_before + 1

        # Verify response contains reward_id
        assert response is not None
        assert const.SERVICE_FIELD_REWARD_ID in response
        reward_id = response[const.SERVICE_FIELD_REWARD_ID]

        # Verify reward data in storage
        reward = coordinator.rewards_data[reward_id]
        assert reward[const.DATA_REWARD_NAME] == "New Reward"
        assert reward[const.DATA_REWARD_COST] == 75.0

    @pytest.mark.asyncio
    async def test_create_reward_service_applies_defaults(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test that missing optional fields get default values."""
        coordinator = scenario_medium.coordinator

        # Create with only required fields
        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CREATE_REWARD,
            {
                const.SERVICE_FIELD_REWARD_NAME: "Minimal Reward",
                const.SERVICE_FIELD_REWARD_COST: 25.0,
            },
            blocking=True,
            return_response=True,
        )

        reward_id = response[const.SERVICE_FIELD_REWARD_ID]
        reward = coordinator.rewards_data[reward_id]

        # Verify defaults applied
        assert reward[const.DATA_REWARD_ICON] == const.DEFAULT_REWARD_ICON
        assert reward[const.DATA_REWARD_DESCRIPTION] == ""
        assert reward[const.DATA_REWARD_LABELS] == []

    @pytest.mark.asyncio
    async def test_create_reward_service_duplicate_name_error(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test that duplicate reward name raises error."""
        # Get existing reward name from scenario
        coordinator = scenario_medium.coordinator
        existing_reward = next(iter(coordinator.rewards_data.values()))
        existing_name = existing_reward[const.DATA_REWARD_NAME]

        # Try to create with same name
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_CREATE_REWARD,
                {
                    const.SERVICE_FIELD_REWARD_NAME: existing_name,
                    const.SERVICE_FIELD_REWARD_COST: 50.0,
                },
                blocking=True,
            )


# ============================================================================
# UPDATE REWARD SERVICE TESTS
# ============================================================================


class TestUpdateRewardService:
    """Tests for kidschores.update_reward service."""

    @pytest.fixture
    async def scenario_medium(
        self,
        hass: HomeAssistant,
        mock_hass_users: dict[str, Any],
    ) -> SetupResult:
        """Load medium scenario."""
        return await setup_from_yaml(
            hass,
            mock_hass_users,
            "tests/scenarios/scenario_medium.yaml",
        )

    @pytest.mark.asyncio
    async def test_update_reward_service_success(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test updating reward via service call."""
        coordinator = scenario_medium.coordinator
        reward_id = next(iter(coordinator.rewards_data.keys()))
        original_reward = coordinator.rewards_data[reward_id].copy()

        # Update cost only
        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_UPDATE_REWARD,
            {
                const.SERVICE_FIELD_REWARD_ID: reward_id,
                const.SERVICE_FIELD_REWARD_COST: 999.0,
            },
            blocking=True,
            return_response=True,
        )

        # Verify response
        assert response[const.SERVICE_FIELD_REWARD_ID] == reward_id

        # Verify cost updated, name preserved
        updated = coordinator.rewards_data[reward_id]
        assert updated[const.DATA_REWARD_COST] == 999.0
        assert updated[const.DATA_REWARD_NAME] == original_reward[const.DATA_REWARD_NAME]

    @pytest.mark.asyncio
    async def test_update_reward_service_not_found_error(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test that invalid reward_id raises error."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_UPDATE_REWARD,
                {
                    const.SERVICE_FIELD_REWARD_ID: "nonexistent-uuid",
                    const.SERVICE_FIELD_REWARD_COST: 50.0,
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_update_reward_service_preserves_internal_id(
        self,
        hass: HomeAssistant,
        scenario_medium: SetupResult,
    ) -> None:
        """Test that internal_id is preserved after update."""
        coordinator = scenario_medium.coordinator
        reward_id = next(iter(coordinator.rewards_data.keys()))
        original_internal_id = coordinator.rewards_data[reward_id][const.DATA_REWARD_INTERNAL_ID]

        # Update reward
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_UPDATE_REWARD,
            {
                const.SERVICE_FIELD_REWARD_ID: reward_id,
                const.SERVICE_FIELD_REWARD_NAME: "Renamed Reward",
            },
            blocking=True,
        )

        # Verify internal_id unchanged
        assert coordinator.rewards_data[reward_id][const.DATA_REWARD_INTERNAL_ID] == original_internal_id
```

---

## Files to Modify

| File                            | Action | Lines Est. |
| ------------------------------- | ------ | ---------- |
| `tests/test_reward_services.py` | EXTEND | ~150       |

**Total new test code**: ~150 lines (E2E service tests)
