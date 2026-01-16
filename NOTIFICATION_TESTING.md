# Notification Testing Guide for KidsChores Development

## Quick Start: Enable Notification Testing

### Option 1: Use Persistent Notifications (Easiest)

Persistent notifications appear in the Home Assistant UI and don't require any mobile app setup.

**Step 1: Configure a Kid/Parent with Persistent Notifications**

In the KidsChores Options Flow:

1. Go to **Settings** → **Devices & Services** → **KidsChores**
2. Click **Configure**
3. Edit a kid or parent
4. Set **Mobile Notify Service** to: `persistent_notification`
5. Save

**Step 2: Test Notifications**

Trigger any chore action (claim, approve, etc.) and check:

- **Notifications Panel** (bell icon in top right of HA UI)
- **Developer Tools** → **Logs** (search for "Notification sent")

---

### Option 2: View Debug Logs (Always Available)

Enable debug logging to see all notification attempts in the Home Assistant logs.

**Step 1: Add Logger Configuration**

Edit `/workspaces/core/config/configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    homeassistant.components.cloud: debug
    custom_components.kidschores: debug # Add this line
    custom_components.kidschores.notification_helper: debug # Extra detail
```

**Step 2: Restart Home Assistant**

**Step 3: Watch Logs in Real-Time**

```bash
tail -f /workspaces/core/config/home-assistant.log | grep -i "notification\|notify"
```

Or view in UI: **Developer Tools** → **Logs**

---

## Testing Different Notification Scenarios

### 1. Test Chore Claim Notification

1. **Enable notification** on a chore:
   - Options Flow → Edit Chore → Enable "Notify on Claim"
2. **Set parent notify service**: `persistent_notification`
3. **Claim the chore** as the kid
4. **Check**: Parent should get notification about claim

### 2. Test Chore Approval Notification

1. **Enable notification** on a chore:
   - Options Flow → Edit Chore → Enable "Notify on Approval"
2. **Set kid notify service**: `persistent_notification`
3. **Claim** the chore as kid
4. **Approve** the chore as parent
5. **Check**: Kid should get notification about approval

### 3. Test Reward Claim Notification

1. **Set kid notify service**: `persistent_notification`
2. **Give kid enough points**
3. **Claim a reward**
4. **Approve the reward** as parent
5. **Check**: Kid should get notification about reward approval

### 4. Test Due Date Reminders

1. **Set kid notify service**: `persistent_notification`
2. **Create a chore** with a due date 1-2 days in the future
3. **Wait for coordinator refresh** (or trigger manually)
4. **Check**: Kid should get "due soon" reminder

---

## Debugging Notification Issues

### Check Service Availability

In Developer Tools → Services, search for `notify.` and see what's available:

- `persistent_notification.create` - Always available
- `notify.mobile_app_*` - Only if mobile app configured
- `notify.test_file` - Only if configured above

### Verify Notification Settings

Check what notify service is configured:

**Developer Tools → States** → Search for:

- `sensor.kc_<kid_name>_profile` → Look at `mobile_notify_service` attribute
- `sensor.kc_<parent_name>_profile` → Look at `mobile_notify_service` attribute

### Common Issues

| Issue                     | Solution                                                  |
| ------------------------- | --------------------------------------------------------- |
| No notifications appear   | Check notify service is set (not blank/None)              |
| Service not found warning | Configure notify service or use `persistent_notification` |
| Notifications not sent    | Check chore has notification toggles enabled              |
| Can't see notifications   | Check Notifications panel (bell icon) in HA UI            |

---

## Advanced: Create Test Notification Button

Create a button to manually trigger test notifications.

**Add to `/workspaces/core/config/configuration.yaml`:**

```yaml
input_button:
  test_kidschores_notification:
    name: Test KidsChores Notification
    icon: mdi:bell-ring

automation:
  - alias: Test KidsChores Notification
    trigger:
      - platform: state
        entity_id: input_button.test_kidschores_notification
    action:
      - service: persistent_notification.create
        data:
          title: "KidsChores Test Notification"
          message: "This is a test notification from KidsChores integration"
          notification_id: "kidschores_test"
```

---

## Monitoring Notification Flow

### 1. Watch Coordinator Logs

```bash
# In one terminal
tail -f /workspaces/core/config/home-assistant.log | grep "coordinator.py"
```

### 2. Watch Notification Helper Logs

```bash
# In another terminal
tail -f /workspaces/core/config/home-assistant.log | grep "notification_helper"
```

### 3. Search for Specific Patterns

```bash
# See all notification payloads
grep "DEBUG: Notification payload" /workspaces/core/config/home-assistant.log

# See all notification sends
grep "DEBUG: Notification sent" /workspaces/core/config/home-assistant.log

# See missing service warnings
grep "not available - skipping notification" /workspaces/core/config/home-assistant.log
```

---

## Expected Log Output

When notifications work correctly, you should see:

```
2026-01-16 12:34:56 DEBUG (MainThread) [custom_components.kidschores.notification_helper]
DEBUG: Notification payload for 'persistent_notification.create':
title='Chore Claimed!', message='Sarah claimed "Clean Room"', actions=[...]

2026-01-16 12:34:56 DEBUG (MainThread) [custom_components.kidschores.notification_helper]
DEBUG: Notification sent via 'persistent_notification.create'
```

When service is missing, you'll see:

```
2026-01-16 12:34:56 WARNING (MainThread) [custom_components.kidschores.notification_helper]
Notification service 'notify.mobile_app_phone' not available - skipping notification.
```

---

## Quick Test Script

Run this in **Developer Tools → Services**:

```yaml
service: persistent_notification.create
data:
  title: "KidsChores Notification Test"
  message: "If you see this, notifications are working!"
  notification_id: "kidschores_manual_test"
```

If this works, your notification system is operational. The issue is likely the notify service configuration in KidsChores.

---

## Next Steps

After confirming notifications work:

1. **Production Setup**: Configure mobile app and use `notify.mobile_app_<device>`
2. **Testing Setup**: Use `persistent_notification` or file notify
3. **CI/CD Setup**: Mock the notify service in tests (already done in KidsChores)

For more details, see:

- `custom_components/kidschores/notification_helper.py` - Implementation
- `tests/test_notification_*.py` - Test patterns
