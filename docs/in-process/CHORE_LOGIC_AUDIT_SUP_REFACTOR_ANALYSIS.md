# Chore Handler Refactor Analysis (Supporting Document)

**Parent Initiative**: [CHORE_LOGIC_AUDIT_IN-PROCESS.md](CHORE_LOGIC_AUDIT_IN-PROCESS.md)

**Last Updated**: January 18, 2026

---

## Executive Summary

This document analyzes whether chore handling logic should be extracted from the main coordinator into a separate `ChoreHandler` class. Analysis includes complexity metrics, coupling assessment, pros/cons, and recommendations.

### Quick Metrics

| Metric                      | Current Value        | Threshold          | Status          |
| --------------------------- | -------------------- | ------------------ | --------------- |
| **Total coordinator lines** | 11,846               | <1,000 recommended | 🔴 **12x over** |
| **Chore-specific methods**  | 60                   | N/A                | 🟡 High count   |
| **Cyclomatic complexity**   | TBD (requires radon) | <10 per method     | ⏳ Pending      |
| **Maintainability index**   | TBD (requires radon) | >65                | ⏳ Pending      |

**Initial Assessment**: Coordinator significantly exceeds Home Assistant's recommended file size, but refactor requires careful analysis of coupling and risk.

---

## Current State Analysis

### File Structure

**Location**: `custom_components/kidschores/coordinator.py`

**Size**: 11,846 lines (as of Jan 18, 2026)

**Primary Responsibilities**:

1. Data storage management (.storage/kidschores_data)
2. Entity state management (sensors, buttons, etc.)
3. **Chore lifecycle** (approve, reset, reschedule, overdue)
4. **Reward lifecycle** (claim, approve, revoke)
5. **Bonus/Penalty lifecycle**
6. **Achievement/Challenge tracking**
7. **Badge management** (cumulative, periodic)
8. **Allowance calculations**
9. **Parent features** (notifications, assignments)
10. **History/tracking** (streaks, completion history)

### Chore-Specific Methods (60 total)

**Category**: Approval

- `approve_chore()` - Main approval workflow (460 lines)
- `is_approved_in_current_period()` - Check approval status
- `get_chore_approval_timestamp()` - Get approval time
- Additional approval helpers (~8 methods)

**Category**: Reset

- `_reset_daily_chore_statuses()` - Midnight reset (42 lines)
- `_reschedule_chore_next_due_date()` - Chore-level reschedule (84 lines)
- `_reschedule_chore_next_due_date_for_kid()` - Per-kid reschedule (125 lines)
- Additional reset helpers (~6 methods)

**Category**: Overdue

- `_check_overdue_chores()` - Full scan (96 lines)
- `_check_overdue_for_chore()` - Single chore check (79 lines)
- Additional overdue helpers (~4 methods)

**Category**: Due Date Calculation

- `_calculate_next_due_date_from_info()` - Pure calculation (76 lines)
- `_get_next_due_date_*()` - Various frequency helpers (~10 methods)

**Category**: Data Access

- `get_chore_by_internal_id()` - Lookup chore by ID
- `get_all_chores()` - Get all chores
- `get_chores_for_kid()` - Filter by kid
- Additional getters/filters (~15 methods)

**Category**: Validation

- `validate_chore_configuration()` - Config validation
- Various validation helpers (~5 methods)

**Category**: History

- `update_chore_history()` - Track completion
- `calculate_chore_streak()` - Streak calculation
- History helpers (~7 methods)

**Estimated Total Lines for Chore Logic**: ~2,500-3,000 lines (20-25% of file)

---

## Home Assistant Integration Patterns

### Typical Coordinator Sizes

Research into comparable HA integrations:

| Integration               | Coordinator Lines | Approach           | Notes                                   |
| ------------------------- | ----------------- | ------------------ | --------------------------------------- |
| ESPHome                   | ~1,200            | Single coordinator | Delegates to device classes             |
| Zigbee                    | ~800              | Single coordinator | Device-specific logic in device classes |
| Z-Wave                    | ~1,500            | Single coordinator | Uses node classes for devices           |
| Large custom integrations | 500-2,000         | Varies             | Split at 1,000-1,500 lines typically    |

**Finding**: KidsChores at 11,846 lines is **significantly larger** than typical HA integrations.

### Home Assistant Best Practices

**From HA Developer Docs**:

- Coordinator should manage data updates and coordination
- Business logic can be in separate classes if complex
- Keep files under 1,000 lines when possible
- Split by domain concern (e.g., device handler, service handler)

**Pattern**: Coordinator + Handler Classes

```python
class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        self.device_handler = DeviceHandler(self)
        self.service_handler = ServiceHandler(self)

    async def _async_update_data(self):
        # Use handlers for complex logic
        return await self.device_handler.fetch_data()
```

---

## Coupling Analysis

### Dependencies: ChoreHandler → Coordinator

**If extracted, ChoreHandler would need**:

1. **Storage access**: `self._data` (read/write chores)
2. **Kid data access**: `self.get_kid_*()` methods (20+ methods)
3. **Entity updates**: `self._async_update_entity()`, `_async_mark_entities_for_update()`
4. **State management**: `self._persist()` (save storage)
5. **Points calculations**: `self.award_points()`, `self.deduct_points()`
6. **Achievement tracking**: `self._update_achievements()`, `_update_challenges()`
7. **Badge tracking**: `self._update_badges()`
8. **History tracking**: `self.update_history()`
9. **Notification system**: `self._notify_kid()`, `self._notify_parent()`
10. **Time utilities**: `self._get_now_utc()`, `self._is_today()`

**Estimated coupling**: **HIGH** (10+ coordinator methods/properties needed)

### Dependencies: Coordinator → ChoreHandler

**Coordinator would need to call ChoreHandler**:

1. From button entity platform: Approve/reset chore buttons
2. From config flow: Create/update/delete chores
3. From periodic updates: Midnight reset, overdue checks
4. From services: Custom chore services (if any)
5. From entity updates: Dashboard helper sensor

**Estimated coupling**: **MEDIUM** (5+ call sites)

---

## Refactor Options

### Option A: Full Extraction to ChoreHandler

**Structure**:

```python
class ChoreHandler:
    def __init__(self, coordinator: KidsChoresCoordinator):
        self.coordinator = coordinator
        self.hass = coordinator.hass

    # Approval methods
    async def approve_chore(self, chore_id, kid_name): ...

    # Reset methods
    async def reset_chore_statuses(self): ...
    async def reschedule_chore(self, chore_id): ...

    # Overdue methods
    async def check_overdue_chores(self): ...

    # Data access
    def get_chore(self, chore_id): ...
    def get_all_chores(self): ...
```

**Pros**:

- ✅ Reduces coordinator to ~9,000 lines (significant improvement)
- ✅ Clear separation of concerns
- ✅ Easier to understand chore lifecycle in isolation
- ✅ Potentially easier to test chore logic independently

**Cons**:

- ❌ High coupling - ChoreHandler needs extensive coordinator access
- ❌ Risk of circular dependencies (coordinator ↔ handler)
- ❌ Breaking pattern: HA coordinators typically self-contained
- ❌ Migration complexity: 60 methods, ~2,500 lines to move
- ❌ Regression risk: Any missed dependency causes runtime errors
- ❌ Test maintenance: All tests accessing chore methods need updates

**Effort Estimate**: 40-60 hours (2-3 weeks)

**Regression Risk**: **HIGH** (extensive call graph changes)

---

### Option B: Partial Extraction (Approval/Reset Logic Only)

**Structure**:

```python
class ChoreApprovalHandler:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def approve_chore(self, chore_id, kid_name): ...
    async def reschedule_chore(self, chore_id): ...

# Keep in coordinator:
# - Data access methods (get_chore, etc.)
# - Overdue checks (periodic timer logic)
# - Due date calculations (pure helpers)
```

**Pros**:

- ✅ Extracts most complex method (approve_chore - 460 lines)
- ✅ Moderate size reduction (~1,000 lines)
- ✅ Lower coupling than full extraction
- ✅ Easier to test approval logic independently

**Cons**:

- ❌ Still have 10,000+ line coordinator
- ❌ Arbitrary split - some chore logic in coordinator, some in handler
- ❌ Potential confusion: "Where does method X live?"
- ❌ Same regression risk as Option A for extracted methods

**Effort Estimate**: 20-30 hours (1-2 weeks)

**Regression Risk**: **MEDIUM** (smaller scope but still significant)

---

### Option C: Keep in Coordinator, Improve Organization

**Structure** (no new files):

