# Configuration: Kids and Parents

This guide covers configuring kids (children in your household) and parents (adults who approve chores and manage points).

> [!TIP] > **Parents can track their own chores too!**: KidsChores now natively supports assigning chores to parents through a linked "Shadow" kid profile that is automatically managed. Parents can choose to enable/disable gamification and approvals, creating a streamlined task and chore manager while keeping robust scheduling, due dates, and all other native capabilities.

---

## Kids Configuration

### Creating a Kid

1. **Settings** → **Devices & Services** → **KidsChores** → **Configure**
2. Select **Manage Kid** → **Add Kid**
3. Fill in the form and click **Submit**

### Kid Configuration Fields

| Field                         | Type     | Required | Default  | Description                                             |
| ----------------------------- | -------- | -------- | -------- | ------------------------------------------------------- |
| **Kid Name**                  | Text     | ✅       | -        | Display name. Must be unique. Used in entity IDs.       |
| **Home Assistant User**       | Select   | ○        | None     | Link to HA user for access restrictions                 |
| **Mobile Notify Service**     | Select   | ○        | Disabled | Notification service (e.g., `notify.mobile_app_*`).     |
| **Language**                  | Language | ○        | English  | UI language for dashboard helper and notifications.     |
| **Enable Due Date Reminders** | Toggle   | ○        | ✅ True  | Send notifications 30 min before unclaimed chore is due |

> [!TIP] > **Notifications**: Due date reminders as well as other chore notifications require both **Mobile Notify Service** to be set.

> [!TIP] > Shadow kid profiles for parents have the same configurable settings but notifications are disabled by default to prevent duplicates—parents already receive chore notifications. Parents may re-enable and use to suit their needs, just be aware of potential duplicates.

### Entities Created

Each kid gets a device with entities including:

- **`sensor.kc_<kid>_points`** - Point balance and statistics
- **`sensor.kc_<kid>_chores`** - Chores completed and statistics
- **`sensor.kc_<kid>_ui_dashboard_helper`** - Pre-sorted lists (chores, rewards, badges, etc.)
- **`sensor.kc_<kid>_chore_status_<chore>`** - Per-kid / Per-chore status tracking
- **Chore buttons** - Claim, approve, disapprove per assigned chore
- **Reward buttons** - Claim, approve, disapprove per assigned reward
- **Bonus/penalty buttons** - Per bonus/penalty
- **`calendar.kc_<kid>`** - Due dates

**Full Details**: See [Technical Reference: Entities & States](Technical-Reference:-Entities-&-States) for complete entity list and attributes.

### Managing Kids

**Edit:** **Configure** → **Manage Kid** → **Edit Kid**

**Remove:** **Configure** → **Manage Kid** → **Delete Kid**

> [!WARNING]
> Deletion is permanent. All entities, history, and points are deleted.

---

## Parents Configuration

### Creating a Parent

1. **Settings** → **Devices & Services** → **KidsChores** → **Configure**
2. Select **Manage Parent** → **Add Parent**
3. Fill in the form and click **Submit**

### Parent Configuration Fields

| Field                      | Type         | Required | Default  | Description                                         |
| -------------------------- | ------------ | -------- | -------- | --------------------------------------------------- |
| **Parent Name**            | Text         | ✅       | -        | Display name. Must be unique.                       |
| **Associated Kids**        | Multi-Select | ✅       | -        | Kids this parent can manage.                        |
| **Home Assistant User**    | Select       | ○        | None     | Link to HA user for authorization.                  |
| **Mobile Notify Service**  | Select       | ○        | Disabled | Notification service for pending approvals.         |
| **Dashboard Language**     | Language     | ○        | English  | UI language (if chore assignment enabled).          |
| **Allow Chore Assignment** | Toggle       | ○        | False    | Create shadow kid so parent can be assigned chores. |
| **Enable Chore Workflow**  | Toggle       | ○        | False    | Parent chores use claim→approve workflow.           |
| **Enable Gamification**    | Toggle       | ○        | False    | Parent participates in points system.               |

**Key Notes:**

- **Associated Kids** _(Required)_: At least one kid must be selected.
- **Home Assistant User**: If linked, only that user can approve chores (authorization check).
- **Allow Chore Assignment**: Creates "shadow kid" - parent appears in chore assignment dropdowns.
- **Enable Chore Workflow**: Without this, parent chores use one-click approval.
- **Enable Gamification**: Without this, parent chores complete without points.

