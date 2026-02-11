# Initiative Plan: Cumulative Badge Maintenance Cycle

## Initiative snapshot

- **Name / Code**: Cumulative Badge Maintenance Cycle (CUMBMC)
- **Target release / milestone**: v0.5.0-beta4
- **Owner / driver(s)**: KidsChores Plan Agent
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                              | Description                                                   | % complete | Quick notes                                           |
| ----------------------------------------- | ------------------------------------------------------------- | ---------- | ----------------------------------------------------- |
| Phase 1 – Engine Retention Fix            | Split `check_retention` for cumulative vs periodic            | 0%         | Engine-only, ~25 lines                                |
| Phase 2 – Manager Maintenance Processing  | Port `_manage_cumulative_badge_maintenance` to manager        | 0%         | Core missing feature: cycle reset, grace, re-promote  |
| Phase 3 – Manager Integration Points      | Wire midnight trigger + `_apply_badge_result` re-promotion    | 0%         | Connect maintenance to scheduled evaluation           |
| Phase 4 – Tests                           | Engine tests + manager maintenance tests                      | 0%         | Must cover all 3 states × 2 outcomes = 6+ scenarios   |
| Phase 5 – Validation                      | Full lint/mypy/test suite                                     | 0%         | Zero regressions across all 1259+ tests               |

1. **Key objective** — Restore the complete cumulative badge maintenance cycle that existed in the old coordinator but was **never migrated** to the refactored manager architecture. This includes: cycle-point reset at cycle boundaries, GRACE state transitions, re-promotion from DEMOTED→ACTIVE, and scheduled maintenance evaluation via midnight rollover.

2. **Summary of recent work** — Deep analysis of old coordinator `_manage_cumulative_badge_maintenance()` (400 lines, user-provided) vs current `gamification_manager.py`. The old code had a complete maintenance state machine. The refactored code has only: (a) cycle_points accumulation, (b) one-way demotion. All other maintenance machinery is missing.

3. **Next steps (short term)** — Phase 1 first (engine fix), then Phase 2 (port maintenance logic to manager), then Phase 3 (wiring).

