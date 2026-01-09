# Ruff Migration Guide - KidsChores Integration

**Migration Date**: January 9, 2026
**From**: Pylint + custom linting scripts
**To**: Ruff (following Home Assistant core practices)

## Why Ruff?

Ruff is **10-50x faster** than pylint while providing the same (or better) checks:

- **Speed**: < 5 seconds vs 22+ seconds for full lint
- **Auto-fix**: Automatically fixes most issues
- **Modern**: Uses latest Python best practices
- **Home Assistant Standard**: Matches core's tooling

## Quick Start

### 1. Install Ruff (if not already installed)

```bash
# Via pip
pip install ruff

# Via uv (faster)
uv pip install ruff
```

### 2. VSCode Extension

Install the official **Ruff extension** by Astral:

- Open VSCode Extensions (`Ctrl+Shift+X`)
- Search for "Ruff"
- Install "Ruff" by charliermarsh

The extension is already configured in `.vscode/settings.json`.

### 3. Basic Usage

```bash
# Check all code (< 5 seconds)
./utils/quick_lint.sh

# Auto-fix issues
./utils/quick_lint.sh --fix

# Check specific file
ruff check custom_components/kidschores/sensor.py

# Format specific file
ruff format custom_components/kidschores/sensor.py
```

## What Changed

### Configuration

| Old                   | New                            | Notes                 |
| --------------------- | ------------------------------ | --------------------- |
| `pyrightconfig.json`  | `pyproject.toml`               | Consolidated config   |
| `pytest.ini`          | `pyproject.toml`               | Pytest config section |
| `utils/lint_check.py` | `ruff check`                   | Direct ruff usage     |
| Custom pylint rules   | Ruff rules in `pyproject.toml` | Simpler               |

### Linting Commands

| Old                          | New                                  | Speed              |
| ---------------------------- | ------------------------------------ | ------------------ |
| `./utils/quick_lint.sh`      | `./utils/quick_lint.sh`              | 22s → 5s           |
| `python utils/lint_check.py` | `ruff check custom_components tests` | 22s → 2s           |
| `pylint file.py`             | `ruff check file.py`                 | Variable → instant |

### Pre-commit Hooks

Now using standard pre-commit with ruff:

```bash
# Install hooks (one-time)
pre-commit install

# Run manually
pre-commit run --all-files
```

## Ruff Configuration

### Key Rules Enabled

Based on Home Assistant's `pyproject.toml`:

```toml
[tool.ruff.lint]
select = [
  "E",      # pycodestyle errors
  "F",      # pyflakes
  "UP",     # pyupgrade (Python modernization)
  "B",      # flake8-bugbear
  "SIM",    # flake8-simplify
  "I",      # isort (import sorting)
  "PL",     # pylint equivalents
  "RUF",    # Ruff-specific rules
  # ... many more
]
```

### Key Rules Ignored

```toml
ignore = [
  "E501",     # line too long (formatter handles this)
  "PLR0911",  # Too many return statements
  "PLR0912",  # Too many branches
  "PLR0913",  # Too many arguments
  # ... reasonable complexity allowances
]
```

### Per-File Ignores

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = [
  "S101",     # Use of assert (required in tests!)
  "PLR2004",  # Magic values (acceptable in tests)
]
```

## Common Migration Issues

### 1. Import Sorting

**Old** (manual):

```python
from pathlib import Path
import json
from homeassistant.core import HomeAssistant
```

**New** (ruff auto-fixes):

```python
import json
from pathlib import Path

