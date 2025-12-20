# Notification Refactor Plan - Quick Reference

**Status**: Ready for Phase 0 decision
**Target**: KidsChores v4.0 (schema v42)
**Estimated**: 32-42 hours

## Critical Decision Needed

**Choose Message Data Pattern** (see full plan for details):

### Option A: Coordinator Pre-formatting

- Translation happens before calling helper
- ❌ Repetitive across 24 call sites
- ✅ Helper stays generic

### Option B: Helper-Level Translation

- Helper does all translation
- ❌ Couples helper to KidsChores
- ✅ Cleaner coordinator

### Option C: Wrapper Method (RECOMMENDED)

- New `_notify_kid_translated()` method
- ✅ Helper stays generic
- ✅ Single extension point for future customization
- ✅ Clean call sites

## Implementation Summary

### Phase 0: Architecture Decision (2-4 hours)

- Choose message_data pattern (A, B, or C)
- Choose test mode approach (auto-detect recommended)
- Choose translation fallback strategy (hardcoded fallback recommended)

### Phase 1: Constants & Translations (8-10 hours)

- Add 15 title constants to const.py
- Add 16 message constants to const.py
- Add all 31 entries to en.json under "notifications" section
- Example: `TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED = "notification_title_chore_assigned"`

### Phase 2: Coordinator Updates (12-16 hours)

- Implement chosen pattern (wrapper method if Option C)
- Add test mode detection: `self._test_mode = "pytest" in sys.modules`
- Update 24 notification calls to use constants
- Convert f-strings to message_data dictionaries

### Phase 3: Testing & Docs (10-12 hours)

- Run linting: `./utils/quick_lint.sh --fix`
- Run tests: `python -m pytest tests/ -v --tb=line`
- Manual testing (mobile + persistent paths)
- Update documentation

## Key Design Decisions

1. **Translation System**: HomeAssistant native only (dashboard custom system out of scope)
2. **Extensibility**: Design supports future custom messages (v4.1+) but not implemented now
3. **Version**: v4.0 with schema v42 (no made-up versions)
4. **Fallback**: Return translation key or hardcoded fallback if lookup fails

## Example Transformation

### Before:

```python
await self._notify_kid(
    kid_id,
    title="KidsChores: New Chore",
    message=f"New chore '{new_name}' assigned! Due: {due_str}",
    extra_data=extra_data,
)
```

### After (if Option C chosen):

```python
await self._notify_kid_translated(
    kid_id=kid_id,
    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED,
    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED,
    message_data={"chore_name": new_name, "due_date": due_str},
    extra_data=extra_data,
)
```

## Future Extensibility Path

When adding custom messages in v4.1+, only modify `_notify_kid_translated()`:

```python
async def _notify_kid_translated(self, ...):
    # 1. Check storage for custom override
    custom_message = self._get_custom_template(kid_id, message_key)
    if custom_message:
        message = custom_message.format(**message_data)
    else:
        # 2. Standard translation (existing)
        message = self.hass.localize(f"component.kidschores.{message_key}", **message_data)
    ...
```

## Files Modified

- `custom_components/kidschores/const.py` - Add 31 constants
- `custom_components/kidschores/translations/en.json` - Add notification section
- `custom_components/kidschores/coordinator.py` - Update all notification calls
- `docs/CODE_REVIEW_GUIDE.md` - Document patterns
- `docs/ARCHITECTURE.md` - Update translation section

## Success Criteria

✅ Zero hardcoded notification strings
✅ All tests pass
✅ Mobile & persistent paths work
✅ Test mode reduces 30-min delays to 5 seconds
✅ Documentation updated
