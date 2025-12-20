# KidsChores Coordinator.py - Notification Constants Inventory

**File**: Supporting document for coordinator.py code standardization  
**Phase**: 1 - Notification Constants Standardization  
**Date**: December 19, 2025  

## Notification Titles Requiring Constants

| Line | Current Hardcoded String | Proposed Constant | Translation Key |
|------|-------------------------|-------------------|----------------|
| 2094 | `"KidsChores: New Chore"` | `TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED` | `"notification_title_chore_assigned"` |
| 3201 | `"KidsChores: Chore Claimed"` | `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED` | `"notification_title_chore_claimed"` |
| 3383 | `"KidsChores: Chore Approved"` | `TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED` | `"notification_title_chore_approved"` |
| 3429 | `"KidsChores: Chore Disapproved"` | `TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED` | `"notification_title_chore_disapproved"` |
| 4661 | `"KidsChores: Reward Claimed"` | `TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED` | `"notification_title_reward_claimed"` |
| 4768 | `"KidsChores: Reward Approved"` | `TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED` | `"notification_title_reward_approved"` |
| 4812 | `"KidsChores: Reward Disapproved"` | `TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED` | `"notification_title_reward_disapproved"` |
| 5541 | `"KidsChores: Badge Earned"` | `TRANS_KEY_NOTIF_TITLE_BADGE_EARNED` | `"notification_title_badge_earned"` |
| 7258 | `"KidsChores: Penalty Applied"` | `TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED` | `"notification_title_penalty_applied"` |
| 7311 | `"KidsChores: Bonus Applied"` | `TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED` | `"notification_title_bonus_applied"` |
| 7480 | `"KidsChores: Achievement Earned"` | `TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED` | `"notification_title_achievement_earned"` |
| 7625 | `"KidsChores: Challenge Completed"` | `TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED` | `"notification_title_challenge_completed"` |
| 7865 | `"KidsChores: Chore Overdue"` | `TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE` | `"notification_title_chore_overdue"` |
| 8927 | `"KidsChores: Reminder for Pending Chore"` | `TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER` | `"notification_title_chore_reminder"` |
| 8965 | `"KidsChores: Reminder for Pending Reward"` | `TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER` | `"notification_title_reward_reminder"` |

**Total Title Constants**: 15 unique constants (some used multiple times)

## Notification Messages Requiring Constants

