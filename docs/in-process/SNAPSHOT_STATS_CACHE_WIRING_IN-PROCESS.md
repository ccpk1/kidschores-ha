# Snapshot Statistics Cache Wiring

## Initiative snapshot

- **Name / Code**: SNAPSHOT_STATS_CACHE_WIRING
- **Target release / milestone**: v0.5.0-beta4
- **Owner / driver(s)**: Agent-assisted
- **Status**: Not started

## Summary & immediate steps

| Phase / Step            | Description                                                     | % complete | Quick notes                             |
| ----------------------- | --------------------------------------------------------------- | ---------- | --------------------------------------- |
| Phase 1 – Architecture  | Move snapshot counts to ephemeral cache, add PRES constants     | 0%         | Foundation for signal wiring            |
| Phase 2 – Engine Reuse  | Manager calls Engine for snapshot counts, hydrates cache        | 0%         | Single source of truth                  |
| Phase 3 – Signal Wiring | Add listeners for "quiet transitions" that don't affect buckets | 0%         | STATUS_RESET, UNDONE, (existing fixups) |
| Phase 4 – Sensor Update | Sensors read snapshot counts from cache, not storage            | 0%         | Cache-first pattern                     |
| Phase 5 – Testing       | Validate signal coverage with scenario tests                    | 0%         | All state transitions covered           |

1. **Key objective** – Ensure "live state" snapshot counts (`current_overdue`, `current_claimed`, `current_approved`, `current_due_today`) are always accurate by treating them as **Calculated Derivative Data** in the ephemeral `_stats_cache`, refreshed on every state-changing signal.

2. **Summary of recent work** – N/A (not started)

3. **Next steps (short term)**
   - Phase 1: Add `PRES_KID_CHORES_CURRENT_*` constants to `const.py`
   - Phase 1: Verify `STATS_TEMPORAL_SUFFIXES` already strips these from storage (✅ confirmed)
   - Phase 2: Update `_refresh_chore_cache()` to call `generate_chore_stats()` and extract snapshot counts

4. **Risks / blockers**
   - **Signal naming clarity**: Confirm `SIGNAL_SUFFIX_CHORE_STATUS_RESET` vs `SIGNAL_SUFFIX_CHORE_UNDONE` semantics
   - **Debounce consideration**: SHARED chores may emit multiple signals in quick succession
   - **Dashboard impact**: Ensure dashboard helper receives updated cache values

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Data model, storage architecture
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Signal patterns, Manager communication
   - [statistics_engine.py](../../custom_components/kidschores/engines/statistics_engine.py) – `generate_chore_stats()` implementation
   - [statistics_manager.py](../../custom_components/kidschores/managers/statistics_manager.py) – `_refresh_chore_cache()` implementation

6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Snapshot counts are **ephemeral** (not persisted) – already in `STATS_TEMPORAL_SUFFIXES`
     - ✅ Engine is the **only calculator** – Manager hydrates cache from Engine output
     - ✅ Cache-first sensor reads – storage only as startup fallback
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

---

## Conceptual Foundation

### Tally vs. Snapshot (Two Different Data Types)

| Concept      | Definition                                            | Storage Location               | Example                             |
| ------------ | ----------------------------------------------------- | ------------------------------ | ----------------------------------- |
| **Tally**    | Historical bucket counts ("How many on Monday?")      | Persistent (`DATA_KID_*`)      | `periods.daily.2026-01-30.approved` |
| **Snapshot** | Live state counts ("How many are overdue right now?") | Ephemeral (`PRES_KID_*` cache) | `current_overdue`                   |

**Critical Distinction**: A tally is **permanent** (what happened). A snapshot is **volatile** (what is true now).

### Snapshot Count Semantics

| Snapshot Key        | Definition                                                    |
| ------------------- | ------------------------------------------------------------- |
| `current_overdue`   | Chores in `OVERDUE` state right now                           |
| `current_claimed`   | Chores in `CLAIMED` state right now (awaiting approval)       |
| `current_approved`  | Chores approved **within current reset cycle** (not all-time) |
| `current_due_today` | Chores with due date = today                                  |

**Reset Cycle Note**: For `current_approved`, the count resets based on the chore's `approval_reset_type`:

