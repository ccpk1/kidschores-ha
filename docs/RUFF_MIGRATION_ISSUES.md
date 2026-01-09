# Ruff Migration - Issues & Fixes

## Issues Encountered & Resolved

### 1. ✅ Deprecated `ruff.importStrategy` Setting

**Issue**: VSCode showed deprecation warning:

```
Deprecated: This setting is only used by ruff-lsp which is deprecated
in favor of the native language server.
```

**Fix**: Removed `"ruff.importStrategy": "fromEnvironment"` from settings.

**Why**: The new native Ruff language server doesn't need this setting. It automatically detects the Python environment.

**Updated**: `.vscode/settings.json`

---

### 2. ✅ "Even Better TOML" Extension Prompt

**Issue**: VSCode asked to install "Even Better TOML" extension.

**Why**: This is **expected and recommended**!

The extension is needed because:

- `pyproject.toml` uses TOML format
- Extension provides syntax highlighting, validation, and IntelliSense
- Already in `.vscode/extensions.json` recommendations

**Action**: Click "Install" when prompted, or install manually:

1. Extensions panel (Ctrl+Shift+X)
2. Search "Even Better TOML"
3. Install by tamasfe

---

### 3. ✅ Python Interpreter Warning

**Issue**: VSCode showed "Select Python Interpreter" warning.

**Fix**: Updated `.vscode/settings.json` with correct path:

```json
{
  "python.defaultInterpreterPath": "/home/vscode/.local/ha-venv/bin/python3"
}
```

**Manual Selection** (if still needed):

1. Press `Ctrl+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose: `/home/vscode/.local/ha-venv/bin/python3`

---

## Current Working Configuration

### `.vscode/settings.json` (Updated)

```json
{
  "python.defaultInterpreterPath": "/home/vscode/.local/ha-venv/bin/python3",

  // Ruff configuration (native language server)
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  },

  // Ruff settings (no deprecated options)
  "ruff.enable": true,
  "ruff.organizeImports": true,
  "ruff.fixAll": true,
  "ruff.lint.enable": true,
  "ruff.format.args": []
}
```

### Extensions Needed

1. **Ruff** (charliermarsh.ruff) - Required ✅
2. **Python** (ms-python.python) - Required ✅
3. **Pylance** (ms-python.vscode-pylance) - Required ✅
4. **Even Better TOML** (tamasfe.even-better-toml) - Recommended for `pyproject.toml`
5. **YAML** (redhat.vscode-yaml) - Optional for YAML files

---

## Verification Steps

### 1. Check Extensions Installed

```bash
# In VSCode:
# Extensions panel (Ctrl+Shift+X)
# Ensure "Ruff" by charliermarsh is installed and enabled
```

### 2. Reload Window

```bash
# After installing/updating extensions:
Ctrl+Shift+P → "Developer: Reload Window"
```

### 3. Test Ruff Integration

1. Open any Python file in `custom_components/kidschores/`
2. Make a style error (e.g., add unused import)
3. Should see yellow squiggle immediately
4. Save file (Ctrl+S) - should auto-format
5. Check "Output" panel → Select "Ruff" to see activity

### 4. Test Linting Command

```bash
# Should work without errors now
./utils/quick_lint.sh
```

---

## Troubleshooting

### "Ruff not working in VSCode"

1. Check extension installed: Extensions → Search "Ruff" → Should show "charliermarsh.ruff" as installed
2. Check Output panel: View → Output → Select "Ruff" from dropdown
3. Reload window: Ctrl+Shift+P → "Developer: Reload Window"
4. Check settings: `.vscode/settings.json` should have `"ruff.enable": true`

### "Python interpreter warnings persist"

```bash
# Manually select interpreter:
Ctrl+Shift+P → "Python: Select Interpreter"
# Choose: /home/vscode/.local/ha-venv/bin/python3
```

### "TOML syntax not highlighted"

Install "Even Better TOML" extension:

```bash
Extensions (Ctrl+Shift+X) → Search "Even Better TOML" → Install
```

---

## What Changed vs Initial Config

### Removed (Deprecated)

```json
"ruff.importStrategy": "fromEnvironment"  // ❌ Not needed with native server
```

### Updated

```json
"python.defaultInterpreterPath": "/home/vscode/.local/ha-venv/bin/python3"  // ✅ Correct path
```

### No Change Needed

- All other ruff settings work correctly with native language server
- Format on save works
- Auto-organize imports works
- Linting works

---

## Status: All Issues Resolved ✅

- ✅ Deprecation warning fixed (removed obsolete setting)
- ✅ Python interpreter path corrected
- ✅ TOML extension recommendation clarified
- ✅ Configuration tested and working

**Next Step**: You should now be able to:

1. Save Python files and see auto-formatting
2. See inline ruff errors/warnings
3. Run `./utils/quick_lint.sh` successfully
4. Edit `pyproject.toml` with proper syntax highlighting (after installing TOML extension)

---

**Last Updated**: January 9, 2026
**Status**: Issues resolved, configuration working ✅
