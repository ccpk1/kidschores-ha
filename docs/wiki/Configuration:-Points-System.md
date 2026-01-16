# Configuration: Points System

The Points System is the central currency for KidsChores. Kids earn points from chores and bonuses, then spend them on rewards.

> [!TIP] > **System-Wide Configuration**: Points label and icon apply to all kids. Customize during setup or via Reconfigure System Settings.

---

## Points Configuration

### Label & Icon (Initial Setup)

Configure during integration setup (after welcome screen, before kids):

| Field            | Type | Required | Default            | Description                                     |
| ---------------- | ---- | -------- | ------------------ | ----------------------------------------------- |
| **Points Label** | Text | ✅       | "Points"           | Display name (e.g., "Stars", "Coins", "Tokens") |
| **Points Icon**  | Icon | ○        | `mdi:star-outline` | Icon shown throughout system                    |

**Edit Later**: Settings → Devices & Services → KidsChores → Configure → Manage Points

> [!NOTE]
> Changing label/icon updates all entities immediately. Kids' point balances remain unchanged.

### Manual Adjustment Buttons (General Options)

Configure 6 button values (3 positive, 3 negative) for quick parent adjustments:

**Location**: Configure → General Options → Manual Points Adjustment Button Values

**Format**: Values separated by `|` (pipe character)

**Default**: `+1.0 | -1.0 | +2.0 | -2.0 | +10.0 | -10.0`

