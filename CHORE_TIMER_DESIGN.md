# Chore Timer Processing: From-Scratch Design

## Approval Reset: The Gatekeeper

**Critical Insight**: Approval reset is the **gatekeeper** that determines when rescheduling occurs. Rescheduling is NOT a parallel operation - it's triggered BY approval reset after the reset completes.

### Approval Reset Timing Options

| Type                | Trigger              | When Reschedule Happens                       |
| ------------------- | -------------------- | --------------------------------------------- |
| `AT_MIDNIGHT_ONCE`  | Midnight timer       | After approval reset at midnight              |
| `AT_MIDNIGHT_MULTI` | Midnight timer       | After approval reset at midnight              |
| `AT_DUE_DATE_ONCE`  | Due date passes      | After approval reset at due date              |
| `AT_DUE_DATE_MULTI` | Due date passes      | After approval reset at due date              |
| `UPON_COMPLETION`   | In approval workflow | Immediately after approval (not timer-driven) |

### What Happens at Each Trigger Point

**AT*MIDNIGHT*\* (Midnight Timer)**:

```
Midnight arrives
    ↓
Is chore APPROVED? ──YES──→ Approval Reset → Reschedule → PENDING
    │
    NO (still PENDING/CLAIMED/OVERDUE)
    ↓
Check overdue handling + pending claims options
    ↓
Handle accordingly (HOLD, CLEAR, AUTO_APPROVE, etc.)
```

**AT*DUE_DATE*\* (Due Date Timer)**:

```
Due date passes
    ↓
Is chore APPROVED? ──YES──→ Approval Reset → Reschedule → PENDING
    │
    NO (still PENDING/CLAIMED)
    ↓
Check overdue handling options:
  - MARK_OVERDUE → transition to OVERDUE
  - CLEAR_IMMEDIATE → approval reset → reschedule → PENDING
  - CLEAR_ON_NEXT_APPROVE → leave as-is, reschedule on next approval
    ↓
Check pending claims options:
  - HOLD → skip reset, keep claims
  - CLEAR → discard claims, proceed with reset
  - AUTO_APPROVE → approve first, then reset
```

**UPON_COMPLETION (In Approval Workflow)**:

```
Parent approves chore
    ↓
Approval workflow completes
    ↓
Immediately: Approval Reset → Reschedule → PENDING
(No timer involved - happens synchronously in approve_chore())
```

---

## Current Entry Points (The Mess)

We have **multiple timer-driven methods** that iterate through chores separately:

| Method                           | Trigger                 | Iterates Chores | Purpose                                       |
| -------------------------------- | ----------------------- | --------------- | --------------------------------------------- |
| `process_time_checks()`          | PERIODIC_UPDATE (~5min) | ✅ Single pass  | Categorize: overdue, due_window, reminder     |
| `process_scheduled_resets()`     | MIDNIGHT_ROLLOVER       | ✅ Full pass    | Approval reset + reschedule approved chores   |
| `_reschedule_recurring_chores()` | Called by above         | ✅ Full pass    | Move due dates forward for approved recurring |
| `process_overdue_chores()`       | Manual/API              | ✅ Full pass    | Force overdue check                           |
| `reset_overdue_chores()`         | Service call            | ✅ Full pass    | Admin reset overdue to pending                |
| `reset_all_chores()`             | Service call            | ✅ Full pass    | Admin bulk reset                              |

**Problem**: At midnight, we iterate through all chores at least 3x separately.

---

## From-Scratch Design: Scanner + Gatekeeper Pattern

### Principle: Scanner Categorizes, Gatekeeper Decides, Workers Execute

```
process_time_checks(now_utc)  [Single pass - categorizes all chores]
    ↓
    Returns categorized dict with NEW categories
    ↓
_process_approval_boundary(entries, trigger)  [GATEKEEPER - decides what to do]
    ↓
    For APPROVED chores: approval reset → reschedule (chained)
    For NON-APPROVED chores: respect overdue_handling + pending_claims options
```

