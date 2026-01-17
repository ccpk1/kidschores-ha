# Notifications Overview

The KidsChores integration sends mobile notifications through Home Assistant's companion app to keep kids and parents informed about chore activity, reward claims, and gamification milestones.

---

## Notification Events & Recipients

The integration sends **17 different notification types** across 4 categories:

### Chore Notifications

| Event                 | Trigger                                | Recipients    | Actionable                          |
| --------------------- | -------------------------------------- | ------------- | ----------------------------------- |
| **Chore Assigned**    | Chore assigned to kid via options flow | Kid           | No                                  |
| **Chore Claimed**     | Kid presses claim button               | Parents       | Yes - Approve/Disapprove/Remind     |
| **Chore Approved**    | Parent approves claimed chore          | Kid + Parents | No                                  |
| **Chore Disapproved** | Parent disapproves claimed chore       | Kid + Parents | No                                  |
| **Chore Overdue**     | Chore past due date                    | Kid + Parents | Kids: Yes - Claim Now / Parents: No |
| **Chore Due Soon**    | Chore due within reminder window       | Kid           | Yes - Claim Now                     |

### Reward Notifications

| Event                  | Trigger                           | Recipients | Actionable                      |
| ---------------------- | --------------------------------- | ---------- | ------------------------------- |
| **Reward Claimed**     | Kid spends points on reward       | Parents    | Yes - Approve/Disapprove/Remind |
| **Reward Approved**    | Parent approves reward redemption | Kid        | No                              |
| **Reward Disapproved** | Parent disapproves reward claim   | Kid        | No                              |

### Gamification Notifications

| Event                     | Trigger                                  | Recipients    | Actionable |
| ------------------------- | ---------------------------------------- | ------------- | ---------- |
| **Badge Earned**          | Kid completes badge requirements         | Kid + Parents | No         |
| **Penalty Applied**       | Parent deducts points via penalty button | Kid           | No         |
| **Bonus Applied**         | Parent awards points via bonus button    | Kid           | No         |
| **Achievement Completed** | Kid completes achievement milestones     | Kid + Parents | No         |
| **Challenge Completed**   | Kid finishes challenge goals             | Kid + Parents | No         |

### Reminder Notifications

| Event                        | Trigger                                  | Recipients | Actionable                      |
| ---------------------------- | ---------------------------------------- | ---------- | ------------------------------- |
| **Chore Reminder (30 min)**  | Parent presses "Remind in 30 min" button | Parents    | Yes - Approve/Disapprove/Remind |
| **Reward Reminder (30 min)** | Parent presses "Remind in 30 min" button | Parents    | Yes - Approve/Disapprove/Remind |

---

## Actionable Notifications

Notifications marked as **Actionable** include buttons that parents can press directly from the notification:

- **Approve** - Marks chore/reward as approved and awards/deducts points
- **Disapprove** - Rejects the claim and resets the chore or refunds points
- **Remind in 30 min** - Schedules a follow-up reminder notification

These action buttons allow parents to manage approvals without opening Home Assistant.

### Overdue & Due-Soon Notifications

Both **Overdue** and **Due-Soon** notifications for **kids** include a **"Claim Now"** action button, allowing kids to claim the chore directly from the notification.

**Overdue** notifications for **parents** are **informational only** - they do not include Approve/Disapprove buttons.

- **Why?** Approve/Disapprove action buttons only make sense for chores that have been claimed and are awaiting parent review. Overdue chores haven't been claimed yet.
- **What happens**: When a kid taps "Claim Now" from either notification type, the chore is claimed and parents receive a proper approval request with action buttons.

---

## Notification Replacement System (Smart Tags)

Notifications use a **smart tagging system** to prevent notification spam. When a new notification is sent with the same tag, it **replaces** the previous notification instead of stacking.

### How Tags Work

Each notification is tagged with a unique identifier combining the entity type and truncated entity IDs. Identifiers are automatically shortened to the first 8 characters to comply with Apple's 64-byte notification header limit while maintaining sufficient uniqueness.

| Notification Type   | Tag Pattern                                       | Example                               |
| ------------------- | ------------------------------------------------- | ------------------------------------- |
| **Chore Approval**  | `kidschores-status-{chore_id[:8]}-{kid_id[:8]}`   | `kidschores-status-abc12345-def6789`  |
| **Reward Approval** | `kidschores-rewards-{reward_id[:8]}-{kid_id[:8]}` | `kidschores-rewards-xyz78901-def6789` |
| **System Alerts**   | `kidschores-system-{kid_id[:8]}`                  | `kidschores-system-def67890`          |

**Technical Note**: The integration uses UUIDs internally, which provide sufficient uniqueness in the first 8 characters. This truncation is transparent to users and prevents iOS notification errors.

### Example: Multiple Chore Notifications

When Zoë claims multiple chores, **each notification remains independent**:

1. Zoë claims "Make Bed" (chore1) → Tag: `kidschores-status-abc12345-def67890`
2. Zoë claims "Feed Dog" (chore2) → Tag: `kidschores-status-xyz78901-def67890`

**Result**: Parents see **both notifications** because each chore has a unique tag (different chore IDs in first 8 chars).

### Reminder Notifications

When parents press "Remind in 30 min":

- A new notification is scheduled with the **same tag** as the original chore
- After 30 minutes, the reminder **replaces** only that specific chore's notification
- Other chore notifications remain untouched