- `AT_MIDNIGHT_*`: Resets at midnight
- `AT_DUE_DATE_*`: Resets at due date
- `UPON_COMPLETION`: Resets when approved

### Architecture Principle: Engine as Single Source of Truth

```
┌────────────────────────────────────────────────────────────────┐
│                     StatisticsEngine                           │
│  generate_chore_stats(kid_info, chores_data) → full_stats      │
│  (ONLY place that knows how to count chores by state)          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   StatisticsManager                            │
│  _refresh_chore_cache(kid_id):                                 │
│    1. Call engine.generate_chore_stats()                       │
│    2. Extract snapshot counts → _stats_cache[kid_id]           │
│    3. Extract temporal aggregates → _stats_cache[kid_id]       │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                      Sensors                                   │
│  Read from _stats_cache FIRST                                  │
│  Fallback to persistent storage only during startup            │
└────────────────────────────────────────────────────────────────┘
```

---

## Signal Coverage Matrix

### State-Changing Signals

| Signal               | State Transition     | Affects Snapshot? | Affects Tally?           | Current Status                |
| -------------------- | -------------------- | ----------------- | ------------------------ | ----------------------------- |
| `CHORE_CLAIMED`      | PENDING → CLAIMED    | ✅ Yes            | ✅ Yes (claimed_today)   | ✅ Listened, tally recorded   |
| `CHORE_APPROVED`     | CLAIMED → APPROVED   | ✅ Yes            | ✅ Yes (approved_today)  | ✅ Listened, tally recorded   |
| `CHORE_COMPLETED`    | (varies by criteria) | ✅ Yes            | ✅ Yes (completed_today) | ✅ Listened, tally recorded   |
| `CHORE_DISAPPROVED`  | CLAIMED → PENDING    | ✅ Yes            | ✅ Yes (disapproved)     | ✅ Listened, tally recorded   |
| `CHORE_OVERDUE`      | PENDING → OVERDUE    | ✅ Yes            | ✅ Yes (overdue_today)   | ✅ Listened, tally recorded   |
| `CHORE_STATUS_RESET` | OVERDUE → PENDING    | ✅ Yes            | ❌ No                    | ❌ **NOT listened** (THE BUG) |
| `CHORE_UNDONE`       | APPROVED → PENDING   | ✅ Yes            | ❓ Maybe (reversal?)     | ❌ **NOT listened** (gap)     |

### Signals That Need NEW Listeners (Phase 3)

1. **`SIGNAL_SUFFIX_CHORE_STATUS_RESET`** – Parent "skips" overdue chore
   - Transition: OVERDUE → PENDING
   - Cache impact: `current_overdue` decrements
   - Tally impact: None (no bucket write)

2. **`SIGNAL_SUFFIX_CHORE_UNDONE`** – Parent undoes approval
   - Transition: APPROVED → PENDING (with point reclamation)
   - Cache impact: `current_approved` decrements
   - Tally impact: TBD – should we decrement the approval bucket? (Scope: separate initiative)

### Existing Listeners That Need Cache Refresh Added

All existing listeners (`_on_chore_claimed`, `_on_chore_approved`, etc.) currently:

- ✅ Record tally via `record_transaction()`
- ✅ Call `_refresh_chore_cache()` (which aggregates tallies)
- ❌ **But** `_refresh_chore_cache()` doesn't compute snapshot counts

**Solution**: Enhance `_refresh_chore_cache()` to also extract snapshot counts from `generate_chore_stats()` output.

---

## Detailed Phase Tracking

### Phase 1 – Architecture (Constants & Verification)

**Goal**: Establish the ephemeral snapshot count infrastructure.

**Steps / detailed work items**:

1. - [ ] **1.1** Add PRES constants to `const.py` (~line 1245):

   ```python
   # Snapshot counts (ephemeral, derived from current chore states)
   PRES_KID_CHORES_CURRENT_OVERDUE: Final = "pres_kid_chores_current_overdue"
   PRES_KID_CHORES_CURRENT_CLAIMED: Final = "pres_kid_chores_current_claimed"
   PRES_KID_CHORES_CURRENT_APPROVED: Final = "pres_kid_chores_current_approved"
   PRES_KID_CHORES_CURRENT_DUE_TODAY: Final = "pres_kid_chores_current_due_today"
   ```

