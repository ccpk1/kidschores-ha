# Backup Forms Translation Refactor Plan

**Date**: December 30, 2025
**Status**: 🔴 Planning - Ready for Implementation
**Objective**: Fix hardcoded text in backup action forms and implement proper translation system

---

## Executive Summary

The backup management forms in `options_flow.py` currently have significant hardcoded text issues that prevent proper internationalization. This plan outlines a comprehensive refactor to match the proven translation patterns used in `config_flow.py`'s data recovery system.

### Key Problems Identified

1. ❌ **Hardcoded emoji labels** in `view_backups` step (lines 2540-2565)

   - "🔄 Restore: {filename}..."
   - "🗑️ Delete: {filename}..."
   - "↩️ Return to backup menu"

2. ❌ **Mixed translation approaches** in `backup_actions_menu` (lines 2470-2490)

   - Uses `translation_key` but still has hardcoded option values

3. ❌ **No translation keys** in confirmation forms

   - `create_manual_backup` (line 2625-2635) - missing translation_key
   - `delete_backup_confirm` (line 2670-2678) - missing translation_key
   - `confirm_restore_backup` - needs review

4. ❌ **Inconsistent patterns** across backup flows
   - Some forms use SelectSelector properly, others don't
   - No consistent emoji strategy

---

## Reference Implementation: Config Flow Data Recovery

### ✅ What Works (config_flow.py lines 88-197)

**Pattern Analysis:**

```python
# GOOD: Fixed options with translation_key
options = ["current_active", "start_fresh", "paste_json"]

# GOOD: Dynamic backup files with emoji ONLY (no text)
for backup in backups:
    age_str = fh.format_backup_age(backup["age_hours"])
    tag_display = backup["tag"].replace("-", " ").title()
    backup_display = f"[{tag_display}] {backup['filename']} ({age_str})"
    emoji_option = f"📄 {backup_display}"  # Emoji + data only
    options.append(emoji_option)

# GOOD: SelectSelector with translation_key
selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=options,
        mode=selector.SelectSelectorMode.LIST,
        translation_key="data_recovery_selection",  # KEY POINT
        custom_value=True,
    )
)
```

**Translation File (en.json lines 1403-1410):**

```json
"data_recovery_selection": {
  "options": {
    "cancel": "↩️  Cancel (return to backup menu)",
    "start_fresh": "🆕 Start fresh (creates backup of existing data)",
    "current_active": "📂 Use current active data file",
    "paste_json": "📋 Paste JSON from data file or diagnostics"
  }
}
```

### Key Success Factors

1. ✅ Fixed options get translated via `translation_key`
2. ✅ Dynamic data (filenames) use emoji prefix WITHOUT text
3. ✅ User sees: "📄 [Manual] kidschores_2025_12_30.json (2 days ago)"
4. ✅ No language-specific text in dynamic options
5. ✅ `custom_value=True` allows emoji-prefixed values

---

## Proposed Solution Architecture

### Strategy Change: Separate Action Selection from File Management

**Current Problem:**

- Mixed action selection + file display in one form
- Creates translation nightmare with dynamic labels

**Solution:**

- **Step 1**: Action selection menu (create/delete/restore) - ALL TRANSLATED
- **Step 2**: File selection menu (if needed) - EMOJI ONLY for files

### New Flow Structure

```
backup_actions_menu
├─ create_backup → create_manual_backup → [confirmation]
├─ delete_backup → select_backup_to_delete → delete_backup_confirm
├─ restore_backup → select_backup_to_restore → confirm_restore_backup
└─ return_to_menu → async_step_init()
```

---

## Detailed Implementation Plan

### Phase 1: Backup Actions Menu (Main Entry)

**File**: `options_flow.py` - `async_step_backup_actions_menu` (lines 2450-2490)

**Current State:**

```python
options=["view_backups", "create_backup", "return_to_menu"],
translation_key=const.TRANS_KEY_CFOF_BACKUP_ACTIONS,
```

**Refactor To:**

```python
options=["create_backup", "delete_backup", "restore_backup", "return_to_menu"],
translation_key="backup_actions_menu",  # NEW translation key
```

**Translation Updates Needed:**

