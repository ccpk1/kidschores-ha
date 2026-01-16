# Points System - Research Documentation

**Research Date**: 2025-01-16
**Purpose**: Complete code-validated reference for Points System documentation
**Sources**: const.py, config_flow.py, options_flow.py, flow_helpers.py, kc_helpers.py, translations/en.json

---

## Configuration Fields

### Points Label & Icon (Config Flow - Initial Setup)

**Form Step**: `points_label` (CONFIG_FLOW_STEP_POINTS)
**Schema**: `build_points_schema()` in flow_helpers.py

| Field            | Form Key       | Storage Key         | Type         | Required | Default              | Validation |
| ---------------- | -------------- | ------------------- | ------------ | -------- | -------------------- | ---------- |
| **Points Label** | `points_label` | `CONF_POINTS_LABEL` | string       | ✅       | `"Points"`           | Non-empty  |
| **Points Icon**  | `points_icon`  | `CONF_POINTS_ICON`  | IconSelector | ○        | `"mdi:star-outline"` | Valid icon |

**Function**: `build_points_data()` converts form keys to storage keys
**Validation**: `validate_points_inputs()` checks label is non-empty
**Error Key**: `points_label_required`

### Manual Points Adjustment Values (Options Flow - General Options)

**Form Step**: `general_options`
**Field**: `points_adjust_values`
**Storage Key**: `CONF_POINTS_ADJUST_VALUES`
**Type**: Multiline text (parsed to list[float])
**Default**: `[+1.0, -1.0, +2.0, -2.0, +10.0, -10.0]`
**Format**: Values separated by `|` (e.g., `+1 | -1 | +2 | -2 | +10 | -10`)

**Parser**: `parse_points_adjust_values()` in kc_helpers.py

- Splits on `|` separator
- Strips whitespace
- Converts to float (handles comma as decimal separator)
- Logs error for invalid numbers

**Usage**: Creates 6 button entities per kid (3 positive, 3 negative)

- Entity naming: `button.kc_<kid>_points_adjust_<sign><value>`
- Translation: `{sign_label} {points_label}` (e.g., "+1 Points", "-2 Points")

---

## Points Earning

### From Chores

- **When**: Parent approves a chore claim
- **Amount**: `default_points` field from chore configuration
- **Multiplier**: Applied if kid has active badge with points multiplier
- **Tracking**: `sensor.kc_<kid>_points` attribute `points_earned` updated

### From Bonuses

- **Trigger**: Parent presses bonus button (`button.kc_<kid>_bonus_<bonus_name>`)
- **Amount**: `bonus_points` field from bonus configuration
- **Multiplier**: Badge multiplier applies to bonus points
- **Tracking**: Bonus application count tracked per bonus

### Badge Multipliers

- **When Active**: Kid has earned/maintained required badge
- **Multiplier**: `points_multiplier` field from badge configuration (default: 1.0)
- **Effect**: All earned points (chores + bonuses) multiplied
- **Example**: Badge with 1.5x multiplier → 10-point chore = 15 points earned

---

## Points Spending

### On Rewards

- **Trigger**: Parent approves reward claim
- **Amount**: `reward_cost` field from reward configuration
- **Validation**: Kid must have sufficient points before claim approval
- **Tracking**: `sensor.kc_<kid>_points` attribute `points_spent` updated
- **Note**: Points NOT deducted at claim time, only at approval

### On Penalties

- **Trigger**: Parent presses penalty button (`button.kc_<kid>_penalty_<penalty_name>`)
- **Amount**: `penalty_points` field from penalty configuration
- **Validation**: No minimum balance check (can go negative)
- **Tracking**: Penalty application count tracked per penalty

---

## Points Sensors

### Primary Points Sensor: `sensor.kc_<kid>_points`

**State**: Current points balance (number)
**Purpose**: Live points tracking with comprehensive history

**Key Attributes**:

- `points_earned` - Total points earned (all-time)
- `points_spent` - Total points spent (all-time)
- `points_earned_today` - Today's earnings
- `points_earned_weekly` - This week's earnings
- `points_earned_monthly` - This month's earnings
- `points_spent_today` - Today's spending
- `points_spent_weekly` - This week's spending
- `points_spent_monthly` - This month's spending
- `points_max_ever` - Highest balance achieved
- `kid_name` - Kid's name
- `purpose` - `"kid_points"`
- `points_label` - Configured points label
- `points_icon` - Configured points icon

### Optional Extra Sensors (Disabled by Default)

Enable via: Configure → General Options → Show Extra Entities

**Points Earned Sensors** (per kid):

- `sensor.kc_<kid>_points_earned_daily`
- `sensor.kc_<kid>_points_earned_weekly`
- `sensor.kc_<kid>_points_earned_monthly`
- `sensor.kc_<kid>_points_max_ever`

**Note**: All data available in `sensor.kc_<kid>_points` attributes.
Extra sensors exist for users who prefer separate entities.

---

## Manual Points Adjustment Buttons

### Button Entities (per kid)

**6 buttons created from `CONF_POINTS_ADJUST_VALUES` list**:

- 3 positive value buttons (add points)
- 3 negative value buttons (subtract points)

**Entity Format**: `button.kc_<kid>_points_adjust_<sign><value>`
**Example**:

- `button.kc_sarah_points_adjust_plus1`
- `button.kc_sarah_points_adjust_minus1`
- `button.kc_sarah_points_adjust_plus2`
- `button.kc_sarah_points_adjust_minus2`
- `button.kc_sarah_points_adjust_plus10`
- `button.kc_sarah_points_adjust_minus10`

**Translation**: `{sign_label} {points_label}`

- `sign_label` = "+" or "-"
- `points_label` = Configured label (e.g., "Points")
- Result: "+1 Points", "-2 Points", etc.

**Default Icons**:

- Positive single: `mdi:plus-circle-outline`
- Negative single: `mdi:minus-circle-outline`
- Positive multiple: `mdi:plus-circle-multiple-outline`
- Negative multiple: `mdi:minus-circle-multiple-outline`

**Purpose**: Parent manual adjustments without creating chores/bonuses/penalties
**Use Cases**:

- Quick corrections
- Spontaneous rewards
- Behavioral adjustments
- Teaching moments

---

## Constants & Defaults

### System Defaults (const.py)

```python
DEFAULT_POINTS = 5                    # Default chore points
DEFAULT_POINTS_LABEL = "Points"       # Default label
DEFAULT_POINTS_ICON = "mdi:star-outline"  # Default icon
DEFAULT_POINTS_ADJUST_VALUES = [+1.0, -1.0, +2.0, -2.0, +10.0, -10.0]  # Manual buttons
DEFAULT_POINTS_MULTIPLIER = 1.0       # Default badge multiplier
```

### Icon Defaults

```python
DEFAULT_POINTS_ADJUST_PLUS_ICON = "mdi:plus-circle-outline"
DEFAULT_POINTS_ADJUST_PLUS_MULTIPLE_ICON = "mdi:plus-circle-multiple-outline"
DEFAULT_POINTS_ADJUST_MINUS_ICON = "mdi:minus-circle-outline"
DEFAULT_POINTS_ADJUST_MINUS_MULTIPLE_ICON = "mdi:minus-circle-multiple-outline"
```

---

## Configuration Locations

### Initial Setup (Config Flow)

1. **Step**: `points_label` (after welcome, before kids)
2. **Fields**: Points Label, Points Icon
3. **Storage**: Config entry options
4. **Can Edit**: Via Reconfigure System Settings

### Post-Setup (Options Flow)

1. **Menu**: Configure → General Options
2. **Fields**: Manual Points Adjustment Button Values
3. **Format**: Multiline text with `|` separator
4. **Storage**: Config entry options
5. **Can Edit**: Yes, anytime via General Options