### Scanner Categories (Extended)

| Category                     | Condition                              | Purpose                         |
| ---------------------------- | -------------------------------------- | ------------------------------- |
| `overdue`                    | Past due, not yet marked OVERDUE       | Existing - mark OVERDUE state   |
| `in_due_window`              | Within due_window_offset               | Existing - notify due soon      |
| `due_reminder`               | Within reminder_offset                 | Existing - notify reminder      |
| `approval_boundary_midnight` | `AT_MIDNIGHT_*` types, at midnight     | NEW - needs gatekeeper decision |
| `approval_boundary_due_date` | `AT_DUE_DATE_*` types, due date passed | NEW - needs gatekeeper decision |

**Note**: `UPON_COMPLETION` is NOT in scanner - it's handled synchronously in `approve_chore()` workflow.

### Extended ChoreTimeEntry

```python
ChoreTimeEntry = TypedDict("ChoreTimeEntry", {
    # Existing fields
    "chore_id": str,
    "kid_id": str,
    "due_dt": datetime,
    "chore_info": dict[str, Any],
    "time_until_due": timedelta,

    # NEW fields for gatekeeper decisions
    "current_state": str,              # PENDING, CLAIMED, APPROVED, OVERDUE
    "approval_reset_type": str,        # AT_MIDNIGHT_*, AT_DUE_DATE_*, UPON_COMPLETION
    "overdue_handling_type": str,      # MARK_OVERDUE, CLEAR_IMMEDIATE, etc.
    "pending_claims_handling": str,    # HOLD, CLEAR, AUTO_APPROVE
    "recurring_frequency": str,        # DAILY, WEEKLY, MONTHLY, CUSTOM, NONE
    "completion_criteria": str,        # INDEPENDENT, SHARED, SHARED_FIRST
})
```

---

## Gatekeeper Logic: `_process_approval_boundary()`

This is the **brain** that decides what to do based on approval reset type, then state.

### Critical Understanding

1. **PENDING = No Action Needed**: If state is PENDING, the chore has a due date in the future (or no due date). No reset or reschedule required.

2. **Completion Criteria is Fundamental**:
   - **INDEPENDENT**: Each kid has their own state/due date → process per-kid
   - **SHARED/SHARED_FIRST**: One chore-level state/due date → process once for all kids

3. **Special Case - Daily/Weekly Without Due Date**:
   - Never go OVERDUE (no due date to pass)
   - Still do approval reset at midnight if CLAIMED or APPROVED
   - These are "always eligible" for midnight reset

4. **OVERDUE Must Respect overdue_handling**:
   - `AT_DUE_DATE`: Mark overdue, wait for approval reset boundary
   - `NEVER_OVERDUE`: Never mark overdue
   - `CLEAR_AT_APPROVAL_RESET`: Mark overdue, clear at next reset boundary
   - `CLEAR_IMMEDIATE_ON_LATE`: Clear immediately, reschedule

