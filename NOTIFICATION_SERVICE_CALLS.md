# KidsChores Notification Testing - Service Call Examples

## Quick Test in Home Assistant UI

Go to **Developer Tools** → **Services** and run these test service calls:

---

## 1. Test Basic Persistent Notification

**Service:** `persistent_notification.create`

```yaml
title: "KidsChores Test"
message: "If you see this, persistent notifications work!"
notification_id: "kidschores_test_basic"
```

**Expected Result:** Notification appears in the bell icon (top right)

---

## 2. Configure Kid/Parent to Use Notifications

### Option A: Via UI (Recommended)

1. **Settings** → **Devices & Services** → **KidsChores**
2. Click **Configure** on the KidsChores integration
3. Click **Kids**
4. Select a kid
5. Set **Mobile Notify Service** to one of:
   - `persistent_notification` (shows in UI - **recommended for development**)
   - `notify.mobile_app_<device>` (production)
6. Save

### Option B: Via Storage File (Advanced)

Edit: `/workspaces/core/config/.storage/kidschores_data`

Find your kid's section and add:

```json
{
  "internal_id": "your-kid-id",
  "name": "TestKid",
  "mobile_notify_service": "persistent_notification",
  ...
}
```

Then restart Home Assistant.

---

## 4. Trigger Real Notifications

Once a kid/parent has a notify service configured:

### Test Chore Claim Notification (to parent)

1. Configure parent with `persistent_notification`
2. Enable **Notify on Claim** for a chore (Options Flow → Chores → Edit Chore)
3. Claim the chore using the kid's claim button
4. Check notification bell icon

### Test Chore Approval Notification (to kid)

1. Configure kid with `persistent_notification`
2. Enable **Notify on Approval** for a chore
3. Claim chore as kid
4. Approve chore as parent
5. Check notification bell icon

### Test Reward Notification

1. Configure kid with `persistent_notification`
2. Give kid enough points
3. Claim a reward
4. Approve the reward claim
5. Check notification bell icon

---

## 5. Monitor Notification Logs

### Watch Logs in Real-Time

```bash
# Option 1: Full notification logs
tail -f /workspaces/core/config/home-assistant.log | grep -i "notification"

# Option 2: Just KidsChores notifications
tail -f /workspaces/core/config/home-assistant.log | grep "kidschores.*notification"

# Option 3: Use the testing utility
/workspaces/kidschores-ha/utils/test_notifications.sh
```

### Search Past Logs

```bash
# See all notification attempts
grep "Notification payload" /workspaces/core/config/home-assistant.log

# See successful sends
grep "Notification sent via" /workspaces/core/config/home-assistant.log

# See service availability warnings
grep "not available - skipping notification" /workspaces/core/config/home-assistant.log
```

---

## Expected Log Output

### Successful Notification

```
2026-01-16 12:34:56 DEBUG (MainThread) [custom_components.kidschores.notification_helper]
DEBUG: Notification payload for 'persistent_notification.create':
title='Chore Approved!', message='Your chore "Clean Room" was approved!', actions=[]

2026-01-16 12:34:56 DEBUG (MainThread) [custom_components.kidschores.notification_helper]
DEBUG: Notification sent via 'persistent_notification.create'
```

### Missing Service (Expected During Setup)

```
2026-01-16 12:34:56 WARNING (MainThread) [custom_components.kidschores.notification_helper]
Notification service 'notify.mobile_app_phone' not available - skipping notification.
This is normal during migration or if the mobile app/notification integration isn't configured yet.
```

---

## Troubleshooting Checklist

- [ ] Home Assistant is running
- [ ] Debug logging enabled in `configuration.yaml`
- [ ] Kid/Parent has `mobile_notify_service` configured
- [ ] Notification service exists (check Developer Tools → Services)
  - `persistent_notification.create` is always available
  - `notify.mobile_app_*` requires mobile app setup
- [ ] Chore has notification toggles enabled (notify_on_claim, notify_on_approval, etc.)
- [ ] Logs show notification attempts (no errors)
- [ ] For persistent_notification: Check bell icon in HA UI
- [ ] For file notifications: Check `/workspaces/core/config/notifications.txt`

---

## Quick Reference Commands

```bash
# Start notification test utility
/workspaces/kidschores-ha/utils/test_notifications.sh

# Watch logs
tail -f /workspaces/core/config/home-assistant.log | grep notification

# Check file notifications
cat /workspaces/core/config/notifications.txt

# Clear file notifications
> /workspaces/core/config/notifications.txt

# Restart Home Assistant (after config changes)
# Use "Restart Home Assistant" in UI or restart the task
```

---

## Next Steps

1. ✅ **Enable debug logging** (already done in your configuration.yaml)
2. ⏳ **Restart Home Assistant** to apply changes
3. ⏳ **Configure a test kid** with `persistent_notification`
4. ⏳ **Trigger a chore action** and watch logs
5. ⏳ **Check notification appeared** in UI (bell icon)

---

## Production Setup

For actual production use with mobile devices:

1. Install **Home Assistant Companion App** on mobile device
2. Device will register as `notify.mobile_app_<device_name>`
3. Configure kids/parents to use that service
4. Notifications will appear on their mobile device

For development/testing, `persistent_notification` is perfect!
