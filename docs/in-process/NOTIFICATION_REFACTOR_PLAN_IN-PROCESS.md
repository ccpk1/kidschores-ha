# Notification Standardization & Refactor Plan

## Initiative snapshot

- **Name / Code**: Notification System Standardization (NOTIF-REFACTOR)
- **Target release / milestone**: KidsChores v4.3+
- **Owner / driver(s)**: Development Team / AI Agent
- **Status**: Not started (awaiting Phase 1 approval)

## Summary & immediate steps

| Phase / Step                          | Description                                                        | % complete | Quick notes                                           |
| ------------------------------------- | ------------------------------------------------------------------ | ---------- | ----------------------------------------------------- |
| Phase 1 – Constant Definition         | Define 31 notification constants in const.py + translation entries | 0%         | 18 titles + 13 messages identified                    |
| Phase 2 – Coordinator Updates         | Replace hardcoded strings with constants in coordinator.py         | 0%         | 24 notification calls to update                       |
| Phase 3 – Validation & Documentation  | Test all notification scenarios and update docs                    | 0%         | Must verify mobile + persistent notification delivery |

1. **Key objective** – Eliminate all hardcoded notification strings from coordinator.py (31 total violations) by implementing proper const.py-based constants with translation support, improving maintainability and enabling future multi-language support.

2. **Summary of recent work** – Comprehensive audit completed (Phase 0 Repeatable Audit Framework); identified 24 notification call sites with 100% hardcoded strings (18 unique titles + 13 unique messages).

3. **Next steps (short term)** – Define `TRANS_KEY_NOTIF_TITLE_*` and `TRANS_KEY_NOTIF_MESSAGE_*` constants in const.py, add corresponding entries to en.json, begin systematic replacement in coordinator.py notification calls.

4. **Risks / blockers** – Notification system integration complexity requires careful testing; message_data dictionary pattern needs consistent implementation; coordination with notification_helper.py may be required.

5. **References**
   - Code review findings: `docs/in-process/COORDINATOR_CODE_REVIEW.md` (Section 6b: Notification-Specific Audit)
   - Notification constants inventory: `docs/in-process/COORDINATOR_CODE_NOTIFICATION_CONSTANTS.md`
   - Code standards: `docs/CODE_REVIEW_GUIDE.md` (Phase 0 Step 6b)
   - Testing approach: `tests/TESTING_AGENT_INSTRUCTIONS.md`

6. **Decisions & completion check**
   - **Decisions captured**:
     * Use `TRANS_KEY_NOTIF_TITLE_*` and `TRANS_KEY_NOTIF_MESSAGE_*` naming convention
     * Convert f-strings to placeholder substitution with message_data dict
     * Maintain backward compatibility with existing notification behavior
     * Full testing required for both mobile and persistent notification paths
   - **Completion confirmation**: `[ ]` All follow-up items completed (constants defined, coordinator updated, translations added, testing verified, documentation updated) before requesting owner approval to mark initiative done.

## Tracking expectations

- **Summary upkeep**: Update percentages after completing each phase; track blocker resolution and test results.
- **Detailed tracking**: Phase-specific sections below contain detailed implementation steps, code snippets, and validation criteria.

---

## Detailed phase tracking

### Phase 1 – Constant Definition & Translation Setup

- **Goal**: Define all 31 notification constants in const.py and add corresponding translation entries to en.json
- **Steps / detailed work items**
  1. **Define notification title constants in const.py** (Status: Not started)
     - Add 18 `TRANS_KEY_NOTIF_TITLE_*` constants
     - Follow naming convention: `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED = "notification_title_chore_claimed"`
     - Constants needed:
       * `TRANS_KEY_NOTIF_TITLE_NEW_CHORE`
       * `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED`
       * `TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED`
       * `TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED`
       * `TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE`
       * `TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED`
       * `TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED`
       * `TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED`
       * `TRANS_KEY_NOTIF_TITLE_BADGE_EARNED`
       * `TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED`
       * `TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED`
       * `TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED`
       * `TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED`
       * `TRANS_KEY_NOTIF_TITLE_REMINDER_PENDING_CHORE`
       * `TRANS_KEY_NOTIF_TITLE_REMINDER_PENDING_REWARD`

  2. **Define notification message constants in const.py** (Status: Not started)
     - Add 13 `TRANS_KEY_NOTIF_MESSAGE_*` constants
     - Examples:
       * `TRANS_KEY_NOTIF_MESSAGE_NEW_CHORE = "notification_message_new_chore"`
       * `TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED = "notification_message_chore_claimed"`
       * `TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED = "notification_message_chore_approved"`

  3. **Add translation entries to en.json** (Status: Not started)
     - Add all 31 new translation entries under appropriate sections
     - Use placeholder substitution instead of f-strings: `"New chore '{chore_name}' assigned! Due: {due_date}"`
     - Ensure all placeholders match coordinator usage: `chore_name`, `kid_name`, `reward_name`, `points`, etc.

  4. **Validation** (Status: Not started)
     - Verify all constants follow naming convention
     - Confirm all en.json entries use proper placeholder syntax
     - Cross-check that no hardcoded strings remain in notification calls

- **Key issues**
  - Must coordinate constant naming with existing `TRANS_KEY_*` patterns in const.py
  - Placeholder names in en.json must match exactly with coordinator's message_data keys

### Phase 2 – Coordinator Notification Call Updates

- **Goal**: Replace all 24 hardcoded notification calls in coordinator.py with constant-based patterns
- **Steps / detailed work items**
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

  2. **Update `_notify_parents` calls** (10 instances) (Status: Not started)
     - Apply same transformation pattern as `_notify_kid`
     - Ensure actions array remains unchanged
     - Update extra_data if needed for consistency

  3. **Update notification helper if needed** (Status: Not started)
     - Review `notification_helper.py` to verify it supports message_data pattern
     - Add translation lookup if not already present
     - Ensure fallback to hardcoded strings if translation fails (defensive coding)

  4. **Systematic replacement** (Status: Not started)
     - Use multi_replace_string_in_file for efficient bulk changes
     - Replace in order: chore notifications → reward notifications → badge/achievement/challenge notifications → reminder notifications
     - Test notification delivery after each category

- **Key issues**
  - Notification helper may need updates to support translation lookup
  - Message_data pattern must be implemented consistently across all calls
  - Actions array structure must remain backward compatible

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
       * New chore assignment
       * Chore claim/approval/disapproval
       * Reward claim/approval/disapproval
       * Badge/achievement/challenge earned
       * Penalty/bonus applied
       * Overdue chore notifications
       * Reminder notifications (30-minute delay)

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

## Dependencies & Blockers

- **Requires**: Storage-only architecture (v4.2+) stable
- **Blocked by**: None currently
- **Blocks**: Multi-language support initiative (future)
- **Related to**: String literal constants standardization (Phase 2 of overall coordinator refactor)