```python
async def _process_approval_boundary(
    self,
    entries: list[ChoreTimeEntry],
    trigger: str,  # "midnight" or "due_date"
) -> ProcessingResult:
    """Gatekeeper: Process approval boundary for categorized entries.

    STEP 1: Filter by approval_reset_type (determines what's in scope)
    ─────────────────────────────────────────────────────────────────
    - trigger="midnight" → only AT_MIDNIGHT_* chores
    - trigger="due_date" → only AT_DUE_DATE_* chores
    - UPON_COMPLETION → NEVER in scope (handled synchronously in approval workflow)

    STEP 2: Route by completion_criteria
    ────────────────────────────────────
    - INDEPENDENT → process per-kid (each kid has own state/due date)
    - SHARED/SHARED_FIRST → process chore-level (one state for all kids)

    STEP 3: Process by state (in order)
    ────────────────────────────────────
    A. PENDING → NO ACTION (due date is in future or no due date needed)

    B. APPROVED/APPROVED_IN_PART → Reset → Reschedule → PENDING
       (Straightforward - chore completed, start next period)

    C. CLAIMED (has pending claim, not yet approved) →
       Check pending_claims_handling:
         - HOLD: Skip this kid (preserve their pending claim)
         - AUTO_APPROVE: Approve first, then reset
         - CLEAR: Discard claim, then reset

    D. OVERDUE (was marked overdue, never completed) →
       Check overdue_handling:
         - AT_DUE_DATE: Reset → Reschedule (standard boundary reset)
         - CLEAR_AT_APPROVAL_RESET: Reset → Reschedule (clears overdue)
         - CLEAR_IMMEDIATE_ON_LATE: Already handled at due date, skip
         - NEVER_OVERDUE: Won't be in OVERDUE state

    Returns:
        ProcessingResult with counts of resets, reschedules, holds, etc.
    """
    result = ProcessingResult()

    for entry in entries:
        approval_reset_type = entry["approval_reset_type"]
        completion_criteria = entry["completion_criteria"]

        # ─────────────────────────────────────────────────────────
        # STEP 1: Scope check - is this chore in scope for this trigger?
        # ─────────────────────────────────────────────────────────
        if trigger == "midnight":
            if approval_reset_type not in [
                APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            ]:
                continue  # Not in scope for midnight run

        elif trigger == "due_date":
            if approval_reset_type not in [
                APPROVAL_RESET_AT_DUE_DATE_ONCE,
                APPROVAL_RESET_AT_DUE_DATE_MULTI,
            ]:
                continue  # Not in scope for due_date run

        # UPON_COMPLETION is never in scope (handled in approve workflow)
        if approval_reset_type == APPROVAL_RESET_UPON_COMPLETION:
            continue

        # ─────────────────────────────────────────────────────────
        # STEP 2: Route by completion_criteria
        # ─────────────────────────────────────────────────────────
        if completion_criteria == COMPLETION_CRITERIA_INDEPENDENT:
            # Process per-kid (each kid has own state/due date)
            result += await self._process_independent_entry(entry, trigger)
        else:
            # SHARED/SHARED_FIRST: Process chore-level
            result += await self._process_shared_entry(entry, trigger)

    return result


async def _process_independent_entry(
    self,
    entry: ChoreTimeEntry,
    trigger: str
) -> ProcessingResult:
    """Process INDEPENDENT chore - each kid has their own state/due date."""
    result = ProcessingResult()
    chore_id = entry["chore_id"]

    # For INDEPENDENT, we need to check each assigned kid
    for kid_id in entry["assigned_kids"]:
        kid_state = self._get_kid_chore_state(kid_id, chore_id)
        kid_due_date = self._get_per_kid_due_date(chore_id, kid_id)

        # Skip if due date is in future (PENDING with future due)
        if kid_due_date and kid_due_date > now_utc:
            continue

        # A. PENDING → No action (already reset or no due date needed)
        if kid_state == CHORE_STATE_PENDING:
            continue

        # B. APPROVED → Reset → Reschedule
        if kid_state in [CHORE_STATE_APPROVED, CHORE_STATE_APPROVED_IN_PART]:
            await self._do_approval_reset_for_kid(chore_id, kid_id)
            self._do_reschedule_for_kid(chore_id, kid_id)
            result.reset_count += 1
            result.reschedule_count += 1
            continue

        # C. CLAIMED → Check pending_claims_handling
        if kid_state == CHORE_STATE_CLAIMED:
            pending_handling = entry["pending_claims_handling"]

            if pending_handling == PENDING_CLAIMS_HOLD:
                result.hold_count += 1
                continue  # Skip - preserve their claim

            if pending_handling == PENDING_CLAIMS_AUTO_APPROVE:
                await self._auto_approve_for_kid(chore_id, kid_id)
                result.auto_approve_count += 1
                # Fall through to reset

            # CLEAR or after AUTO_APPROVE → Reset
            await self._do_approval_reset_for_kid(chore_id, kid_id)
            self._do_reschedule_for_kid(chore_id, kid_id)
            result.reset_count += 1
            result.reschedule_count += 1
            continue

        # D. OVERDUE → Check overdue_handling
        if kid_state == CHORE_STATE_OVERDUE:
            overdue_handling = entry["overdue_handling_type"]

            # CLEAR_IMMEDIATE already handled when it became overdue, skip
            if overdue_handling == OVERDUE_HANDLING_CLEAR_IMMEDIATE_ON_LATE:
                continue

            # AT_DUE_DATE, CLEAR_AT_APPROVAL_RESET → Reset at boundary
            await self._do_approval_reset_for_kid(chore_id, kid_id)
            self._do_reschedule_for_kid(chore_id, kid_id)
            result.reset_count += 1
            result.reschedule_count += 1

    return result


async def _process_shared_entry(
    self,
    entry: ChoreTimeEntry,
    trigger: str
) -> ProcessingResult:
    """Process SHARED/SHARED_FIRST chore - one chore-level state for all kids."""
    result = ProcessingResult()
    chore_id = entry["chore_id"]
    state = entry["current_state"]  # Chore-level state
    due_date = entry["due_dt"]      # Chore-level due date

    # Skip if due date is in future
    if due_date and due_date > now_utc:
        return result

    # A. PENDING → No action
    if state == CHORE_STATE_PENDING:
        return result

    # B. APPROVED → Reset all kids → Reschedule chore
    if state in [CHORE_STATE_APPROVED, CHORE_STATE_APPROVED_IN_PART]:
        await self._do_approval_reset_for_shared(entry)
        self._do_reschedule_for_shared(entry)
        result.reset_count += len(entry["assigned_kids"])
        result.reschedule_count += 1
        return result

    # C. CLAIMED → Check pending_claims_handling for each kid
    if state == CHORE_STATE_CLAIMED:
        pending_handling = entry["pending_claims_handling"]

        for kid_id in entry["assigned_kids"]:
            if not self._kid_has_pending_claim(kid_id, chore_id):
                continue  # This kid doesn't have a claim

            if pending_handling == PENDING_CLAIMS_HOLD:
                result.hold_count += 1
                continue  # Skip this kid

            if pending_handling == PENDING_CLAIMS_AUTO_APPROVE:
                await self._auto_approve_for_kid(chore_id, kid_id)
                result.auto_approve_count += 1

        # After handling all claims, reset the chore
        await self._do_approval_reset_for_shared(entry)
        self._do_reschedule_for_shared(entry)
        result.reset_count += 1
        result.reschedule_count += 1
        return result

    # D. OVERDUE → Check overdue_handling
    if state == CHORE_STATE_OVERDUE:
        overdue_handling = entry["overdue_handling_type"]

        if overdue_handling == OVERDUE_HANDLING_CLEAR_IMMEDIATE_ON_LATE:
            return result  # Already handled

        await self._do_approval_reset_for_shared(entry)
        self._do_reschedule_for_shared(entry)
        result.reset_count += 1
        result.reschedule_count += 1

    return result
```

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    GATEKEEPER ENTRY                              │
│                 _process_approval_boundary()                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: SCOPE CHECK (approval_reset_type)                       │
├─────────────────────────────────────────────────────────────────┤
│ trigger="midnight"  → AT_MIDNIGHT_* only                        │
│ trigger="due_date"  → AT_DUE_DATE_* only                        │
│ UPON_COMPLETION     → SKIP (handled in approve workflow)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (in scope)
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: ROUTE BY COMPLETION CRITERIA                            │
├─────────────────────────────────────────────────────────────────┤
│ INDEPENDENT → _process_independent_entry() (per-kid)            │
│ SHARED/SHARED_FIRST → _process_shared_entry() (chore-level)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: STATE CHECK                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │   PENDING    │──→ NO ACTION (due in future, nothing to do)   │
│  └──────────────┘                                               │
│         │                                                       │
│         ▼ not pending                                           │
│  ┌──────────────┐                                               │
│  │   APPROVED   │──→ Reset → Reschedule → PENDING               │
│  └──────────────┘                                               │
│         │                                                       │
│         ▼ not approved                                          │
│  ┌──────────────┐    ┌─────────────────────────────────────┐   │
│  │   CLAIMED    │──→ │ Check pending_claims_handling:      │   │
│  └──────────────┘    │  • HOLD → Skip (preserve claim)     │   │
│         │            │  • AUTO_APPROVE → Approve first     │   │
│         │            │  • CLEAR → Discard claims           │   │
│         │            └──────────────┬──────────────────────┘   │
│         │                           ▼ (unless HOLD)            │
│         │                  Reset → Reschedule → PENDING         │
│         ▼ not claimed                                           │
│  ┌──────────────┐    ┌─────────────────────────────────────┐   │
│  │   OVERDUE    │──→ │ Check overdue_handling:             │   │
│  └──────────────┘    │  • AT_DUE_DATE → Reset at boundary  │   │
│                      │  • CLEAR_AT_RESET → Reset clears it │   │
│                      │  • CLEAR_IMMEDIATE → Already done   │   │
│                      └──────────────┬──────────────────────┘   │
│                                     ▼ (unless CLEAR_IMMEDIATE) │
│                            Reset → Reschedule → PENDING         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Special Case: Daily/Weekly Without Due Date