| Line | Current F-String Pattern | Proposed Constant | Translation Key |
|------|---------------------------|-------------------|----------------|
| 2095 | `f"New chore '{new_name}' was assigned to you! Due: {due_str}"` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED` | `"notification_message_chore_assigned"` |
| 3202-3204 | `f"'{self.kids_data[kid_id][const.DATA_KID_NAME]}' claimed chore '{self.chores_data[chore_id][const.DATA_CHORE_NAME]}'"` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED` | `"notification_message_chore_claimed"` |
| 3384-3386 | `f"Your chore '{chore_info[const.DATA_CHORE_NAME]}' was approved. You earned {default_points} points plus multiplier."` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED` | `"notification_message_chore_approved"` |
| 3430 | `f"Your chore '{chore_info[const.DATA_CHORE_NAME]}' was disapproved."` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED` | `"notification_message_chore_disapproved"` |
| 4662 | `f"'{kid_info[const.DATA_KID_NAME]}' claimed reward '{reward_info[const.DATA_REWARD_NAME]}'"` | `TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED` | `"notification_message_reward_claimed"` |
| 4769 | `f"Your reward '{reward_info[const.DATA_REWARD_NAME]}' was approved."` | `TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED` | `"notification_message_reward_approved"` |
| 4813 | `f"Your reward '{reward_info[const.DATA_REWARD_NAME]}' was disapproved."` | `TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED` | `"notification_message_reward_disapproved"` |
| 5542 | `f"You earned a new badge: '{badge_name}'!"` | `TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_KID` | `"notification_message_badge_earned_kid"` |
| 5550 | `f"'{self.kids_data[kid_id][const.DATA_KID_NAME]}' earned a new badge: '{badge_name}'!"` | `TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_PARENT` | `"notification_message_badge_earned_parent"` |
| 7259 | `f"A '{penalty_info[const.DATA_PENALTY_NAME]}' penalty was applied. Your points changed by {penalty_pts}."` | `TRANS_KEY_NOTIF_MESSAGE_PENALTY_APPLIED` | `"notification_message_penalty_applied"` |
| 7312 | `f"A '{bonus_info[const.DATA_BONUS_NAME]}' bonus was applied. Your points changed by {bonus_pts}."` | `TRANS_KEY_NOTIF_MESSAGE_BONUS_APPLIED` | `"notification_message_bonus_applied"` |
| 7481 | `f"You have earned the achievement: '{achievement_info.get(const.DATA_ACHIEVEMENT_NAME)}'."` | `TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_KID` | `"notification_message_achievement_earned_kid"` |
| 7489 | `f"{self.kids_data[kid_id][const.DATA_KID_NAME]} has earned the achievement: '{achievement_info.get(const.DATA_ACHIEVEMENT_NAME)}'."` | `TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_PARENT` | `"notification_message_achievement_earned_parent"` |
| 7626 | `f"You have completed the challenge: '{challenge_info.get(const.DATA_CHALLENGE_NAME)}'."` | `TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_KID` | `"notification_message_challenge_completed_kid"` |
| 7634 | `f"{self.kids_data[kid_id][const.DATA_KID_NAME]} has completed the challenge: '{challenge_info.get(const.DATA_CHALLENGE_NAME)}'."` | `TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_PARENT` | `"notification_message_challenge_completed_parent"` |
| 7866 | `f"Your chore '{chore_info.get('name', 'Unnamed Chore')}' is overdue"` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_KID` | `"notification_message_chore_overdue_kid"` |
| 7874 | `f"{kh.get_kid_name_by_id(self, kid_id)}'s chore '{chore_info.get('name', 'Unnamed Chore')}' is overdue"` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_PARENT` | `"notification_message_chore_overdue_parent"` |
| 8928 | `f"Reminder: {kid_info.get(const.DATA_KID_NAME, 'A kid')} has '{chore_info.get(const.DATA_CHORE_NAME, 'Unnamed Chore')}' chore pending approval."` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER` | `"notification_message_chore_reminder"` |
| 8966 | `f"Reminder: {kid_info.get(const.DATA_KID_NAME, 'A kid')} has '{reward_name}' reward pending approval."` | `TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER` | `"notification_message_reward_reminder"` |

**Total Message Constants**: 19 unique constants

## Implementation Pattern

### Old Pattern (❌ Current)
```python
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title="KidsChores: Chore Approved",
        message=f"Your chore '{chore_info[const.DATA_CHORE_NAME]}' was approved. You earned {default_points} points plus multiplier.",
        extra_data=extra_data,
    )
)
```

### New Pattern (✅ Target)
```python
self.hass.async_create_task(
    self._notify_kid(
        kid_id,
        title=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED,
        message=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED,
        message_data={
            "chore_name": chore_info[const.DATA_CHORE_NAME],
            "points": default_points
        },
        extra_data=extra_data,
    )
)
```

## Required en.json Entries

```json
{
  "notifications": {
    "titles": {
      "notification_title_chore_assigned": "KidsChores: New Chore",
      "notification_title_chore_claimed": "KidsChores: Chore Claimed",
      "notification_title_chore_approved": "KidsChores: Chore Approved",
      "notification_title_chore_disapproved": "KidsChores: Chore Disapproved",
      "notification_title_reward_claimed": "KidsChores: Reward Claimed",
      "notification_title_reward_approved": "KidsChores: Reward Approved",
      "notification_title_reward_disapproved": "KidsChores: Reward Disapproved",
      "notification_title_badge_earned": "KidsChores: Badge Earned",
      "notification_title_penalty_applied": "KidsChores: Penalty Applied",
      "notification_title_bonus_applied": "KidsChores: Bonus Applied",
      "notification_title_achievement_earned": "KidsChores: Achievement Earned",
      "notification_title_challenge_completed": "KidsChores: Challenge Completed",
      "notification_title_chore_overdue": "KidsChores: Chore Overdue",
      "notification_title_chore_reminder": "KidsChores: Reminder for Pending Chore",
      "notification_title_reward_reminder": "KidsChores: Reminder for Pending Reward"
    },
    "messages": {
      "notification_message_chore_assigned": "New chore '{chore_name}' was assigned to you! Due: {due_date}",
      "notification_message_chore_claimed": "'{kid_name}' claimed chore '{chore_name}'",
      "notification_message_chore_approved": "Your chore '{chore_name}' was approved. You earned {points} points plus multiplier.",
      "notification_message_chore_disapproved": "Your chore '{chore_name}' was disapproved.",
      "notification_message_reward_claimed": "'{kid_name}' claimed reward '{reward_name}'",
      "notification_message_reward_approved": "Your reward '{reward_name}' was approved.",
      "notification_message_reward_disapproved": "Your reward '{reward_name}' was disapproved.",
      "notification_message_badge_earned_kid": "You earned a new badge: '{badge_name}'!",
      "notification_message_badge_earned_parent": "'{kid_name}' earned a new badge: '{badge_name}'!",
      "notification_message_penalty_applied": "A '{penalty_name}' penalty was applied. Your points changed by {points}.",
      "notification_message_bonus_applied": "A '{bonus_name}' bonus was applied. Your points changed by {points}.",
      "notification_message_achievement_earned_kid": "You have earned the achievement: '{achievement_name}'.",
      "notification_message_achievement_earned_parent": "'{kid_name}' has earned the achievement: '{achievement_name}'.",
      "notification_message_challenge_completed_kid": "You have completed the challenge: '{challenge_name}'.",
      "notification_message_challenge_completed_parent": "'{kid_name}' has completed the challenge: '{challenge_name}'.",
      "notification_message_chore_overdue_kid": "Your chore '{chore_name}' is overdue",
      "notification_message_chore_overdue_parent": "'{kid_name}'s chore '{chore_name}' is overdue",
      "notification_message_chore_reminder": "Reminder: '{kid_name}' has '{chore_name}' chore pending approval.",
      "notification_message_reward_reminder": "Reminder: '{kid_name}' has '{reward_name}' reward pending approval."
    }
  }
}
```

## Summary

- **Total Constants Required**: 34 (15 titles + 19 messages)
- **Total Lines to Modify**: 24 notification function calls
- **Translation Entries**: 34 new entries in en.json
- **Estimated Effort**: 40-50 hours (including testing)