```json
"backup_actions_menu": {
  "options": {
    "create_backup": "💾 Create backup now",
    "delete_backup": "🗑️  Delete a backup",
    "restore_backup": "🔄 Restore from backup",
    "return_to_menu": "↩️  Return to main menu"
  }
}
```

**Constant Updates:**

- Add: `TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU = "backup_actions_menu"`
- Verify: `CFOF_BACKUP_ACTION_SELECTION` exists

---

### Phase 2: Delete Backup Flow (NEW)

**New Step Required**: `async_step_select_backup_to_delete`

**Purpose**: Show only backup files (emoji + data, no action text)

**Implementation:**

```python
async def async_step_select_backup_to_delete(self, user_input=None):
    """Select a backup file to delete."""
    from .storage_manager import KidsChoresStorageManager

    storage_manager = KidsChoresStorageManager(self.hass)

    if user_input is not None:
        selection = user_input.get(const.CFOF_BACKUP_SELECTION)

        if selection == "cancel":
            return await self.async_step_backup_actions_menu()

        # Extract filename from emoji-prefixed selection
        if selection.startswith("🗑️ "):
            filename = self._extract_filename_from_selection(selection)
            self._backup_to_delete = filename
            return await self.async_step_delete_backup_confirm()

    # Discover backups
    backups = await fh.discover_backups(self.hass, storage_manager)

    # Build options - EMOJI ONLY for files
    options = []
    for backup in backups:
        # Skip protected backups
        if backup["tag"] not in [const.BACKUP_TAG_PRE_MIGRATION, const.BACKUP_TAG_MANUAL]:
            age_str = fh.format_backup_age(backup["age_hours"])
            size_kb = backup["size_bytes"] / 1024
            tag_display = backup["tag"].replace("-", " ").title()

            # EMOJI ONLY - no "Delete:" text
            option = f"🗑️ [{tag_display}] {backup['filename']} ({age_str}, {size_kb:.1f} KB)"
            options.append(option)

    options.append("cancel")  # Translated via translation_key

    return self.async_show_form(
        step_id=const.OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE,
        data_schema=vol.Schema({
            vol.Required(const.CFOF_BACKUP_SELECTION): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="select_backup_to_delete",
                    custom_value=True,
                )
            )
        }),
        description_placeholders={"backup_count": str(len(backups))},
    )
```

**Translation:**

```json
"select_backup_to_delete": {
  "options": {
    "cancel": "↩️  Cancel (return to backup menu)"
  }
}
```

**Constants Needed:**

- `OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE = "select_backup_to_delete"`
- `TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE = "select_backup_to_delete"`

---

### Phase 3: Restore Backup Flow (NEW)

**New Step Required**: `async_step_select_backup_to_restore`

**Implementation:** (Similar to delete, but with 🔄 emoji)

```python
async def async_step_select_backup_to_restore(self, user_input=None):
    """Select a backup file to restore."""
    # Similar pattern to select_backup_to_delete
    # Use 🔄 emoji instead of 🗑️
    # Options: "🔄 [{tag}] filename.json (age, size)"
    # translation_key="select_backup_to_restore"
```

**Translation:**

```json
"select_backup_to_restore": {
  "options": {
    "cancel": "↩️  Cancel (return to backup menu)"
  }
}
```

**Constants Needed:**

- `OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE = "select_backup_to_restore"`
- `TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE = "select_backup_to_restore"`

---

### Phase 4: Confirmation Forms Translation

#### 4A: Create Manual Backup Confirmation

**File**: `options_flow.py` - `async_step_create_manual_backup` (lines 2590-2635)

**Current Issue:** No translation_key for form description

**Fix:**

```python
return self.async_show_form(
    step_id=const.OPTIONS_FLOW_STEP_CREATE_MANUAL_BACKUP,
    data_schema=vol.Schema({
        vol.Required("confirm", default=False): selector.BooleanSelector(),
    }),
    description_placeholders={
        "backup_count": str(current_backup_count),
        "retention": str(retention_setting),
    },
)
```

**Translation:**