2. - [ ] **1.2** Verify `STATS_TEMPORAL_SUFFIXES` already includes:
   - `_current_overdue` ✅ (line 1279)
   - `_current_claimed` ✅ (line 1280)
   - `_current_approved` ✅ (line 1281)
   - `_current_due_today` ✅ (line 1278)
   - **Result**: No changes needed – these are already stripped from persistent storage.

3. - [ ] **1.3** Document in `const.py` the distinction:
   ```python
   # =============================================================================
   # SNAPSHOT STATISTICS (Ephemeral)
   # =============================================================================
   # Snapshot counts represent "current state" at a point in time.
   # They are calculated by generate_chore_stats() and cached in _stats_cache.
   # They are NEVER persisted to storage (see STATS_TEMPORAL_SUFFIXES).
   ```

**Key issues**:

- None anticipated for Phase 1.

---

### Phase 2 – Engine Reuse (Manager Calls Engine)

**Goal**: Make `_refresh_chore_cache()` use `generate_chore_stats()` as the single source of truth for snapshot counts.

**Steps / detailed work items**:

1. - [ ] **2.1** Read current `_refresh_chore_cache()` implementation (statistics_manager.py ~920-1020)
   - Currently: Iterates `kid_chore_data` manually to aggregate period buckets
   - Missing: Snapshot counts (current_overdue, etc.)

2. - [ ] **2.2** Modify `_refresh_chore_cache()` to:

   ```python
   def _refresh_chore_cache(self, kid_id: str) -> None:
       """Refresh chore statistics cache for a kid.

       Calls StatisticsEngine.generate_chore_stats() and extracts:
       1. Snapshot counts (current_overdue, current_claimed, etc.)
       2. Temporal aggregates (approved_today, claimed_week, etc.)

       Args:
           kid_id: The kid's internal ID
       """
       kid_info = self._get_kid(kid_id)
       if not kid_info:
           return

       cache = self._stats_cache.setdefault(kid_id, {})

       # Use Engine as single source of truth
       full_stats = self._coordinator.stats.generate_chore_stats(
           kid_info, self._coordinator.chores_data
       )

       # Extract snapshot counts to cache
       cache[const.PRES_KID_CHORES_CURRENT_OVERDUE] = full_stats.get(
           const.DATA_KID_CHORE_STATS_CURRENT_OVERDUE, 0
       )
       cache[const.PRES_KID_CHORES_CURRENT_CLAIMED] = full_stats.get(
           const.DATA_KID_CHORE_STATS_CURRENT_CLAIMED, 0
       )
       cache[const.PRES_KID_CHORES_CURRENT_APPROVED] = full_stats.get(
           const.DATA_KID_CHORE_STATS_CURRENT_APPROVED, 0
       )
       cache[const.PRES_KID_CHORES_CURRENT_DUE_TODAY] = full_stats.get(
           const.DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY, 0
       )

       # Keep existing temporal aggregate logic (or also extract from full_stats)
       # ... rest of method unchanged OR simplify to also extract from full_stats
   ```

3. - [ ] **2.3** Decision: Should temporal aggregates (approved_today, etc.) also come from `generate_chore_stats()`?
   - **Pros**: Single iteration, guaranteed consistency
   - **Cons**: `generate_chore_stats()` iterates all chores; current `_refresh_chore_cache()` is more targeted
   - **Recommendation**: Extract snapshot counts from Engine; keep existing temporal logic for now. Consolidation can be a future optimization.

4. - [ ] **2.4** Verify `_coordinator.stats` accessor exists and returns `StatisticsEngine` instance.

**Key issues**:

- Performance: `generate_chore_stats()` iterates all chores. If called frequently, may need memoization.
- Scope creep: Resist urge to consolidate all temporal logic in Phase 2. Keep it focused.

---

### Phase 3 – Signal Wiring (Quiet Transitions)

**Goal**: Add listeners for signals that change chore state but don't affect period buckets.

**Steps / detailed work items**:

