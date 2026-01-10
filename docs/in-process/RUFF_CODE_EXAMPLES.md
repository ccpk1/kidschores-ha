# Ruff Code Examples - Before & After

Real examples from KidsChores showing how code changes with ruff.

## 1. Import Sorting (I001)

### ❌ Before (unsorted)

```python
from pathlib import Path
import json
from homeassistant.core import HomeAssistant
import logging
from homeassistant.config_entries import ConfigEntry
from . import const
```

### ✅ After (ruff --fix)

```python
import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import const
```

**Rule**: Standard library → Third party → Local imports, each group sorted alphabetically.

---

## 2. Protected Access in Tests (SLF001)

### ❌ Before (error without suppression)

```python
def test_persist():
    """Test coordinator persistence."""
    coordinator._persist()  # SLF001: Private member accessed
```

### ✅ After (with suppression)

```python
def test_persist():
    """Test coordinator persistence."""
    coordinator._persist()  # ruff: noqa: SLF001
```

Or file-level for multiple uses:

```python
# ruff: noqa: SLF001
"""Test module docstring."""

def test_persist():
    coordinator._persist()  # Now OK

def test_data():
    data = coordinator._data  # Also OK
```

---

## 3. F-strings Without Placeholders (F541)

### ❌ Before

```python
message = f"Starting integration"  # F541
logger.info(f"Setup complete")    # F541
```

### ✅ After

```python
message = "Starting integration"  # Regular string
logger.info("Setup complete")     # Regular string
```

Only use f-strings when you have placeholders:

```python
# ✅ Good - has placeholder
logger.info(f"Kid {kid_name} earned {points} points")
```

---

## 4. Unused Imports (F401)

### ❌ Before

```python
from typing import Any, Dict, List  # Dict unused
from homeassistant.core import HomeAssistant, callback  # callback unused
```

### ✅ After (ruff --fix auto-removes)

```python
from typing import Any, List
from homeassistant.core import HomeAssistant
```

---

## 5. Unused Variables (F841)

### ❌ Before

```python
def process_data():
    result = fetch_data()  # F841: Assigned but never used
    return True
```

### ✅ After (Option 1: Remove)

```python
def process_data():
    fetch_data()  # Just call it
    return True
```

### ✅ After (Option 2: Use underscore)

```python
def process_data():
    _result = fetch_data()  # Underscore prefix = intentionally unused
    return True
```

---

## 6. Missing `raise from` (B904)

### ❌ Before

```python
try:
    data = await client.fetch()
except ClientError:
    raise HomeAssistantError("Failed to fetch")  # B904
```

### ✅ After

```python
try:
    data = await client.fetch()
except ClientError as err:
    raise HomeAssistantError("Failed to fetch") from err
```

**Why**: Preserves the original exception traceback for debugging.

---

## 7. Type Checking Imports (TC002)

### ❌ Before (runtime import not needed)

```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

def my_function(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Only use for type hints, not runtime."""
    pass
```

### ✅ After

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