### Automatic Notification Clearing

When a chore or reward is approved/disapproved via the **dashboard** (not the notification button), the original notification is automatically cleared from parent devices. This prevents stale notifications with action buttons that no longer apply.

---

## Enabling & Disabling Notifications

### Per-Kid Notification Services

Each kid and parent can have their own notification service configured:

1. Go to **Integration → Configure → Manage Kid/Parent**
2. Edit kid or parent profile
3. Set **Notification Service** field to the HA Companion service (e.g., `notify.mobile_app_phone`)
4. Leave blank to disable notifications for that person

**Note**: A parent with no notification service configured will not receive chore approval requests or aggregated notifications.

### Per-Chore Reminder Control

Each chore has an individual notification setting:

1. Go to **Integration → Configure → Manage Chore**
2. Edit chore
3. Toggle **Send Reminders** setting:
   - **ON** (default) - Kid receives due-soon reminders
   - **OFF** - Kid does not receive reminders for this chore

This allows you to silence reminders for routine chores while keeping them for important ones.

---

## Language & Translation System

Notifications are sent in **each recipient's preferred language**, not the system language. The integration uses a custom translation architecture that supports:

- **Per-kid dashboard language** - Each kid can have their own language preference
- **Per-parent language** - Each parent can have their own language preference
- **Automatic fallback** - If a translation is missing, English is used

### How Language Selection Works

The integration maintains separate translation files for each language:

- `translations_custom/en_notifications.json` - English notification templates
- `translations_custom/es_notifications.json` - Spanish notification templates
- `translations_custom/nl_notifications.json` - Dutch notification templates
- _(Additional languages supported)_

**Key Features**:

- Parents and kids can use **different languages** - a Spanish-speaking parent can approve chores for an English-speaking kid
- Notification content (title, message, action buttons) are all translated
- Translation sensor entities (`sensor.kc_ui_dashboard_lang_{code}`) provide localized strings

For complete details on the translation architecture, see [ARCHITECTURE.md - Translation Architecture](https://github.com/ad-ha/kidschores-ha/blob/main/docs/ARCHITECTURE.md#translation-architecture).

---

## Mobile App Setup

To receive notifications, you must have the **Home Assistant Companion App** installed:

### iOS Setup

1. Install [Home Assistant Companion](https://apps.apple.com/app/home-assistant/id1099568401) from App Store
2. Log in to your Home Assistant instance
3. Enable notifications when prompted
4. Note your device's notification service name (e.g., `notify.mobile_app_iphone`)

### Android Setup

1. Install [Home Assistant Companion](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android) from Google Play
2. Log in to your Home Assistant instance
3. Enable notifications when prompted
4. Note your device's notification service name (e.g., `notify.mobile_app_phone`)

### Finding Your Service Name

1. Go to **Developer Tools → Services**
2. Search for services starting with `notify.mobile_app_`
3. Use this service name in kid/parent profiles

---

## Troubleshooting

### Not Receiving Notifications

**Check these settings:**

1. **Profile Level**: Kid/Parent has valid notification service configured?
2. **Mobile App**: Companion app installed and logged in?
3. **App Permissions**: Notification permissions granted to HA Companion app?
4. **Chore Level**: (For reminders) Chore has "Send Reminders" enabled?

### Notifications in Wrong Language

- Check kid/parent profile language setting
- Verify translation file exists for selected language
- Missing translations automatically fall back to English

### Action Buttons Not Working

- Ensure you're using Home Assistant Companion app (not browser notifications)
- Action buttons require HA Companion app v2021.6.0 or later
- Check Home Assistant logs for errors when pressing buttons

### iOS Error: "apns-collapse-id header must not exceed 64 bytes"

If you see this error in logs, you're running an older version (pre-v0.5.0). **Update to v0.5.0 or later** - the integration now automatically truncates notification tags to comply with Apple's limit.

### Notifications Not Clearing on iOS

If approved/disapproved notifications remain visible on parent devices after handling them via the dashboard:

- **Cause**: Configuration issue with notification service format
- **Solution**: Verify notification service is set correctly in parent profile (should be `notify.mobile_app_device_name`, not `notify.notify.mobile_app_device_name`)
- **Fixed in**: v0.5.0+ automatically handles both formats

### Testing Notifications

Test notifications by:

1. Having a kid claim a chore (parents should receive approval request)
2. Having a parent apply a bonus (kid should receive points notification)
3. Checking Home Assistant logs: `custom_components.kidschores.notification_helper`

---

## Technical Reference

- **Implementation**: [`notification_helper.py`](https://github.com/ad-ha/kidschores-ha/blob/main/custom_components/kidschores/notification_helper.py)
- **Action Handler**: [`notification_action_handler.py`](https://github.com/ad-ha/kidschores-ha/blob/main/custom_components/kidschores/notification_action_handler.py)
- **Translation System**: See [ARCHITECTURE.md - Translation Architecture](https://github.com/ad-ha/kidschores-ha/blob/main/docs/ARCHITECTURE.md#translation-architecture)
- **All 17 Events Documented**: See [NOTIFICATION_REFACTOR_IN-PROCESS.md](https://github.com/ad-ha/kidschores-ha/blob/main/docs/in-process/NOTIFICATION_REFACTOR_IN-PROCESS.md#notification-event-reference)

---

**Last Updated**: January 2026 (v0.5.0)
