# Dashboard Integration

**Target Audience**: Users wanting auto-populating dashboards
**Prerequisites**: KidsChores integration installed and configured
**Related**: [Quick Start Guide](Getting-Started:-Quick-Start.md)

---

## Overview

KidsChores includes a companion dashboard system that automatically populates with your chores, rewards, badges, and kid profiles. No manual card configuration needed—the dashboard reads from your entities and displays everything in an organized, mobile-friendly interface.

**Why a separate repository?**

- Dashboard is optional (KidsChores works without it)
- Different update cycle (dashboard UI vs integration logic)
- Easier customization for advanced users
- Keeps integration lightweight

---

## Dashboard Helper Sensor

Every kid gets a **Dashboard Helper Sensor** that powers the auto-populating UI:

```yaml
sensor.kc_<kid>_ui_dashboard_helper
```

### What It Provides

The dashboard helper pre-processes data for efficient template rendering:

**Pre-Sorted Lists**:

- `chores` - All chores sorted by status and due date
- `rewards` - Available rewards sorted by cost
- `badges` - Badge progress and maintenance status
- `bonuses` - Recent bonus point adjustments
- `penalties` - Recent penalty adjustments
- `achievements` - Achievement progress (legacy)
- `challenges` - Active challenges (legacy)

**Aggregated Metrics**:

- Badge maintenance countdown
- Achievement progress percentages
- Reward claim counts
- Point statistics

**Localized Strings**:

- `ui_translations` - All 40+ UI labels in user's language
- Eliminates need for language-specific YAML variants

### Example Usage

```yaml
{% set dashboard_helper = 'sensor.kc_sarah_ui_dashboard_helper' %}
{% set ui = state_attr(dashboard_helper, 'ui_translations') or {} %}
{% set chore_list = state_attr(dashboard_helper, 'chores') | default([], true) %}

# Pre-sorted by backend - just iterate
{% for chore in chore_list %}
  {{ chore.name }}: {{ chore.status }}
{% endfor %}
```

**Performance benefit**: Backend does expensive sorting/filtering once; frontend just renders.

---

## Installation

### Repository

