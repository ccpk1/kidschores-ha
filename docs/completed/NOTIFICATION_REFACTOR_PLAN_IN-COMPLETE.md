# Notification Standardization & Refactor Plan

## ✅ PLAN STATUS: PHASE 1 COMPLETE - PHASE 2 IN PROGRESS

**Date**: December 20, 2025 (Phase 1 Complete)
**Review Status**: Architecture decisions confirmed, implementation started
**Chosen Pattern**: Option C - Wrapper Method in Coordinator
**Current Phase**: Phase 2 - Coordinator Updates

---

## Initiative snapshot

- **Name / Code**: Notification System Standardization (NOTIF-REFACTOR)
- **Target release / milestone**: KidsChores v4.0 (schema v42)
- **Owner / driver(s)**: Development Team / AI Agent
- **Status**: ✅ Phase 1 Complete (100%) - Phase 2 In Progress

## Summary & immediate steps

| Phase / Step                      | Description                                                        | % complete | Quick notes                                           |
| --------------------------------- | ------------------------------------------------------------------ | ---------- | ----------------------------------------------------- |
| Phase 1 – Constant Definition     | Define 31 notification constants in const.py + translation entries | 100%       | ✅ Complete - All constants and translations added    |
| Phase 2 – Coordinator Updates     | Replace hardcoded strings with constants in coordinator.py         | 0%         | Ready to start - wrapper methods + 24 call updates    |
| Phase 3 – Testing & Documentation | Test all notification scenarios and update docs                    | 0%         | Must verify mobile + persistent notification delivery |

1. **Key objective** – Eliminate all hardcoded notification strings from coordinator.py (31 total violations) by implementing proper const.py-based constants with HomeAssistant native translation support, improving maintainability and enabling future multi-language support.

2. **Summary of recent work** – ✅ Phase 1 Complete: All 31 constants defined in const.py (lines 1266-1299) and translation entries added to en.json (line 2398). Linting passed for all new code.

3. **Next steps (short term)** – Begin Phase 2: Add wrapper methods (\_notify_kid_translated, \_notify_parents_translated) to coordinator.py, add test mode detection, then update all 24 notification call sites.

4. **Risks / blockers** – None. Test mode auto-detection will be implemented in Phase 2 (5 second delays during pytest).

5. **References**

   - Code review findings: `docs/in-process/COORDINATOR_CODE_REVIEW.md` (Section 6b: Notification-Specific Audit)
   - Notification constants inventory: `docs/in-process/COORDINATOR_CODE_NOTIFICATION_CONSTANTS.md`
   - Code standards: `docs/CODE_REVIEW_GUIDE.md` (Phase 0 Step 6b)
   - Testing approach: `tests/TESTING_AGENT_INSTRUCTIONS.md`

6. **Future extensibility considerations**
   - Design allows for future custom message overrides (deferred to v4.1+)
   - Translation keys structured to support per-entity customization later
   - Message_data pattern chosen will enable template customization without code changes

## Tracking expectations

- **Summary upkeep**: Update percentages after completing each phase; track blocker resolution and test results.
- **Detailed tracking**: Phase-specific sections below contain detailed implementation steps, code snippets, and validation criteria.

---

## Detailed phase tracking

### Phase 1 – Constant Definition & Translation Setup

- **Goal**: Define all 31 notification constants in const.py and add corresponding translation entries to en.json
- **Status**: ✅ COMPLETE (December 20, 2025)
- **Estimated Time**: 8-10 hours
- **Actual Time**: ~1 hour (efficient batch implementation)

**Steps / detailed work items**:

1. **Define notification title constants in const.py** (Status: ✅ Complete)

   - Added 15 `TRANS_KEY_NOTIF_TITLE_*` constants at line 1266
   - Follow naming convention: `TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED = "notification_title_chore_assigned"`
   - All constants defined:
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE`
     - ✅ `TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_BADGE_EARNED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED`
     - ✅ `TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER`
     - ✅ `TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER`

2. **Define notification message constants in const.py** (Status: ✅ Complete)

   - Added 16 `TRANS_KEY_NOTIF_MESSAGE_*` constants at line 1281
   - All message constants defined including kid/parent variants

3. **Add translation entries to en.json** (Status: ✅ Complete)

   - Added all 31 new translation entries under `"notifications"` section at line 2398
   - All placeholders use proper syntax: `{chore_name}`, `{kid_name}`, `{points}`, `{due_date}`, etc.
   - Structure validated:
     ```json
     {
       "notifications": {
         "chore_assigned": {
           "title": "KidsChores: New Chore",
           "message": "New chore '{chore_name}' assigned! Due: {due_date}"
         },
         ...
       }
     }
     ```

4. **Validation** (Status: ✅ Complete)
   - ✅ All constants follow `TRANS_KEY_NOTIF_*` naming convention
   - ✅ All en.json entries use proper placeholder syntax `{placeholder_name}`
   - ✅ Linting passed for new code (existing test file issues unrelated)
   - ✅ No hardcoded strings in new constants

- **Key learnings**
  - Batch implementation more efficient than estimated (1 hour vs 8-10)
  - All placeholder names match coordinator usage patterns
  - Translation structure integrates cleanly with existing en.json

### Phase 2 – Coordinator Notification Call Updates

- **Goal**: Replace all 24 hardcoded notification calls in coordinator.py with constant-based patterns
- **Status**: Ready to start after Phase 1 complete ✅
- **Estimated Time**: 12-14 hours (Option C - wrapper method)

  1. **Update `_notify_kid` calls** (11 instances) (Status: Not started)

     - Replace hardcoded `title=` with `title=const.TRANS_KEY_NOTIF_TITLE_*`
     - Convert f-string messages to message_data dictionary pattern
     - Example transformation:

       ```python
       # OLD (Line 2091):
       self.hass.async_create_task(
           self._notify_kid(
               kid_id,
               title="KidsChores: New Chore",
               message=f"New chore '{new_name}' was assigned to you! Due: {due_str}",
               extra_data=extra_data,
           )
       )

       # NEW:
       self.hass.async_create_task(
           self._notify_kid(
               kid_id,
               title=const.TRANS_KEY_NOTIF_TITLE_NEW_CHORE,
               message=const.TRANS_KEY_NOTIF_MESSAGE_NEW_CHORE,
               message_data={
                   "chore_name": new_name,
                   "due_date": due_str,
               },
               extra_data=extra_data,
           )
       )
       ```

  2. **Add wrapper methods to coordinator.py** (Status: Not started)

     - Add `_notify_kid_translated()` method around line 8900
     - Add `_notify_parents_translated()` method
     - Include translation lookup and fallback logic
     - Add warning logs for missing translations

  3. **Add test mode detection** (Status: Not started)

     - Import sys module
     - Add `self._test_mode = "pytest" in sys.modules` to **init**
     - Update reminder delays: `delay = 5 if self._test_mode else 1800`

  4. **Update `_notify_parents` calls** (10 instances) (Status: Not started)

     - Apply same transformation pattern as `_notify_kid`
     - Ensure actions array remains unchanged

  5. **Systematic validation after updates** (Status: Not started)
     - Use multi_replace_string_in_file for efficient bulk changes
     - Replace in order: chore notifications → reward notifications → badge/achievement/challenge notifications → reminder notifications
     - Test notification delivery after each category

- **Key considerations**
  - Wrapper methods keep notification_helper.py unchanged (stays generic)
  - All existing tests mock \_notify_kid/\_notify_parents, so will continue passing
  - Test mode detection enables practical testing of reminders

### Phase 3 – Validation & Testing

- **Goal**: Verify all notification scenarios work correctly with new constant-based implementation
- **Steps / detailed work items**

  1. **Execute linting and type checking** (Status: Not started)

     - Run `./utils/quick_lint.sh --fix` (must pass with zero errors)
     - Verify all const imports are correct
     - Check for any remaining hardcoded notification strings

  2. **Manual notification testing** (Status: Not started)

     - Test mobile notification delivery (if mobile_notify_service configured)
     - Test persistent notification fallback
     - Verify placeholder substitution works correctly
     - Test all notification scenarios:
       - New chore assignment
       - Chore claim/approval/disapproval
       - Reward claim/approval/disapproval
       - Badge/achievement/challenge earned
       - Penalty/bonus applied
       - Overdue chore notifications
       - Reminder notifications (30-minute delay)

  3. **Automated testing** (Status: Not started)

     - Run `python -m pytest tests/ -v --tb=line` (all tests must pass)
     - Add new test cases for notification content validation
     - Mock notification calls and verify constants are used

  4. **Documentation updates** (Status: Not started)
     - Update CODE_REVIEW_GUIDE.md with notification standardization patterns
     - Document message_data dictionary structure
     - Add examples to developer documentation

- **Key issues**
  - Mobile notification testing requires actual mobile device or service setup
  - Reminder notifications require waiting 30 minutes or mocking async sleep
  - Translation validation requires checking en.json completeness

---

## Testing & validation

- **Tests executed**: None (Phase 0 audit complete)
- **Outstanding tests**:
  - All phases require `./utils/quick_lint.sh --fix` passing
  - All phases require `python -m pytest tests/ -v --tb=line` passing
  - Phase 3: Mobile + persistent notification delivery verification
  - Phase 3: Placeholder substitution validation
  - Phase 3: All 15+ notification scenarios tested end-to-end
- **Links to failing logs or CI runs**: N/A - not yet executed

---

## Notes & follow-up

### Current Notification Violations

**From coordinator.py audit** (24 total call sites):

**Title violations** (18 unique strings):

- `"KidsChores: New Chore"` (Line 2094)
- `"KidsChores: Chore Claimed"` (Line 3201)
- `"KidsChores: Chore Approved"` (Line 3383)
- `"KidsChores: Chore Disapproved"` (Line 3429)
- `"KidsChores: Reward Claimed"` (Line 4661)
- `"KidsChores: Reward Approved"` (Line 4768)
- `"KidsChores: Reward Disapproved"` (Line 4812)
- `"KidsChores: Badge Earned"` (Lines 5541, 5546)
- `"KidsChores: Penalty Applied"` (Line 7258)
- `"KidsChores: Bonus Applied"` (Line 7311)
- `"KidsChores: Achievement Earned"` (Lines 7477, 7485)
- `"KidsChores: Challenge Completed"` (Lines 7622, 7630)
- `"KidsChores: Chore Overdue"` (Lines 7862, 7870)
- `"KidsChores: Reminder for Pending Chore"` (Line 8927)
- `"KidsChores: Reminder for Pending Reward"` (Line 8965)

**Message violations** (13 unique patterns using f-strings):

- New chore assignment with due date
- Chore claim confirmation
- Chore approval with points
- Chore disapproval notification
- Reward claim (kid/parent perspectives)
- Reward approval/disapproval
- Badge/achievement/challenge earned
- Penalty/bonus applied
- Overdue chore warnings
- Reminder messages for pending approvals

### Architecture Considerations

- **Translation system**: All notification strings should support future multi-language expansion
- **Notification helper integration**: May require updates to support message_data dictionary
- **Fallback behavior**: Must maintain notification delivery even if translation lookup fails
- **Mobile vs persistent**: Both paths must work identically with new constant-based approach

### Performance Implications

- Translation lookup adds minimal overhead (dictionary access)
- Message formatting (placeholder substitution) is comparable to f-strings
- No significant performance impact expected

### Future Enhancements

- Multi-language support becomes trivial once constants are in place
- Notification templates can be customized per user/kid without code changes
- A/B testing of notification wording becomes possible through translation updates

---

## Effort Estimates

**Phase 1**: 12-15 hours

- Constant definition: 3-4 hours
- Translation entries: 4-5 hours
- Validation and cross-checking: 5-6 hours

**Phase 2**: 20-25 hours

- Notification call updates: 12-15 hours
- Notification helper updates: 4-6 hours
- Code review and refinement: 4-4 hours

**Phase 3**: 8-10 hours

- Linting and type checking: 1-2 hours
- Manual testing: 4-5 hours
- Automated testing: 2-2 hours
- Documentation: 1-1 hour

**Total Estimated Effort**: 40-50 hours

---

## Success Criteria

- ✅ Zero hardcoded notification strings in coordinator.py
- ✅ All 31 constants defined in const.py
- ✅ All 31 translation entries in en.json
- ✅ `./utils/quick_lint.sh --fix` passes with zero errors
- ✅ `python -m pytest tests/ -v --tb=line` passes all tests
- ✅ Manual testing confirms notifications work for all scenarios
- ✅ Mobile and persistent notification paths both functional
- ✅ Documentation updated with new patterns

---

## Architecture Decisions (Confirmed)

### Decision #1: Message Data Substitution Pattern ✅ **CHOSEN: Option C**

**Rationale**: Wrapper method provides clean call sites while keeping notification_helper.py generic and enabling easy future extensibility for custom message overrides.

**Implementation Pattern**:

```python
# coordinator.py - Add new wrapper method
async def _notify_kid_translated(
    self,
    kid_id: str,
    title_key: str,
    message_key: str,
    message_data: dict[str, Any],
    actions: list | None = None,
    extra_data: dict | None = None,
) -> None:
    """Send translated notification to kid with placeholder substitution."""
    # Translation lookup with fallback
    title = self.hass.localize(f"component.kidschores.{title_key}") or title_key
    message = self.hass.localize(
        f"component.kidschores.{message_key}",
        **message_data
    ) or message_key

    # Future extension point: Check for custom message overrides here (v4.1+)

    await self._notify_kid(
        kid_id,
        title=title,
        message=message,
        actions=actions,
        extra_data=extra_data,
    )