**Example Custom Values**: `+5.0 | -5.0 | +10.0 | -10.0 | +25.0 | -25.0

> [!TIP] > **Use Cases**: Quick corrections, spontaneous rewards, behavioral adjustments, teaching moments without creating formal chores/bonuses.

---

## Earning Points

### From Chores

**When**: Parent approves a chore claim

**Amount**: Chore's `default_points` value

**Badge Multiplier**: If kid has active badge, points multiplied (e.g., 1.5x turns 10 points into 15)

**Example**:

```
Chore: "Make Bed" = 10 points
Kid has Gold Badge (1.5x multiplier)
Points Earned: 10 × 1.5 = 15 points
```

### From Bonuses

**When**: Parent presses bonus button

**Amount**: Bonus's `bonus_points` value

**Badge Multiplier**: Applied same as chores

**Use Case**: Extra credit for exceptional work beyond regular chores

### Manual Adjustments

**When**: Parent presses one of 6 manual adjustment buttons

**Amount**: Configured button value (e.g., +1, -2, +10)

**No Multiplier**: Manual adjustments bypass badge multipliers

**Entities**: `button.kc_<kid>_points_adjust_plus1`, `button.kc_<kid>_points_adjust_minus1`, etc.

---

## Spending Points

### On Rewards

**When**: Parent approves reward claim

**Amount**: Reward's `cost` value

**Validation**: Kid must have sufficient points before approval

**Timing**: Points deducted at approval time (NOT at claim time)

**Example**:

```
Reward: "Ice Cream" costs 10 points
Kid claims (balance still 45 points)
Parent approves → 10 points deducted
New balance: 35 points
```

### On Penalties

**When**: Parent presses penalty button

**Amount**: Penalty's `penalty_points` value

**No Minimum**: Balance can go negative

**Use Case**: Consequences for broken rules or incomplete responsibilities

---

## Points Tracking

### Primary Points Sensor

**Entity**: `sensor.kc_<kid>_points`

**State**: Current point balance (number)

**Key Attributes**:

- `points_earned` - Total earned (all-time)
- `points_spent` - Total spent (all-time)
- `points_earned_today` - Today's earnings
- `points_earned_weekly` - This week's earnings
- `points_earned_monthly` - This month's earnings
- `points_spent_today` - Today's spending
- `points_spent_weekly` - This week's spending
- `points_spent_monthly` - This month's spending
- `points_max_ever` - Highest balance achieved
- `points_label` - Configured label
- `points_icon` - Configured icon

### Optional Extra Sensors

**Enable**: Configure → General Options → Show Extra Entities

**Entities** (per kid):

- `sensor.kc_<kid>_points_earned_daily`
- `sensor.kc_<kid>_points_earned_weekly`
- `sensor.kc_<kid>_points_earned_monthly`
- `sensor.kc_<kid>_points_max_ever`

> [!NOTE]
> All data available in `sensor.kc_<kid>_points` attributes. Extra sensors exist for users who prefer separate entities.

---

## Manual Adjustment Buttons

Each kid gets 6 button entities based on configured values:

**Entity Format**: `button.kc_<kid>_<sign>_<value>`

**Default Buttons** (for kid "Sarah"):

- `button.kc_sarah_points_plus_1_0` - "+1.0 Points"
- `button.kc_sarah_points_minus_1_0` - "-1.0 Points"
- `button.kc_sarah_points_plus_2_0` - "+2.0 Points"
- `button.kc_sarah_pointst_minus_2_0` - "-2.0 Points"
- `button.kc_sarah_points_plus_10_0` - "+10.0 Points"
- `button.kc_sarah_points_minus_10_0` - "-10.0 Points"

**Button Labels**: `{sign} {points_label}` (e.g., "+5.0 Stars" if label is "Stars")

**Icons**:

- Single values: `mdi:plus-circle-outline` / `mdi:minus-circle-outline`
- Multiple values: `mdi:plus-circle-multiple-outline` / `mdi:minus-circle-multiple-outline`

---

## Badge Multipliers

When a kid has an active badge with a points multiplier:

**Applies To**:

- ✅ Chore points (when parent approves)
- ✅ Bonus points (when parent applies)

**Does NOT Apply To**:

- ❌ Reward costs (no discount on spending)
- ❌ Penalty amounts (no reduction in consequences)
- ❌ Manual adjustments (bypass multipliers)

**Example**:

```
Badge: "Gold Star" with 1.5x multiplier
Chore: 10 points → Kid earns 15 points (10 × 1.5)
Bonus: 5 points → Kid earns 7.5 points (5 × 1.5)
Reward: 20 points → Kid spends exactly 20 (no discount)
Manual +10 button → Kid gets exactly 10 (no multiplier)
```

---

## Points System Flow

**Earning Cycle**:

1. Kid claims chore → Parent approves → Points earned (with badge multiplier)
2. Parent presses bonus button → Points earned (with badge multiplier)
3. Parent presses +X manual button → Points added (no multiplier)

**Spending Cycle**:

1. Kid claims reward → Parent approves → Points deducted
2. Parent presses penalty button → Points deducted

**Balance Updates**: All transactions update `sensor.kc_<kid>_points` immediately

---

## Troubleshooting

| Issue                                 | Solution                                                                                                  |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Wrong label showing                   | Reconfigure → System Settings → Update Points Label                                                       |
| Manual buttons not working            | Check General Options → Points Adjust Values configured                                                   |
| Points not multiplied by badge        | Verify kid has active badge with points_multiplier > 1.0                                                  |
| Negative balance allowed              | Expected behavior - penalties can reduce balance below 0                                                  |
| Statistics warning after label change | Normal behavior - unit changed from old to new label. Fix via Developer Tools → Statistics (no data loss) |

> [!NOTE] > **Label Changes & Statistics**: Changing points label triggers a statistics warning because Home Assistant tracks unit changes (e.g., "Points" → "Stars"). Resolve via Settings → Developer Tools → Statistics following Home Assistant's standard fix approach. No impact on point balances or history.

---

## Related Documentation

- [Configuration: Kids and Parents](Configuration:-Kids-and-Parents) - Set up kids to track points
- [Chore Configuration Guide](Chore-Configuration-Guide) - Primary way to earn points
- [Configuration: Rewards](Configuration:-Rewards) - Primary way to spend points
- [Configuration: Badges](Configuration:-Badges) - Points multipliers (coming soon)
- [Technical Reference: Entities & States](Technical-Reference:-Entities-&-States) - Complete entity details

---

**Last Updated**: January 2026 (v0.5.0)