```json
"config": {
  "step": {
    "create_manual_backup": {
      "title": "Create Manual Backup",
      "description": "Create a new backup of your KidsChores data.\n\nCurrent backups: {backup_count}\nRetention setting: {retention} backups",
      "data": {
        "confirm": "Confirm backup creation"
      }
    }
  }
}
```

#### 4B: Delete Backup Confirmation

**File**: `options_flow.py` - `async_step_delete_backup_confirm` (lines 2637-2678)

**Current Translation:** Partial (has description_placeholders but no proper step description)

**Fix:**

```json
"config": {
  "step": {
    "delete_backup_confirm": {
      "title": "Confirm Backup Deletion",
      "description": "⚠️  You are about to permanently delete this backup:\n\n{backup_filename}\n\nThis action cannot be undone.",
      "data": {
        "confirm": "Confirm deletion"
      }
    }
  }
}
```

#### 4C: Restore Backup Confirmation

**Review Required**: Check `async_step_confirm_restore_backup` for translation completeness

---

### Phase 5: Remove Old `view_backups` Step

**Current**: Lines 2492-2588 in `options_flow.py`

**Action**: DELETE - replaced by separate delete/restore flows

**Rationale:**

- Mixed action types (restore/delete) in one form = translation nightmare
- Hardcoded labels with dynamic data
- Violates separation of concerns

---

## Translation File Changes Summary

### ⚠️ CRITICAL: Translation File Synchronization

**ALL changes MUST be applied to BOTH translation files:**

- `translations/en.json` (English - master reference)
- `translations/es.json` (Spanish - exact parallel structure)

**Synchronization Requirements:**

- ✅ Every key added to en.json MUST have corresponding entry in es.json
- ✅ JSON structure MUST be identical (same nesting, same keys)
- ✅ Emoji characters MUST be identical across both files
- ✅ Translation quality: Spanish translations should be natural, not literal word-for-word
- ✅ Placeholders: `{backup_count}`, `{backup_filename}`, etc. must remain unchanged in both files

**Validation Steps:**

1. After adding translations, verify JSON structure matches
2. Test both English and Spanish language modes
3. Confirm emoji display correctly in both languages
4. Check placeholder substitution works in both languages

---

### New Selectors to Add

**English (en.json):**

```json
"selector": {
  "backup_actions_menu": {
    "options": {
      "create_backup": "💾 Create backup now",
      "delete_backup": "🗑️  Delete a backup",
      "restore_backup": "🔄 Restore from backup",
      "return_to_menu": "↩️  Return to main menu"
    }
  },
  "select_backup_to_delete": {
    "options": {
      "cancel": "↩️  Cancel (return to backup menu)"
    }
  },
  "select_backup_to_restore": {
    "options": {
      "cancel": "↩️  Cancel (return to backup menu)"
    }
  }
}
```

**Spanish (es.json):**

```json
"selector": {
  "backup_actions_menu": {
    "options": {
      "create_backup": "💾 Crear copia de seguridad ahora",
      "delete_backup": "🗑️  Eliminar una copia de seguridad",
      "restore_backup": "🔄 Restaurar desde copia de seguridad",
      "return_to_menu": "↩️  Volver al menú principal"
    }
  },
  "select_backup_to_delete": {
    "options": {
      "cancel": "↩️  Cancelar (volver al menú de copias)"
    }
  },
  "select_backup_to_restore": {
    "options": {
      "cancel": "↩️  Cancelar (volver al menú de copias)"
    }
  }
}
```

### Config Steps to Add

**English (en.json):**

```json
"config": {
  "step": {
    "create_manual_backup": {
      "title": "Create Manual Backup",
      "description": "Create a new backup of your KidsChores data.\n\nCurrent backups: {backup_count}\nRetention setting: {retention} backups",
      "data": {
        "confirm": "Confirm backup creation"
      }
    },
    "delete_backup_confirm": {
      "title": "Confirm Backup Deletion",
      "description": "⚠️  You are about to permanently delete this backup:\n\n{backup_filename}\n\nThis action cannot be undone.",
      "data": {
        "confirm": "Confirm deletion"
      }
    },
    "select_backup_to_delete": {
      "title": "Select Backup to Delete",
      "description": "Choose a backup file to delete.\n\nAvailable backups: {backup_count}\n\n⚠️  Protected backups (pre-migration, manual) cannot be deleted."
    },
    "select_backup_to_restore": {
      "title": "Select Backup to Restore",
      "description": "Choose a backup file to restore.\n\nAvailable backups: {backup_count}\n\n⚠️  This will replace your current data!"
    }
  }
}
```

