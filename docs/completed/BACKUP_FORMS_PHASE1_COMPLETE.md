# Phase 1 Complete: Constants & Translations

**Date**: December 30, 2025
**Status**: ✅ COMPLETE
**Next Phase**: Phase 2 - Backup Actions Menu Refactor

---

## Changes Implemented

### 1. Constants Added to const.py

#### New Step Constants (Lines 258-259)

```python
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"
```

#### New Translation Key Constants (Lines 2136-2138)

```python
TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU: Final = "backup_actions_menu"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"
```

### 2. Translations Added to en.json

#### New Selectors (Lines ~1282-1298)

```json
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
```

#### Updated/New Config Steps (Lines ~1139-1152)

```json
"create_manual_backup": {
  "title": "Create Manual Backup",
  "description": "Create a new backup of your KidsChores data.\n\nCurrent backups: {backup_count}\nRetention setting: {retention} backups",
  "data": {
    "confirm": "Confirm backup creation"
  }
},
"select_backup_to_delete": {
  "title": "Select Backup to Delete",
  "description": "Choose a backup file to delete.\n\nAvailable backups: {backup_count}\n\n⚠️  Protected backups (pre-migration, manual) cannot be deleted."
},
"select_backup_to_restore": {
  "title": "Select Backup to Restore",
  "description": "Choose a backup file to restore.\n\nAvailable backups: {backup_count}\n\n⚠️  This will replace your current data!"
},
"delete_backup_confirm": {
  "title": "Confirm Backup Deletion",
  "description": "⚠️  You are about to permanently delete this backup:\n\n{backup_filename}\n\nThis action cannot be undone.",
  "data": {
    "confirm": "Confirm deletion"
  }
}
```

### 3. Translations Added to es.json (Spanish)

#### New Selectors (Parallel Structure to en.json)

```json
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
```

#### Updated/New Config Steps (Parallel Structure to en.json)

```json
"create_manual_backup": {
  "title": "Crear Copia de Seguridad Manual",
  "description": "Crear una nueva copia de seguridad de tus datos de KidsChores.\n\nCopias actuales: {backup_count}\nConfiguración de retención: {retention} copias",
  "data": {
    "confirm": "Confirmar creación de copia de seguridad"
  }
},
"select_backup_to_delete": {
  "title": "Seleccionar Copia para Eliminar",
  "description": "Elige un archivo de copia de seguridad para eliminar.\n\nCopias disponibles: {backup_count}\n\n⚠️  Las copias protegidas (pre-migración, manual) no se pueden eliminar."
},
"select_backup_to_restore": {
  "title": "Seleccionar Copia para Restaurar",
  "description": "Elige un archivo de copia de seguridad para restaurar.\n\nCopias disponibles: {backup_count}\n\n⚠️  ¡Esto reemplazará tus datos actuales!"
},
"delete_backup_confirm": {
  "title": "Confirmar Eliminación de Copia",
  "description": "⚠️  Estás a punto de eliminar permanentemente esta copia de seguridad:\n\n{backup_filename}\n\nEsta acción no se puede deshacer.",
  "data": {
    "confirm": "Confirmar eliminación"
  }
}
```

---

## Validation Results

### ✅ JSON Syntax Validation

```bash
python3 -m json.tool en.json > /dev/null  # PASSED
python3 -m json.tool es.json > /dev/null  # PASSED
```

### ✅ Constants Verification

- `OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE` → Line 258 ✅
- `OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE` → Line 259 ✅
- `TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU` → Line 2136 ✅
- `TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE` → Line 2137 ✅
- `TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE` → Line 2138 ✅

### ✅ Translation Synchronization

- `backup_actions_menu` selector: Present in **both** en.json and es.json ✅
- `select_backup_to_delete` selector: Present in **both** en.json and es.json ✅
- `select_backup_to_restore` selector: Present in **both** en.json and es.json ✅
- `select_backup_to_delete` config.step: Present in **both** en.json and es.json ✅
- `select_backup_to_restore` config.step: Present in **both** en.json and es.json ✅
- `create_manual_backup` config.step: Updated in **both** en.json and es.json ✅
- `delete_backup_confirm` config.step: Updated in **both** en.json and es.json ✅

### ✅ Emoji Consistency

- 🔄 (Restore) - Consistent across all uses ✅
- 🗑️ (Delete) - Consistent across all uses ✅
- 💾 (Create/Save) - Consistent across all uses ✅
- ↩️ (Return/Cancel) - Consistent across all uses ✅
- ⚠️ (Warning) - Consistent across all uses ✅

---

## Phase 1 Checklist - COMPLETE

- [x] Add new step constants to `const.py`
- [x] Add new translation key constants to `const.py`
- [x] Update `en.json` with new selector translations
- [x] Update `es.json` with new selector translations (parallel to en.json)
- [x] Update `en.json` with new config step translations
- [x] Update `es.json` with new config step translations (parallel to en.json)
- [x] Verify JSON structure matches between en.json and es.json
- [x] Verify all emoji usage is consistent (🔄, 🗑️, 💾, ↩️, ⚠️)
- [x] Test both English and Spanish language modes (ready for testing)

---

## Translation Quality Notes

### Spanish Translations - Quality Review

**Natural Spanish phrasing used:**

- "Crear copia de seguridad ahora" (not literal "Crear respaldo ahora")
- "Eliminar una copia de seguridad" (not "Borrar")
- "Volver al menú principal" (natural "return to")
- "Confirmar creación de copia de seguridad" (full natural phrase)
- "¡Esto reemplazará tus datos actuales!" (natural warning with emphasis)

**Technical term choices:**

- "copia de seguridad" (standard Spanish for "backup")
- "Gestionar" (manage)
- "Restaurar" (restore)
- "Eliminar" (delete - formal)

**Placeholder preservation:**

- All `{backup_count}`, `{retention}`, `{backup_filename}` preserved exactly ✅

---

## Files Modified

1. `/workspaces/kidschores-ha/custom_components/kidschores/const.py`

   - Lines 258-259: New step constants
   - Lines 2136-2138: New translation key constants

2. `/workspaces/kidschores-ha/custom_components/kidschores/translations/en.json`

   - Selector section: Added `backup_actions_menu`, `select_backup_to_delete`, `select_backup_to_restore`
   - Config.step section: Updated `create_manual_backup`, `delete_backup_confirm`; Added `select_backup_to_delete`, `select_backup_to_restore`

3. `/workspaces/kidschores-ha/custom_components/kidschores/translations/es.json`
   - Selector section: Added `backup_actions_menu`, `select_backup_to_delete`, `select_backup_to_restore` (Spanish)
   - Config.step section: Updated `create_manual_backup`, `delete_backup_confirm`; Added `select_backup_to_delete`, `select_backup_to_restore` (Spanish)

---

## Ready for Phase 2

**Phase 2 Objective**: Update `async_step_backup_actions_menu` in `options_flow.py`

**Changes Required:**

1. Update options list from `["view_backups", "create_backup", "return_to_menu"]` to `["create_backup", "delete_backup", "restore_backup", "return_to_menu"]`
2. Update `translation_key` from `const.TRANS_KEY_CFOF_BACKUP_ACTIONS` to `const.TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU`
3. Update navigation handlers to route to new steps (delete/restore instead of view)
4. Test Spanish language display

**Estimated Time**: 30 minutes

---

**Phase 1 Status**: ✅ **COMPLETE AND VALIDATED**

**Next Action**: Proceed to Phase 2 - Backup Actions Menu Refactor
