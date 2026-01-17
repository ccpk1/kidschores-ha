# Configuration: Rewards

Rewards are items that kids can claim by spending their earned points.

> [!TIP] > **Universal Rewards**: All kids can claim any reward (no per-kid assignment needed). Simple workflow: claim → approve/disapprove.

---

## Creating a Reward

1. **Settings** → **Devices & Services** → **KidsChores** → **Configure**
2. Select **Manage Reward** → **Add Reward**
3. Fill in the form and click **Submit**

> [!NOTE]
> During initial setup, you'll be asked "Number of Rewards" - enter count or `0` to skip and add later.

---

## Reward Configuration Fields

| Field             | Type          | Required | Default            | Description                                     |
| ----------------- | ------------- | -------- | ------------------ | ----------------------------------------------- |
| **Reward Name**   | Text          | ✅       | -                  | Display name. Must be unique.                   |
| **Reward Cost**   | Number        | ✅       | 10                 | Points required to claim. Min: 0                |
| **Description**   | Text          | ○        | Empty              | Optional notes.                                 |
| **Reward Labels** | Label (multi) | ○        | None               | Tags for organization (e.g., "treats", "toys"). |
| **Icon**          | Icon          | ○        | `mdi:gift-outline` | Icon for entities.                              |

> [!TIP] > **Labels help organize**: Use labels like `"screen_time"`, `"treats"`, `"physical_items"` for dashboard filtering.

---

## Reward Claiming Workflow

1. **Kid Claims** → Parent notified (no points deducted yet)
2. **Parent Approves** → Points deducted, reward granted, resets to Available
3. **Parent Disapproves** → No points involved, resets to Available

> [!NOTE]
> Rewards can be claimed multiple times. Each claim is a separate transaction.

> [!TIP] > **Undo for Kids**: Kids can press the **Disapprove** button while in Claimed status to undo their claim. This isn't tracked as a disapproval statistic.

---

## Entities Created

Each reward creates 4 entities per kid:

- **Sensor** (`sensor.kc_<kid>_reward_status_<name>`): Current state + detailed attributes
- **Claim Button**: For kids to claim the reward
- **Approve Button**: For parents to approve claims
- **Disapprove Button**: For parents to reject claims (Kids can press the **Disapprove** button while in Claimed status to undo their claim)

### Reward Sensor Attributes

The reward sensor tracks comprehensive claim history and statistics:

- **Basic Info**: Kid name, reward name, description, cost
- **Status**: Pending claims count, last claimed/approved/disapproved timestamps
- **Statistics**: Claims/approvals/disapprovals by time period (today, week, month, year, all-time)
- **Points**: Points spent by time period
- **Metrics**: Approval rate (%), average claims per day (week/month)
- **Related Buttons**: Entity IDs for claim/approve/disapprove buttons

> [!TIP]
> Use these attributes in dashboards for reward analytics (e.g., most popular rewards, approval rates, spending trends).

> [!NOTE]
> See [Technical Reference: Entities & States](Technical:-Entities-States.md) for full entity list and details.

---

## Managing Rewards

**Edit a Reward**: Configure → Manage Reward → Edit Reward.

**Delete a Reward**: Configure → Manage Reward → Delete Reward.

> [!WARNING]
> Deletion is permanent. All reward entities are removed. Pending claims are auto-disapproved with points refunded.

---

## Notifications

Kid and parent notifications are sent when rewards are claimed, approved, or disapproved. Configure in the [Notifications step](Configuration:-Notifications).

---

## Troubleshooting

| Issue                                    | Solution                                     |
| ---------------------------------------- | -------------------------------------------- |
| Kid can't claim reward                   | Check kid has enough points (Cost ≤ Balance) |
| "A reward with this name already exists" | Choose a unique reward name                  |
| Reward entities missing                  | Reload integration after adding reward       |
| Points not refunded on disapproval       | Check coordinator logs for storage issues    |

---

## Related Documentation

- [Configuration: Kids and Parents](Configuration:-Kids-and-Parents) - Set up kids to claim rewards
- [Configuration: Points System](Configuration:-Points-System) - Configure point earning and spending rules
- [Chore Configuration Guide](Chore-Configuration-Guide) - How kids earn points
- [Technical Reference: Entities & States](Technical:-Entities-States.md) - Complete entity details
- [Dashboard: Auto-Populating UI](Dashboard:-Auto-Populating-UI) - Display rewards in dashboard

---

**Last Updated**: January 2026 (v0.5.0)