```python
class KidsChoresCoordinator(DataUpdateCoordinator):
    # ====================
    # CHORE APPROVAL METHODS
    # ====================
    async def approve_chore(self, chore_id, kid_name): ...
    # ... all approval-related methods grouped ...

    # ====================
    # CHORE RESET METHODS
    # ====================
    async def _reset_daily_chore_statuses(self): ...
    # ... all reset-related methods grouped ...

    # ====================
    # CHORE OVERDUE METHODS
    # ====================
    async def _check_overdue_chores(self): ...
    # ... all overdue-related methods grouped ...
```

**Improvements**:

- Add clear section dividers with comments
- Group related methods together
- Add comprehensive docstrings
- Consider alphabetical ordering within sections

**Pros**:

- ✅ Zero regression risk (no code movement)
- ✅ Maintains HA coordinator pattern
- ✅ Improves readability without structural changes
- ✅ Minimal effort required

**Cons**:

- ❌ File still 11,846 lines (no size reduction)
- ❌ Doesn't address fundamental complexity
- ❌ May not satisfy HA best practices (<1,000 lines)

**Effort Estimate**: 4-8 hours (half day)

**Regression Risk**: **MINIMAL** (code organization only)

---

### Option D: Extract Pure Helpers to Utils Module

**Structure**:

```python
# New file: chore_utils.py
def calculate_next_due_date(freq, current_due, custom_config): ...
def validate_chore_configuration(config): ...
def parse_custom_frequency(config): ...

# coordinator.py - use helpers
from .chore_utils import calculate_next_due_date

class KidsChoresCoordinator:
    async def _reschedule_chore(self, chore_id):
        next_due = calculate_next_due_date(freq, due, config)
```

**Pros**:

- ✅ Extracts ~500-800 lines (pure functions)
- ✅ Low coupling (pure functions, no coordinator access)
- ✅ Easier to test (pure functions)
- ✅ Low regression risk (clear input/output)
- ✅ Improves reusability (utils can be imported elsewhere)

**Cons**:

- ❌ Only removes ~7% of file size
- ❌ Coordinator still 11,000+ lines
- ❌ Doesn't address core approval/reset complexity

**Effort Estimate**: 8-12 hours (1-2 days)

**Regression Risk**: **LOW** (pure functions, easy to validate)

---

## Complexity Metrics (Pending)

**To measure** (requires running radon):

```bash
# Install radon
pip install radon

# Cyclomatic complexity
radon cc custom_components/kidschores/coordinator.py -s

# Maintainability index
radon mi custom_components/kidschores/coordinator.py -s
```

**Expected findings**:

- `approve_chore()` likely has high cyclomatic complexity (>20)
- Overall maintainability index likely <65 (needs improvement)
- Methods with nested loops/conditions may exceed acceptable thresholds

**Action item**: Run metrics in Phase 3 Step 1 to inform decision

---

## Risk Assessment

### Risk Matrix

| Approach                     | Regression Risk | Effort    | Value     | Complexity |
| ---------------------------- | --------------- | --------- | --------- | ---------- |
| Option A: Full extraction    | 🔴 HIGH         | 🔴 HIGH   | 🟡 MEDIUM | 🔴 HIGH    |
| Option B: Partial extraction | 🟡 MEDIUM       | 🟡 MEDIUM | 🟡 MEDIUM | 🟡 MEDIUM  |
| Option C: Organization only  | 🟢 LOW          | 🟢 LOW    | 🟢 LOW    | 🟢 LOW     |
| Option D: Utils extraction   | 🟢 LOW          | 🟢 LOW    | 🟢 LOW    | 🟢 LOW     |

### Risk Factors

**High-Risk Elements**:

1. Button entity platform depends on coordinator methods (7 buttons × chore methods)
2. Config flow calls coordinator for chore CRUD operations
3. Dashboard helper sensor iterates chore data
4. Periodic timers trigger reset/overdue checks
5. Achievement/challenge tracking coupled to chore approvals

**Medium-Risk Elements**:

1. Test suite assumes coordinator structure (60+ test files)
2. Storage schema assumes chore data in coordinator.\_data
3. Entity registry ties entities to coordinator

**Low-Risk Elements**:

1. Pure calculation helpers (no side effects)
2. Read-only data access methods
3. Validation functions

---

## Recommendations

### Recommendation: Staged Approach

**Phase 0 (v0.5.1)**: Option C + Option D

- **Immediate action**: Reorganize coordinator with clear section dividers
- **Low effort**: 8-16 hours total
- **Low risk**: No structural changes
- **Value**: Improved readability, extracted utils