```
Chore has:
  - recurring_frequency = DAILY or WEEKLY
  - due_date = None (no due date)
  - approval_reset_type = AT_MIDNIGHT_*

Behavior:
  - NEVER goes OVERDUE (no due date to pass)
  - At midnight, if CLAIMED or APPROVED:
    → Process through normal gatekeeper flow
    → Reset → (No reschedule needed - no due date)
  - If PENDING: No action
```

---

## Worker Methods (Called by Gatekeeper)

### `_do_approval_reset()` - Reset approval state

```python
async def _do_approval_reset(self, entry: ChoreTimeEntry) -> None:
    """Execute approval reset for a single entry.

    Actions:
    1. Reset status to PENDING
    2. Reset approval_period_start timestamp
    3. Clear pending claim count
    4. Emit signal for entity updates
    """
    kid_id = entry["kid_id"]
    chore_id = entry["chore_id"]

    self._reset_status_to_pending(kid_id, chore_id)
    self._reset_approval_period(kid_id, chore_id)
```

### `_do_reschedule()` - Calculate next due date

```python
def _do_reschedule(self, entry: ChoreTimeEntry) -> None:
    """Execute due date rescheduling for a single entry.

    Actions:
    1. Calculate next due date using schedule engine
    2. Update storage (chore-level or per-kid based on completion_criteria)

    Note: Does NOT change state - that's approval reset's job.
    """
    if entry["recurring_frequency"] == FREQUENCY_NONE:
        return  # Non-recurring, no reschedule needed

    if entry["completion_criteria"] == COMPLETION_CRITERIA_INDEPENDENT:
        self._reschedule_chore_next_due_date_for_kid(...)
    else:
        self._reschedule_chore_next_due(...)
```