4. **Risks / blockers**
   - The old code used `baseline + cycle_points` for tier determination. The new code uses `stats.get_period_total()` (all-time earned). **The tier determination is fundamentally different** — the plan must account for this architectural change.
   - The old code called `_persist()` and `async_set_updated_data()` directly. The new architecture uses manager→coordinator delegation and signal-based communication.
   - `cycle_points` is accumulated even when no badge has `maintenance_rules > 0`. This is wasteful but harmless — guarding it is a follow-up optimization.
   - The old `_get_cumulative_badge_levels()` used `baseline + cycle_points` for total. The new version uses `stats.get_period_total()`. This means tier boundaries work differently — **cycle_points is now ONLY for maintenance evaluation, not tier determination**.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Engine vs Manager distinction, signal-first communication
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Constant naming, engine purity rules
   - Old coordinator code: `_manage_cumulative_badge_maintenance()` (user-provided attachment)
   - Wiki specification: `kidschores-ha.wiki/Configuration:-Badges-Cumulative.md`
   - Supporting analysis: [CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS.md](./CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - **Tier determination**: Uses `stats.get_period_total()` (all-time earned) — NOT `baseline + cycle_points`. The old `baseline` field has been removed.
     - **`cycle_points` purpose**: ONLY for maintenance cycle evaluation (did kid earn enough THIS cycle?). Not used for badge tier threshold comparison.
     - **Engine fix**: Option A — `check_retention()` gets cumulative-specific branch evaluating `cycle_points >= maintenance_rules`
     - **Maintenance processing**: Port old coordinator logic to `GamificationManager.process_cumulative_maintenance()` as a new manager method
     - **Signal wiring**: GamificationManager subscribes to `SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER` to trigger maintenance checks
     - **Re-promotion**: Handled in BOTH `_apply_badge_result()` (immediate, on point change) AND `process_cumulative_maintenance()` (time-based, at midnight)
     - **`maintenance_rules = 0`** means no maintenance requirement → retention always passes, maintenance processing skips (by design)
     - **`SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`**: Currently dead signal — will be used for post-maintenance-processing notification OR removed if unnecessary
   - **Completion confirmation**: `[ ]` All follow-up items completed before requesting owner approval

---

## Gap Analysis: Old Coordinator vs Current Manager

### What the Old Code Did (Complete Maintenance State Machine)

The old `_manage_cumulative_badge_maintenance()` handled these 8 responsibilities:

| # | Responsibility                         | Old Code Behavior                                                      |
|---|----------------------------------------|------------------------------------------------------------------------|
| 1 | **Guard: no badge earned**             | Early return if `_get_cumulative_badge_levels()` returns no highest     |
| 2 | **Guard: reset not enabled**           | Clear maintenance dates, persist, return if `frequency == None`        |
| 3 | **First-time setup**                   | Set initial `maintenance_end_date` and `grace_end_date` on first earn  |
| 4 | **ACTIVE → evaluate at end_date**      | Compare `cycle_points >= maintenance_required`                         |
| 5 | **ACTIVE → GRACE transition**          | If points not met but grace_days > 0, set status = GRACE               |
| 6 | **GRACE → evaluate at grace_end_date** | If points met → award_success; if expired → demotion                   |
| 7 | **Award success (re-promotion)**       | Reset dates, set status = ACTIVE, award badge, grant awards            |
| 8 | **Demotion**                           | Set status = DEMOTED, current_badge = next_lower, **reset cycle_points to 0**, baseline += cycle_points, recalculate multiplier |

### What the Current Manager Has

| # | Responsibility                         | Current Status         | Location                           |
|---|----------------------------------------|------------------------|------------------------------------|
| 1 | Guard: no badge earned                 | ✅ Exists              | `get_cumulative_badge_levels()`    |
| 2 | Guard: reset not enabled               | ❌ **MISSING**         | —                                  |
| 3 | First-time setup                       | ⚠️ Partial (in `recalculate_all_badges` L2319+) | Only sets dates on badge creation |
| 4 | ACTIVE → evaluate at end_date          | ❌ **MISSING**         | —                                  |
| 5 | ACTIVE → GRACE transition              | ❌ **MISSING**         | GRACE constant defined, never set  |
| 6 | GRACE → evaluate at grace_end_date     | ❌ **MISSING**         | —                                  |
| 7 | Award success (re-promotion)           | ❌ **MISSING**         | `_apply_badge_result` has no branch for criteria_met + already_earned |
| 8 | Demotion                               | ✅ Exists              | `demote_cumulative_badge()` L1727  |

### What the Current Manager Does Have (Working)

| Feature                     | Status  | Location                       |
|-----------------------------|---------|--------------------------------|
| cycle_points accumulation   | ✅      | `_on_points_changed()` L205    |
| Tier determination          | ✅      | `get_cumulative_badge_levels()` uses `stats.get_period_total()` |
| Demotion (one-way)          | ✅      | `demote_cumulative_badge()` L1727 |
| Progress display            | ✅      | `get_cumulative_badge_progress()` L1586 |
| Multiplier update           | ✅      | `update_point_multiplier_for_kid()` L1410 |
| Badge recording             | ✅      | `_record_badge_earned()` L2078 |

### Critical Differences: Old vs New Architecture

| Aspect | Old Coordinator | New Manager Architecture |
|--------|----------------|--------------------------|
| **Tier total** | `baseline + cycle_points` | `stats.get_period_total()` (all-time) |
| **baseline field** | Stored in progress, absorbs cycle_points on demotion | **REMOVED** (schema v44) |
| **Persistence** | `self._persist()` + `self.async_set_updated_data()` | `self.coordinator._persist()` + signal emission |
| **Multiplier update** | `self._update_point_multiplier_for_kid()` | `self.update_point_multiplier_for_kid()` → emits signal to EconomyManager |
| **Badge award** | `self._award_badge()` | `self._record_badge_earned()` + signal |
| **Scheduled trigger** | Called from `_manage_badge_maintenance()` | ❌ No scheduled trigger exists |

---

## Detailed phase tracking

### Phase 1 – Engine Retention Fix

- **Goal**: Make `check_retention()` semantically correct for cumulative badges by evaluating `cycle_points >= maintenance_rules` instead of `total_points_earned >= threshold` (which never fails).
- **Files touched**: `custom_components/kidschores/engines/gamification_engine.py` ONLY
- **Steps / detailed work items**

  1. - [ ] **Modify `check_retention()` (~L308-327)** — Add cumulative badge branch before fallthrough to `evaluate_badge()`.

     New logic:
     ```python
     @classmethod
     def check_retention(cls, context, badge_data) -> EvaluationResult:
         badge_type = badge_data.get(const.DATA_BADGE_TYPE, "")
         if badge_type == const.BADGE_TYPE_CUMULATIVE:
             return cls._evaluate_cumulative_retention(context, badge_data)
         return cls.evaluate_badge(context, badge_data)
     ```

  2. - [ ] **Add `_evaluate_cumulative_retention()` classmethod** (~25 lines, after `check_retention()`).

     Data sources:
     - `context["cumulative_badge_progress"]["cycle_points"]` — accumulated by manager `_on_points_changed`
     - `badge_data[DATA_BADGE_TARGET][DATA_BADGE_MAINTENANCE_RULES]` — threshold for maintenance

     Key behaviors:
     - `maintenance_rules <= 0` → `criteria_met = True` (no maintenance required)
     - `cycle_points >= maintenance_rules` → `criteria_met = True`
     - `cycle_points < maintenance_rules` → `criteria_met = False`
     - `criterion_type = "cumulative_maintenance"` (distinguishes from acquisition's `"cumulative_points"`)

  3. - [ ] **Verify `evaluate_badge()` inline cumulative block (~L211-240) remains untouched** — Acquisition path works correctly.

  4. - [ ] **Verify periodic badge paths unaffected** — `check_retention` for periodic falls through to `evaluate_badge()`.

- **Key issues**: None. Additive change only.

---

### Phase 2 – Manager Maintenance Processing

- **Goal**: Port the old coordinator's `_manage_cumulative_badge_maintenance()` state machine to `GamificationManager` as `process_cumulative_maintenance()`, adapted for the new architecture.
- **Files touched**: `custom_components/kidschores/managers/gamification_manager.py`
- **Steps / detailed work items**

  1. - [ ] **Add `process_cumulative_maintenance(kid_id: str)` method** — New public method on GamificationManager. Port the old coordinator logic with these architectural adaptations:

     **Adaptations from old code to new architecture:**

     | Old Pattern | New Pattern |
     |-------------|-------------|
     | `self.kids_data.get(kid_id)` | `self.coordinator.kids_data.get(kid_id)` |
     | `self._get_cumulative_badge_levels(kid_id)` | `self.get_cumulative_badge_levels(kid_id)` |
     | `self._persist()` | `self.coordinator._persist()` |
     | `self.async_set_updated_data(self._data)` | Signal emission (see Phase 3) |
     | `self._award_badge(kid_id, badge_id)` | `self._record_badge_earned(kid_id, badge_id)` + emit badge earned signal |
     | `self._update_point_multiplier_for_kid(kid_id)` | `self.update_point_multiplier_for_kid(kid_id)` |
     | `kh.dt_today_iso()` | Use helpers or `dt_utils` equivalent |
     | `kh.dt_add_interval(...)` | Use helpers or `dt_utils` equivalent |
     | `kh.dt_next_schedule(...)` | Use helpers or `dt_utils` equivalent |
     | `const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE` references | **REMOVE** — baseline no longer exists in schema v44 |

     **Critical logic preserved from old code:**

     ```
     1. Guard: early return if no kid_info or no highest_earned badge
     2. Guard: if reset_enabled == False → clear maintenance dates, persist, return
     3. Extract: end_date, grace_date, status, cycle_points from progress
     4. Get: maintenance_required, frequency, grace_days from highest_earned badge
     5. State evaluation:
        a. (ACTIVE or DEMOTED) + past end_date:
           - cycle_points >= maintenance_required → award_success
           - past grace_date → demotion_required
           - grace_days > 0 → set GRACE
           - else → demotion_required
        b. GRACE:
           - cycle_points >= maintenance_required → award_success
           - past grace_date → demotion_required
     6. Calculate next maintenance/grace dates (if award/demotion/first_time)
     7. Apply award_success: status=ACTIVE, reset cycle_points=0, update dates,
        set current_badge=highest, re-award badge
     8. Apply demotion: status=DEMOTED, reset cycle_points=0, set current_badge=next_lower,
        recalculate multiplier
     9. Apply first_time: just set initial dates
     10. Persist
     ```

     **Key difference from old code — cycle_points reset:**
     - Old code: On demotion, `baseline += cycle_points; cycle_points = 0`
     - New code: On demotion, just `cycle_points = 0` (baseline removed)
     - Old code: On award_success, cycle_points was NOT reset (kept accumulating)
     - New code: On award_success, `cycle_points = 0` (cycle is complete, start fresh)
     - **Justification**: Wiki says "If goal met: Cycle resets". Since `cycle_points` is now purely a maintenance counter (not a tier component), resetting on success is correct.

  2. - [ ] **Remove all `baseline` references from maintenance logic** — The old code had `baseline + cycle_points` on demotion. Since baseline is removed (schema v44), demotion simply resets `cycle_points = 0`. Tier determination uses `stats.get_period_total()` independently.

  3. - [ ] **Handle first-time setup** — When badge first earned and `reset_enabled=True` but no `maintenance_end_date` exists yet, calculate and set initial maintenance/grace dates. (Ported directly from old code's `is_first_time` block.)

  4. - [ ] **Add `process_all_kids_maintenance()` loop method** — Iterates all kids and calls `process_cumulative_maintenance(kid_id)` for each.

     ```python
     def process_all_kids_maintenance(self) -> None:
         """Process cumulative badge maintenance for all kids."""
         for kid_id in list(self.coordinator.kids_data):
             self.process_cumulative_maintenance(kid_id)
     ```

  5. - [ ] **Verify `_on_points_changed` cycle_points accumulation** — Confirm it works correctly with maintenance. Currently accumulates for ALL positive deltas regardless of whether maintenance is configured. This is acceptable (0 maintenance_rules → retention always passes, accumulated points harmless).

- **Key issues**
  - **Date calculation imports**: Builder must verify which `dt_*` functions exist in `helpers/` vs `utils/dt_utils.py`. The old code used `kh.dt_today_iso()`, `kh.dt_add_interval()`, `kh.dt_next_schedule()`. Manager CAN use `helpers/` functions (unlike engines which must stay pure).
  - **Signal emission vs direct persist**: Manager calls `self.coordinator._persist()` then emits signal. Determine correct signal for post-maintenance notification.
  - **DEMOTED re-entry**: The old code's status check includes DEMOTED: `status in (ACTIVE, DEMOTED)`. This means a DEMOTED kid's next maintenance window still runs — they can meet the requirement and get re-promoted. **This is the time-based re-promotion path.** Must be preserved.

---

### Phase 3 – Manager Integration Points

- **Goal**: Wire the new maintenance processing into the existing manager lifecycle.
- **Files touched**: `custom_components/kidschores/managers/gamification_manager.py`, possibly `const.py`
- **Steps / detailed work items**

  1. - [ ] **Subscribe GamificationManager to MIDNIGHT_ROLLOVER** — Add listener in `async_initialize()`:

     ```python
     self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)
     ```

     Handler:
     ```python
     async def _on_midnight_rollover(self) -> None:
         """Process daily maintenance checks at midnight."""
         self.process_all_kids_maintenance()
     ```

     **Note**: ChoreManager, UIManager, StatisticsManager already subscribe. GamificationManager needs to be added.

  2. - [ ] **Add re-promotion branch to `_apply_badge_result()` (~L798-892)** — Handle the `criteria_met=True + already_earned=True` case for immediate re-promotion.

     Current branches:
     - `criteria_met=True + not already_earned` → Award badge
     - `criteria_met=False + already_earned` → Demote (cumulative only)

     New branch:
     - `criteria_met=True + already_earned + DEMOTED status` → **Re-promote**: set status=ACTIVE, update current_badge, reset cycle_points, recalculate multiplier

     **Why here AND in `process_cumulative_maintenance()`**: Wiki says "Requalification: Immediate when kid earns enough points (no full cycle required)". Points changes trigger `_evaluate_badge_for_kid()` → `check_retention()` (Phase 1 fix) → `_apply_badge_result()`. This path handles IMMEDIATE re-promotion. The midnight path handles TIME-BASED cycle evaluation.

     **Idempotency guard**: Check `status == DEMOTED` before re-promoting. If already ACTIVE, no-op.

  3. - [ ] **Evaluate `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` usage** — Options:
     - **Use it**: Emit after `process_all_kids_maintenance()` for UI/sensor refresh
     - **Remove it**: If `BADGE_UPDATED`/`BADGE_EARNED` signals suffice
     - **Recommendation**: Use it — emit once after the loop completes (not per-kid)

  4. - [ ] **Verify `recalculate_all_badges()` compatibility** — The existing method (L2230-2520) sets initial dates for new badges. Confirm it doesn't conflict with `process_cumulative_maintenance()`.

- **Key issues**
  - **Two re-promotion paths**: (a) Time-based via midnight → `process_cumulative_maintenance()`, (b) Event-based via point change → `_apply_badge_result()`. Both must set status=ACTIVE and reset cycle_points. Guard with status check to prevent double-processing.
  - **Signal ordering**: Midnight rollover fires for multiple managers. Ensure GamificationManager's handler doesn't conflict with StatisticsManager's period flush.

---

### Phase 4 – Tests

- **Goal**: Comprehensive coverage for engine retention + manager maintenance processing.
- **Files touched**: `tests/test_gamification_engine.py`, potentially new test file
- **Steps / detailed work items**

  **Engine Tests** (in `test_gamification_engine.py`):

  1. - [ ] **Update `make_badge()` helper** — Add `maintenance_threshold` parameter → `DATA_BADGE_MAINTENANCE_RULES` in target.
  2. - [ ] **Fix `test_check_retention_criteria_met`** — Test with `cycle_points >= maintenance_threshold`.
  3. - [ ] **Fix `test_check_retention_criteria_not_met`** — Test with `cycle_points < maintenance_threshold`.
  4. - [ ] **Add test: zero maintenance always passes** — `maintenance_threshold=0, cycle_points=0 → True`.
  5. - [ ] **Add test: periodic retention uses acquisition logic** — Verify periodic doesn't hit cumulative path.
  6. - [ ] **Clean up stale `cumulative_baseline` references** — Remove from `make_context()`.

  **Manager Maintenance Tests**:

  7. - [ ] **ACTIVE + end_date past + points met → award_success** — Status ACTIVE, cycle_points=0, dates advanced.
  8. - [ ] **ACTIVE + end_date past + points NOT met + grace>0 → GRACE** — Status transitions.
  9. - [ ] **ACTIVE + end_date past + points NOT met + no grace → DEMOTED** — Status DEMOTED, cycle_points=0.
  10. - [ ] **GRACE + points met → ACTIVE** — Re-promotion from grace.
  11. - [ ] **GRACE + expired → DEMOTED** — Demotion from grace.
  12. - [ ] **DEMOTED + end_date past + points met → ACTIVE** — Time-based re-promotion.
  13. - [ ] **maintenance_rules=0 → skip** — No state changes.
  14. - [ ] **reset not enabled → clear dates** — Early return path.
  15. - [ ] **First-time setup → dates initialized** — New badge gets dates.
  16. - [ ] **Immediate re-promotion via `_apply_badge_result`** — criteria_met + earned + DEMOTED → ACTIVE.

- **Key issues**: Need test infrastructure mocking coordinator, stats engine, kids_data with cumulative progress.

---

### Phase 5 – Validation

- **Goal**: Full quality gate pass.
- **Steps**:

  1. - [ ] `./utils/quick_lint.sh --fix` — Must pass (ruff + boundaries 10/10).
  2. - [ ] `mypy custom_components/kidschores/` — Zero errors.
  3. - [ ] `python -m pytest tests/test_gamification_engine.py -v` — All engine tests pass.
  4. - [ ] `python -m pytest tests/ -v --tb=line` — All 1259+ tests pass.
  5. - [ ] Spot-check periodic badge tests unaffected.
  6. - [ ] `grep -r "baseline_points" tests/ custom_components/` — Cleanup complete.

---

## Notes & follow-up

### Architectural Insight: `cycle_points` Role Has Changed

In the old coordinator:
- `baseline + cycle_points = total_points` → used for **tier determination** (which badge level)
- On demotion: `baseline += cycle_points; cycle_points = 0` → total preserved for tiers

In the new manager:
- `stats.get_period_total()` = total earned → used for **tier determination**
- `cycle_points` is ONLY for **maintenance evaluation** (did kid earn enough THIS cycle?)
- On demotion: just `cycle_points = 0` — no baseline, tiers use stats engine
- On award success: `cycle_points = 0` — cycle complete, fresh start

This makes `cycle_points` simpler — a pure maintenance counter, not a tier component.

### `baseline` Field Status

- **Removed in schema v44** (prior work)
- Old code stored baseline in progress, used for tier calc
- New code: tiers from `stats.get_period_total()` (authoritative)
- Old demotion logic (`baseline += cycle_points`) → replaced by `cycle_points = 0`

### Date Utility Functions

Old code used `kh.dt_today_iso()`, `kh.dt_add_interval()`, `kh.dt_next_schedule()`. Builder must verify which are in `helpers/` (HA-aware, OK for manager) vs `utils/dt_utils.py` (pure). Key functions: today ISO date, add interval to date, next schedule occurrence. These likely live in `helpers/dt_helpers.py` or similar.

### Follow-up Optimizations (Out of Scope)

- [ ] Guard `_on_points_changed` to only accumulate when maintenance_rules > 0 on any badge
- [ ] Review `recalculate_all_badges()` initial setup for conflicts
- [ ] Decide fate of `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` (use or remove)
