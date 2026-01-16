# Rewards Configuration Research

**Research Date**: 2026-01-16
**Source Files**: `config_flow.py`, `options_flow.py`, `flow_helpers.py`, `const.py`, `translations/en.json`

## Overview

Rewards are items that kids can claim/redeem by spending their earned points. Unlike chores (which have 20+ fields and complex workflows), rewards are simpler entities with only 5 configuration fields.

---

## Configuration Fields

### Field Summary Table

| Field Name        | Form Key             | Storage Key     | Type                    | Required | Default               | Validation                |
| ----------------- | -------------------- | --------------- | ----------------------- | -------- | --------------------- | ------------------------- |
| **Reward Name**   | `reward_name`        | `name`          | `str`                   | ✅       | -                     | Must be unique, non-empty |
| **Reward Cost**   | `reward_cost`        | `cost`          | `NumberSelector`        | ✅       | `10`                  | Min: 0, Step: 0.1         |
| **Description**   | `reward_description` | `description`   | `str`                   | ○        | `""` (SENTINEL_EMPTY) | Optional                  |
| **Reward Labels** | `reward_labels`      | `reward_labels` | `LabelSelector` (multi) | ○        | `[]`                  | Optional, multiple labels |
| **Icon**          | `icon`               | `icon`          | `IconSelector`          | ○        | `"mdi:gift-outline"`  | Optional, mdi: format     |

### Field Details

#### 1. Reward Name

- **Form Key**: `CFOF_REWARDS_INPUT_NAME` = `"reward_name"`
- **Storage Key**: `DATA_REWARD_NAME` = `"name"`
- **Type**: String
- **Required**: ✅ Yes
- **Default**: SENTINEL_EMPTY (no default, user must provide)
- **Validation**:
  - Cannot be empty (stripped)
  - Must be unique across all existing rewards
  - Error keys:
    - `TRANS_KEY_CFOF_INVALID_REWARD_NAME` = `"invalid_reward_name"` → "Reward name cannot be empty"
    - `TRANS_KEY_CFOF_DUPLICATE_REWARD` = `"duplicate_reward"` → "A reward with this name already exists"
- **Translation**: `"Reward Name"` (from `en.json`)
- **Usage**: Display name for the reward, used in entity names

#### 2. Reward Cost

- **Form Key**: `CFOF_REWARDS_INPUT_COST` = `"reward_cost"`
- **Storage Key**: `DATA_REWARD_COST` = `"cost"`
- **Type**: `NumberSelector` (BOX mode)
- **Required**: ✅ Yes
- **Default**: `DEFAULT_REWARD_COST` = `10`
- **Validation**:
  - Min: 0 (no negative costs)
  - Step: 0.1 (allows decimal points)
  - No max limit
- **Translation**: `"Reward Cost"` (from `en.json`)
- **Usage**: Number of points required to claim/redeem the reward

#### 3. Description

- **Form Key**: `CFOF_REWARDS_INPUT_DESCRIPTION` = `"reward_description"`
- **Storage Key**: `DATA_REWARD_DESCRIPTION` = `"description"`
- **Type**: String
- **Required**: ○ No
- **Default**: SENTINEL_EMPTY = `""`
- **Validation**: None (optional field)
- **Translation**: `"Description (optional)"` (from `en.json`)
- **Usage**: Optional notes/details about the reward

#### 4. Reward Labels

- **Form Key**: `CFOF_REWARDS_INPUT_LABELS` = `"reward_labels"`
- **Storage Key**: `DATA_REWARD_LABELS` = `"reward_labels"`
- **Type**: `LabelSelector` (multiple=True)
- **Required**: ○ No
- **Default**: `[]` (empty list)
- **Validation**: None (optional field)
- **Translation**: `"Reward Labels"` (from `en.json`)
- **Usage**: Categorization/filtering system for rewards (e.g., "screen_time", "toys", "treats")

#### 5. Icon

- **Form Key**: `CFOF_REWARDS_INPUT_ICON` = `"icon"`
- **Storage Key**: `DATA_REWARD_ICON` = `"icon"`
- **Type**: `IconSelector`
- **Required**: ○ No
- **Default**: `DEFAULT_REWARD_ICON` = `"mdi:gift-outline"`
- **Validation**: Must use mdi: format
- **Translation**: `"Icon (mdi:xxx)"` (from `en.json`)
- **Usage**: Icon displayed for reward entities

---

## Internal Fields (Not User-Configurable)

These fields are generated automatically by the system:

| Field               | Storage Key       | Type                | Purpose                        |
| ------------------- | ----------------- | ------------------- | ------------------------------ |
| **Internal ID**     | `internal_id`     | `str` (UUID)        | Primary key for reward         |
| **Reward ID**       | `reward_id`       | `str`               | Legacy/alternate identifier    |
| **Notification ID** | `notification_id` | `str`               | Used for notification tracking |
| **Timestamp**       | `timestamp`       | ISO datetime string | Creation/modification time     |

---

## Configuration Flow

### Initial Setup (config_flow.py)

**Step 1**: `async_step_reward_count`

- Ask: "How many rewards do you want to define?"
- Input: `reward_count` (integer, default: 0)
- Translation key: `config.step.reward_count`
- Can skip: Yes (enter 0 to skip rewards)

**Step 2**: `async_step_rewards` (loops for each reward)

- Title: "Define Reward"
- Description: "Enter details for each reward."
- Schema: Built by `build_reward_schema()`
- Validation: `validate_rewards_inputs()`
- Data builder: `build_rewards_data()`
- Translation key: `config.step.rewards`