def my_function(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    """Now imports only when type checking."""
    pass
```

**Note**: Only do this if imports are ONLY used for type hints, not at runtime.

---

## 8. Import Position (PLC0415)

### ❌ Before (import inside function)

```python
def cleanup(hass: HomeAssistant) -> None:
    """Clean up devices."""
    from homeassistant.helpers import device_registry as dr  # PLC0415

    registry = dr.async_get(hass)
```

### ✅ After (Option 1: Move to top)

```python
from homeassistant.helpers import device_registry as dr

def cleanup(hass: HomeAssistant) -> None:
    """Clean up devices."""
    registry = dr.async_get(hass)
```

### ✅ After (Option 2: Suppress if intentional)

```python
def cleanup(hass: HomeAssistant) -> None:
    """Clean up devices."""
    from homeassistant.helpers import device_registry as dr  # noqa: PLC0415
    # Intentionally here to avoid circular import

    registry = dr.async_get(hass)
```

---

## 9. Modern Python Syntax (UP)

### ❌ Before (old-style)

```python
from typing import Dict, List, Optional

def process(data: Optional[Dict[str, List[int]]]) -> List[str]:
    results: List[str] = []
    if data is not None:
        pass
    return results
```

### ✅ After (ruff --fix for some, manual for others)

```python
from typing import Optional  # Can't auto-fix to | None with Optional still used

def process(data: dict[str, list[int]] | None) -> list[str]:
    results: list[str] = []
    if data is not None:
        pass
    return results
```

Or even better (Python 3.13+):

```python
def process(data: dict[str, list[int]] | None) -> list[str]:
    results = []  # Type inferred
    if data is not None:
        pass
    return results
```

---

## 10. Line Length (E501) - Usually Ignored

### ❌ Before (too long)

```python
some_very_long_variable_name = some_function_call(argument1, argument2, argument3, argument4, argument5)
```

### ✅ After (formatted)

```python
some_very_long_variable_name = some_function_call(
    argument1,
    argument2,
    argument3,
    argument4,
    argument5,
)
```

**Note**: `ruff format` handles this automatically!

---

## 11. Pytest Assert in Non-Test (S101)

### ❌ Before (in production code)

```python
# custom_components/kidschores/coordinator.py
def validate_data(data):
    assert data is not None  # S101: Use of assert
    return data
```

### ✅ After

```python
def validate_data(data):
    if data is None:
        raise ValueError("Data cannot be None")
    return data
```

**Note**: Asserts are OK in tests! Tests auto-configured to allow S101.

---

## 12. Magic Numbers (PLR2004) - Often Ignored in Tests

### ❌ Before (magic number)

```python
if points > 100:  # PLR2004: Magic value
    level = "advanced"
```

### ✅ After (Option 1: Constant)

```python
ADVANCED_THRESHOLD = 100

if points > ADVANCED_THRESHOLD:
    level = "advanced"
```

### ✅ After (Option 2: Suppress in tests)

```python
# In test file - this is OK
def test_points():
    assert kid_points > 100  # noqa: PLR2004
```

---

## 13. Module-Level Suppressions (Common in Tests)

### Old Style (Pylint)

```python
"""Test module."""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import pytest
```

### New Style (Ruff)

```python
"""Test module."""

# ruff: noqa: SLF001, PLW0621

import pytest
```

Or more explicit:

```python
"""Test module.

Suppressions:
- SLF001: Protected access needed to test internal methods
- PLW0621: Pytest fixtures intentionally redefine names
"""

# ruff: noqa: SLF001, PLW0621

import pytest
```

---

## 14. Complex Example: Full File Transformation

### Before (Pylint era)

```python
"""Helper module."""

# pylint: disable=protected-access
# pylint: disable=too-many-arguments

import json
from typing import Dict, List, Optional
from pathlib import Path
from homeassistant.core import HomeAssistant
import logging

_LOGGER = logging.getLogger(__name__)

def process_data(hass: HomeAssistant, data: Optional[Dict[str, List[int]]], threshold: int = 100) -> List[str]:
    """Process data."""
    results: List[str] = []
    if data is not None:
        for key, values in data.items():
            if len(values) > threshold:  # Magic number
                results.append(f"Key: {key}")
    return results
```

### After (Ruff era)

```python
"""Helper module.

Suppressions:
- SLF001: Protected access for testing internal state
"""

# ruff: noqa: SLF001

import json
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

THRESHOLD_DEFAULT = 100


def process_data(
    hass: HomeAssistant,
    data: dict[str, list[int]] | None,
    threshold: int = THRESHOLD_DEFAULT,
) -> list[str]:
    """Process data and return matching keys."""
    results = []
    if data is not None:
        for key, values in data.items():
            if len(values) > threshold:
                results.append(f"Key: {key}")
    return results
```

**Changes**:

- Imports sorted automatically
- Modern type hints (`dict` vs `Dict`, `| None` vs `Optional`)
- Magic number extracted to constant
- Ruff suppression syntax
- Better docstring
- Auto-formatted by ruff

---

## Quick Migration Checklist

When you run `./utils/quick_lint.sh --fix`, most issues auto-fix:

- ✅ Import sorting (I001)
- ✅ Unused imports (F401)
- ✅ F-strings without placeholders (F541)
- ✅ Some UP rules (modern syntax)

Needs manual attention:

- ⚠️ Protected access (SLF001) - Add `# noqa: SLF001`
- ⚠️ Import position (PLC0415) - Move or suppress
- ⚠️ Type checking imports (TC002) - Refactor or suppress
- ⚠️ Missing `raise from` (B904) - Add `from err`

---

**Pro Tip**: Run with `--fix` first, then handle remaining issues one by one!