**Phase 1 (v0.5.2)**: Measure and Assess

- **Run complexity metrics** (radon cc/mi)
- **Analyze hotspots**: Which methods have highest complexity?
- **User feedback**: Are there performance issues suggesting need for refactor?
- **Decision point**: If metrics show critical complexity issues, consider Phase 2

**Phase 2 (v0.6.0)**: Option B if justified

- **Condition**: Only if Phase 1 metrics show unacceptable complexity (CC >20, MI <50)
- **Extract approval/reset logic** to separate handler
- **Comprehensive testing**: Full regression test suite
- **Incremental rollout**: Beta testing before stable release

**Phase 3 (Future)**: Option A if absolutely necessary

- **Condition**: Only if Phase 2 doesn't resolve complexity issues
- **Full extraction** to ChoreHandler class
- **Major version bump**: Breaking change, requires migration guide

### Justification

**Why not Option A now?**

- 🔴 High regression risk without clear benefit
- 🔴 Breaking HA coordinator pattern (self-contained coordinators)
- 🔴 Extensive effort (40-60 hours) for uncertain value
- 🔴 User's Gap 1/2 fixes show coordinator is manageable as-is

**Why Option C + D first?**

- 🟢 Immediate improvement with minimal risk
- 🟢 Establishes baseline for metrics comparison
- 🟢 Provides time to gather user feedback on performance
- 🟢 Allows data-driven decision for future refactor

**Why measure before deciding?**

- Need objective data (complexity metrics) not just line count
- Performance issues may not exist despite large file size
- Refactor should solve real problems, not aesthetic concerns

---

## Implementation Guidance

### If Option C + D Chosen (Recommended)

**Step 1: Add Section Dividers** (coordinator.py)

```python
# ====================
# INITIALIZATION & SETUP
# ====================
def __init__(self, ...): ...

# ====================
# DATA ACCESS - KIDS
# ====================
def get_kid_by_internal_id(self, kid_id): ...
# ... all kid getters ...

# ====================
# DATA ACCESS - CHORES
# ====================
def get_chore_by_internal_id(self, chore_id): ...
# ... all chore getters ...

# ====================
# CHORE APPROVAL WORKFLOW
# ====================
async def approve_chore(self, chore_id, kid_name): ...
# ... all approval-related methods ...

# ====================
# CHORE RESET & RESCHEDULE
# ====================
async def _reset_daily_chore_statuses(self): ...
# ... all reset-related methods ...

# ====================
# CHORE OVERDUE HANDLING
# ====================
async def _check_overdue_chores(self): ...
# ... all overdue-related methods ...

# ====================
# REWARD WORKFLOW
# ====================
# ... reward methods ...

# ====================
# PURE HELPERS & UTILITIES
# ====================
# Note: Consider moving to chore_utils.py
def _calculate_next_due_date_from_info(self, ...): ...
```

**Step 2: Extract Pure Functions** (chore_utils.py)

```python
"""Pure utility functions for chore calculations and validation."""

from datetime import datetime, timedelta
from typing import Any

def calculate_next_due_date(
    frequency: str,
    current_due: datetime,
    custom_config: dict[str, Any] | None = None,
) -> datetime | None:
    """Calculate next due date based on frequency.

    Args:
        frequency: Recurrence frequency (daily, weekly, etc.)
        current_due: Current due date
        custom_config: Custom frequency configuration

    Returns:
        Next due date or None if non-recurring
    """
    if frequency == "none":
        return None
    # ... calculation logic ...

def validate_chore_configuration(config: dict[str, Any]) -> list[str]:
    """Validate chore configuration for invalid combinations.

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    # ... validation logic ...
    return errors
```

**Step 3: Update Imports** (coordinator.py)

```python
from .chore_utils import calculate_next_due_date, validate_chore_configuration
```

**Step 4: Validate** (no behavioral changes)