---

## Translation Keys

### Config Flow

- `config.step.points_label.title`: "Points Label"
- `config.step.points_label.description`: "Set a custom label for your points (e.g., 'Stars', 'Tokens')"
- `config.step.points_label.data.points_label`: "Points Label"
- `config.step.points_label.data.points_icon`: "Points Icon"

### Options Flow

- `options.step.general_options.data.points_adjust_values`: "Manual Points Adjustment Button Values"
- `options.step.general_options.data_description.points_adjust_values`: "List of values for the manual points adjustment buttons. Each value separate by '|'."

### Errors

- `config.error.points_label_required`: "Points label is required"
- `options.error.invalid_points_adjust_values`: "Invalid points adjust values. Must be a list."

### Entity Translations

- `entity.button.parent_points_adjust_button.name`: "{sign_label} {points_label}"
- `entity.button.parent_points_adjust_button.state_attributes.purpose_button_points_adjust.state.purpose_button_points_adjust`: "Parent manually adjusts kid's points"

---

## Key Differences from Other Entities

| Aspect               | Chores/Rewards               | Points System                     |
| -------------------- | ---------------------------- | --------------------------------- |
| **Configuration**    | Per-item (name, cost/points) | System-wide (label, icon)         |
| **Earning/Spending** | Per-transaction tracking     | Lifetime totals + time periods    |
| **Entities**         | 4 per kid per item           | 1 sensor + 6 buttons per kid      |
| **Customization**    | Full config per item         | Global label/icon + manual values |
| **Multipliers**      | No multipliers               | Badge multipliers apply           |

---

## Documentation Notes

1. **Focus on Configuration**: Label, icon, manual adjustment values
2. **Earning Sources**: Chores (with badge multipliers), bonuses
3. **Spending Destinations**: Rewards (at approval), penalties
4. **Manual Adjustments**: Emphasize 3+3 button pattern, use cases
5. **Sensor Attributes**: Rich tracking data (earned, spent, max, time periods)
6. **Badge Integration**: Multipliers boost earned points, not spending

---

## Examples for Documentation

### Basic Configuration

```yaml
# Initial Setup
Points Label: "Stars"
Points Icon: "mdi:star"

# General Options
Manual Points Adjustment Values: "+1 | -1 | +5 | -5 | +20 | -20"
```

### Resulting Entities (for kid "Sarah")

```yaml
# Points Sensor
sensor.kc_sarah_points
  State: 45
  Attributes:
    points_label: "Stars"
    points_icon: "mdi:star"
    points_earned: 150
    points_spent: 105
    points_earned_today: 20
    points_max_ever: 75

# Manual Adjustment Buttons
button.kc_sarah_points_adjust_plus1   # "+1 Stars"
button.kc_sarah_points_adjust_minus1  # "-1 Stars"
button.kc_sarah_points_adjust_plus5   # "+5 Stars"
button.kc_sarah_points_adjust_minus5  # "-5 Stars"
button.kc_sarah_points_adjust_plus20  # "+20 Stars"
button.kc_sarah_points_adjust_minus20 # "-20 Stars"
```

### Earning Examples

```yaml
# From Chore (with 1.5x badge multiplier)
Chore: "Make Bed" = 10 points
Kid has Gold Badge (1.5x multiplier)
Points Earned: 10 × 1.5 = 15 points

# From Bonus
Bonus: "Extra Help" = 5 points
Badge multiplier applies: 5 × 1.5 = 7.5 points

# Manual Adjustment
Parent presses "+20 Stars" button
Balance increased by 20 (no multiplier)
```

### Spending Examples

```yaml
# Reward Claim → Approval
Reward: "Ice Cream" costs 10 stars
Kid claims (no deduction yet)
Parent approves → 10 stars deducted
Balance updated, points_spent increases

# Penalty Applied
Penalty: "Room Not Clean" = 5 points
Parent presses penalty button
5 stars deducted immediately
```