---

## Timer Handlers (Simplified)

**PERIODIC_UPDATE (~5min)**:

```python
async def _on_periodic_update(self, payload: dict[str, Any]) -> None:
    scan = self.process_time_checks(now_utc)

    # Time-based notifications and state changes
    await self._process_overdue(scan["overdue"], now_utc)
    self._process_due_window(scan["in_due_window"])
    self._process_due_reminder(scan["due_reminder"])

    # AT_DUE_DATE_* approval boundaries (when due date passes during day)
    await self._process_approval_boundary(
        scan["approval_boundary_due_date"],
        trigger="due_date"
    )
```

**MIDNIGHT_ROLLOVER**:

```python
async def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
    scan = self.process_time_checks(now_utc)

    # AT_MIDNIGHT_* approval boundaries
    await self._process_approval_boundary(
        scan["approval_boundary_midnight"],
        trigger="midnight"
    )

    # Note: Don't process due_date boundaries here - periodic handles those
    # Note: Don't process overdue here - periodic handles that
```

---

## UPON_COMPLETION: Handled in Workflow

For `UPON_COMPLETION` approval reset type, the reset + reschedule happens **synchronously** in the approval workflow, not via timer:

```python
# In approve_chore() method:
async def approve_chore(self, kid_id: str, chore_id: str, ...) -> None:
    # ... approval logic ...

    # Check if this is UPON_COMPLETION type
    approval_reset_type = chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)

    if approval_reset_type == APPROVAL_RESET_UPON_COMPLETION:
        # Immediate reset + reschedule (no timer needed)
        await self._do_approval_reset(entry)
        self._do_reschedule(entry)
```