### Options Flow (options_flow.py)

Rewards can be managed after initial setup through:

**Add Reward**: `async_step_add_reward`

- Uses same schema as config flow
- Validates against existing rewards
- Creates reward via `coordinator._create_reward()`
- Persists and marks reload needed

**Edit Reward**: `async_step_edit_reward`

- Step ID: `OPTIONS_FLOW_STEP_EDIT_REWARD` = `"edit_reward"`
- Loads existing reward data as defaults
- Same validation as add
- Updates coordinator data

**Delete Reward**: `async_step_delete_reward`

- Step ID: `OPTIONS_FLOW_STEP_DELETE_REWARD` = `"delete_reward"`
- Placeholder: `OPTIONS_FLOW_PLACEHOLDER_REWARD_NAME` = `"reward_name"`
- Removes reward from coordinator
- Persists changes

---

## Reward Claiming Workflow

### States

Rewards don't have complex workflow states like chores. Instead:

1. **Available** - Reward exists and is claimable (if kid has enough points)
2. **Claimed** - Kid has claimed the reward (points deducted, pending parent approval)
3. **Approved** - Parent approved the redemption (reward granted)
4. **Disapproved** - Parent rejected the redemption (points refunded)

### Entities Created Per Kid

For each reward, each kid gets:

- **`sensor.kc_<kid>_reward_<reward>`** - Reward status sensor
- **`button.kc_<kid>_claim_reward_<reward>`** - Claim/redeem button
- **`button.kc_<kid>_approve_reward_<reward>`** - Parent approval button
- **`button.kc_<kid>_disapprove_reward_<reward>`** - Parent disapproval button

### Notifications

**Claim Notification** (to parents):

- Title: `TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED` = `"notification_title_reward_claimed"`
- Message (kid): `TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_KID`
- Message (parent): `TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_PARENT`

**Approval Notification** (to kid):

- Title: `TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED`
- Message: `TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED`

**Disapproval Notification** (to kid):

- Title: `TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED`
- Message: `TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED`

**Reminder Notification**:

- Title: `TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER`
- Message: `TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER`

---

## Key Differences from Chores

| Aspect                   | Chores                                                                   | Rewards                                              |
| ------------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------- |
| **Configuration Fields** | 20+ fields                                                               | 5 fields                                             |
| **Complexity**           | High (scheduling, recurrence, shared modes, auto-approve, streaks, etc.) | Low (just name, cost, optional metadata)             |
| **Assignment**           | Per-kid (can be shared across multiple kids)                             | Universal (all kids can claim any reward)            |
| **Workflow**             | Claim → Approve → Complete (with auto-approve, multi-approval variants)  | Claim → Approve/Disapprove (simple)                  |
| **Point Flow**           | Earn points on completion                                                | Spend points on claim                                |
| **States**               | 6+ states (pending, claimed, approved, disapproved, overdue, reset)      | 4 states (available, claimed, approved, disapproved) |

---

## Validation Summary

### Required Validations

- ✅ Reward name must not be empty
- ✅ Reward name must be unique
- ✅ Reward cost must be ≥ 0

### No Validations For

- Description (any string or empty)
- Labels (any label set or empty)
- Icon (any mdi: icon or default)

### Error Keys

- `CFOP_ERROR_REWARD_NAME` = `"reward_name"` - Error field for name validation
- `TRANS_KEY_CFOF_INVALID_REWARD_NAME` = `"invalid_reward_name"` - Empty name error
- `TRANS_KEY_CFOF_DUPLICATE_REWARD` = `"duplicate_reward"` - Duplicate name error

---

## Storage Format

Rewards are stored in `.storage/kidschores_data` under the `rewards` key as a dictionary keyed by `internal_id`:

```python
{
    "rewards": {
        "abc-123-uuid": {
            "name": "Ice Cream",
            "cost": 20,
            "description": "Trip to ice cream shop",
            "reward_labels": ["treats", "food"],
            "icon": "mdi:ice-cream",
            "internal_id": "abc-123-uuid"
        }
    }
}
```

---

## Translation Keys Reference

### Config Flow

- `config.step.reward_count.title`: "Number of Rewards"
- `config.step.reward_count.description`: "How many rewards do you want to define?"
- `config.step.reward_count.data.reward_count`: "Reward Count"
- `config.step.rewards.title`: "Define Reward"
- `config.step.rewards.description`: "Enter details for each reward."
- `config.step.rewards.data.reward_name`: "Reward Name"
- `config.step.rewards.data.reward_cost`: "Reward Cost"
- `config.step.rewards.data.reward_description`: "Description (optional)"
- `config.step.rewards.data.reward_labels`: "Reward Labels"
- `config.step.rewards.data.icon`: "Icon (mdi:xxx)"

### Error Messages

- `config.error.duplicate_reward`: "A reward with this name already exists"
- `config.error.invalid_reward_name`: "Reward name cannot be empty"

---

## Documentation Notes

When documenting rewards:

1. **Emphasize simplicity** - Rewards are much simpler than chores
2. **Cost is key** - The main decision is how many points the reward costs
3. **Universal availability** - All kids can claim any reward (unlike chore assignment)
4. **No scheduling** - Rewards don't have due dates, recurrence, or scheduling
5. **Labels for organization** - Labels help parents categorize rewards (e.g., screen time vs physical items)
6. **Approval workflow is simple** - Just claim → approve/disapprove (no multi-approval, auto-approve, etc.)

---

**Research Complete** ✅
Next: Create `Configuration:-Rewards.md` documentation (~200-250 lines)
