# Phase 3c: Notification System Hardcoded Strings - Follow-Up Finding

**Date Identified**: December 19, 2025
**Priority**: Medium (for future phase)
**Status**: 🟡 **DEFERRED** - Document for later refactoring

---

## Executive Summary

After completing Phase 3b (translation placeholder remediation), a follow-up audit identified **20+ hardcoded notification strings** across the notification system. These were NOT caught by Phase 3 because they use a different pattern: direct string literals in `title=` and `message=` parameters rather than exception messages.

**Scope**: Notification title/message strings in `coordinator.py` notification calls

**Impact**: Medium - notifications still functional but not localized/translatable

---

## Problem Statement

### Current Pattern (Hardcoded)

```python
# ❌ CURRENT: Hardcoded notification strings
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title="KidsChores: Chore Approved",  # ❌ Hardcoded
        message=(
            f"Your chore '{chore_info[const.DATA_CHORE_NAME]}' was approved. "  # ❌ Hardcoded + f-string
            f"You earned {default_points} points plus multiplier."
        ),
        extra_data=extra_data,
    )
)
```

### Target Pattern (Standardized)

```python
# ✅ TARGET: Translated notification strings
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED,  # ✅ Constant
        message=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED,  # ✅ Constant with placeholders
        message_data={  # ✅ Separate data dict for substitution
            "chore_name": chore_info[const.DATA_CHORE_NAME],
            "points": default_points,
        },
        extra_data=extra_data,
    )
)
```

---

## Identified Locations

### Coordinator.py Notification Calls

**Total Occurrences**: 20+ hardcoded notification strings

#### Kid Notifications (\_notify_kid calls)

1. **Line 3257-3265**: Chore approved notification

   - Title: `"KidsChores: Chore Approved"` ❌
   - Message: f-string with chore name and points ❌

2. **Line 3297-3303**: Chore disapproved notification

   - Title: `"KidsChores: Chore Disapproved"` ❌
   - Message: f-string with chore name ❌

3. **Line 4624-4630**: Reward approved notification

   - Title: `"KidsChores: Reward Approved"` ❌
   - Message: f-string with reward name ❌

4. **Line 4665-4671**: Reward disapproved notification

   - Title: `"KidsChores: Reward Disapproved"` ❌
   - Message: f-string with reward name ❌

5. **Line 5394-5400**: Reward redemption notification (to kid)

   - Title: `"KidsChores: Reward Redeemed"` ❌
   - Message: f-string with reward name and cost ❌

6. **Line 7093-7100**: Penalty applied notification

   - Title: `"KidsChores: Penalty Applied"` ❌
   - Message: f-string with penalty name and points ❌

7. **Line 7140-7147**: Bonus applied notification

   - Title: `"KidsChores: Bonus Applied"` ❌
   - Message: f-string with bonus name and points ❌

8. **Line 7309-7316**: Chore due date set notification

   - Title: `"KidsChores: Chore Due Date Set"` ❌
   - Message: f-string with chore name and date ❌

9. **Line 7454-7461**: Chore due date skipped notification

   - Title: `"KidsChores: Chore Due Date Skipped"` ❌
   - Message: f-string with chore name ❌

10. **Line 7694-7701**: Badge earned notification
    - Title: `"KidsChores: Badge Earned"` ❌
    - Message: f-string with badge name ❌

#### Parent Notifications (\_notify_parents calls)

11. **Line 3081-3090**: Chore claimed notification

    - Title: `"KidsChores: Chore Claimed"` ❌
    - Message: f-string with kid name and chore name ❌

12. **Line 4523-4532**: Reward redemption notification (to parents)

    - Title: `"KidsChores: Reward Redeemed"` ❌
    - Message: f-string with kid name, reward name, cost ❌

13. **Line 5402-5411**: Reward redemption with insufficient points

    - Title: `"KidsChores: Reward Redemption Failed"` ❌
    - Message: f-string with kid name, reward name, points ❌

14. **Line 7317-7326**: Chore due date set (parent notification)

    - Title: `"KidsChores: Chore Due Date Set"` ❌
    - Message: f-string with kid name, chore name, date ❌

15. **Line 7462-7471**: Chore due date skipped (parent notification)

    - Title: `"KidsChores: Chore Due Date Skipped"` ❌
    - Message: f-string with kid name, chore name ❌

16. **Line 7702-7711**: Badge earned (parent notification)
    - Title: `"KidsChores: Badge Earned"` ❌
    - Message: f-string with kid name, badge name ❌

#### Reminder Notifications (async methods)

17. **Line 8726-8736**: Chore approval reminder

    - Title: `"KidsChores: Reminder - Chore Approval"` ❌
    - Message: f-string with kid name, chore name ❌

18. **Line 8764-8774**: Reward approval reminder
    - Title: `"KidsChores: Reminder - Reward Approval"` ❌
    - Message: f-string with kid name, reward name ❌

---

## Why This Wasn't Caught in Phase 3

### Phase 3 Focus

Phase 3 targeted **exception messages** using these patterns:

- `raise HomeAssistantError(f"...")`
- `raise ServiceValidationError(f"...")`
- Translation placeholders in error dictionaries

### Different Pattern in Notifications

Notifications use **direct function parameters**:

- `title="Hardcoded String"`
- `message=f"Hardcoded {variable} String"`
- NOT using exception raising patterns

### Grep Pattern Differences

