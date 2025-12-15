# Linting Tool Updates - December 2025

## Overview

Updated linting tools to clarify acceptable warnings vs critical errors, and added comprehensive guidance on suppressing false positives.

## Changes Made

### 1. lint_check.py - Core Script Updates

**Module Docstring** - Added clarity on acceptable warnings:

- Line length over 100 chars acceptable if improves readability
- Severity 2 pylint warnings acceptable (too-many-lines, import-outside-toplevel)
- Added suppression pattern examples

**check_long_lines()** - Enhanced output:

- Now states "(acceptable if improves readability)" in warning message
- Added blue info messages explaining it's WARNING only, not a failure
- Clearly states this follows testing instructions

**Final Summary** - Added suppression guidance:

- Shows how to use `# type: ignore[return-value]` for flexible return types
- Shows how to use `# pylint: disable=<code>  # Reason` inline
- Shows module-level suppression pattern
- Clarifies that line length and severity 2 warnings don't cause failure

### 2. README_LINTING.md - Documentation Updates

**New Section: "Suppressing False Positives"** with specific examples:

#### Type Errors - Flexible Return Types

```python
# For helper functions like parse_datetime_to_utc that intentionally return multiple types
def parse_datetime_to_utc(value: Any) -> datetime | date | str | None:
    ...

# At usage site when you know the specific type
result = parse_datetime_to_utc(some_value)
if isinstance(result, datetime):
    # type: ignore[arg-type]  # parse_datetime_to_utc returns datetime here
    use_datetime(result)
```

#### PyLint Warnings

```python
# Inline suppression with reason
result = _internal_function()  # pylint: disable=protected-access  # Testing internal API

# Module-level suppression (after docstring, before imports)
"""Test module for config flow."""
# pylint: disable=protected-access  # This test module accesses internal APIs
```

#### When to Suppress - Clear Guidelines

✅ **Suppress when**:

- Intentional design choice (e.g., flexible return types)
- Testing requires access to internals
- Known limitation of static analysis tools
- Long lines improve readability

❌ **Don't suppress when**:

- Actual bugs or type mismatches
- Code can be refactored to satisfy checker
- Unclear why error occurs (investigate first)

## Key Principles

1. **Line Length**: Acceptable if breaking the line hurts readability (complex f-strings, long function signatures)

2. **Type Errors in Helper Functions**: Many datetime helper functions in kc_helpers.py intentionally return multiple types (datetime | date | str | None) for flexibility. At usage sites, add `# type: ignore[arg-type]` when you know the specific type being returned.

3. **Testing Patterns**: Module-level suppressions for `protected-access` and `redefined-outer-name` are standard in test files.

4. **Severity 2 Warnings**: Always acceptable - tool doesn't fail on these.

## Validation

```bash
# Run the linting tool on itself
python utils/lint_check.py --file utils/lint_check.py
```

Result:

- ✅ Pylint: 9.84/10
- ✅ Type errors: 0
- ✅ Trailing whitespace: None
- ⚠️ 2 lines over 100 chars (acceptable - improves readability)
- ✅ Exit code: 0 (PASSED)

## Impact on Development Workflow

**Before**: Confusion about whether line length warnings should block commits
**After**: Clear that line length is informational only

**Before**: Unclear how to handle intentional flexible return types in helper functions
**After**: Clear pattern: `# type: ignore[arg-type]` with explanatory comment

**Before**: Every type error treated as critical
**After**: Distinction between bugs vs intentional design choices

## Next Steps

When fixing type errors in kc_helpers.py:

1. Review each error to determine if it's a bug or intentional design
2. For intentional flexible return types: Add `# type: ignore[return-value]` to function
3. For usage sites: Add `# type: ignore[arg-type]` where you know the specific type
4. For actual bugs: Fix the code
