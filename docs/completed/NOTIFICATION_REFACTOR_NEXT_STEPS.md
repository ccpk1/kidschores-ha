# Notification Refactor - Next Steps

**Status**: ✅ Architecture approved - ready for Phase 1 implementation
**Date**: December 20, 2025
**Pattern Chosen**: Option C - Wrapper Method in Coordinator

---

## 🎯 Immediate Action Items

### Phase 1: Constant Definition & Translation Setup (8-10 hours)

**Start immediately with:**

#### Step 1.1: Define Title Constants in const.py

Add these 15 constants after existing `TRANS_KEY_NOTIF_ACTION_*` constants (~line 1263):

```python
# Notification Title Translation Keys
TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED = "notification_title_chore_assigned"
TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED = "notification_title_chore_claimed"
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED = "notification_title_chore_approved"
TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED = "notification_title_chore_disapproved"
TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE = "notification_title_chore_overdue"
TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER = "notification_title_chore_reminder"

TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED = "notification_title_reward_claimed"
TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED = "notification_title_reward_approved"
TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED = "notification_title_reward_disapproved"
TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER = "notification_title_reward_reminder"

TRANS_KEY_NOTIF_TITLE_BADGE_EARNED = "notification_title_badge_earned"
TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED = "notification_title_achievement_earned"
TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED = "notification_title_challenge_completed"

TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED = "notification_title_penalty_applied"
TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED = "notification_title_bonus_applied"
```

#### Step 1.2: Define Message Constants in const.py

Add these 16 constants immediately after title constants:

```python
# Notification Message Translation Keys
TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED = "notification_message_chore_assigned"
TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED = "notification_message_chore_claimed"
TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED = "notification_message_chore_approved"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED = "notification_message_chore_disapproved"
TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE = "notification_message_chore_overdue"
TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER = "notification_message_chore_reminder"

TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_KID = "notification_message_reward_claimed_kid"
TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_PARENT = "notification_message_reward_claimed_parent"
TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED = "notification_message_reward_approved"
TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED = "notification_message_reward_disapproved"
TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER = "notification_message_reward_reminder"

TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_KID = "notification_message_badge_earned_kid"
TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_PARENT = "notification_message_badge_earned_parent"
TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_KID = "notification_message_achievement_earned_kid"
TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_PARENT = "notification_message_achievement_earned_parent"
TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_KID = "notification_message_challenge_completed_kid"
TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_PARENT = "notification_message_challenge_completed_parent"

TRANS_KEY_NOTIF_MESSAGE_PENALTY_APPLIED = "notification_message_penalty_applied"
TRANS_KEY_NOTIF_MESSAGE_BONUS_APPLIED = "notification_message_bonus_applied"
```

#### Step 1.3: Add Translation Entries to en.json

Add this section to `custom_components/kidschores/translations/en.json`:

```json
{
  "notifications": {
    "chore_assigned": {
      "title": "KidsChores: New Chore",
      "message": "New chore '{chore_name}' was assigned to you! Due: {due_date}"
    },
    "chore_claimed": {
      "title": "KidsChores: Chore Claimed",
      "message": "'{kid_name}' claimed chore '{chore_name}'"
    },
    "chore_approved": {
      "title": "KidsChores: Chore Approved",
      "message": "Chore '{chore_name}' approved! +{points} points"
    },
    "chore_disapproved": {
      "title": "KidsChores: Chore Disapproved",
      "message": "Chore '{chore_name}' was not approved"
    },
    "chore_overdue": {
      "title": "KidsChores: Chore Overdue",
      "message": "Chore '{chore_name}' is overdue! Due date was {due_date}"
    },
    "chore_reminder": {
      "title": "KidsChores: Reminder for Pending Chore",
      "message": "Reminder: Chore '{chore_name}' claimed by '{kid_name}' is waiting for approval"
    },

    "reward_claimed_kid": {
      "title": "KidsChores: Reward Claimed",
      "message": "You claimed reward '{reward_name}' for {points} points!"
    },
    "reward_claimed_parent": {
      "title": "KidsChores: Reward Claimed",
      "message": "'{kid_name}' claimed reward '{reward_name}' for {points} points"
    },
    "reward_approved": {
      "title": "KidsChores: Reward Approved",
      "message": "Reward '{reward_name}' approved!"
    },
    "reward_disapproved": {
      "title": "KidsChores: Reward Disapproved",
      "message": "Reward '{reward_name}' was not approved"
    },
    "reward_reminder": {
      "title": "KidsChores: Reminder for Pending Reward",
      "message": "Reminder: Reward '{reward_name}' claimed by '{kid_name}' is waiting for approval"
    },

    "badge_earned_kid": {
      "title": "KidsChores: Badge Earned",
      "message": "You earned the '{badge_name}' badge!"
    },
    "badge_earned_parent": {
      "title": "KidsChores: Badge Earned",
      "message": "'{kid_name}' earned the '{badge_name}' badge!"
    },

    "achievement_earned_kid": {
      "title": "KidsChores: Achievement Earned",
      "message": "You earned achievement '{achievement_name}'!"
    },
    "achievement_earned_parent": {
      "title": "KidsChores: Achievement Earned",
      "message": "'{kid_name}' earned achievement '{achievement_name}'!"
    },

    "challenge_completed_kid": {
      "title": "KidsChores: Challenge Completed",
      "message": "You completed challenge '{challenge_name}'!"
    },
    "challenge_completed_parent": {
      "title": "KidsChores: Challenge Completed",
      "message": "'{kid_name}' completed challenge '{challenge_name}'!"
    },

    "penalty_applied": {
      "title": "KidsChores: Penalty Applied",
      "message": "Penalty '{penalty_name}' applied: -{points} points"
    },
    "bonus_applied": {
      "title": "KidsChores: Bonus Applied",
      "message": "Bonus '{bonus_name}' applied: +{points} points"
    }
  }
}
```

#### Step 1.4: Validation Checklist

After completing Steps 1.1-1.3:

- [ ] Run `./utils/quick_lint.sh --fix` (must pass)
- [ ] Verify all 31 constants follow `TRANS_KEY_NOTIF_*` naming convention
- [ ] Confirm all JSON placeholders use `{placeholder_name}` syntax
- [ ] Check that placeholder names match coordinator usage (chore_name, kid_name, points, due_date, etc.)
- [ ] Commit Phase 1 changes before starting Phase 2

---

## Phase 2: Coordinator Updates (12-14 hours)

**Start after Phase 1 complete:**

### Step 2.1: Add Wrapper Method to Coordinator

Add this method to `coordinator.py` around line 8900 (after `_notify_parents`):

```python
async def _notify_kid_translated(
    self,
    kid_id: str,
    title_key: str,
    message_key: str,
    message_data: dict[str, Any],
    actions: list | None = None,
    extra_data: dict | None = None,
) -> None:
    """Send translated notification to kid with placeholder substitution.

    Args:
        kid_id: Internal ID of the kid to notify
        title_key: Translation key for notification title (from const.py)
        message_key: Translation key for notification message (from const.py)
        message_data: Dictionary of placeholder values for message formatting
        actions: Optional list of notification actions
        extra_data: Optional additional data for notification payload
    """
    # Translation lookup with fallback to key
    title = self.hass.localize(f"component.kidschores.{title_key}") or title_key
    message = self.hass.localize(
        f"component.kidschores.{message_key}",
        **message_data
    ) or message_key

    # Log warning if translation missing (key returned as-is)
    if title == title_key:
        LOGGER.warning("Missing notification title translation: %s", title_key)
    if message == message_key:
        LOGGER.warning("Missing notification message translation: %s", message_key)

    # Future extension point: Custom message overrides go here (v4.1+)

    await self._notify_kid(
        kid_id,
        title=title,
        message=message,
        actions=actions,
        extra_data=extra_data,
    )


async def _notify_parents_translated(
    self,
    title_key: str,
    message_key: str,
    message_data: dict[str, Any],
    actions: list | None = None,
    extra_data: dict | None = None,
) -> None:
    """Send translated notification to parents with placeholder substitution."""
    title = self.hass.localize(f"component.kidschores.{title_key}") or title_key
    message = self.hass.localize(
        f"component.kidschores.{message_key}",
        **message_data
    ) or message_key

    if title == title_key:
        LOGGER.warning("Missing notification title translation: %s", title_key)
    if message == message_key:
        LOGGER.warning("Missing notification message translation: %s", message_key)

    await self._notify_parents(
        title=title,
        message=message,
        actions=actions,
        extra_data=extra_data,
    )
```

### Step 2.2: Add Test Mode Detection

