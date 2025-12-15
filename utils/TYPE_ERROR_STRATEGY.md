# Handling Type Errors in kc_helpers.py - Quick Reference

## The Situation

The comprehensive linting revealed ~160 type errors, primarily in `kc_helpers.py`. Most are NOT bugs, but intentional design choices for flexible helper functions.

## Root Cause: Intentionally Flexible Return Types

Many datetime helper functions are designed to handle multiple input types and return multiple output types for maximum flexibility:

```python
def parse_datetime_to_utc(value: Any) -> datetime | date | str | None:
    """Parse various datetime formats to UTC-aware datetime.

    Returns:
    - datetime: When successfully parsed
    - date: When only date available (no time component)
    - str: When value is already ISO string
    - None: When value is None or invalid
    """
```

This is **intentional design** to handle Home Assistant's varied datetime representations.

## Solution Strategy

### 1. For Helper Functions with Flexible Returns

Add `# type: ignore[return-value]` to the function definition:

```python
def parse_datetime_to_utc(value: Any) -> datetime | date | str | None:
    """Parse various datetime formats."""
    # type: ignore[return-value]  # Intentionally returns multiple types for flexibility
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return value  # Return date as-is
    if isinstance(value, str):
        return value  # Return ISO string
    return None
```

### 2. For Usage Sites (Caller Code)

When you know the specific type being returned, add inline suppression:

```python
# You know this will return datetime because input is datetime
result = parse_datetime_to_utc(user_input_datetime)
if isinstance(result, datetime):
    days_diff = (result - now).days  # type: ignore[arg-type]  # result is datetime here
```

OR use type guards:

```python
result = parse_datetime_to_utc(value)
if isinstance(result, datetime):
    # Type checker now knows result is datetime
    use_as_datetime(result)
elif isinstance(result, date):
    # Type checker now knows result is date
    use_as_date(result)
```

### 3. For Actual Type Mismatches (Real Bugs)

Fix the code:

```python
# ❌ Wrong - adding timedelta to string
end_date = start_date + timedelta(days=7)  # If start_date is str

# ✅ Right - ensure it's datetime first
start_dt = parse_datetime_to_utc(start_date)
if isinstance(start_dt, datetime):
    end_date = start_dt + timedelta(days=7)
```

## Priority Order for Fixes

1. **High Priority**: Fix actual bugs (operations on wrong types)
2. **Medium Priority**: Add suppressions to helper function definitions
3. **Low Priority**: Add suppressions at usage sites (often type guards handle this)

## Examples from kc_helpers.py

### Common Pattern 1: Date/DateTime Operations

```python
def calculate_days_difference(start: date | datetime, end: date | datetime) -> int:
    """Calculate difference between dates."""
    # type: ignore[operator]  # Supports both date and datetime subtraction
    return (end - start).days
```

### Common Pattern 2: Optional DateTime Returns

```python
def get_last_update_time(entity_data: dict) -> datetime | None:
    """Get last update time from entity."""
    # type: ignore[return-value]  # Returns datetime or None
    value = entity_data.get("last_updated")
    return parse_datetime_to_utc(value) if value else None
```

### Common Pattern 3: String or DateTime

```python
def format_for_storage(dt: datetime | date | str) -> str:
    """Convert to ISO string for JSON storage."""
    # type: ignore[arg-type]  # Handles multiple input types
    if isinstance(dt, datetime):
        return dt.isoformat()
    if isinstance(dt, date):
        return dt.isoformat()
    return dt  # Already string
```

## Testing After Fixes

```bash
# Run comprehensive linting
./utils/quick_lint.sh

# Should show:
# - Pylint scores 9.4+ (unchanged)
# - Type errors significantly reduced or with suppressions
# - Exit code 0 (success)

# Verify tests still pass
python -m pytest tests/ -v
```

## When in Doubt

1. **Is this a design choice or a bug?**

   - Design choice → Add suppression with comment explaining why
   - Bug → Fix the code

2. **Can I use type guards instead?**

   - Yes → Prefer type guards (better than suppressions)
   - No → Use `# type: ignore[specific-error]` with comment

3. **Is the suppression too broad?**
   - Use specific error codes: `[arg-type]`, `[return-value]`, `[operator]`
   - Never use bare `# type: ignore` (too broad)

## Key Principle

**Flexible helpers are a feature, not a bug.** Home Assistant entities return varied datetime representations. Our helpers accommodate this reality. Type checkers see it as an error; we document it as intentional with suppressions.