```bash
# Phase 3 search pattern (caught exceptions):
grep -n 'raise.*Error.*f"' coordinator.py

# Would need this pattern for notifications:
grep -n 'title="[A-Z]' coordinator.py
grep -n 'message=.*f"' coordinator.py
```

---

## Required Refactoring Work

### Step 1: Define Notification Translation Constants

Add to `const.py` (~40 new constants):

```python
# Notification Titles
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED: Final = "chore_approved_title"
TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED: Final = "chore_disapproved_title"
TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED: Final = "chore_claimed_title"
TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED: Final = "reward_approved_title"
TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED: Final = "reward_disapproved_title"
TRANS_KEY_NOTIF_TITLE_REWARD_REDEEMED: Final = "reward_redeemed_title"
TRANS_KEY_NOTIF_TITLE_REWARD_FAILED: Final = "reward_failed_title"
TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED: Final = "penalty_applied_title"
TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED: Final = "bonus_applied_title"
TRANS_KEY_NOTIF_TITLE_DUE_DATE_SET: Final = "due_date_set_title"
TRANS_KEY_NOTIF_TITLE_DUE_DATE_SKIPPED: Final = "due_date_skipped_title"
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED: Final = "badge_earned_title"
TRANS_KEY_NOTIF_TITLE_REMINDER_CHORE: Final = "reminder_chore_title"
TRANS_KEY_NOTIF_TITLE_REMINDER_REWARD: Final = "reminder_reward_title"

# Notification Messages
TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED: Final = "chore_approved_message"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED: Final = "chore_disapproved_message"
TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED: Final = "chore_claimed_message"
# ... (20+ more message constants)
```

### Step 2: Update en.json Translations

Add translation entries with placeholders:

```json
{
  "notifications": {
    "chore_approved_title": "KidsChores: Chore Approved",
    "chore_approved_message": "Your chore '{chore_name}' was approved. You earned {points} points plus multiplier.",
    "chore_disapproved_title": "KidsChores: Chore Disapproved",
    "chore_disapproved_message": "Your chore '{chore_name}' was disapproved.",
    "chore_claimed_title": "KidsChores: Chore Claimed",
    "chore_claimed_message": "'{kid_name}' claimed chore '{chore_name}'",
    ...
  }
}
```

### Step 3: Modify Notification Helper

Update `notification_helper.py` to support translation keys:

```python
async def async_send_notification(
    hass: HomeAssistant,
    notify_service: str,
    title: str,  # Can now be translation key
    message: str,  # Can now be translation key
    message_data: Optional[dict[str, Any]] = None,  # For placeholder substitution
    actions: Optional[list[dict[str, str]]] = None,
    extra_data: Optional[dict[str, str]] = None,
    translate: bool = True,  # Flag to enable translation
) -> None:
    """Send notification with optional translation support."""

    if translate:
        # Look up translations and substitute placeholders
        title = _translate_string(hass, title)
        message = _translate_string(hass, message, message_data)

    # ... rest of notification logic
```

### Step 4: Update All Notification Calls

Replace 20+ notification calls in coordinator.py:

```python
# BEFORE:
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title="KidsChores: Chore Approved",
        message=f"Your chore '{chore_info[const.DATA_CHORE_NAME]}' was approved.",
    )
)

# AFTER:
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED,
        message=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED,
        message_data={
            "chore_name": chore_info[const.DATA_CHORE_NAME],
        },
    )
)
```

---

## Estimated Effort

- **Constants**: ~40 new translation constants in const.py
- **Translations**: ~40 entries in en.json
- **Helper Changes**: Modify notification_helper.py to support translation (1 function)
- **Notification Calls**: Update 20+ calls in coordinator.py
- **Testing**: Validate all notification scenarios still work

**Time Estimate**: 4-6 hours

---

## Why Defer to Later Phase

### Current Priority: Core Translation System

- Phase 3/3b focused on error messages (higher priority - user sees in UI immediately)
- Notifications are functional, just not translated
- No user-reported issues with current notification text

### Technical Dependencies

- Notification system refactor can be isolated
- Does NOT block other translation work
- Can be done after core error/validation translations complete

### Testing Complexity

- Requires testing with actual mobile devices/notification services
- Need to verify placeholder substitution works correctly
- More time-consuming to validate than exception messages

---

## Success Criteria (When Implemented)

- ✅ All notification titles use TRANS*KEY_NOTIF_TITLE*\* constants
- ✅ All notification messages use TRANS*KEY_NOTIF_MESSAGE*\* constants
- ✅ No f-strings in notification calls (use message_data dict instead)
- ✅ All translation entries exist in en.json
- ✅ Placeholder substitution works correctly
- ✅ All 510 tests still pass
- ✅ Lint score maintained (≥9.60/10)

---

## Next Steps

1. **Immediate**: Document this finding ✅ (this document)
2. **Phase 4**: Focus on validating current translation system (error messages)
3. **Phase 5**: Final validation and linting
4. **Phase 6** (future): Notification system refactor (schedule separately)

---

## Documentation Location

This finding is tracked in:

- `/docs/in-process/PHASE3C_NOTIFICATION_REFACTOR_FINDING.md` (this document)
- Reference added to CODE_REVIEW_GUIDE.md for future prevention

---

**Status**: 🟡 **DOCUMENTED FOR FUTURE WORK**
**Blocking**: ❌ No - does not block current standardization work
**Priority**: Medium - functional but not ideal