Add to `coordinator.py` `__init__` method (around line 130):

```python
import sys

# In __init__:
self._test_mode = "pytest" in sys.modules
LOGGER.debug("Coordinator initialized in %s mode", "TEST" if self._test_mode else "PRODUCTION")
```

### Step 2.3: Update Notification Calls

Transform all 24 notification calls. Example pattern:

**OLD (Line 2091):**

```python
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title="KidsChores: New Chore",
        message=f"New chore '{new_name}' was assigned to you! Due: {due_str}",
        extra_data=extra_data,
    )
)
```

**NEW:**

```python
self.hass.async_create_task(
    self._notify_kid_translated(
        kid_id,
        title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED,
        message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED,
        message_data={
            "chore_name": new_name,
            "due_date": due_str,
        },
        extra_data=extra_data,
    )
)
```

**Locations to update** (see NOTIFICATION_REFACTOR_PLAN_IN-PROCESS.md Phase 2 for complete list):

- Lines 2091-2097: New chore assignment
- Lines 3201-3206: Chore claimed
- Lines 3383-3390: Chore approved
- Lines 3429-3433: Chore disapproved
- Lines 4661-4666, 4669-4674: Reward claimed (kid + parent)
- Lines 4768-4773: Reward approved
- Lines 4812-4816: Reward disapproved
- Lines 5541-5545, 5549-5553: Badge earned (kid + parent)
- Lines 7258-7262: Penalty applied
- Lines 7311-7315: Bonus applied
- Lines 7480-7484, 7488-7492: Achievement earned (kid + parent)
- Lines 7625-7629, 7633-7637: Challenge completed (kid + parent)
- Lines 7865-7869, 7873-7877: Chore overdue (kid + parent)
- Lines 8927-8931: Chore reminder (parents)
- Lines 8965-8969: Reward reminder (parents)

### Step 2.4: Update Reminder Delays

In reminder methods (lines 8920-8970), change:

**OLD:**

```python
await asyncio.sleep(1800)  # 30 minutes
```

**NEW:**

```python
delay = 5 if self._test_mode else 1800  # 5 sec in tests, 30 min in production
LOGGER.debug("Reminder delay: %d seconds (%s mode)", delay, "TEST" if self._test_mode else "PRODUCTION")
await asyncio.sleep(delay)
```

---

## Phase 3: Testing & Documentation (10-12 hours)

### Step 3.1: Linting & Type Checking

```bash
./utils/quick_lint.sh --fix
```

Must pass with zero errors.

### Step 3.2: Automated Tests

```bash
python -m pytest tests/ -v --tb=line
```

All tests must pass.

### Step 3.3: Manual Testing

Test each notification scenario:

- [ ] New chore assignment
- [ ] Chore claim/approve/disapprove
- [ ] Reward claim/approve/disapprove
- [ ] Badge/achievement/challenge earned
- [ ] Penalty/bonus applied
- [ ] Overdue chore notifications
- [ ] Reminder notifications (verify 5 sec delay in tests)
- [ ] Verify mobile + persistent notification paths

### Step 3.4: Documentation Updates

Update these files:

- [ ] `docs/ARCHITECTURE.md` - Add notification translation section
- [ ] `docs/CODE_REVIEW_GUIDE.md` - Update Phase 0 Step 6b with new pattern
- [ ] Commit final changes with comprehensive commit message

---

## Success Criteria Checklist

- [ ] All 31 constants defined in const.py
- [ ] All 31 translations in en.json
- [ ] All 24 notification calls updated
- [ ] Test mode auto-detection working
- [ ] `./utils/quick_lint.sh --fix` passes
- [ ] `python -m pytest tests/ -v --tb=line` passes
- [ ] Manual testing confirms notifications work
- [ ] Documentation updated
- [ ] No hardcoded notification strings remain

---

## Estimated Timeline

- **Phase 1**: 8-10 hours
- **Phase 2**: 12-14 hours
- **Phase 3**: 10-12 hours
- **Total**: 30-36 hours

---

## Questions or Issues?

Reference these documents:

- Main plan: `NOTIFICATION_REFACTOR_PLAN_IN-PROCESS.md`
- Quick reference: `NOTIFICATION_REFACTOR_QUICKREF.md`
- Code standards: `CODE_REVIEW_GUIDE.md`
- Testing instructions: `tests/TESTING_AGENT_INSTRUCTIONS.md`