**Spanish (es.json):**

```json
"config": {
  "step": {
    "create_manual_backup": {
      "title": "Crear Copia de Seguridad Manual",
      "description": "Crear una nueva copia de seguridad de tus datos de KidsChores.\n\nCopias actuales: {backup_count}\nConfiguración de retención: {retention} copias",
      "data": {
        "confirm": "Confirmar creación de copia de seguridad"
      }
    },
    "delete_backup_confirm": {
      "title": "Confirmar Eliminación de Copia",
      "description": "⚠️  Estás a punto de eliminar permanentemente esta copia de seguridad:\n\n{backup_filename}\n\nEsta acción no se puede deshacer.",
      "data": {
        "confirm": "Confirmar eliminación"
      }
    },
    "select_backup_to_delete": {
      "title": "Seleccionar Copia para Eliminar",
      "description": "Elige un archivo de copia de seguridad para eliminar.\n\nCopias disponibles: {backup_count}\n\n⚠️  Las copias protegidas (pre-migración, manual) no se pueden eliminar."
    },
    "select_backup_to_restore": {
      "title": "Seleccionar Copia para Restaurar",
      "description": "Elige un archivo de copia de seguridad para restaurar.\n\nCopias disponibles: {backup_count}\n\n⚠️  ¡Esto reemplazará tus datos actuales!"
    }
  }
}
```

---

## Constants to Add/Update

### New Step Constants

```python
# In const.py OPTIONS_FLOW section
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"
```

### New Translation Keys

```python
# In const.py TRANS_KEY section
TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU: Final = "backup_actions_menu"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"
```

### Update Existing

```python
# Verify these exist:
CFOF_BACKUP_ACTION_SELECTION: Final = "backup_action_selection"
CFOF_BACKUP_SELECTION: Final = "backup_selection"
OPTIONS_FLOW_STEP_BACKUP_ACTIONS: Final = "backup_actions_menu"
OPTIONS_FLOW_STEP_DELETE_BACKUP_CONFIRM: Final = "delete_backup_confirm"
OPTIONS_FLOW_STEP_CREATE_MANUAL_BACKUP: Final = "create_manual_backup"
```

---

## Helper Functions Needed

### Filename Extraction Utility

```python
def _extract_filename_from_selection(self, selection: str) -> str:
    """Extract backup filename from emoji-prefixed selection.

    Format: "🔄 [Tag] filename.json (age, size)"
    Returns: "filename.json"
    """
    # Remove emoji prefix
    if selection.startswith("🔄 ") or selection.startswith("🗑️ "):
        display_part = selection[3:].strip()

        # Extract from "[Tag] filename.json (age, size)"
        if "] " in display_part and " (" in display_part:
            start_idx = display_part.find("] ") + 2
            end_idx = display_part.rfind(" (")
            if start_idx < end_idx:
                return display_part[start_idx:end_idx]

    # Fallback: return as-is (shouldn't happen)
    return selection
```

---

## Implementation Checklist

### Phase 1: Constants & Translations

- [ ] Add new step constants to `const.py`
- [ ] Add new translation key constants to `const.py`
- [ ] Update `en.json` with new selector translations
- [ ] Update `es.json` with new selector translations (parallel to en.json)
- [ ] Update `en.json` with new config step translations
- [ ] Update `es.json` with new config step translations (parallel to en.json)
- [ ] Verify JSON structure matches between en.json and es.json
- [ ] Verify all emoji usage is consistent (🔄, 🗑️, 💾, ↩️)
- [ ] Test both English and Spanish language modes

### Phase 2: Backup Actions Menu Refactor

- [ ] Update `async_step_backup_actions_menu` options list
- [ ] Update navigation handlers (delete/restore instead of view)
- [ ] Update translation_key reference
- [ ] Test: Spanish language shows translated menu

### Phase 3: Delete Flow Implementation