from homeassistant.core import HomeAssistant
```

**Fix**: Run `ruff check --fix`

### 2. F-strings Without Placeholders

**Old**:

```python
message = f"Starting integration"  # F541
```

**New**:

```python
message = "Starting integration"
```

**Fix**: Auto-fixed by ruff or convert to regular string

### 3. Unused Imports

**Old** (pylint: W0611):

```python
from typing import Any, Dict  # Dict unused
```

**New**:

```python
from typing import Any
```

**Fix**: Ruff removes automatically with `--fix`

### 4. Module-Level Suppressions

**Old** (pylint):

```python
# pylint: disable=protected-access
```

**New** (ruff):

```python
# ruff: noqa: SLF001
```

Or at file top:

```python
# ruff: noqa: SLF001
```

## Workflow Changes

### Before (Pylint Era)

```bash
# 1. Write code
# 2. Run lint (22 seconds)
./utils/quick_lint.sh --fix

# 3. Manually fix remaining issues
# 4. Run tests
python -m pytest tests/ -v
```

### Now (Ruff Era)

```bash
# 1. Write code (VSCode auto-formats on save!)
# 2. Run lint (5 seconds)
./utils/quick_lint.sh --fix

# 3. Most issues auto-fixed already!
# 4. Run tests
python -m pytest tests/ -v
```

## VSCode Integration

With the `.vscode/settings.json` in place:

✅ **Format on save** - Ruff formats automatically
✅ **Auto-imports** - Organize imports on save
✅ **Inline errors** - See issues as you type
✅ **Quick fixes** - Click lightbulb to fix issues

## Pre-commit Integration

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```

Then:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files

# Hooks run automatically on commit
git commit -m "feat: new feature"  # Ruff runs first!
```

## Testing Impact

### Test Files

Ruff is **more permissive** for tests:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = [
  "S101",     # assert is required in tests!
  "PLR2004",  # Magic values OK in test data
  "PLR0912",  # Complex tests allowed
]
```

### Migration Checklist

- [x] Remove old `pylint` module-level comments
- [x] Replace with `# ruff: noqa` if needed (rare)
- [x] Run `ruff check --fix tests/` to auto-fix
- [x] Run full test suite to verify
- [x] Update documentation

## Performance Comparison

Real-world timings on KidsChores codebase (30 Python files):

| Operation                    | Pylint        | Ruff     | Speedup         |
| ---------------------------- | ------------- | -------- | --------------- |
| Full lint check              | 22s           | 5s       | **4.4x faster** |
| Single file check            | 0.8s          | 0.05s    | **16x faster**  |
| Auto-fix trailing whitespace | Manual script | Built-in | N/A             |
| Import sorting               | Manual        | Auto     | N/A             |

## FAQ

**Q: Do I need to keep pylint installed?**
A: No, ruff replaces pylint entirely.

**Q: What about mypy/type checking?**
A: Keep mypy for type checking. Ruff doesn't do type analysis (yet).

**Q: Can I still use # pylint: disable comments?**
A: No, replace with `# ruff: noqa: CODE` or `# type: ignore` for type issues.

**Q: Does this match Home Assistant standards?**
A: Yes! Our config is based directly on HA core's `pyproject.toml`.

**Q: What if ruff is too strict?**
A: Add specific rules to `ignore` list in `pyproject.toml`.

## Troubleshooting

### Ruff Not Running in VSCode

1. Check extension is installed: "Ruff" by charliermarsh
2. Reload window: `Ctrl+Shift+P` → "Developer: Reload Window"
3. Check output: View → Output → Select "Ruff"

### Pre-commit Hook Fails

```bash
# Update hooks
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

### Code Still Has Issues After --fix

Some issues can't be auto-fixed:

- Complex logic issues (PLR rules)
- Type-related issues
- Design pattern issues

Review ruff output and fix manually.

## Additional Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ruff Rules Reference](https://docs.astral.sh/ruff/rules/)
- [Home Assistant Ruff Config](https://github.com/home-assistant/core/blob/dev/pyproject.toml)
- [Migrating from Pylint to Ruff](https://docs.astral.sh/ruff/faq/#how-does-ruff-compare-to-pylint)

## Support

If you encounter issues:

1. Check this guide first
2. Review Home Assistant core's ruff config
3. Search ruff documentation
4. Ask in Home Assistant developer community

---

**Last Updated**: January 9, 2026
**Status**: Migration complete ✅
