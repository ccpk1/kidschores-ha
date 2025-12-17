# Localization & Translation Modernization Plan

**Status**: In Progress
**Started**: December 16, 2025
**Related**: Phase 1 Refactoring Complete (constant organization)

## Overview

Modernize KidsChores integration to use Home Assistant 2024/2025 translation standards. Current implementation has ~100 instances of f-string patterns that embed `TRANS_KEY_*` constants, preventing proper internationalization. Most entities already use `_attr_has_entity_name = True` + `_attr_translation_key`, but fallback patterns and some manual name construction need fixing.

## Key Architectural Decisions

### ✅ CONFIRMED: Keep As-Is

1. **unique_id construction** (~50 instances)

   - Pattern: `f"{entry.entry_id}_{kid_id}_{chore_id}{SUFFIX}"`
   - Reason: Stable technical identifier, must never change
   - Decision: Correct pattern, no changes needed

2. **entity_id construction** (~45 instances)

   - Pattern: `f"{SENSOR_KC_PREFIX}{kid_name}{MIDFIX}{chore_name}"`
   - Reason: Uses slugified actual names, not TRANS_KEY constants
   - Decision: Correct pattern, no changes needed

3. **Attribute keys** (all ATTR\_\* constants)

   - Pattern: `ATTR_TOTAL_POINTS = "total_points"`
   - Reason: Technical identifiers for programmatic access via `state_attr()`
   - Decision: Must remain constant English identifiers
   - Note: Display labels are translated via `translations/en.json` under `state_attributes`

4. **Award item prefixes** (~10 instances)

   - Pattern: `f"{AWARD_ITEMS_PREFIX_REWARD}{reward_id}"` → `"reward:abc123"`
   - Reason: Internal parsing protocol, not user-facing
   - Decision: Keep as-is

5. **File paths** (3 instances)

   - Pattern: `f"{storage_path.name}_backup_{timestamp}"`
   - Reason: Filesystem naming, not user-facing
   - Decision: Keep as-is

6. **Error messages** (~35 instances)
   - Pattern: `raise HomeAssistantError(f"Kid '{kid_name}' not found")`
   - Reason: Developer/debug messages, acceptable English
   - Decision: Keep for now (could enhance later, not critical)

### ❌ CONFIRMED: Must Fix

1. **Entity display names with TRANS_KEY** (2 instances)
   - Problem: `self._attr_name = f"{TRANS_KEY_CALENDAR_NAME}: {kid_name}"`
   - Shows: Literal constant value in UI
   - Fix: Remove manual `_attr_name` assignment, rely on existing `_attr_translation_key`
   - Files: `calendar.py:60`, `select.py:227`
   - Note: Most entities already use correct pattern (`_attr_has_entity_name = True` + `_attr_translation_key` + `_attr_translation_placeholders`)

1a. **Manual friendly_name in attributes** (1 instance)

- Problem: `attributes[const.ATTR_FRIENDLY_NAME] = badge_info.get(const.DATA_BADGE_NAME)`
- Shows: Redundant and incorrect - `friendly_name` is auto-computed by HA
- Fix: Remove from attributes dict (line 1273)
- File: `sensor.py:1273` (BadgeSensor)

