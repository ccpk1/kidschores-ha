# Quick Start Guide

Walk through creating your first kid, parent, and chore to understand the basic KidsChores workflow.

> [!NOTE]
> This guide covers the **minimum steps** to get started. For complete configuration options, see the entity-specific guides linked below.

---

## What You'll Do

By the end of this guide, you'll have:

- ✅ Created your first kid
- ✅ Created your first parent
- ✅ Created your first chore
- ✅ Tested the claim-approve-points workflow

**Time required**: ~10 minutes

---

## Step 1: Create Your First Kid

Kids earn points by completing chores.

**Required field:**

- **Name**: Enter the kid's name (e.g., "Sarah")

All other fields are optional. Click **Submit** to continue.

> **Navigation**: **Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure** → **Manage Kid** → **Add Kid**

For complete kid configuration options (icons, Home Assistant user linking, notifications, etc.), see [Kids and Parents Guide](Configuration:-Kids-Parents.md).

---

## Step 2: Create Your First Parent

Parents approve chores and manage the system.

**Required field:**

- **Name**: Enter the parent's name (e.g., "Mom")

**Important field:**

- **Associated Kids**: Select which kids this parent can manage (select "Sarah")

All other fields are optional. Click **Submit** to continue.

> **Navigation**: **Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure** → **Manage Parent** → **Add Parent**

For complete parent configuration options, see [Kids and Parents Guide](Configuration:-Kids-Parents.md).

---

## Step 3: Create Your First Chore

Let's create a simple chore to test the workflow.

**Required fields:**

- **Name**: "Make Bed"
- **Default Points**: `10`
- **Assigned Kids**: Select "Sarah"

**Recommended settings** (for testing):

- **Recurring Frequency**: Select "Daily"

All other fields can use default values. Click **Submit** to continue.

> **Navigation**: **Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure** → **Manage Chore** → **Add Chore**

For complete chore configuration options (recurrence patterns, approval settings, overdue handling, etc.), see [Chores Guide](Configuration:-Chores.md).

---

## Step 4: Test the Chore Workflow

### View Entities Created

**Developer Tools** → **States**

Search for "sarah" to see the entities created:

- **Points sensor** (`sensor.kc_sarah_points`): Shows current points balance
- **Chore status sensor** (`sensor.kc_sarah_chore_status_make_bed`): Shows chore state (`pending`, `claimed`, `approved`, `overdue`) and statistics
- **Chore buttons**: Claim, approve, and disapprove buttons

For a complete list of all entity types, see [Entities Overview](Technical:-Entities-States.md).

### Understanding the Workflow

Here's the basic chore cycle:

```
1. Chore Created → Status: pending
   ↓
2. Kid Claims → Status: claimed
   ↓
3. Parent Approves → Status: approved (points awarded)
   ↓
4. Approval Reset Time (e.g., midnight) → Status: pending (cycle repeats)
```

**Key points:**

- Points are awarded when a parent **approves**
- Approved chores reset to pending based on their **approval reset schedule** (default: `At Midnight (Once)`, meaning the chore can be completed **once** per approval cycle)
- When the approval reset occurs, recurring chores are **rescheduled** to their next due date based on recurrence settings
- Parents and kids can receive notifications when chores are acted on (if configured)

---

### Claim the Chore

**Developer Tools** → **Actions**

Call the button press service:

```yaml
action: button.press
target:
  entity_id: button.kc_sarah_chore_claim_make_bed
```

**Check the status sensor** (`sensor.kc_sarah_chore_status_make_bed`) - state should now be `claimed`.

### Approve the Chore

**Developer Tools** → **Actions**

Call the button press service:

```yaml
action: button.press
target:
  entity_id: button.kc_sarah_chore_approval_make_bed
```

**Check the status sensor** - state should now be `approved`.

### Check Points Awarded

**Developer Tools** → **States**

Find the points sensor (`sensor.kc_sarah_points`) - it should now show `10` points.

---

## Using a Dashboard

Instead of using Developer Tools, you'll want a user-friendly dashboard for everyday use.

**This integration handles all the backend work** - it creates all the entities you need (sensors, buttons, etc.) so you can display them however you like. You have complete creative freedom to:

- Build custom Lovelace cards using the entities from [Entities Overview](Technical:-Entities-States.md)
- Create your own dashboard layouts that match your family's needs
- Use any Home Assistant dashboard features (conditional cards, badges, graphs, etc.)
- Integrate with other integrations and automations

**However, the quickest way to see everything** is to use the [**Auto-Populating Dashboard**](Advanced:-Dashboard.md). This pre-built UI automatically displays all your kids, chores, rewards, and badges with no manual entity configuration - just add the dashboard YAML and it works immediately.

See the [Dashboard Wiki](Advanced:-Dashboard.md) for installation instructions, or explore the [Entities Overview](Technical:-Entities-States.md) to build your own custom interface.

---

## What's Next?

Now that you understand the basics, explore:

- **[Kids and Parents Guide](Configuration:-Kids-Parents.md)** - User management, notifications, multi-parent approvals
- **[Chores Guide](Configuration:-Chores.md)** - Recurrence patterns, approval settings, overdue handling, shared chores
- **[Entities Overview](Technical:-Entities-States.md)** - Complete list of all sensors and buttons created
- **[Rewards Guide](Configuration:-Rewards.md)** - Let kids spend their points
- **[Badges Guide](Configuration:-Badges-Cumulative.md)** - Set up milestone achievements
- **[Auto-Populating Dashboard](Advanced:-Dashboard.md)** - Pre-built dashboard UI

---

**Remember**: This guide shows the minimum required fields. Each entity type has many more configuration options available in the full guides linked above.