**Dashboard Repository**: [kidschores-ha-dashboard](https://github.com/ccpk1/kidschores-ha-dashboard)

### Quick Install

1. **Download Dashboard YAML**:
   - Visit the [dashboard repository](https://github.com/ccpk1/kidschores-ha-dashboard)
   - Download `kc_dashboard_all.yaml`

2. **Create Dashboard in Home Assistant**:
   - Navigate to **Settings → Dashboards**
   - Click **+ Add Dashboard**
   - Choose **New dashboard from scratch**
   - Enter name: "KidsChores - [Kid Name]"

3. **Paste YAML Content**:
   - Open dashboard
   - Click **⋮** (three dots) → **Edit Dashboard**
   - Click **⋮** again → **Raw configuration editor**
   - Paste content from `kc_dashboard_all.yaml`
   - Replace `Kidname` with your kid's actual name (case-sensitive)
   - Save

4. **Verify**:
   - Dashboard should populate with all chores, rewards, badges
   - Check that sensors exist: `sensor.kc_<kid>_ui_dashboard_helper`

### Multiple Kids

Create one dashboard per kid:

- Duplicate YAML file
- Change all instances of kid name
- Create separate dashboard for each child

---

## Dashboard Features

### Auto-Populating Cards

**Chore Cards**:

- Today's chores (AM/PM groups)
- This week's chores
- Overdue chores
- Pending approvals (parent view)

**Reward Showcase**:

- Available rewards sorted by cost
- Claim buttons
- Point balance display

**Badge Display**:

- Progress bars for active badges
- Maintenance countdown
- Badge history

**Stats & Metrics**:

- Points earned (today, week, month, all-time)
- Chore completion streaks
- Approval rates

### Mobile Optimization

Dashboard is designed for:

- ✅ Phone screens (primary use case)
- ✅ Tablets
- ✅ Smartwatches (action buttons work on watches)

### Customization

**User Preferences** (in YAML):

- `pref_column_count` - Number of columns
- `pref_use_overdue` - Show/hide overdue section
- `pref_use_labels` - Filter by specific labels

**Colors**:

- `green` = approved
- `orange` = claimed/pending
- `red` = overdue
- `blue` = multi-approved (shared chores)
- `purple` = partial approval

---

## How Entities Integrate

### Entity Naming Convention

All KidsChores entities follow this pattern:

```
<platform>.kc_<kid_slug>_<purpose>
```

**Example** (kid named "Sarah"):

```yaml
sensor.kc_sarah_points                    # Total points
sensor.kc_sarah_ui_dashboard_helper       # Dashboard data
button.kc_sarah_feed_dog_claim            # Claim button
button.kc_sarah_feed_dog_approve          # Approve button
sensor.kc_sarah_feed_dog                  # Chore status
```

### Dashboard Reads From

**Button Entities**:

- `button.kc_<kid>_<chore>_claim` - Kid presses to claim
- `button.kc_<kid>_<chore>_approve` - Parent presses to approve

**Sensor Entities**:

- `sensor.kc_<kid>_points` - Point balance
- `sensor.kc_<kid>_<chore>` - Individual chore status/attributes
- `sensor.kc_<kid>_ui_dashboard_helper` - Pre-processed dashboard data

**Actions Triggered**:

- Press claim/approve buttons directly from dashboard
- No need for automation or script layers
- Instant feedback (entity state updates)

---

## Advanced Customization

### Custom Card Groups

Edit YAML to add custom groupings:

```yaml
# Add morning routine group
- type: heading
  heading: "🌅 Morning Routine"
- type: custom:auto-entities
  filter:
    include:
      - entity_id: sensor.kc_sarah_*
        attributes:
          labels: morning
```

### Conditional Sections

Show sections based on conditions:

```yaml
# Only show rewards if kid has points
card_mod:
  style: |
    {% if states('sensor.kc_sarah_points')|int > 0 %}
      ha-card { display: block; }
    {% else %}
      ha-card { display: none; }
    {% endif %}
```

### Label-Based Filtering

Focus on specific chore types:

```yaml
# Show only pet care chores
pref_label_filter: "pets"
```

---

## Troubleshooting

### Dashboard Shows "err-\*" Text

**Cause**: Dashboard helper sensor not found or missing attributes

**Fix**:

1. Verify sensor exists: `sensor.kc_<kid>_ui_dashboard_helper`
2. Check entity state in **Developer Tools → States**
3. Verify `ui_translations` attribute is populated
4. Reload integration if needed

### Chores Not Appearing

**Cause**: Entity naming mismatch

**Fix**:

1. Check kid name slug: Developer Tools → States → search `kc_<name>`
2. Home Assistant slugifies names (removes accents, lowercases, replaces spaces)
3. Update YAML to match exact slug

### Buttons Don't Work

**Cause**: Button entities don't exist or wrong entity IDs

**Fix**:

1. Verify button entities exist: `button.kc_<kid>_<chore>_claim`
2. Check Developer Tools → States for exact entity IDs
3. Update dashboard YAML with correct entity IDs

---

## Dashboard vs Custom Cards

**Dashboard Repository** (Recommended):

- ✅ Pre-built, tested layouts
- ✅ Auto-populating (no manual config)
- ✅ Mobile-optimized
- ✅ Regular updates from community

**Custom Cards** (DIY):

- ✅ Full control over layout
- ✅ Integrate with other dashboards
- ❌ More complex setup
- ❌ Manual entity configuration

**Both approaches work**—choose based on your comfort level with YAML and dashboard design.

---

## Related Documentation

- **[Quick Start Guide](Getting-Started:-Quick-Start.md)** - Basic entity overview
- **[Technical Reference: Entities & States](Technical:-Entities-States.md)** - Complete entity documentation
- **[Services Reference](Services:-Reference.md)** - Service calls from dashboard buttons

---

## Dashboard Repository

**Full documentation, examples, and updates**:
🔗 **[kidschores-ha-dashboard GitHub Repository](https://github.com/ccpk1/kidschores-ha-dashboard)**

**Includes**:

- Complete dashboard YAML files
- Customization examples
- Troubleshooting guides
- Community contributions
- Update changelogs

---

**Last Updated**: v0.5.0 (January 2026)