### Understanding Shadow Kids

When **Allow Chore Assignment** is enabled, a **shadow kid** is created, allowing chores to be assigned to the parent.

| Aspect                            | Regular Kid | Shadow Kid (Parent)                                     |
| --------------------------------- | ----------- | ------------------------------------------------------- |
| Created via                       | Kids menu   | Parents menu (automatic)                                |
| Managed via                       | Kids menu   | Parents menu to enable / Kids menu for customizing      |
| Points sensor                     | Always      | Only if gamification enabled                            |
| Claim button / Dissapprove button | Always      | Only if workflow enabled                                |
| Approve button                    | Always      | Always (Approve handles claim and approve in one click) |

**Entity Naming:** Shadow kids use parent's name (e.g., `sensor.kc_mom_chore_status_mow_lawn`)

**Deletion:** Deleting parent deletes shadow kid and all entities.

> [!NOTE] > **Existing Users—Upgrade Your Manual Kid Profile**: If you've been using a regular kid entity for yourself, use the one-time linking service in [Service: Shadow Kid Linking User Guide](Service:-Shadow-Kid-Linking-User-Guide) to migrate that kid to a parent's shadow kid account. This preserves all history and chore assignments without re-setup. Simply enabling **Allow Chore Assignment** on a new parent would create a duplicate shadow kid and lose your existing data.

**Advanced:** For more details on linking and managing shadow kids, see [Service: Shadow Kid Linking User Guide](Service:-Shadow-Kid-Linking-User-Guide).

### Parent Capability Tiers

**Tier 1: Basic Approval** _(Default)_

- Can: Approve kid chores, approve rewards, apply bonuses/penalties
- Entities: None

**Tier 2: Parent with Chores** _(Approval-Only)_

- Config: **Allow Chore Assignment** = True
- Can: Be assigned chores, one-click approval
- Entities: Chore sensors, approve buttons, calendar
- Missing: Claim/disapprove buttons, points

**Tier 3: Parent with Workflow**

- Config: Chore assignment + **Enable Chore Workflow** = True
- Adds: Claim and disapprove buttons

**Tier 4: Full Gamification**

- Config: All options enabled
- Adds: Points, rewards, badges, bonuses/penalties

### Managing Parents

**Edit:** **Configure** → **Manage Parent** → **Edit Parent**
**Remove:** **Configure** → **Manage Parent** → **Delete Parent**

> [!NOTE]
> Toggling **Allow Chore Assignment** off will unlink the shadow kid and leave it as `<kid>_unlinked`. The kid can then be manually deleted through **Manage Kid** if desired. This preserves data as a safety precaution.

> [!WARNING]
> Deletion of parent is permanent. If chore assignment was enabled, the shadow kid will be unlinked and left as `<kid>_unlinked` in the system. You can manually delete this unlinked kid through **Manage Kid** if desired.

---

## Workflows

### Kid Chore Approval

1. Kid claims → Parent notified
2. Parent approves → Points awarded
3. Alternative: Parent disapproves → Returns to pending

### Parent Chore Completion

**Tier 2:** One-click approve → Complete
**Tier 3:** Claim → Other adult approves → Complete
**Tier 4:** Same as Tier 3, with points

---

## Troubleshooting

| Issue                                   | Solution                          |
| --------------------------------------- | --------------------------------- |
| "Must have at least one associated kid" | Select at least one kid           |
| Shadow kid entities missing             | Enable **Allow Chore Assignment** |
| Parent doesn't have Claim button        | Enable **Enable Chore Workflow**  |
| Parent doesn't have points              | Enable **Enable Gamification**    |

---

## Related Documentation

- [Quick Start Guide](Quick-Start-Guide) - First-time setup
- [Technical Reference: Entities & States](Technical-Reference:-Entities-&-States) - Complete entity details
- [Service: Shadow Kid Linking User Guide](Service:-Shadow-Kid-Linking-User-Guide) - Advanced shadow kid management
- [Dashboard: Auto-Populating UI](Dashboard:-Auto-Populating-UI) - Dashboard helper usage

---

**Last Updated**: January 2026 (v0.5.0)