1. - [ ] **3.1** Add `SIGNAL_SUFFIX_CHORE_STATUS_RESET` listener:

   ```python
   def _setup_listeners(self) -> None:
       """Set up signal listeners for statistics tracking."""
       # ... existing listeners ...

       # Quiet transitions (state change only, no bucket impact)
       self.listen(
           const.SIGNAL_SUFFIX_CHORE_STATUS_RESET,
           self._on_chore_status_reset,
       )
   ```

2. - [ ] **3.2** Implement `_on_chore_status_reset()`:

   ```python
   def _on_chore_status_reset(
       self,
       kid_id: str,
       chore_id: str,
       chore_name: str,
       **kwargs: Any,
   ) -> None:
       """Handle chore status reset (parent skips overdue chore).

       Transition: OVERDUE → PENDING
       Impact: Snapshot counts change, no bucket writes needed.
       """
       const.LOGGER.debug(
           "Chore status reset for kid %s, chore %s - refreshing snapshot cache",
           kid_id,
           chore_id,
       )
       self._refresh_chore_cache(kid_id)
   ```

3. - [ ] **3.3** Add `SIGNAL_SUFFIX_CHORE_UNDONE` listener:

   ```python
   self.listen(
       const.SIGNAL_SUFFIX_CHORE_UNDONE,
       self._on_chore_undone,
   )
   ```

4. - [ ] **3.4** Implement `_on_chore_undone()`:

   ```python
   def _on_chore_undone(
       self,
       kid_id: str,
       chore_id: str,
       points_to_reclaim: float,
       **kwargs: Any,
   ) -> None:
       """Handle chore undo (parent reverses approval).

       Transition: APPROVED → PENDING
       Impact: Snapshot counts change.
       Future: May need bucket reversal (decrement approved_today).
       """
       const.LOGGER.debug(
           "Chore undone for kid %s, chore %s - refreshing snapshot cache",
           kid_id,
           chore_id,
       )
       self._refresh_chore_cache(kid_id)
       # NOTE: Bucket reversal (decrement approved) is out of scope.
       # If needed, create separate initiative.
   ```

5. - [ ] **3.5** Verify signal payload signatures match:
   - `CHORE_STATUS_RESET` emits: `kid_id`, `chore_id`, `chore_name` (chore_manager.py ~454)
   - `CHORE_UNDONE` emits: `kid_id`, `chore_id`, `points_to_reclaim` (chore_manager.py ~395)

**Key issues**:

- **CHORE_UNDONE bucket reversal**: Should we decrement `approved_today` when a chore is undone? Out of scope for this initiative – creates a "reversal" pattern that needs careful design.

---

### Phase 4 – Sensor Update (Cache-First Reads)

**Goal**: Sensors read snapshot counts from `_stats_cache`, not persistent storage.

**Steps / detailed work items**:

1. - [ ] **4.1** Update `KidChoresSensor.extra_state_attributes` (sensor.py ~1310):
   - Current: Reads `DATA_KID_CHORE_STATS` from storage, then merges PRES cache
   - Change: For `current_*` keys, read from PRES cache only (storage fallback for startup)

   ```python
   # Phase 7.5: Add temporal stats from presentation cache
   pres_stats = self.coordinator.statistics_manager.get_stats(self._kid_id)

   # Snapshot counts from cache ONLY (not storage)
   for snapshot_key in (
       const.PRES_KID_CHORES_CURRENT_OVERDUE,
       const.PRES_KID_CHORES_CURRENT_CLAIMED,
       const.PRES_KID_CHORES_CURRENT_APPROVED,
       const.PRES_KID_CHORES_CURRENT_DUE_TODAY,
   ):
       if snapshot_key in pres_stats:
           # Strip "pres_kid_chores_" prefix (16 chars)
           attr_key = snapshot_key[16:]
           attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{attr_key}"] = pres_stats[snapshot_key]
   ```

2. - [ ] **4.2** Verify startup behavior:
   - On first load, before any signal fires, `_stats_cache` may be empty
   - `coordinator._first_refresh()` calls `chore_manager.recalculate_chore_stats_for_kid()` → writes to storage
   - Sensors will get snapshot counts from storage until first signal fires
   - After first signal, cache takes over
   - **This is acceptable** – cache is hydrated on any state change

