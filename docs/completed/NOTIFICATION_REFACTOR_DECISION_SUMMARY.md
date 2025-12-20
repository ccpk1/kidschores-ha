# Notification Refactor - Decision Summary

**Date**: December 20, 2025
**Status**: ✅ All architectural decisions confirmed

---

## Decisions Made

### ✅ Decision #1: Message Data Substitution Pattern

**CHOSEN**: **Option C - Wrapper Method in Coordinator**

**Why**: Best balance of clean call sites, generic helper reusability, and future extensibility.

**Implementation**: Two new wrapper methods in coordinator.py:

- `_notify_kid_translated()` - Handles translation lookup + placeholder substitution + calls existing `_notify_kid()`
- `_notify_parents_translated()` - Same pattern for parent notifications

**Key Benefit**: Single extension point for future custom message overrides (v4.1+) without changing 24 call sites.

---

### ✅ Decision #2: Test Mode Reminder Delays

**CHOSEN**: **Auto-detect pytest environment**

**Implementation**:

```python
# coordinator.py __init__
import sys
self._test_mode = "pytest" in sys.modules

# In reminder methods
delay = 5 if self._test_mode else 1800  # 5 sec vs 30 min
```

**Why**: No user configuration needed, automatic, simple. Makes testing practical.

---

### ✅ Decision #3: Translation Fallback Strategy

**CHOSEN**: **Return translation key + log warning**

**Implementation**:

```python
title = self.hass.localize(f"component.kidschores.{title_key}") or title_key
if title == title_key:
    LOGGER.warning("Missing notification title translation: %s", title_key)
```

**Why**: Makes missing translations obvious during development without breaking notifications in production.

---

## What This Enables

### Immediate Benefits (v4.0)

- ✅ Zero hardcoded notification strings
- ✅ All notifications use constants from const.py
- ✅ Proper translation system via HA native localization
- ✅ Practical testing (5 second reminder delays in tests)
- ✅ Better maintainability (single source of truth)

### Future Capabilities (v4.1+)

- Multi-language support (just add more JSON language files)
- Custom per-kid notification messages (modify wrapper method only)
- A/B testing notification wording (change JSON, no code changes)
- Template customization without code deployment

---

## Implementation Phases

### Phase 1: Define Constants & Translations (8-10 hours)

- Add 15 title constants to const.py
- Add 16 message constants to const.py
- Add 31 translation entries to en.json
- **Start immediately** - all decisions made

### Phase 2: Update Coordinator (12-14 hours)

- Add wrapper methods (\_notify_kid_translated, \_notify_parents_translated)
- Add test mode auto-detection
- Update 24 notification call sites
- Update reminder delays

### Phase 3: Testing & Documentation (10-12 hours)

- Run linting and tests
- Manual notification testing
- Update architecture and code review docs

**Total Effort**: 30-36 hours

---

## Ready to Proceed?

See **NOTIFICATION_REFACTOR_NEXT_STEPS.md** for detailed implementation instructions.

Phase 1 can begin immediately - all blocking decisions are resolved.