- [ ] Create `async_step_select_backup_to_delete`
- [ ] Implement emoji-only file display
- [ ] Add cancel option with translation
- [ ] Update `async_step_delete_backup_confirm` translations
- [ ] Test: Deletion flow works end-to-end

### Phase 4: Restore Flow Implementation

- [ ] Create `async_step_select_backup_to_restore`
- [ ] Implement emoji-only file display
- [ ] Add cancel option with translation
- [ ] Update `async_step_confirm_restore_backup` translations
- [ ] Test: Restore flow works end-to-end

### Phase 5: Create Flow Enhancement

- [ ] Update `async_step_create_manual_backup` with translations
- [ ] Add description placeholders
- [ ] Test: Creation flow shows proper translations

### Phase 6: Cleanup

- [ ] Remove `async_step_view_backups` (lines 2492-2588)
- [ ] Remove unused constants (if any)
- [ ] Remove unused translation keys (if any)
- [ ] Update tests to match new flow structure

### Phase 7: Validation

- [ ] Run Spanish language test to verify all translations work
- [ ] Test all backup flows (create, delete, restore, cancel)
- [ ] Verify emoji-only file display (no hardcoded text)
- [ ] Confirm no regression in backup functionality
- [ ] Run full test suite: `python -m pytest tests/ -v`
- [ ] Run linting: `./utils/quick_lint.sh --fix`

---

## Benefits of This Refactor

1. ✅ **Full Internationalization**: All text translatable
2. ✅ **Consistent Pattern**: Matches proven config_flow approach
3. ✅ **Separation of Concerns**: Actions separate from file selection
4. ✅ **User Clarity**: Each form has single clear purpose
5. ✅ **Maintainability**: Translation-first design prevents future hardcoding
6. ✅ **Testing**: Each flow testable independently
7. ✅ **Spanish/Other Languages**: Works seamlessly with any language

---

## Risks & Mitigation

### Risk 1: Breaking Existing Workflows

**Mitigation**:

- Implement in feature branch
- Comprehensive testing before merge
- Maintain backup of old code

### Risk 2: Translation Key Mismatches

**Mitigation**:

- Validate all TRANS*KEY*\* constants exist
- Cross-reference with en.json
- Use Phase 0 audit framework

### Risk 3: Emoji Inconsistency

**Mitigation**:

- Document emoji mapping (🔄=restore, 🗑️=delete, 💾=create)
- Use constants for emojis if needed
- Consistent across all flows

---

## Testing Strategy

### Unit Tests Needed

1. `test_backup_actions_menu_translations.py`

   - Verify translation_key works
   - Check all options translated
   - Test Spanish language

2. `test_backup_delete_flow.py`

   - Test file selection with emoji
   - Test cancel navigation
   - Test deletion confirmation

3. `test_backup_restore_flow.py`

   - Test file selection with emoji
   - Test cancel navigation
   - Test restore confirmation

4. `test_backup_create_flow.py`
   - Test confirmation form
   - Test translation placeholders
   - Test return navigation

### Integration Tests

- Full backup cycle: create → view → delete
- Spanish language end-to-end test
- Navigation between all backup forms

---

## Estimated Effort

- **Phase 1 (Constants/Translations)**: 30 minutes
- **Phase 2 (Actions Menu)**: 30 minutes
- **Phase 3 (Delete Flow)**: 1 hour
- **Phase 4 (Restore Flow)**: 1 hour
- **Phase 5 (Create Flow)**: 30 minutes
- **Phase 6 (Cleanup)**: 30 minutes
- **Phase 7 (Testing)**: 1 hour

**Total**: ~5 hours for complete refactor

---

## Success Criteria

✅ **Zero hardcoded user-facing text** in backup forms
✅ **All SelectSelector use translation_key**
✅ **Dynamic filenames use emoji-only prefix**
✅ **Spanish language test passes** for all backup flows
✅ **Consistent with config_flow pattern**
✅ **All tests pass** (existing + new)
✅ **Linting passes** with 9.5+/10 score

---

**Next Steps**: Review plan → Approve → Implement Phase 1 (Constants/Translations)

**Documentation**: Update ARCHITECTURE.md after implementation to document new backup flow pattern