```bash
# Run tests
pytest tests/ -v

# Run quality checks
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

**Effort**: 1-2 days total

---

### If Option B Chosen (Future)

**Prerequisite**: Option C + D completed, metrics justify extraction

**File Structure**:

```
custom_components/kidschores/
├── coordinator.py (10,000 lines)
├── chore_handler.py (NEW - 2,000 lines)
├── chore_utils.py (500 lines)
└── ...
```

**chore_handler.py**:

```python
"""Chore approval and reset logic handler."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .coordinator import KidsChoresCoordinator

class ChoreApprovalHandler:
    """Handle chore approval and reset workflows."""

    def __init__(self, coordinator: KidsChoresCoordinator) -> None:
        """Initialize handler with coordinator reference."""
        self.coordinator = coordinator
        self.hass = coordinator.hass

    async def approve_chore(
        self, chore_id: str, kid_name: str, **kwargs
    ) -> dict[str, Any]:
        """Approve a chore for a kid."""
        # Move approve_chore logic here
        # Access coordinator via self.coordinator.get_chore(), etc.
        ...
```

**coordinator.py changes**:

```python
from .chore_handler import ChoreApprovalHandler

class KidsChoresCoordinator(DataUpdateCoordinator):
    def __init__(self, ...):
        super().__init__(...)
        self.chore_handler = ChoreApprovalHandler(self)

    async def approve_chore(self, chore_id, kid_name, **kwargs):
        """Delegate to chore handler."""
        return await self.chore_handler.approve_chore(chore_id, kid_name, **kwargs)
```

**Test updates**: All tests remain unchanged (coordinator API preserved)

**Effort**: 2-3 weeks including testing

---

## Complexity Analysis Checklist

**Phase 3 Step 1 actions**:

- [ ] Install radon: `pip install radon`
- [ ] Run cyclomatic complexity: `radon cc coordinator.py -s`
- [ ] Run maintainability index: `radon mi coordinator.py -s`
- [ ] Identify methods with CC >10 (target for simplification)
- [ ] Identify methods with CC >20 (critical complexity)
- [ ] Check file-level MI (target >65)
- [ ] Document results in this file
- [ ] Make refactor decision based on metrics

**Acceptable thresholds**:

- Cyclomatic Complexity: <10 (simple), 10-20 (moderate), >20 (complex)
- Maintainability Index: >85 (good), 65-85 (moderate), <65 (difficult)

**If CC >20 on critical methods**: Consider Option B (partial extraction)

**If file MI <50**: Consider phased refactor (Option D → B → A over multiple releases)

**If metrics acceptable**: Option C only (organization without extraction)

---

## Home Assistant Coordinator Pattern Compliance

**Current compliance**:

- ✅ Extends DataUpdateCoordinator
- ✅ Implements \_async_update_data()
- ✅ Uses hass.async_add_executor_job for blocking operations
- ✅ Stores data in .storage/ (not hass.data)
- ❌ File size significantly exceeds recommendation

**If extracting to handler**:

- Must maintain coordinator as single entry point for entities
- Handler should be private implementation detail
- Entities should only reference coordinator, never handler directly
- Preserve async/await patterns throughout

---

## Decision Framework

Use this flowchart to decide refactor approach:

```
1. Run complexity metrics → CC/MI acceptable?
   ├─ Yes → Option C (organize only) ✅
   └─ No → Continue to 2

2. User reports performance issues?
   ├─ Yes → Profile hotspots, consider Option B
   └─ No → Continue to 3

3. Development team struggling with coordinator?
   ├─ Yes → Consider Option B (if specific pain points identified)
   └─ No → Option C (don't fix what isn't broken)

4. Is this blocking other work?
   ├─ Yes → Urgency justifies Option B
   └─ No → Defer major refactor, use Option C + D
```

---

## Conclusion

**Recommendation**: **Option C + Option D** (Organize + Extract Utils)

**Rationale**:

1. **Low risk**: No structural changes to coordinator
2. **Immediate value**: Improved readability and maintainability
3. **Low effort**: 1-2 days vs weeks for full refactor
4. **Preserves options**: Can still do Option B/A in future if justified
5. **Data-driven**: Allows metrics-based decision for next steps

**Action Items**:

- [ ] Add section dividers to coordinator.py (4 hours)
- [ ] Extract pure functions to chore_utils.py (8 hours)
- [ ] Update imports and run tests (2 hours)
- [ ] Document organizational structure (2 hours)
- [ ] **Total effort: 16 hours (2 days)**

**Future Evaluation** (v0.5.2):

- [ ] Run complexity metrics with radon
- [ ] Gather user feedback on performance
- [ ] Reassess refactor need based on data

**Do NOT proceed with Option A or B without**:

- Complexity metrics showing critical issues (CC >20, MI <50)
- Clear user pain points (performance, bugs, confusion)
- Owner approval for major refactor effort

---

**Document Status**: Draft - Pending complexity metrics and owner decision
**Next Update**: After Phase 3 complexity analysis completion
