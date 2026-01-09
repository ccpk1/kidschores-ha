# Ruff Quick Reference

**One-page cheat sheet for daily use**

## 🚀 Common Commands

```bash
# Check all code (< 5 seconds)
./utils/quick_lint.sh

# Auto-fix all issues
./utils/quick_lint.sh --fix

# Check specific file
ruff check path/to/file.py

# Format specific file
ruff format path/to/file.py

# Check + format with auto-fix
ruff check --fix path/to/file.py && ruff format path/to/file.py
```

## 📝 Common Error Codes

| Code        | Meaning                           | Fix                                 |
| ----------- | --------------------------------- | ----------------------------------- |
| **F401**    | Unused import                     | Remove import or use `# noqa: F401` |
| **F841**    | Unused variable                   | Remove or prefix with `_`           |
| **F541**    | f-string without placeholders     | Use regular string                  |
| **E501**    | Line too long                     | Break line or ignore                |
| **I001**    | Imports not sorted                | Run with `--fix`                    |
| **B904**    | Missing `raise from`              | Add `from err`                      |
| **UP**      | Use modern Python syntax          | Run with `--fix` or update code     |
| **PLC0415** | Import not at top                 | Move import or ignore               |
| **SLF001**  | Private member access             | Add `# noqa: SLF001`                |
| **TC002**   | Import should be in TYPE_CHECKING | Add to TYPE_CHECKING block          |

## 🔧 Suppression Patterns

### Single line

```python
from typing import Any  # noqa: F401  # Needed for type hints

coordinator._persist()  # ruff: noqa: SLF001
```

### Multiple rules on one line

```python
value = magic_number  # noqa: PLR2004, PLR0912
```

### Entire file

```python
# ruff: noqa: SLF001, PLC0415
"""Module docstring."""

# Then your imports and code...
```

### Specific section

```python
# ruff: noqa
# This section has many intentional violations
complex_legacy_code()
# ruff: noqa
```

## 🎨 Format on Save (VSCode)

Already configured in `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

Just save the file (`Ctrl+S`) and ruff formats automatically!

## 🪝 Pre-commit Hooks

```bash
# One-time setup
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Update hooks to latest
pre-commit autoupdate

# Bypass for emergency commits
git commit --no-verify -m "message"
```

## 📦 Installation

```bash
# Via pip
pip install ruff

# Via uv (faster)
uv pip install ruff

# Check version
ruff --version  # Should be >= 0.13.0
```

## 🔍 Diagnostics

```bash
# Show all rules
ruff linter

# Explain specific rule
ruff rule F401

# Show config being used
ruff config

# Show ignored files
ruff check --statistics
```

## 🏗️ VSCode Integration

**Required Extension**: `charliermarsh.ruff`

### Verify It's Working

1. Open a Python file
2. Make a style error (e.g., unused import)
3. Should see yellow squiggle instantly
4. Save file (`Ctrl+S`) - should auto-format

### Troubleshooting

```bash
# View → Output → Select "Ruff"
# Check for errors there

# If not working, reload window:
# Ctrl+Shift+P → "Developer: Reload Window"
```

## 📚 Quick Config Changes

Edit `pyproject.toml`:

```toml
[tool.ruff.lint]
ignore = [
  "E501",     # Line too long
  "PLR0913",  # Too many arguments
  # Add your rule here
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
  "S101",     # assert allowed in tests
]
```

## ⚡ Performance Tips

```bash
# Check only changed files (fastest)
git diff --name-only | grep "\.py$" | xargs ruff check

# Parallel checking (automatic in ruff)
ruff check .  # Uses all CPU cores

# Cache is at .ruff_cache/ - delete if issues
rm -rf .ruff_cache/
```

## 🆘 Emergency: Disable Ruff Temporarily

### VSCode

```json
// .vscode/settings.json
{
  "ruff.enable": false
}
```

### CLI

```bash
# Bypass quick_lint.sh
python -m pytest tests/ -v  # Just run tests
```

### Pre-commit

```bash
git commit --no-verify  # Skip all hooks
```

## 📖 Learning Resources

- **Rules**: https://docs.astral.sh/ruff/rules/
- **Config**: https://docs.astral.sh/ruff/configuration/
- **VSCode**: https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff
- **Home Assistant Example**: https://github.com/home-assistant/core/blob/dev/pyproject.toml

## 🎯 Daily Workflow

```bash
# 1. Write code (VSCode auto-formats on save)

# 2. Before commit:
./utils/quick_lint.sh --fix

# 3. Review auto-fixes (git diff)

# 4. Run tests
python -m pytest tests/ -v

# 5. Commit (pre-commit hooks run automatically)
git commit -m "feat: your feature"
```

## ✅ Definition of Done

Before marking work complete:

```bash
# Both must pass:
./utils/quick_lint.sh           # ✅ No ruff errors
python -m pytest tests/ -v      # ✅ All tests pass
```

---

**Keep this handy!** Print or bookmark for quick reference.