---

## Key Benefits of This Design

1. **Single iteration** through chores (done in `process_time_checks`)
2. **Gatekeeper pattern** - one method makes all the decisions
3. **Chained operations** - reschedule is always triggered BY approval reset
4. **Options respected** - overdue handling and pending claims honored
5. **Clear timing**:
   - `UPON_COMPLETION` → in approval workflow (immediate)
   - `AT_DUE_DATE_*` → in periodic update (when due date passes)
   - `AT_MIDNIGHT_*` → in midnight rollover
6. **Method names match behavior**:
   - `_process_approval_boundary()` → gatekeeper that decides
   - `_do_approval_reset()` → executes reset
   - `_do_reschedule()` → executes reschedule

---

## Migration Path (From Mess to Clean)

### Phase 1: Extend Scanner

- Add `approval_boundary_midnight` and `approval_boundary_due_date` categories
- Add new fields to `ChoreTimeEntry`

### Phase 2: Create Gatekeeper

- `_process_approval_boundary()` - new gatekeeper method
- `_do_approval_reset()` - extract/rename from existing
- `_do_reschedule()` - wrapper around existing reschedule methods

### Phase 3: Update Timer Handlers

- `_on_midnight_rollover()` → call gatekeeper with "midnight" trigger
- `_on_periodic_update()` → call gatekeeper with "due_date" trigger

### Phase 4: Update UPON_COMPLETION in Workflow

- Modify `approve_chore()` to call gatekeeper workers directly

### Phase 5: Deprecate Old Methods

- `process_scheduled_resets()` → DELETE
- `process_recurring_chore_resets()` → DELETE
- `_reschedule_recurring_chores()` → DELETE
- `_reset_shared_chore()` → DELETE
- `_reset_independent_chore()` → DELETE

---

## Summary: Method Naming

| Method                         | Role                            | Naming Pattern             |
| ------------------------------ | ------------------------------- | -------------------------- |
| `_process_approval_boundary()` | Gatekeeper - decides what to do | `process_*` (orchestrator) |
| `_do_approval_reset()`         | Worker - executes reset         | `_do_*` (action verb)      |
| `_do_reschedule()`             | Worker - calculates next due    | `_do_*` (action verb)      |
| `_reset_status_to_pending()`   | Helper - state change only      | `reset_*_to_*`             |
| `_reset_approval_period()`     | Helper - clear tracking         | `reset_*_period`           |
| `reset_all_chores()`           | Admin - bulk operation          | `reset_*_bulk`             |
| `reset_overdue_chores()`       | Admin - filtered operation      | `reset_*_overdue`          |

Does this revised architecture capture the gatekeeper relationship correctly?