3. - [ ] **4.3** Consider: Should `_first_refresh()` also hydrate the PRES cache?
   - **Recommendation**: Yes, add `statistics_manager._refresh_chore_cache(kid_id)` call in `_first_refresh()` for immediate accuracy.

4. - [ ] **4.4** Update dashboard helper if it reads snapshot counts directly:
   - Check `ui_manager.py` for `current_overdue` references
   - Ensure it reads from StatisticsManager cache

**Key issues**:

- Startup race condition: Sensors may render before cache is hydrated. Fallback to storage is safe.

---

### Phase 5 – Testing

**Goal**: Validate all state transitions update snapshot counts correctly.

**Steps / detailed work items**:

1. - [ ] **5.1** Create test file: `tests/test_snapshot_stats_cache.py`

2. - [ ] **5.2** Test scenarios using `scenario_medium` fixture:
   - `test_status_reset_decrements_overdue`:
     - Setup: Chore in OVERDUE state
     - Action: Call `chore_manager.reset_chore()`
     - Assert: `current_overdue` in cache decrements by 1
   - `test_claim_increments_claimed`:
     - Setup: Chore in PENDING state
     - Action: Press claim button (via service)
     - Assert: `current_claimed` in cache increments by 1
   - `test_approval_transitions_claimed_to_approved`:
     - Setup: Chore in CLAIMED state
     - Action: Press approve button
     - Assert: `current_claimed` decrements, `current_approved` increments
   - `test_disapproval_decrements_claimed`:
     - Setup: Chore in CLAIMED state
     - Action: Press disapprove button
     - Assert: `current_claimed` decrements by 1
   - `test_undo_decrements_approved`:
     - Setup: Chore in APPROVED state
     - Action: Call `chore_manager.undo_chore()`
     - Assert: `current_approved` in cache decrements by 1

3. - [ ] **5.3** Test cache-sensor integration:
   - Assert sensor attributes reflect cache values after state changes
   - Assert cache is hydrated on `_first_refresh()`

4. - [ ] **5.4** Run full test suite:
   ```bash
   ./utils/quick_lint.sh --fix
   mypy custom_components/kidschores/
   python -m pytest tests/ -v --tb=line
   ```

**Key issues**:

- Test isolation: Each test should reset cache state.

---

## Testing & Validation

- **Tests executed**: None yet (planning phase)
- **Outstanding tests**: All Phase 5 tests
- **Links**: N/A

---

## Notes & Follow-up

### Out of Scope (Future Initiatives)

1. **Bucket Reversal for UNDO**: Should undoing an approval decrement `approved_today`? This is a "historical rewrite" that needs careful consideration. Create separate initiative if needed.

2. **Temporal Aggregate Consolidation**: Current `_refresh_chore_cache()` manually iterates period buckets. Could be simplified to extract all temporal stats from `generate_chore_stats()`. Deferred to avoid scope creep.

3. **Debounce for SHARED Chores**: SHARED chores may emit multiple signals in quick succession (one per kid). Consider debouncing cache refresh. Monitor performance first.

### Verification Commands

```bash
# After Phase 3 (Signal Wiring)
grep -n "SIGNAL_SUFFIX_CHORE_STATUS_RESET" custom_components/kidschores/managers/statistics_manager.py
grep -n "SIGNAL_SUFFIX_CHORE_UNDONE" custom_components/kidschores/managers/statistics_manager.py

# After Phase 4 (Sensor Update)
grep -n "PRES_KID_CHORES_CURRENT" custom_components/kidschores/sensor.py

# Full validation
./utils/quick_lint.sh --fix && mypy custom_components/kidschores/ && python -m pytest tests/ -v
```

### Architecture Decision Records

| Decision                                      | Rationale                                                                 | Date       |
| --------------------------------------------- | ------------------------------------------------------------------------- | ---------- |
| Snapshot counts are ephemeral (not persisted) | They represent "now" and are meaningless when read from a file days later | 2026-01-30 |
| Engine is single source of truth for counting | Avoids duplicate iteration logic in Manager                               | 2026-01-30 |
| Cache-first sensor reads                      | Ensures UI reflects latest state changes immediately                      | 2026-01-30 |
| Bucket reversal out of scope                  | Historical rewrites need separate design discussion                       | 2026-01-30 |