2. **Fallback name patterns** (~60 instances) ✅ RESOLVED

   - Problem: `.get(DATA_KID_NAME, f"{TRANS_KEY_LABEL_KID} {kid_id}")`
   - Shows: `"label_kid abc123"` when entity name missing
   - **Decision**: Remove all fallbacks entirely - entities should NOT be created if name missing
   - **Rationale**:
     - Config/options flows already require non-empty names for ALL entity types during creation
     - Research confirmed 7/9 entity types validated in all flows (add + edit)
     - 2 validation gaps found: Kids & Parents edit flows (missing empty name check)
     - With validation complete, fallbacks become dead code (entities can't exist without names)
   - **Fix Strategy**:
     1. Add validation gaps to Kids & Parents edit flows (options_flow.py)
     2. Remove all 60 fallback patterns from entity creation
     3. Add defensive logging helper for data corruption detection
   - Files: `sensor.py` (27), `button.py` (11), `select.py` (11), `calendar.py` (2)

3. **Config flow summary** (9 instances)

   - Problem: `f"{TRANS_KEY_CFOF_SUMMARY_KIDS}{kids_names}\n\n"`
   - Shows: Concatenated constant names in user-facing summary
   - Fix: Use `description_placeholders` dict pattern
   - File: `config_flow.py:922-930`

4. **TRANS_KEY constant itself uses f-string** (1 instance)

   - Problem: `TRANS_KEY_CALENDAR_NAME = f"{KIDSCHORES_TITLE} Calendar"`
   - Should be: Plain string key like `"calendar_name"`
   - Fix: Rollback to static string constant
   - File: `const.py:1858`

5. **Button delta labels** (4 instances)
   - Problem: `f"{TRANS_KEY_BUTTON_DELTA_PLUS_LABEL}{delta}"`
   - Shows: Constant name in button labels
   - Fix: Use translation system with placeholders
   - File: `button.py:1060-1067`

### ⚠️ OPEN QUESTIONS

**NEXT DECISION NEEDED:**

1. **Device grouping strategy** 🔴 BLOCKING

   - Current: Entities use `_attr_has_entity_name = True` but NO `device_info` set
   - Without device: Entity name = `"Sarah - Status - Dishes"` (full name from translation)
   - With device: Entity name = `"Status - Dishes"` + Device name = `"Sarah"` → Shows as `"Sarah Status - Dishes"`
   - Question: Should we add device grouping? Group all kid-related entities under device "Kid: Sarah"?
   - Modern pattern: Prefers device grouping for better organization
   - **Options:**
     - **A**: Keep current (no devices) - simpler, entity names standalone
     - **B**: Add device per kid - better UI organization, follows modern pattern
     - **C**: Hybrid - only group sensors/buttons per kid, leave selects/calendar separate
   - **Impact**: Affects translation key structure and placeholder usage
   - Decision: TBD

2. **Hardcoded English in attribute values**
   - Example: `f"Points: {award_points}"`, `f"Multiplier: {multiplier}"`
   - Location: `sensor.py:1370` in badge award details
   - Note: These are attribute VALUES (not keys), shown in more-info dialog
   - Question: Translate for consistency? Or acceptable as English?
   - Decision: TBD - Low priority (can defer to later phase)

## Implementation Phases

### Phase 2A: Critical Fixes (High Priority)

**Goal**: Fix user-facing translation issues

- [ ] **Task 1**: Fix `TRANS_KEY_CALENDAR_NAME` constant definition

  - File: `const.py:1858`
  - Change: `f"{KIDSCHORES_TITLE} Calendar"` → `"calendar_name"`
  - Impact: 1 line

- [ ] **Task 2**: Remove manual name construction in calendar/select

  - Files: `calendar.py:60`, `select.py:227`
  - Pattern: Delete `_attr_name = f"..."` lines (entities already have `_attr_translation_key` + `_attr_translation_placeholders`)
  - Impact: 2 entities (delete 2 lines)

- [ ] **Task 2a**: Remove ATTR_FRIENDLY_NAME from BadgeSensor attributes

  - File: `sensor.py:1273`
  - Pattern: Delete `attributes[const.ATTR_FRIENDLY_NAME] = ...` line
  - Reason: `friendly_name` is auto-computed by HA, shouldn't be in attributes dict
  - Impact: 1 line deletion

- [ ] **Task 3**: Fix validation gaps in options flow

  - File: `options_flow.py`
  - Add empty name validation to edit flows:
    - `async_step_edit_kid` (lines 1013-1050): Add `if not new_name:` check before duplicate validation
    - `async_step_edit_parent` (lines 1102-1140): Add `if not new_name:` check before duplicate validation
  - Pattern: `if not new_name: errors[CFOP_ERROR_*_NAME] = TRANS_KEY_CFOF_INVALID_*_NAME`
  - Impact: 2 validation gaps fixed (~10 lines total)

- [ ] **Task 4**: Create defensive logging helper

  - File: New function in `kc_helpers.py`
  - Purpose: Log error and return None when entity name missing (data corruption detection)
  - Signature: `get_entity_name_or_log_error(hass, entity_type: str, entity_id: str, entity_data: dict, name_key: str) -> str | None`
  - Returns: Name if present, None if missing (with error log)
  - Usage: `if not (name := get_entity_name_or_log_error(...)): return` (skip entity creation)

- [ ] **Task 5**: Remove all fallback patterns (bulk work)

  - Files: `sensor.py` (27), `button.py` (11), `select.py` (11), `calendar.py` (2)
  - Pattern: `.get(DATA_*_NAME, f"{TRANS_KEY...}")` → `.get(DATA_*_NAME)`
  - Add defensive check: `if not (name := get_entity_name_or_log_error(...)): return`
  - Impact: ~60 instances + 51 defensive checks

- [ ] **Task 6**: Fix config flow summary ✅ APPROACH DECIDED

  - File: `config_flow.py:922-930` (method `async_step_summary`)
  - Pattern: Add `hass.localize()` calls to resolve TRANS_KEY constants
  - Implementation: `self.hass.localize(f"component.{DOMAIN}.config.step.user.data.summary_kids")`
  - Impact: 9 lines modified (one per entity type)
  - Translation keys: Add 9 keys to `translations/en.json` under `config.step.user.data`
  - See "Config Flow Summary Discussion" section for detailed implementation pattern

- [ ] **Task 7**: Verify translation entries exist
  - File: `translations/en.json`
  - Ensure: All `TRANS_KEY_*` constants have corresponding entries
  - Add: Calendar entity translations with placeholder syntax

**Estimated Effort**: 2-3 hours (excluding Task 6 which needs discussion)
**Breaking Changes**: Entity names will change (entity_ids stable via unique_id)

### Phase 2B: UI Polish (Medium Priority)

**Goal**: Fix button labels and remaining UI text

- [ ] **Task 8**: Fix button delta labels

  - File: `button.py:1060-1067`
  - Pattern: Replace `f"{TRANS_KEY...}{delta}"` with translation_placeholders
  - Impact: 4 instances (sign_label, sign_text)

- [ ] **Task 9**: Translate hardcoded English in attribute values
  - File: `sensor.py:1370` (badge award details)
  - Pattern: `f"Points: {value}"` → use translation
  - Impact: ~5 instances
  - Note: Depends on decision (see Open Questions)

**Estimated Effort**: 1 hour (excluding tasks pending decisions)

### Phase 2C: Testing & Validation (Required)

- [ ] **Task 10**: Test entity name changes

  - Verify: English, German, Spanish translations render correctly
  - Check: entity_ids remain stable (unique_id unchanged)
  - Validate: Dashboard still works with new names
  - Test: Empty name validation in Kids/Parents edit flows

- [ ] **Task 11**: Update tests

  - Files: `test_sensor_values.py`, `test_dashboard_templates.py`
  - Pattern: Update assertions for new entity names
  - Add: Multi-language entity name tests
  - Add: Negative tests for empty name validation (2 new test cases)

- [ ] **Task 12**: Create migration guide
  - Document: Entity name changes in release notes
  - Provide: Dashboard YAML update examples
  - Mark: Breaking change in changelog
  - Note: Validation changes are non-breaking improvements

**Estimated Effort**: 2 hours

## Technical Details

### Modern HA Translation Pattern

**Correct implementation** (KidsChores already uses this for most entities):

```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True  # ✅ Enable modern naming
    _attr_translation_key = "points_sensor"  # ✅ Key for lookup
    _attr_translation_placeholders = {"kid_name": kid_name}  # ✅ Dynamic values

    # ❌ DO NOT set _attr_name manually (translation system handles it)
    # ❌ DO NOT set _attr_friendly_name (auto-computed by HA)
```

**In `translations/en.json`**:

```json
{
  "entity": {
    "sensor": {
      "points_sensor": {
        "name": "{kid_name} Points" // Template with placeholder
      }
    }
  }
}
```

**How Home Assistant computes the display name:**

1. Looks up translation key: `"points_sensor"` → `"{kid_name} Points"`
2. Substitutes placeholders: `{kid_name}` → `"Sarah"`
3. Entity name becomes: `"Sarah Points"`
4. If device_info set: Shows as `"[Device Name] [Entity Name]"`
5. If no device: Shows just entity name

**Result**: `"Sarah Points"` in English, `"Sarah Punkte"` in German

**friendly_name property**: Auto-computed by HA, never set manually. It's read-only.

### Attribute Key vs Display Label

**Attribute keys** (never translate):

```python
attributes = {
    "total_points": 100,  # ← Technical key for state_attr()
    "kid_name": "Sarah"
}
```

**Display labels** (translate in JSON):

```json
{
  "state_attributes": {
    "total_points": {"name": "Total Points"},  # ← Translated label
    "kid_name": {"name": "Kid Name"}
}
```

**Template access** (always uses English key):

```jinja2
{{ state_attr('sensor.kc_sarah_points', 'total_points') }}
```

### Fallback Helper Function Pattern

**Current (wrong)**:

```python
kid_name = kid_info.get(DATA_KID_NAME, f"{TRANS_KEY_LABEL_KID} {kid_id}")
# Result: "label_kid abc123" (literal constant)
```

**Proposed fix**:

```python
kid_name = kid_info.get(DATA_KID_NAME) or get_entity_fallback_name("kid", kid_id)
# Result: "Kid abc123" (clean fallback)
```

**Helper implementation** (to be created):

```python
def get_entity_fallback_name(entity_type: str, entity_id: str) -> str:
    """Return clean fallback name for missing entity.

    Args:
        entity_type: Entity type ("kid", "chore", "reward", etc.)
        entity_id: Internal ID (UUID)

    Returns:
        Formatted fallback like "Kid abc123"
    """
    # Truncate long UUIDs for readability
    short_id = entity_id[:8] if len(entity_id) > 8 else entity_id
    return f"{entity_type.title()} {short_id}"
```

## Files Modified Summary

| File                   | Critical | Medium | Low   | Total  |
| ---------------------- | -------- | ------ | ----- | ------ |
| `sensor.py`            | 27       | 2      | 5     | 34     |
| `button.py`            | 11       | 4      | 0     | 15     |
| `select.py`            | 11       | 0      | 0     | 11     |
| `calendar.py`          | 1        | 1      | 0     | 2      |
| `config_flow.py`       | 9        | 0      | 0     | 9      |
| `const.py`             | 1        | 0      | 0     | 1      |
| `kc_helpers.py`        | +1 new   | 0      | 0     | +1     |
| `translations/en.json` | Verify   | 0      | 0     | TBD    |
| **TOTAL**              | **61**   | **7**  | **5** | **73** |

## Testing Checklist

- [ ] All 126 existing tests still pass
- [ ] Entity names render correctly in UI (English)
- [ ] Entity names render correctly in UI (German)
- [ ] Entity names render correctly in UI (Spanish)
- [ ] entity_ids remain stable after changes
- [ ] unique_ids remain stable after changes
- [ ] Dashboard templates work with new entity names
- [ ] Fallback names appear correctly when entity missing
- [ ] Config flow summary displays properly
- [ ] Button labels show correctly
- [ ] Attribute display labels translate properly
- [ ] No "label\__" or "err-_" strings visible to users

## Migration Notes for Users

### Breaking Changes

**Entity Names Will Change** (v0.x.x)

Entity names will be updated to use proper translations. Entity IDs remain stable via unique_id.

**Before**:

- Entity: `sensor.kc_sarah_chore_status_dishes`
- Name: `"KidsChores: select_label_all_chores"`

**After**:

- Entity: `sensor.kc_sarah_chore_status_dishes` (same)
- Name: `"Sarah Chore Status: Dishes"` (translated)

**Action Required**:

- Dashboard YAML: Update entity name references if hardcoded
- Automations: No changes needed (uses entity_ids, which remain stable)

### Upgrade Guide

```yaml
# Before (old dashboard YAML)
title: "{{ 'KidsChores: select_label_all_chores' }}"

# After (automatic with new translations)
title: "{{ state_attr('sensor.kc_sarah_ui_dashboard_helper', 'ui_translations').welcome }}"
```

## Config Flow Summary Discussion

**Problem**: Config flow summary (lines 922-930) concatenates TRANS_KEY constants in f-strings:

```python
summary = (
    f"{const.TRANS_KEY_CFOF_SUMMARY_KIDS}{kids_names}\n\n"
    f"{const.TRANS_KEY_CFOF_SUMMARY_PARENTS}{parents_names}\n\n"
    f"{const.TRANS_KEY_CFOF_SUMMARY_CHORES}{chores_names}\n\n"
    # ... 9 lines total
)
return self.async_show_form(
    step_id="user",
    description_placeholders={"summary": summary}
)
```

**Challenge**: Summary contains DYNAMIC multi-line content (all entity names per type). Standard `description_placeholders` expects simple key-value pairs, not complex formatted blocks.

**✅ DECISION: Option 1 - Use `hass.localize()` with dynamic concatenation**

**Rationale**:

- Config flow summaries commonly need dynamic content (unpredictable number of entities)
- `hass.localize()` provides full translation support while preserving flexibility
- Minimal code change (just add localization calls to existing logic)
- Works correctly with all language variants (en/de/es)

**Implementation Pattern**:

```python
# Before (broken - shows literal TRANS_KEY)
summary = f"{const.TRANS_KEY_CFOF_SUMMARY_KIDS}{kids_names}\n\n"

# After (working - resolves translation)
kids_label = self.hass.localize(f"component.{const.DOMAIN}.config.step.user.{const.TRANS_KEY_CFOF_SUMMARY_KIDS}")
summary = f"{kids_label}: {kids_names}\n\n"

# Or using translation key directly:
summary = f"{self.hass.localize(f'component.{const.DOMAIN}.config.step.user.data.summary_kids')}: {kids_names}\n\n"
```

**Translation File Structure** (translations/en.json):

```json
{
  "config": {
    "step": {
      "user": {
        "data": {
          "summary_kids": "Kids",
          "summary_parents": "Parents",
          "summary_chores": "Chores",
          "summary_rewards": "Rewards",
          "summary_bonuses": "Bonuses",
          "summary_penalties": "Penalties",
          "summary_achievements": "Achievements",
          "summary_challenges": "Challenges",
          "summary_badges": "Badges"
        }
      }
    }
  }
}
```

**Impact**:

- File: `config_flow.py` lines 922-930
- Changes: ~9 lines (add `hass.localize()` calls)
- Breaking: None (summary display improves, no functional changes)

---

## TRANS_KEY F-String Issue - ✅ DECISION: Option 1

**Problem**: One constant in `const.py` uses f-string embedding another constant:

```python
# Line 1835 in const.py
TRANS_KEY_CALENDAR_NAME = f"{KIDSCHORES_TITLE} Calendar"
# Where KIDSCHORES_TITLE = "KidsChores"
# Results in literal: "KidsChores Calendar"
```

**Why This Is Wrong**:

- `TRANS_KEY_*` constants should be simple string keys for translation lookup (e.g., `"calendar_name"`)
- F-string creates computed value at module load: `"KidsChores Calendar"`
- Translation system cannot find key `"KidsChores Calendar"` in translations/en.json
- Creates cascading issues when used in entity `_attr_translation_key`

**Current Impact**:

- **calendar.py line 60**: Uses this constant in manual name construction
  ```python
  self._attr_name = f"{const.TRANS_KEY_CALENDAR_NAME}: {kid_name}"
  # Results in: "KidsChores Calendar: Sarah" (hardcoded English, not translatable)
  ```
- Translation lookup fails completely

**✅ DECISION: Fix by changing to simple string key**

**Implementation (3 steps)**:

1. **Change constant definition** (const.py:1835)

   ```python
   # Before
   TRANS_KEY_CALENDAR_NAME = f"{KIDSCHORES_TITLE} Calendar"

   # After
   TRANS_KEY_CALENDAR_NAME: Final = "calendar_name"
   ```

   - Impact: 1 line changed
   - Add missing `: Final` type annotation for consistency

2. **Remove manual name construction** (calendar.py:60)

   ```python
   # Before
   self._attr_name = f"{const.TRANS_KEY_CALENDAR_NAME}: {kid_name}"

   # After
   # DELETE the line entirely - entity already has proper translation setup
   ```

   - Entity already has `_attr_translation_key` and `_attr_translation_placeholders`
   - Impact: 1 line deleted

3. **Add/verify translation entry** (translations/en.json)
   ```json
   {
     "entity": {
       "calendar": {
         "calendar": {
           "name": "{kid_name} Calendar"
         }
       }
     }
   }
   ```

**Verification Commands**:

```bash
# Confirm this is the ONLY TRANS_KEY using f-string
grep -n 'TRANS_KEY.*= f"' custom_components/kidschores/const.py

# Expected: Only line 1835
```

**Expected Result After Fix**:

- ✅ Calendar displays as: "Sarah Calendar" (en) / "Sarah Kalender" (de) / "Calendario de Sarah" (es)
- ✅ No hardcoded "KidsChores Calendar" text
- ✅ entity_id remains stable: `calendar.kc_sarah_calendar`

**Status**: Included in Phase 2A Tasks 1 & 2

---

## Button Delta Labels Discussion

**Problem**: Button entities for point adjustments concatenate TRANS_KEY constants with delta values:

```python
# button.py lines 1060-1067
sign_label = (
    f"{const.TRANS_KEY_BUTTON_DELTA_PLUS_LABEL}{delta}"  # "+" concatenated with number
    if delta >= 0
    else f"{delta}"
)
sign_text = (
    f"{const.TRANS_KEY_BUTTON_DELTA_PLUS_TEXT}{delta}"   # "plus_" concatenated with number
    if delta >= 0
    else f"{const.TRANS_KEY_BUTTON_DELTA_MINUS_TEXT}{delta}"  # "minus_" concatenated with number
)
```

**Current Constants** (const.py lines 1816-1818):

```python
TRANS_KEY_BUTTON_DELTA_PLUS_LABEL: Final = "+"       # Literal "+" symbol
TRANS_KEY_BUTTON_DELTA_MINUS_TEXT: Final = "minus_"  # Literal "minus_"
TRANS_KEY_BUTTON_DELTA_PLUS_TEXT: Final = "plus_"    # Literal "plus_"
```

**Current Behavior**:

- `sign_label` used in `_attr_translation_placeholders` → Shows as `"+5"` or `"-10"` in button name
- `sign_text` used in `entity_id` construction → Creates `button.kc_sarah_plus_5_points` or `button.kc_sarah_minus_10_points`

**Analysis**:

- ✅ **entity_id usage**: `sign_text` creates valid entity IDs (`plus_5`, `minus_10`) - technically correct
- ❌ **translation_placeholders usage**: `sign_label` embeds `"+"` constant directly, but this works because it's already the desired symbol
- ⚠️ **Inconsistent pattern**: `TRANS_KEY_*` constants should reference translation keys, not literal values

**Options**:

### Option 1: Keep As-Is (Minimal Change)

**Rationale**: It works correctly, generates proper entity_ids and display text

**Pros**:

- No code changes needed
- Entity IDs are correct and stable
- Display shows correct symbols (`+5`, `-10`)

**Cons**:

- Violates naming convention (TRANS*KEY*\* should be keys, not literals)
- Constants are misleading (look like translation keys but aren't)

---

### Option 2: Rename Constants to Reflect True Purpose

**Change constants to indicate they're literal values, not translation keys**

**Implementation**:

```python
# const.py - Rename to show they're literals
BUTTON_DELTA_PLUS_SYMBOL: Final = "+"
BUTTON_DELTA_MINUS_PREFIX: Final = "minus_"
BUTTON_DELTA_PLUS_PREFIX: Final = "plus_"

# button.py - Update references
sign_label = (
    f"{const.BUTTON_DELTA_PLUS_SYMBOL}{delta}"
    if delta >= 0
    else f"{delta}"
)
```

**Pros**:

- Honest naming - not pretending to be translation keys
- No functional changes
- Improves code clarity

**Cons**:

- Requires updating 3 constant references in button.py
- Minor refactoring effort (~5 lines changed)

---

### Option 3: Full Translation Integration

**Convert to proper translation system with placeholders**

**Implementation**:

```python
# const.py - True translation keys
TRANS_KEY_BUTTON_DELTA_POSITIVE: Final = "delta_positive"
TRANS_KEY_BUTTON_DELTA_NEGATIVE: Final = "delta_negative"

# button.py - Use translation_placeholders
self._attr_translation_placeholders = {
    const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
    const.TRANS_KEY_BUTTON_ATTR_DELTA: abs(delta),
    const.TRANS_KEY_BUTTON_ATTR_SIGN: "positive" if delta >= 0 else "negative",
    const.TRANS_KEY_BUTTON_ATTR_POINTS_LABEL: points_label,
}

# translations/en.json
{
  "entity": {
    "button": {
      "manual_adjustment_button": {
        "name": "{kid_name} {sign} {delta} {points_label}"
      }
    }
  }
}
```

**Pros**:

- Fully proper translation architecture
- Allows language-specific formatting (e.g., German might show "5+" instead of "+5")
- Consistent with modern HA patterns

**Cons**:

- More complex implementation (~20+ lines changed)
- Requires careful testing of entity_id generation
- entity*id still needs English prefixes (`plus*`/`minus\_`) - can't translate
- May require separate logic for entity_id vs display name

---

### Option 4: Hybrid Approach

**Fix naming but keep simple concatenation**

**Implementation**:

```python
# const.py - Clear literal constants
BUTTON_ENTITY_ID_PLUS_PREFIX: Final = "plus_"
BUTTON_ENTITY_ID_MINUS_PREFIX: Final = "minus_"
BUTTON_DISPLAY_PLUS_SYMBOL: Final = "+"

# button.py - Separate concerns
entity_id_prefix = (
    const.BUTTON_ENTITY_ID_PLUS_PREFIX if delta >= 0
    else const.BUTTON_ENTITY_ID_MINUS_PREFIX
)
self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}_{entity_id_prefix}{abs(delta)}_points"

display_sign = const.BUTTON_DISPLAY_PLUS_SYMBOL if delta >= 0 else ""
self._attr_translation_placeholders = {
    const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
    const.TRANS_KEY_BUTTON_ATTR_SIGN_LABEL: f"{display_sign}{delta}",
    const.TRANS_KEY_BUTTON_ATTR_POINTS_LABEL: points_label,
}
```

**Pros**:

- Clear separation: entity_id constants vs display constants
- Proper naming conventions
- No translation complexity

**Cons**:

- More constants to manage
- Medium refactoring effort (~15 lines changed)

---

**✅ DECISION: Option 2 - Rename constants to reflect true purpose**

**Rationale**:

- Minimal code changes (3 constants renamed, 3 references updated)
- Honest naming improves maintainability
- No risk to entity_id stability
- Doesn't add translation complexity for marginal benefit
- Keeps simple concatenation pattern (works correctly)

**Implementation**:

1. **Rename constants** (const.py lines 1816-1818)

   ```python
   # Before
   TRANS_KEY_BUTTON_DELTA_PLUS_LABEL: Final = "+"
   TRANS_KEY_BUTTON_DELTA_MINUS_TEXT: Final = "minus_"
   TRANS_KEY_BUTTON_DELTA_PLUS_TEXT: Final = "plus_"

   # After
   BUTTON_DELTA_PLUS_SYMBOL: Final = "+"         # Display symbol for positive deltas
   BUTTON_DELTA_MINUS_PREFIX: Final = "minus_"   # Entity ID prefix for negative deltas
   BUTTON_DELTA_PLUS_PREFIX: Final = "plus_"     # Entity ID prefix for positive deltas
   ```

2. **Update references** (button.py lines 1060-1067)
   ```python
   # Update 3 constant references
   sign_label = (
       f"{const.BUTTON_DELTA_PLUS_SYMBOL}{delta}"  # Changed from TRANS_KEY_BUTTON_DELTA_PLUS_LABEL
       if delta >= 0
       else f"{delta}"
   )
   sign_text = (
       f"{const.BUTTON_DELTA_PLUS_PREFIX}{delta}"   # Changed from TRANS_KEY_BUTTON_DELTA_PLUS_TEXT
       if delta >= 0
       else f"{const.BUTTON_DELTA_MINUS_PREFIX}{delta}"  # Changed from TRANS_KEY_BUTTON_DELTA_MINUS_TEXT
   )
   ```

**Impact**:

- Files: `const.py` (3 constants renamed), `button.py` (3 references updated)
- Lines changed: ~6 total
- Breaking changes: None (functional behavior identical)
- entity_ids remain stable: `button.kc_sarah_plus_5_points`, `button.kc_sarah_minus_10_points`

**Status**: Included in Phase 2B Task 8

---

## Device Grouping Strategy Discussion ✅ DECIDED

**Decision**: Option 4 - Hybrid with global device (Config entry as service + per-kid devices + global device)
**Decision Date**: 2025-12-16

**Current State**: All entities use `_attr_has_entity_name = True` but NO `device_info` configured. Entities appear ungrouped in HA.

**Entity Inventory** (typical 2-kid, 3-chore, 2-reward setup):

- **Sensors**: ~132-172 entities (13 base per kid + item-specific + 4 global)
- **Buttons**: ~50-60 entities (3× per chore/reward + penalties/bonuses/adjustments per kid)
- **Selects**: 6 entities (4 global + 1 per kid)
- **Calendar**: 2 entities (1 per kid)
- **Total**: ~190-240 entities

**Entity Breakdown by Association**:

| Category                             | Per Kid | Per Item             | Global | Total (2 kids example)              |
| ------------------------------------ | ------- | -------------------- | ------ | ----------------------------------- |
| Kid Status Sensors                   | 13      | -                    | -      | 26                                  |
| Chore Status Sensors                 | -       | 1 per kid per chore  | -      | 6 (3 chores × 2 kids)               |
| Reward/Penalty/Bonus Sensors         | -       | 1 per kid per item   | -      | 8                                   |
| Badge/Achievement/Challenge Progress | -       | 1 per kid per item   | -      | 8                                   |
| Chore Action Buttons                 | -       | 3 per kid per chore  | -      | 18 (3 chores × 2 kids × 3 actions)  |
| Reward Action Buttons                | -       | 3 per kid per reward | -      | 12 (2 rewards × 2 kids × 3 actions) |
| Point Adjustment Buttons             | 6       | -                    | -      | 12 (6 values × 2 kids)              |
| Global Selects                       | -       | -                    | 4      | 4                                   |
| Per-Kid Selects                      | 1       | -                    | -      | 2                                   |
| Calendar                             | 1       | -                    | -      | 2                                   |
| Global Sensors                       | -       | -                    | 4      | 4                                   |

---

### Option 1: No Device Grouping (Current)

**Keep flat entity list - no device hierarchy**

**Pros**:

- Simplest implementation (no code changes)
- Entity names remain simple and self-contained
- No breaking changes to existing integrations

**Cons**:

- Entity list becomes overwhelming with scale (190+ entities)
- Hard to find related entities in UI
- Doesn't follow modern HA patterns (2024+ integrations prefer device grouping)
- No logical organization in dashboards

**Entity Name Pattern**:

```
sensor.kc_sarah_points                    # "Sarah Points"
sensor.kc_sarah_chore_status_dishes       # "Sarah Chore Status Dishes"
button.kc_sarah_claim_chore_dishes        # "Sarah Claim Chore Dishes"
calendar.kc_sarah_calendar                # "Sarah Calendar"
```

---

### Option 2: Per-Kid Devices (Recommended)

**Create one device per kid, group all related entities under it**

**Structure**:

```
Device: "Kid: Sarah"
├── Sensors (20-30)
│   ├── sensor.kc_sarah_points                    → "Points"
│   ├── sensor.kc_sarah_chore_status_dishes       → "Chore Status Dishes"
│   ├── sensor.kc_sarah_completed_chores_today    → "Completed Chores Today"
│   └── sensor.kc_sarah_badge_progress_super_star → "Badge Progress Super Star"
├── Buttons (15-25)
│   ├── button.kc_sarah_claim_chore_dishes        → "Claim Chore Dishes"
│   ├── button.kc_sarah_approve_chore_dishes      → "Approve Chore Dishes"
│   └── button.kc_sarah_plus_5_points             → "Plus 5 Points"
├── Calendar (1)
│   └── calendar.kc_sarah_calendar                → "Calendar"
└── Select (1)
    └── select.kc_sarah_chores                    → "Chores"

Device: "Kid: Tommy"
└── (same structure)

Ungrouped Global Entities:
├── select.kc_all_chores                          → "KidsChores All Chores"
├── select.kc_all_rewards                         → "KidsChores All Rewards"
├── sensor.kc_pending_chore_approvals             → "KidsChores Pending Chore Approvals"
└── sensor.kc_badge_super_star                    → "KidsChores Badge Super Star"
```

**Implementation**:

```python
# In each entity __init__
self._attr_device_info = DeviceInfo(
    identifiers={(const.DOMAIN, kid_id)},
    name=f"Kid: {kid_name}",
    manufacturer="KidsChores",
    model="Kid Profile",
    entry_type=DeviceEntryType.SERVICE,
)
```

**Pros**:

- ✅ **Best organization**: All kid-related entities logically grouped
- ✅ **Scales well**: Clear even with 100+ entities
- ✅ **Modern HA pattern**: Follows 2024+ best practices
- ✅ **Dashboard friendly**: Easy entity picker filtering by device
- ✅ **Clean entity names**: "Points" instead of "Sarah Points" (device name provides context)
- ✅ **One device per kid**: Natural mental model

**Cons**:

- Moderate implementation effort (~5-10 entity classes need device_info)
- Global entities remain ungrouped (but clearly named with "KidsChores" prefix)
- Breaking change: Entity display names change (entity_ids stable)

**Translation Impact**:

- Entity translation keys can be simpler: `"points"` instead of `"kid_points"`
- Device name provides kid context: Device "Kid: Sarah" → Entity "Points" = "Sarah Points" in UI

---

### Option 3: Per-Kid + Per-Function Devices

**Create multiple devices per kid: one for chores, one for rewards, one for points**

**Structure**:

```
Device: "Kid: Sarah - Chores"
├── sensor.kc_sarah_chore_status_dishes      → "Status Dishes"
├── sensor.kc_sarah_completed_chores_today   → "Completed Today"
├── button.kc_sarah_claim_chore_dishes       → "Claim Dishes"
└── button.kc_sarah_approve_chore_dishes     → "Approve Dishes"

Device: "Kid: Sarah - Rewards"
├── sensor.kc_sarah_reward_status_movie      → "Status Movie Night"
├── button.kc_sarah_redeem_reward_movie      → "Redeem Movie Night"
└── button.kc_sarah_approve_reward_movie     → "Approve Movie Night"

Device: "Kid: Sarah - Points"
├── sensor.kc_sarah_points                   → "Balance"
├── sensor.kc_sarah_points_earned_today      → "Earned Today"
└── button.kc_sarah_plus_5_points            → "Add 5"
```

**Pros**:

- Maximum granularity in organization
- Very clean entity names within device context

**Cons**:

- ❌ **Over-complicated**: 3-4 devices per kid (6-8 devices total for 2 kids)
- ❌ **Confusing UX**: Which device should user look in?
- ❌ **High maintenance**: More device management logic
- ❌ **Overkill**: Doesn't match user mental model (kids have chores, not "chore devices")

---

### Option 4: Hybrid - Per-Kid Devices + Shared Device

**Create per-kid devices + one "KidsChores Global" device for shared entities**

**Structure**:

```
Device: "Kid: Sarah"
└── (all Sarah-specific entities)

Device: "Kid: Tommy"
└── (all Tommy-specific entities)

Device: "KidsChores Global"
├── select.kc_all_chores                     → "All Chores"
├── select.kc_all_rewards                    → "All Rewards"
├── sensor.kc_pending_chore_approvals        → "Pending Approvals"
└── sensor.kc_badge_super_star               → "Badge Super Star"
```

**Pros**:

- All entities grouped (nothing orphaned)
- Clear separation: kid-specific vs global

**Cons**:

- Extra device management for marginal benefit
- "Global" device name may confuse users
- Global entities work fine ungrouped with clear naming

---

### Option 5: No Devices for Buttons/Calendar

**Only add devices to sensors, leave buttons/calendar ungrouped**

**Rationale**: Buttons are action-oriented, may not need grouping

**Cons**:

- ❌ **Inconsistent**: Why sensors grouped but not buttons?
- ❌ **Still cluttered**: 50+ button entities still ungrouped
- ❌ **Confusing**: Breaks expected device/entity relationship

---

## ✅ FINAL DECISION: Option 4 - Hybrid with Global Device

**Chosen Architecture**:

1. **Config Entry**: Flagged as `entry_type=DeviceEntryType.SERVICE` (integration-level service)
2. **Per-Kid Devices**: Each kid gets dedicated device with ~40-60 entities
3. **Global Device**: "KidsChores Global" for 4 select entities + 4 global sensors

**Rationale**:

- Config entry as service shows integration in main integrations list
- Per-kid devices match user mental model and modern HA patterns
- Global device prevents orphaned entities (better than ungrouped)
- Scales well for future multi-instance support

**Critical Implementation Detail - Multiple Instances**:

User mentioned potentially allowing multiple KidsChores config entries on same HA instance. This requires **unique device identifiers**:

```python
# ✅ Multi-instance safe identifiers with consistent naming pattern
# Per-kid devices (already unique via UUID)
DeviceInfo(
    identifiers={(DOMAIN, kid_id)},  # kid_id is internal_id (UUID) - naturally unique
    name=f"{kid_name} ({config_entry.title})",  # e.g., "Sarah (KidsChores)"
    manufacturer="KidsChores",
    model="Kid Profile",
    entry_type=DeviceEntryType.SERVICE,
)

# System device (MUST include config entry ID for uniqueness)
DeviceInfo(
    identifiers={(DOMAIN, f"{config_entry.entry_id}_system")},  # Instance-specific
    name=f"System ({config_entry.title})",  # e.g., "System (KidsChores)"
    manufacturer="KidsChores",
    model="System Controls",
    entry_type=DeviceEntryType.SERVICE,
)
```

**Device Naming Examples**:

_Single instance (default title: "KidsChores"):_

- "Sarah (KidsChores)"
- "Michael (KidsChores)"
- "System (KidsChores)"

_Multi-instance with custom titles:_

- "Sarah (Family Chores)", "Michael (Family Chores)", "System (Family Chores)"
- "Sarah (Allowance)", "Emma (Allowance)", "System (Allowance)"
- "Sarah (Summer Camp)", "System (Summer Camp)"

**Key Points**:

- Kid device identifiers already safe (UUID-based)
- System device MUST use `entry_id` in identifier for multi-instance support
- Config entry title defaults to "KidsChores" but can be customized per instance
- Consistent naming pattern: "{entity} ({instance_title})" for both kids and system
- Device cleanup automatic (no entities = device removed)

**Implementation Steps**:

1. Set default config entry title to "KidsChores" in config flow
2. Create `DeviceInfo` helper functions in `kc_helpers.py`:
   - `create_kid_device_info(kid_id: str, kid_name: str, config_entry: ConfigEntry) -> DeviceInfo`
     - Pattern: `f"{kid_name} ({config_entry.title})"`
   - `create_system_device_info(config_entry: ConfigEntry) -> DeviceInfo`
     - Pattern: `f"System ({config_entry.title})"`
     - Identifier: `f"{config_entry.entry_id}_system"`
3. Add `_attr_device_info` to all entity classes:
   - Per-kid entities (~20 classes): Call `create_kid_device_info()`
   - System entities (4 selects + 4 sensors): Call `create_system_device_info()`
4. Update translations for simplified entity names (device provides context)
5. Test device registry handles kid renames and removals correctly
6. Test multi-instance scenario (add second config entry, verify device uniqueness)
7. Should device include kid's age/HA user as additional properties?

**Status**: 🔴 BLOCKING Phase 2A - decision required before implementing display name fixes

---

## Progress Tracking

### Completed

- [x] Analysis of f-string usage patterns (200+ instances categorized)
- [x] Decision matrix (keep vs fix)
- [x] Phase structure and task breakdown
- [x] Fallback strategy decision (remove all fallbacks after fixing validation)
- [x] Research: Config/options flow validation status (found 2 gaps)
- [x] Config flow summary approach decision (Option 1: hass.localize())
- [x] TRANS_KEY f-string issue analysis and fix planning
- [x] Documentation created and updated

### In Progress

- [ ] Phase 2A implementation (ready to begin)

### Blocked

- None

### Future Enhancements

- Device grouping optimization (depends on architecture decision)
- Full translation of attribute values (low priority)
- Notification message translations (separate phase)

## References

- **Home Assistant Core Guidelines**: `/workspaces/core/.github/copilot-instructions.md`
- **Integration Instructions**: `.github/copilot-instructions.md`
- **Phase 1 Refactoring**: `PHASE1_REFACTORING_COMPLETE.md`
- **Current Translation File**: `custom_components/kidschores/translations/en.json`

## Notes

- Translation system already in place: `translations/en.json`, `translations/de.json`, `translations/es.json`
- Most entities already use modern pattern (`_attr_has_entity_name = True` + `_attr_translation_key`)
- Main issue: Fallback patterns and 2 manual name constructions embed TRANS_KEY constants
- Low risk: Fixes are straightforward, following established HA patterns