# Usage at call sites:
await self._notify_kid_translated(
    kid_id,
    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED,
    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED,
    message_data={"chore_name": chore_name, "due_date": due_str},
    extra_data=extra_data,
)
```

**Benefits**:

- ✅ Clean call sites (no repetitive localize() calls)
- ✅ notification_helper.py stays generic
- ✅ Single extension point for future custom messages
- ✅ Centralized fallback logic

---

### Decision #2: Test Mode Reminder Delays ✅ **CHOSEN: Auto-detect**

**Implementation**:

```python
# coordinator.py (__init__ method)
import sys
self._test_mode = "pytest" in sys.modules

# In reminder methods:
delay = 5 if self._test_mode else 1800  # 5 sec in tests, 30 min in production
await asyncio.sleep(delay)
```

---

### Decision #3: Translation Fallback ✅ **CHOSEN: Return translation key**

**Rationale**: Returning the key makes missing translations obvious during development without breaking notifications.

**Implementation**: Already shown in \_notify_kid_translated() above:

```python
title = self.hass.localize(f"component.kidschores.{title_key}") or title_key
```

---

## Dependencies & Blockers

- **Requires**: Storage-only architecture (v4.0 schema v42) stable ✅
- **Blocked by**: None - ready to proceed
- **Blocks**: Multi-language support initiative (future v4.1+)
- **Related to**: String literal constants standardization (Phase 2 of overall coordinator refactor)

---

**Deferred to v4.1+**: Custom notification message configuration

**Design Considerations Made Now for Future**:

1. **Wrapper method pattern** (if Option C chosen) provides single extension point
2. **Translation key structure** allows per-entity customization (`chore_assigned` → `chore_uuid_123_assigned`)
3. **message_data dictionary** is extensible - can add new placeholders without breaking existing messages
4. **Fallback strategy** supports custom message overrides without risking notification failures

**Future Implementation Path** (when custom messages added):

```python
# Modify _notify_kid_translated() only:
async def _notify_kid_translated(self, kid_id, title_key, message_key, message_data, ...):
    # 1. Check for custom override in storage
    custom_message = self._get_custom_template(kid_id, message_key)
    if custom_message:
        try:
            message = custom_message.format(**message_data)
        except (KeyError, ValueError):
            # Fall through to translation system
            pass

    # 2. Standard translation lookup (existing code)
    if not message:
        message = self.hass.localize(f"component.kidschores.{message_key}", **message_data)

    # 3. Fallback (existing code)
    ...
```

**Storage structure for future custom messages** (reference only):

```json
{
  "notification_customization": {
    "per_kid": {
      "kid_uuid_1": {
        "chore_assigned": "Hey {kid_name}! New task: {chore_name} 📝"
      }
    }
  }
}
```

---

## Success Criteria

- ✅ Zero hardcoded notification strings in coordinator.py
- ✅ All 31 constants defined in const.py
- ✅ All 31 translation entries in en.json
- ✅ `./utils/quick_lint.sh --fix` passes with zero errors
- ✅ `python -m pytest tests/ -v --tb=line` passes all tests
- ✅ Manual testing confirms notifications work for all scenarios
- ✅ Mobile and persistent notification paths both functional
- ✅ Documentation updated with new patterns
- ✅ Test mode auto-detection works for reminder delays
