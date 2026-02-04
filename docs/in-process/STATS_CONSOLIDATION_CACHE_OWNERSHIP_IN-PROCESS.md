# Stats Consolidation & Cache Ownership - Implementation Plan

## Initiative snapshot

- **Name / Code**: Stats Consolidation & Cache Ownership (Phase 7G from Data Reset V2)
- **Target release / milestone**: v0.5.0-beta3 (current release)
- **Owner / driver(s)**: Strategic Planning Agent → Builder Agent
- **Status**: Not started (plan complete, ready for handoff)
- **Breaking Change**: Yes - Storage schema v42→v43, API changes, manager rename

## Summary & immediate steps

| Phase / Step                           | Description                                                   | % complete | Quick notes                                                                      |
| -------------------------------------- | ------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------- |
| Phase 1 – point_stats Migration        | Consolidate flat point_stats into period buckets              | 100%       | ✅ COMPLETE - Migration v43, earned/spent split, PRES\_\* reads work             |
| **Phase 1B – Transactional Flush**     | **Fix cache refresh architecture (sensor staleness)**         | **100%**   | ✅ COMPLETE - StatisticsManager owns flush, 8 redundant calls removed            |
| **Phase 1C – point_data Rename**       | **Rename `point_data` → `point_periods` (consistency)**       | **100%**   | ✅ COMPLETE - Migration v43, 11 validation tests (100% pass), cache working      |
| **Phase 2 – Lean Chore Architecture**  | **"Lean Item / Global Bucket" pattern for chore statistics**  | **100%**   | ✅ COMPLETE - chore*periods created, total*\* removed, chore_stats deleted (v43) |
| **Phase 3 – Lean Reward Architecture** | **"Lean Item / Global Bucket" pattern for reward statistics** | **100%**   | ✅ COMPLETE - All steps done; migration fix applied (total\_\* backfill)         |
| Phase 4 – Period Update Ownership      | Centralize ALL period updates in StatisticsManager            | 0%         | Move reward/badge updates from domain managers to listeners                      |
| Phase 5 – Manager Rename               | Rename StatisticsManager → CacheManager                       | 0%         | Post-consolidation name reflects true purpose                                    |
| Phase 6 – Storage Migration            | Schema v43 migration for "Lean Item / Global Bucket"          | 0%         | Create `*_periods`, remove redundant fields, backfill data                       |
| Phase 7 – Testing & Validation         | Comprehensive test coverage for new architecture              | 0%         | Period data integrity, cache refresh, ownership boundaries                       |

1. **Key objective** – Implement "Lean Item / Global Bucket" pattern: eliminate redundant `*_stats` dicts and `total_*` fields from item roots, create sibling `*_periods` buckets at kid level for aggregated history that survives item deletion, centralize ALL period updates through single ownership model (StatisticsManager → CacheManager).

2. **Summary of recent work** – Phase 1C: COMPLETE. Created comprehensive migration validation test suite (771 lines, 11 tests) covering v40→v43 transformation, sensor attributes, temporal stats, and manual adjustment updates. All tests pass (100%). Migration validation confirms point_periods structure works correctly with varying data patterns.

3. **Next steps (short term)** – **Phase 3**: Complete "Lean Item / Global Bucket" for rewards - remove `total_*` fields from `reward_data[uuid]`, remove `notification_ids` (NotificationManager handles via signals), delete `reward_stats` dict. Schema v43 migration.

4. **Risks / blockers** –
   - **Breaking change**: Storage schema v43 (Phase 2 chores + Phase 3 rewards combined)
   - **Landlord/Tenant coordination**: Domain managers create/reset `*_periods` buckets, StatisticsManager only writes
   - **Genesis safety**: Must prevent StatisticsManager from resurrecting buckets after data_reset deletes them
   - **Migration complexity**: Moving `total_*` data into new `*_periods` buckets
   - **Testing burden**: Must validate period data integrity across all stat types
   - **Notification tracking**: Remove notification_ids from reward_data - NotificationManager owns notification lifecycle

5. **References**:
   - [DATA_RESET_SERVICE_V2_IN-PROCESS.md](DATA_RESET_SERVICE_V2_IN-PROCESS.md) § Phase 7G - Original planning
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and period structure
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Manager patterns and event architecture
   - [statistics_manager.py](../../custom_components/kidschores/managers/statistics_manager.py) - Current implementation
   - [statistics_engine.py](../../custom_components/kidschores/engines/statistics_engine.py) - Period update logic

6. **Decisions & completion check**
   - **Decisions captured**:
     - **points_net**: DERIVED on-demand, NEVER stored (calculated as `earned + spent`)
     - **highest_balance**: ONLY in all_time bucket (period-specific peaks not useful)
     - **Split points_total**: → `points_earned` (positive) + `points_spent` (negative)
     - **Keep all_time counters**: Incrementally maintained data (cannot recompute after pruning)
     - **Delete temporal snapshots**: Derived from period buckets (today/week/month/year)
     - **Ownership model**: StatisticsManager is SOLE owner of period updates (domain managers emit signals only)
     - **Post-consolidation name**: CacheManager (reflects ephemeral PRES\_\* cache + period updates)
     - **Phase 1B - Transactional Flush**: StatisticsManager is SOLE owner of `async_set_updated_data()` for transaction signals
     - **Phase 1B - Kill Debounce**: 500ms debounce removed from transaction paths (calculation is microseconds)
     - **Phase 1B - Accounting Man Pattern**: Update → Account → Flush (strict ordering)
     - **Phase 1C - point_data Rename**: Rename `point_data` → `point_periods` (only contains `periods` key)
     - **"Lean Item / Global Bucket" Pattern**: Item-specific `*_data[uuid]` has metadata + `periods`; sibling `*_periods` bucket has aggregated history surviving deletion
     - **Landlord/Tenant Pattern**: Domain managers are Landlords (create/reset `*_periods`); StatisticsManager is Tenant (writes only, uses `.get()` not `.setdefault()`)
     - **Genesis vs. Resurrection**: Landlord calls `_ensure_kid_structures()` at transaction start; Tenant logs warning if bucket missing (prevents resurrection after data_reset)
     - **Remove total\_\* from item roots**: Use `item.periods.all_time` as canonical source (eliminates duplication)
     - **notification_ids**: DELETE from `reward_data[uuid]` - NotificationManager owns notification lifecycle via signal payloads and action buttons (no need for RewardManager tracking)
     - **Schema version**: v43 includes all Phase 1-3 changes (points, chores, rewards consolidation)
   - **Completion confirmation**: `[ ]` All phases complete, migration tested, documentation updated

---

## Tracking expectations

- **Summary upkeep**: Update summary table percentages and notes after each phase completion
- **Detailed tracking**: Use phase sections below for granular progress, blockers, and technical details

---

## Detailed phase tracking

### Phase 1 – point_stats Migration

**Goal**: Move all-time point data from flat `point_stats` into `point_data.periods.all_time` structure.

**Status**: ✅ 100% COMPLETE - Migration v43 deployed in v0.5.0-beta3. All point statistics now read from period buckets. Cache refresh logic exists but has architectural timing issues (covered in Phase 1B).

#### Problem Statement

**Current Duplication**:

- `point_stats` has: `points_earned_all_time`, `points_spent_all_time`, `points_net_all_time`, `by_source_all_time`, `highest_balance_all_time`
- `point_data.periods.all_time` has: `points_total`, `by_source`
- Creates synchronization bugs and storage bloat

**Why point_stats is Data (MUST persist)**:

- `points_earned_all_time` incremented on every transaction (cannot recompute after pruning old periods)
- `points_spent_all_time` incremented on every withdrawal (cannot recompute after pruning)
- `by_source_all_time` incremented per source (cannot recompute after pruning)
- `highest_balance_all_time` tracks historical peak (cannot recompute from pruned data)
- `points_net_all_time` is DERIVED (`earned + spent`) → DELETE

#### Target Structure

**Standard period buckets** (daily/weekly/monthly/yearly):

```json
"daily": {
  "2026-02-02": {
    "points_earned": 2213.0,    // Sum of positive deltas
    "points_spent": -225.0,     // Sum of negative deltas
    // points_net: DERIVED (earned + spent) - not stored
    "by_source": {
      "manual": 1864.0,
      "bonuses": 225.0,
      "penalties": -101.0
    }
  }
}
```

**all_time bucket** (cumulative high-water marks):

```json
"all_time": {
  "all_time": {
    "points_earned": 6173.0,        // ← FROM point_stats.points_earned_all_time
    "points_spent": -696.0,         // ← FROM point_stats.points_spent_all_time
    // points_net: DERIVED (not stored)
    "by_source": {                  // ← FROM point_stats.by_source_all_time
      "chores": 329.0,
      "rewards": -40.0,
      "bonuses": 15.0
    },
    "highest_balance": 2980.0       // ← FROM point_stats.highest_balance_all_time
                                     // ONLY in all_time bucket (cumulative peak)
  }
}
```

#### Steps / detailed work items

**1.1 - Code Audit**:

- [ ] Find all code reading from `point_stats` (grep search)
- [ ] Find all code writing to `point_stats` (StatisticsEngine, EconomyManager)
- [ ] Identify PRES\_\* cache constants using point_stats data
- [ ] List all entity attributes derived from point_stats

**1.2 - Constants Update**:

- [ ] Add `POINT_DATA_PERIOD_EARNED` constant (vs existing `POINT_DATA_PERIOD_TOTAL`)
- [ ] Add `POINT_DATA_PERIOD_SPENT` constant
- [ ] Add `POINT_DATA_PERIOD_HIGHEST_BALANCE` constant (for all_time only)
- [ ] Keep `POINT_DATA_PERIOD_BY_SOURCE` (already exists)
- [ ] Mark point_stats constants as LEGACY

**1.3 - StatisticsEngine Updates**:

- [ ] Update `record_transaction()` to write `points_earned` and `points_spent` separately
  - Positive deltas → `points_earned`
  - Negative deltas → `points_spent`
  - Both go into same period buckets
- [ ] Update `_get_or_create_period_entry()` to initialize both fields
- [ ] Update highest_balance tracking to write to all_time bucket only
- [ ] Keep existing `by_source` tracking (no change)

**1.4 - Migration v44 Creation**:

- [ ] Create `_migrate_to_v44()` method in migration module (note: current schema is v43 in v0.5.0-beta3)
- [ ] Backfill logic:

  ```python
  for period, buckets in point_data.periods.items():
      for bucket_key, bucket_data in buckets.items():
          total = bucket_data.get("points_total", 0.0)
          by_source = bucket_data.get("by_source", {})

          # Split total into earned/spent based on by_source signs
          earned = sum(v for v in by_source.values() if v > 0)
          spent = sum(v for v in by_source.values() if v < 0)

          bucket_data["points_earned"] = earned
          bucket_data["points_spent"] = spent
          # Keep points_total for backward compat? Or delete?
  ```

- [ ] Move point_stats fields into all_time bucket:
  ```python
  all_time_bucket = point_data.periods.setdefault("all_time", {}).setdefault("all_time", {})
  all_time_bucket["points_earned"] = point_stats["points_earned_all_time"]
  all_time_bucket["points_spent"] = point_stats["points_spent_all_time"]
  all_time_bucket["by_source"] = point_stats["by_source_all_time"]
  all_time_bucket["highest_balance"] = point_stats["highest_balance_all_time"]
  ```
- [ ] Delete point_stats (or set to empty dict for backward compat)
- [ ] Increment SCHEMA_VERSION_STORAGE_ONLY to 44 (current: v43 in v0.5.0-beta3)

**1.5 - Reader Updates**:

- [ ] Update all code reading `point_stats.points_earned_all_time` → `point_data.periods.all_time.all_time.points_earned`
- [ ] Update all code reading `point_stats.points_spent_all_time` → `point_data.periods.all_time.all_time.points_spent`
- [ ] Update all code reading `point_stats.by_source_all_time` → `point_data.periods.all_time.all_time.by_source`
- [ ] Update all code reading `point_stats.highest_balance_all_time` → `point_data.periods.all_time.all_time.highest_balance`
- [ ] Replace `points_net_all_time` with calculation: `points_earned + points_spent`

**1.6 - PRES\_\* Cache Updates**:

- [x] Update StatisticsManager cache refresh methods to read from new structure
- [x] Ensure PRES_KID_POINTS_EARNED_ALL_TIME uses `point_data.periods.all_time.all_time.points_earned`
- [x] Ensure PRES_KID_POINTS_SPENT_ALL_TIME uses `point_data.periods.all_time.all_time.points_spent`
- [x] Ensure PRES_KID_HIGHEST_BALANCE_ALL_TIME uses `point_data.periods.all_time.all_time.highest_balance`
- [x] **IN PROGRESS**: Fix cache refresh timing in `_on_points_changed()` - cache must refresh BEFORE `async_set_updated_data()` to ensure sensor attributes show fresh values immediately → **MOVED TO PHASE 1B** (architectural issue requires broader fix)

**1.7 - Testing**:

- [x] ✅ Created comprehensive validation test suite (tests/test_points_migration_validation.py, 771 lines)
- [x] ✅ Test migration v40→v43 (3 tests covering structure, historical data, all_time calculations)
- [x] ✅ Verify sensor attributes work correctly (2 tests covering all 40+ attributes)
- [x] ✅ Test manual adjustments update cache correctly (6 tests covering +10, +2, -2, cumulative)
- [x] ✅ All 11 tests passing (100%) with proper hass_storage fixture pattern
- [x] ✅ Migration handles varying data patterns (kids with only yearly vs full period data)

**Test Coverage Summary**:

- **Migration Tests (3)**: Structure validation, historical data preservation, all_time calculations
- **Attribute Tests (2)**: All temporal stats present, net values derived correctly
- **Manual Adjustment Tests (6)**: Earned/spent/net updates, by_source tracking, highest_balance, cumulative

**Key issues resolved**:

- ✅ Test uses realistic v40beta1 sample data
- ✅ Handles kids with partial period data (not all have monthly/weekly)
- ✅ Validates presentation cache (PRES\_\*) reads from new structure

---

### Phase 1B – Transactional Flush Architecture (Cache Refresh Timing)

**Goal**: Fix the "Asynchronous Desync" causing stale sensor attributes by implementing the "Accounting Man" pattern.

**Status**: ✅ 100% COMPLETE - StatisticsManager owns `async_set_updated_data()` for all transaction signals. 8 redundant calls removed from domain managers. All 1199 tests pass.

#### Problem Statement: The Snapshot Timing Race

**The Core Bug**: `async_set_updated_data()` is a **Snapshot Command**. It tells all entities: "Read your state from the coordinator **right now**." If the StatisticsManager is still "waiting 500ms" to calculate the numbers, the entities snapshot a ghost.

**Why Current Architecture Fails**:

```
ChoreManager.claim_chore():
  1. Update _data (chore state)
  2. _persist()
  3. emit(CHORE_CLAIMED)                    ← Signal queued on event loop
  4. async_set_updated_data()               ← Sensors read stale cache HERE
  ...later...
  5. StatisticsManager._on_chore_claimed()  ← Cache refreshed AFTER sensors read
```

**The Fatal Flaw**: We're debouncing the **Calculation** (cache), but we should only debounce the **Persistence** (disk).

- **Calculating a statistic** (summing buckets) = microseconds (CPU-bound)
- **Writing to disk** (I/O) = milliseconds (hardware wear)
- **Serving "lies" to UI for 500ms** = unacceptable user experience

#### Deep Audit: All Gremlins Found

**Audit Date**: 2026-02-03
**Method**: grep*search for `async_set_updated_data`, `self.emit(`, `_schedule_cache_refresh`, `\_refresh*\*\_cache`

##### Finding 1: Distributed `async_set_updated_data()` Calls (32 Locations!)

Every manager that touches data calls `async_set_updated_data()` independently. This makes it **impossible** to guarantee the "Accounting" is finished before sensors read.

| Manager              | Locations | Risk Level |
| -------------------- | --------- | ---------- |
| ChoreManager         | 12        | 🔴 HIGH    |
| RewardManager        | 6         | 🔴 HIGH    |
| EconomyManager       | 4         | 🔴 HIGH    |
| GamificationManager  | 7         | 🟡 MEDIUM  |
| StatisticsManager    | 1         | ✅ CORRECT |
| migration_pre_v50.py | 2         | 🟢 OK      |

**The Problem**: When `ChoreManager.approve_chore()` emits `CHORE_APPROVED` and immediately calls `async_set_updated_data()`, the signal and the snapshot call are **both put on the event loop**. In many cases, `async_set_updated_data()` executes BEFORE `StatisticsManager._on_chore_approved()` finishes.

##### Finding 2: Wrong Tier for Transaction Events

StatisticsManager uses `_schedule_cache_refresh()` (500ms debounce) for some transaction events:

| Handler                    | Current Pattern                | Should Be               |
| -------------------------- | ------------------------------ | ----------------------- |
| `_on_points_changed()`     | Sync refresh ✅                | ✅ Correct              |
| `_on_chore_approved()`     | `_record_chore_transaction()`  | ✅ Calls refresh inside |
| `_on_chore_claimed()`      | `_record_chore_transaction()`  | ✅ Calls refresh inside |
| `_on_chore_completed()`    | Batch sync refresh             | ✅ Correct              |
| `_on_chore_disapproved()`  | `_record_chore_transaction()`  | ✅ Calls refresh inside |
| `_on_chore_overdue()`      | `_record_chore_transaction()`  | ✅ Calls refresh inside |
| `_on_chore_status_reset()` | ⚠️ `_schedule_cache_refresh()` | 🔴 **GREMLIN #1**       |
| `_on_chore_undone()`       | ⚠️ `_schedule_cache_refresh()` | 🔴 **GREMLIN #2**       |
| `_on_reward_approved()`    | ⚠️ **NO REFRESH AT ALL**       | 🔴 **GREMLIN #3**       |

##### Finding 3: Missing Event Listeners

StatisticsManager doesn't listen to some signals that affect cache values:

| Signal            | StatisticsManager Listens? | Needs PRES\_\* Refresh?                              |
| ----------------- | -------------------------- | ---------------------------------------------------- |
| `REWARD_CLAIMED`  | ❌ NO                      | ✅ YES                                               |
| `BONUS_APPLIED`   | ❌ NO                      | ✅ YES (via POINTS_CHANGED, but needs reward cache)  |
| `PENALTY_APPLIED` | ❌ NO                      | ✅ YES (via POINTS_CHANGED, but needs penalty stats) |

##### Finding 4: Signal-Then-Flush Race Condition in RewardManager

```python
# reward_manager.py lines 506-519
async def approve(...):
    self._grant_to_kid(...)
    self._recalculate_stats_for_kid(kid_id)

    self.coordinator._persist()

    self.emit(const.SIGNAL_SUFFIX_REWARD_APPROVED, ...)  # Signal queued

    self.coordinator.async_set_updated_data(...)  # RACE: sensors read BEFORE signal processed!
```

**EconomyManager.withdraw()** is called inside `approve()` and emits `POINTS_CHANGED`, but the `async_set_updated_data()` at the end of `approve()` can still beat the StatisticsManager handler.

#### Risk Assessment

| Rank | Finding                          | Severity    | Category     | Impact                                             |
| ---- | -------------------------------- | ----------- | ------------ | -------------------------------------------------- |
| 1    | Snapshot Timing Race             | 🔴 CRITICAL | Architecture | Sensors read cache before calculation finishes     |
| 2    | Distributed Flush (32 locations) | 🔴 HIGH     | Standards    | Impossible to guarantee accounting before snapshot |
| 3    | Missing Listeners                | 🟡 MEDIUM   | Logic        | REWARD_CLAIMED, BONUS_APPLIED don't refresh cache  |
| 4    | Unnecessary 500ms Throttle       | 🟢 LOW      | Performance  | Adds complexity for microsecond-fast dict lookups  |

#### The Solution: "Transactional Flush" Pattern

**Principle**: Update → Account → Flush (in that order, always)

##### Pattern 1: "Accounting Man" Flush

StatisticsManager becomes the **sole owner** of `async_set_updated_data()` for transaction signals.

**Current Flow** (broken):

```
DomainManager.action():
  1. Modify _data
  2. _persist()
  3. emit(SIGNAL)
  4. async_set_updated_data()  ← TOO EARLY
```

**New Flow** (correct):

```
DomainManager.action():
  1. Modify _data
  2. _persist()
  3. emit(SIGNAL)
  ← NO async_set_updated_data() here

StatisticsManager._on_signal():
  1. Update period buckets
  2. _refresh_*_cache()  ← Synchronous, immediate
  3. async_set_updated_data()  ← ONLY after accounting complete
```

##### Pattern 2: Synchronous Cache for Transactions, Debounce for Background

| Trigger Type      | Refresh Pattern                      | Rationale                         |
| ----------------- | ------------------------------------ | --------------------------------- |
| Human-initiated   | `_refresh_*_cache()` sync            | User expects instant feedback     |
| Background sweeps | `_schedule_cache_refresh()` debounce | Batching prevents thundering herd |
| Midnight rollover | `invalidate_cache()` sync            | Clean slate at midnight           |

#### Steps / Detailed Work Items

**1B.1 - Remove Debounce from Transaction Paths**: ✅ COMPLETE

- [x] Change `_on_chore_status_reset()`: Replace `_schedule_cache_refresh(kid_id, "chore")` with `_refresh_chore_cache(kid_id)`
- [x] Change `_on_chore_undone()`: Replace `_schedule_cache_refresh(kid_id, "chore")` with `_refresh_chore_cache(kid_id)`

**1B.2 - Add Missing Cache Refresh to `_on_reward_approved()`**: ✅ COMPLETE

- [x] Add `self._refresh_reward_cache(kid_id)` to `_on_reward_approved()` (point cache handled by \_on_points_changed)
- Note: Point cache refresh happens via EconomyManager.withdraw() → POINTS_CHANGED → \_on_points_changed()

**1B.3 - Add Missing Signal Listeners**: ✅ COMPLETE

- [x] Add listener for `SIGNAL_SUFFIX_REWARD_CLAIMED` → `_on_reward_claimed()` with `_refresh_reward_cache()` and `async_set_updated_data()`
- [x] Add listener for `SIGNAL_SUFFIX_REWARD_DISAPPROVED` → `_on_reward_disapproved()` with `_refresh_reward_cache()` and `async_set_updated_data()`
- [x] Verified `BONUS_APPLIED` / `PENALTY_APPLIED` signals flow through `POINTS_CHANGED` (no separate listeners needed)

**1B.4 - Implement "Accounting Man" Pattern**: ✅ COMPLETE (StatisticsManager handlers)

Domain managers stop calling `async_set_updated_data()`. StatisticsManager calls it after processing each transaction signal.

**Option A: StatisticsManager Owns All Flushes** (Implemented for v0.5.0-beta3)

- [x] Add `async_set_updated_data()` call at end of:
  - `_on_chore_approved()` → after `_record_chore_transaction()`
  - `_on_chore_claimed()` → after `_record_chore_transaction()`
  - `_on_chore_completed()` → after batch loop
  - `_on_chore_disapproved()` → after `_record_chore_transaction()`
  - `_on_chore_overdue()` → after `_record_chore_transaction()`
  - `_on_chore_status_reset()` → after `_refresh_chore_cache()`
  - `_on_chore_undone()` → after `_refresh_chore_cache()`
  - `_on_reward_approved()` → after `_refresh_*_cache()` calls
  - `_on_reward_claimed()` → after `_refresh_reward_cache()`
  - `_on_reward_disapproved()` → after `_refresh_reward_cache()`
- Note: `_on_points_changed()` already had Transactional Flush pattern (the original working example)

**Option B: Central Flush Coordinator** (Future consideration)

- Create a new `FlushManager` or add to `SystemManager`
- All managers call `coordinator.schedule_flush()` instead of direct `async_set_updated_data()`
- Single 16ms debounce aggregates all signals in one event loop tick

**1B.5 - Remove Redundant `async_set_updated_data()` Calls**: ✅ COMPLETE

Audit and remove from domain managers where StatisticsManager now owns the flush:

**ChoreManager** (11→5 locations): 6 REMOVED

- [x] Line 413: `claim_chore()` → **REMOVED** (StatisticsManager.\_on_chore_claimed owns flush)
- [x] Line 786: `approve_chore()` → **REMOVED** (StatisticsManager.\_on_chore_approved/completed owns flush)
- [x] Line 886: `disapprove_chore()` → **REMOVED** (StatisticsManager.\_on_chore_disapproved owns flush)
- [x] Line 954: `undo_chore()` (parent) → **REMOVED** (StatisticsManager.\_on_chore_undone owns flush)
- [x] Line 1355: `_process_overdue()` → **REMOVED** (StatisticsManager.\_on_chore_overdue owns flush)
- [x] Line 1054: `undo_claim()` (kid self) → **KEEP** (no signal emitted - silent undo)
- [x] Line 1715: `set_due_date()` → **KEEP** (config change, no stat signal)
- [x] Line 1831: `skip_due_date()` → **KEEP** (config change, no stat signal)
- [x] Line 1854: `reset_all_chore_states_to_pending()` → **KEEP** (batch with persist=False)
- [x] Line 1903: `reset_overdue_chores()` → **KEEP** (batch with persist=False)
- [x] Line 2762: `_transition_chore_state()` → **KEEP** (needed when emit=False or state!=PENDING)

**RewardManager** (6→4 locations): 2 REMOVED

- [x] Line 519: `approve()` → **REMOVED** (StatisticsManager.\_on_reward_approved owns flush)
- [x] Line 403: `claim()` → **REMOVED** (StatisticsManager.\_on_reward_claimed owns flush)
- [x] Line 125: `_on_badge_granted()` → **KEEP** (badge event, no stat signal listener)
- [ ] Line 670: `disapprove()` → **KEEP** (no REWARD_DISAPPROVED listener)
- [ ] Line 728: `undo_claim()` → **KEEP** (silent undo, no signal)
- [ ] Line 821: `reset_rewards()` → **KEEP** (batch reset, no signal)

**EconomyManager** (4 locations to audit): **DEFERRED**

- [ ] Line 744, 847, 934, 1037: These are for CRUD operations (bonus/penalty create/update) - keep for now

**GamificationManager** (7 locations): **DEFERRED**

- [ ] These are for badge/achievement/challenge operations - keep unless covered by new signals

**1B.6 - Keep Debounce ONLY For Background Operations**: ✅ COMPLETE (by design)

- [x] `_schedule_cache_refresh()` remains available for:
  - Midnight rollover (via `_on_midnight_rollover()` which uses `invalidate_cache()`)
  - Background sweeps (future use)
- [x] Transaction handlers now use sync refresh + immediate flush

**1B.7 - Testing**: ✅ COMPLETE

- [x] All 1199 tests pass
- [x] Test chore claim → sensor attributes update immediately
- [x] Test reward approve → points sensor shows deduction immediately
- [x] Verify no duplicate `async_set_updated_data()` calls (only StatisticsManager for transactions)

**1B.8 - Documentation**: DEFERRED to Phase 5 (post-CacheManager rename)

- [ ] Update ARCHITECTURE.md § Event Architecture with "Accounting Man" pattern
- [ ] Update DEVELOPMENT_STANDARDS.md § 5.3 with new flush ownership rules
- [ ] Add docstring to StatisticsManager explaining flush ownership

#### Key Issues / Dependencies

- ✅ **RESOLVED**: 8 redundant `async_set_updated_data()` calls removed from domain managers
- ✅ **RESOLVED**: StatisticsManager now owns flush for all transaction signals
- **Backward compatibility**: No storage changes, pure architectural refactor
- **Performance**: Net positive - fewer duplicate flushes, no 500ms delay

#### Decision Log

| Decision                                             | Rationale                                                      | Date       |
| ---------------------------------------------------- | -------------------------------------------------------------- | ---------- |
| StatisticsManager owns all transaction flushes       | Single "Accounting Man" ensures cache is fresh before snapshot | 2026-02-03 |
| Kill 500ms debounce for transaction paths            | Calculation is microseconds; delay causes stale reads          | 2026-02-03 |
| Keep debounce for background operations              | Midnight rollover / bulk sweeps benefit from batching          | 2026-02-03 |
| Option A (v0.5.0-beta3) over Option B (FlushManager) | Simpler, less invasive for current release                     | 2026-02-03 |

---

### Phase 1C – point_data Rename (Consistency)

**Goal**: Rename `point_data` → `point_periods` to eliminate unnecessary nesting and align with new `chore_periods`/`reward_periods` naming.

**Status**: ✅ 100% Complete - v42→v43 migration implemented, all tests passing

#### Problem Statement

**Current Structure**:

```json
"kid": {
  "point_data": {
    "periods": { ... }  // ← Only child is "periods"
  }
}
```

**Why Rename**:

- `point_data` contains ONLY a `periods` key - the extra nesting is unnecessary
- New `chore_periods` and `reward_periods` will be flat period buckets
- Consistency: all three should be `*_periods` at kid level

**Target Structure**:

```json
"kid": {
  "point_periods": { "daily": {}, "weekly": {}, "monthly": {}, "yearly": {}, "all_time": {} },
  "chore_periods": { "daily": {}, "weekly": {}, "monthly": {}, "yearly": {}, "all_time": {} },
  "reward_periods": { "daily": {}, "weekly": {}, "monthly": {}, "yearly": {}, "all_time": {} }
}
```

#### Steps / Detailed Work Items

**1C.1 - Constants Update**:

- [x] Add `DATA_KID_POINT_PERIODS = "point_periods"` to const.py
- [x] Mark `DATA_KID_POINT_DATA` as LEGACY (will be removed after migration)
- [x] Update section comments to reflect v43+ structure

**1C.2 - Code Updates**:

- [x] Search for all `DATA_KID_POINT_DATA` usages (found 5 files)
- [x] Update readers to use `DATA_KID_POINT_PERIODS` directly (no `.periods` access needed)
  - Updated: EconomyManager, StatisticsManager, KidPointsSensor, sensor_legacy, data_builders
- [x] Update writers (StatisticsManager/Engine) to use new key
- [x] Add proper type annotations to avoid mypy errors

**1C.3 - Migration Logic**:

- [x] Add `_migrate_point_periods_v43()` to PreV50Migrator
- [x] Flatten: `point_data.periods` → `point_periods`
- [x] Transform: `points_total` → `points_earned` (positive by_source) + `points_spent` (negative)
- [x] Extract: `highest_balance` from `point_stats` → `point_periods.all_time.all_time`
- [x] Remove: Deprecated `point_stats` and `point_data` buckets
- [x] Add helper method `_transform_period_entry()` for field transformations

**1C.4 - Genesis Logic**:

- [x] Update `EconomyManager._ensure_point_structures()` to create `point_periods` directly
- [x] Verify no nested `.periods` creation needed

**1C.5 - Testing**:

- [x] Lint check: ✅ Passed (9.8/10 - ruff, mypy, boundaries all clean)
- [x] Test suite: ✅ 1199 tests passing
- [x] Type check: ✅ Zero mypy errors
- [x] Added `point_periods` to KidData TypedDict
- [x] Runtime verification: Fixed presentation cache bug in `_refresh_point_cache()`

**Runtime Bug Fixed** (Post-Implementation):

- **Issue**: After migration, temporal stats (today/week/month/year) showed zeros in sensor attributes despite correct storage structure
- **Root Cause**: `StatisticsManager._refresh_point_cache()` still reading from old nested `point_data.periods` path (line 1078)
- **Fix**: Updated line 1078 to read from flat `point_periods` structure: `pts_periods = kid_info.get(const.DATA_KID_POINT_PERIODS, {})`
- **Validation**: All tests pass, lint clean, temporal stats now populate correctly in sensors

**Key Issues**: Migration handles v42→v43 transformation, preserves highest_balance from point_stats, calculates earned/spent from by_source. Presentation cache now correctly reads from flat `point_periods` structure.

---

### Phase 2 – Lean Chore Architecture ("Lean Item / Global Bucket" Pattern)

**Goal**: Implement "Lean Item / Global Bucket" pattern for chores - remove redundant `total_*` fields from item roots, create sibling `chore_periods` bucket, delete `chore_stats` entirely.

**Status**: 🚧 IN PROGRESS - Code audit & test planning (2026-02-03)

**Learnings Applied from Phase 1C**:

- ✅ Use hass_storage fixture for pytest-homeassistant integration
- ✅ Test migration with realistic sample data showing varied chore patterns
- ✅ Validate all sensor attributes comprehensively (~30+ chore-related attributes)
- ✅ Test cache refresh timing with manual operations (claim, approve, disapprove)
- ✅ Handle edge cases (chores with no history, varying period coverage)

#### The "Lean Item / Global Bucket" Pattern

**Principle**: Separate concerns between Item-specific data and Aggregated history.

| Layer               | Location           | Contents                                             | Survives Item Deletion? |
| ------------------- | ------------------ | ---------------------------------------------------- | ----------------------- |
| **Boutique** (Item) | `chore_data[uuid]` | Metadata, state, timestamps, item-specific `periods` | ❌ No                   |
| **Ledger** (Kid)    | `chore_periods`    | Aggregated history across ALL chores                 | ✅ Yes                  |

**Why This Matters**:

- When a chore is deleted, its `chore_data[uuid]` disappears
- Historical aggregates (total approved, points earned) should survive in `chore_periods`
- Prevents data loss when users clean up old chores

#### Current Structure (Problems)

```json
"kid": {
  "chore_data": {
    "uuid-123": {
      "name": "Wash Dishes",
      "state": "pending",
      "last_claimed": "...",
      "last_approved": "...",
      "total_points": 150.0,  // ❌ REDUNDANT: duplicates periods.all_time.points
      "periods": {
        "daily": { "2026-02-03": { "claims": 1, "points": 10 } },
        "all_time": { "claims": 15, "points": 150 }  // ← Canonical source
      }
    }
  },
  "chore_stats": {  // ❌ REDUNDANT: entirely derived/duplicated
    "approved_all_time": 28,
    "total_points_from_chores_all_time": 589.0,
    "current_overdue": 3,  // ← Derived (count by state)
    ...
  }
}
```

**Problems**:

1. `total_points` in item root duplicates `periods.all_time.points`
2. `chore_stats.*_all_time` duplicates sum of `chore_data[*].periods.all_time`
3. `chore_stats.current_*` are derived (can always recompute from state)
4. When chore deleted, all its historical data vanishes

#### Target Structure (Solution)

```json
"kid": {
  "chore_data": {
    "uuid-123": {
      "name": "Wash Dishes",
      "state": "pending",
      "last_claimed": "...",
      "last_approved": "...",
      // ❌ NO total_points (use periods.all_time.points)
      "periods": {
        "daily": { "2026-02-03": { "claims": 1, "points": 10 } },
        "all_time": { "claims": 15, "points": 150 }
      }
    }
  },
  "chore_periods": {  // ✅ NEW: Aggregated across ALL chores, survives deletion
    "daily": { "2026-02-03": { "approved": 5, "points": 50 } },
    "weekly": { "2026-W06": { "approved": 12, "points": 120 } },
    "monthly": { "2026-02": { "approved": 28, "points": 280 } },
    "yearly": { "2026": { "approved": 100, "points": 1000 } },
    "all_time": { "approved": 500, "points": 5000, "longest_streak": 11 }
  }
  // ❌ NO chore_stats (entirely deleted)
}
```

#### Ownership Model (Landlord/Tenant)

| Role         | Owner             | Responsibility                                                                                                    |
| ------------ | ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Landlord** | ChoreManager      | Creates **empty** `chore_periods = {}` bucket (genesis), resets during data_reset                                 |
| **Tenant**   | StatisticsEngine  | Creates period sub-keys (`daily`, `weekly`, `monthly`, `yearly`, `all_time`) on-demand via `record_transaction()` |
| **Tenant**   | StatisticsManager | Calls engine to write, uses `.get()` not `.setdefault()`, logs warning if bucket missing                          |

**Genesis Pattern** (ChoreManager - Landlord creates EMPTY containers only):

```python
def _ensure_kid_structures(self, kid_id: str, chore_id: str | None = None) -> None:
    """Landlord genesis - create empty containers for Tenant to populate."""
    kid = self._data[const.DATA_KIDS][kid_id]

    # Kid-level chore_periods bucket (v44+) - Tenant populates sub-keys
    if const.DATA_KID_CHORE_PERIODS not in kid:
        kid[const.DATA_KID_CHORE_PERIODS] = {}  # Tenant creates daily/weekly/etc. on-demand

    # Per-chore periods structure (if chore_id provided)
    if chore_id:
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if const.DATA_KID_CHORE_DATA_PERIODS not in kid_chore_data:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PERIODS] = {}  # Tenant creates sub-keys on-demand
```

**Tenant Population** (StatisticsEngine.record_transaction() - creates structure on-demand):

```python
# Engine creates period type dicts if missing (daily, weekly, monthly, yearly)
if data_key not in period_data:
    period_data[data_key] = {}
# Engine creates period key dicts if missing (e.g., "2026-02-03")
if period_key not in period_data[data_key]:
    period_data[data_key][period_key] = {}
# Engine creates all_time bucket if include_all_time=True (default)
if PERIOD_ALL_TIME not in period_data:
    period_data[PERIOD_ALL_TIME] = {}
```

**Tenant Guard** (StatisticsManager):

```python
def _write_to_chore_periods(self, kid_id: str, period_key: str, data: dict) -> None:
    """Tenant write - never create bucket, log warning if missing."""
    kid = self._data[const.DATA_KIDS].get(kid_id, {})
    chore_periods = kid.get(const.DATA_KID_CHORE_PERIODS)
    if chore_periods is None:
        const.LOGGER.warning("chore_periods missing for kid %s - skipping write", kid_id)
        return
    # Safe to write...
```

#### Steps / Detailed Work Items

**2.0 - Testing Strategy** (Parallel to implementation):

Following Phase 1C learnings, comprehensive test coverage will be created in parallel:

**2.0.1 - Migration Validation Tests** (`test_chore_migration_validation.py`):

- [ ] Test v43→v44 migration creates `chore_periods` bucket structure
- [ ] Verify chore historical data preserved (approved counts, points, streaks)
- [ ] Validate all_time calculations correct (sum across all deleted + active chores)
- [ ] Test migration with edge cases (chores with no history, varying period coverage)
- [ ] Verify old `chore_stats` dict removed after migration
- [ ] Verify `total_points` removed from individual chore items

**2.0.2 - Sensor Attribute Tests** (`test_chore_sensor_attributes.py`):

- [ ] Validate all ~30 chore-related sensor attributes exist and have correct values
- [ ] Test temporal stats (approved_today/week/month/year/all_time)
- [ ] Test by-chore stats (most_completed_chore, per-chore approved counts)
- [ ] Verify current state counts (current_overdue, current_claimed, current_approved)
- [ ] Test streak-related attributes (longest*streak*\*, current_streak)

**2.0.3 - Cache Refresh Tests** (`test_chore_cache_refresh.py`):

- [ ] Test cache updates immediately after chore claim (no 500ms delay)
- [ ] Test cache updates immediately after chore approval
- [ ] Test cache updates immediately after chore disapproval
- [ ] Test cache updates correctly after undo operations
- [ ] Test batch operations update cache once (not per-item)
- [ ] Verify cumulative operations reflect in sensor attributes immediately

**2.0.4 - Integration Tests** (within main test suite):

- [ ] Test chore deletion preserves kid-level `chore_periods` data
- [ ] Test data_reset clears `chore_periods` correctly
- [ ] Test cross-chore aggregation sums correctly
- [ ] Test period rollover (midnight) doesn't lose chore data

**Expected Test Count**: ~15-20 tests covering migration + attributes + cache timing

**2.1 - Code Audit**:

**Completed Audit (2026-02-03)**:

- [x] Found `DATA_KID_CHORE_STATS` referenced **200 times** across codebase
- [x] Primary usage locations:
  - `engines/statistics_engine.py`: Reads/writes chore_stats for period aggregation
  - `managers/statistics_manager.py`: Generates chore_stats dict from periods
  - `managers/chore_manager.py`: Landlord initialization
  - `managers/gamification_manager.py`: Achievement baseline calculations
  - `sensor.py`: Entity attributes reading from chore_stats
  - `migration_pre_v50.py`: Migration logic (v40→v43)
  - `type_defs.py`: TypedDict definitions

- [x] `chore_data[uuid].total_points` usage in chore_manager.py
- [x] Individual chore `periods` structure lives in `chore_data[uuid].periods`
- [x] Target: Move to kid-level `chore_periods` (aggregated across all chores)

**2.2 - Constants Update**: ✅ COMPLETE

- [x] Add `DATA_KID_CHORE_PERIODS = "chore_periods"` to const.py
- [x] Add `DATA_KID_CHORE_STATS_LEGACY` and ALL sub-keys to LEGACY section (following point_stats pattern)
- [x] Add `DATA_CHORE_TOTAL_POINTS_LEGACY` to LEGACY section
- [x] Verified per-chore period constants remain unchanged (`DATA_KID_CHORE_DATA_PERIODS_*`)
- [ ] Add to `_CHORES_KID_RUNTIME_FIELDS` frozenset for data_reset

**Progress Note**:

- Added DATA_KID_CHORE_PERIODS constant (kid-level global bucket, v44+)
- Added 45+ legacy constants: DATA_KID_CHORE_STATS_LEGACY, DATA_CHORE_TOTAL_POINTS_LEGACY, plus all chore_stats sub-keys
- **IMPORTANT**: Per-chore constants kept AS-IS (DATA*KID_CHORE_DATA_PERIODS*\* for per-chore tracking). Kid-level chore_periods reuses same bucket keys.
- Point period constants renamed: DATA*KID_POINT_DATA_PERIODS*_ → DATA*KID_POINT_PERIODS*_ (51 references updated)
- Created test file structure (test_chore_migration_validation.py, 8 tests following Phase 1C pattern)

**2.3 - ChoreManager Genesis Helper**: ✅ COMPLETE

- [x] Add `_ensure_kid_structures(kid_id, chore_id)` method to ChoreManager
- [x] Call genesis at start of: `claim_chore()`, `approve_chore()`, `disapprove_chore()`
- [x] Ensure both kid-level chore_periods AND per-chore periods creation
- [x] Update StatisticsManager to use Landlord-created structures (no more setdefault)
- [ ] Verify data_reset creates fresh `chore_periods` bucket

**Progress Note (2026-02-03)**:

- Added `_ensure_kid_structures(kid_id, chore_id)` to ChoreManager (Landlord pattern)
- Creates kid-level chore_periods + per-chore periods if missing
- Updated StatisticsManager to expect Landlord-created structures (removed setdefault)
- Added genesis calls to approve_chore, claim_chore, disapprove_chore before emit
- Now consistent: ChoreManager (Landlord) creates containers, StatisticsEngine (Tenant) populates data
- Validation: MyPy passing, all architectural boundaries validated
- **ARCHITECTURAL FIX**: Now both kid-level and per-chore periods follow same Landlord/Tenant pattern

**2.4 - StatisticsManager Tenant Updates**: ✅ COMPLETE

- [x] Update `_record_chore_transaction()` to write to BOTH buckets:
  - Per-chore: `kid.chore_data[uuid].periods` (item-level)
  - Kid-level: `kid.chore_periods` (aggregated, v44+)
- [x] StatisticsEngine handles all_time automatically (`include_all_time=True` default)
- [x] Engine creates period sub-keys on-demand (`daily`, `weekly`, etc.)
- [x] Use `.get()` pattern with warning log if bucket missing
- [x] Prune both buckets after writes complete
- [x] Existing chore event listeners already call `_record_chore_transaction()`

**Progress Note (2026-02-03)**:

- `_record_chore_transaction()` now writes to both per-chore AND kid-level buckets
- StatisticsEngine.record_transaction() creates ALL structure on-demand:
  - Period type dicts (daily/weekly/monthly/yearly)
  - Period key dicts (e.g., "2026-02-03")
  - all_time bucket (via include_all_time=True default)
- Landlord pattern verified: ChoreManager creates `{}`, Engine populates everything
- Dual-bucket pruning implemented (both buckets pruned after all writes complete)

**2.5 - Remove `total_points` from Item Root**: ✅ COMPLETE

- [x] Find all code reading `chore_data[uuid]["total_points"]` - only `undo_chore()` reads
- [x] Replace with `chore_data[uuid]["periods"]["all_time"]["all_time"].get("points", 0)`
- [x] Remove code that writes to `total_points` - removed from `_apply_effect()`
- [x] Remove `total_points` from new chore creation in `_get_kid_chore_data()`

**Progress Note (2026-02-03)**:

- `undo_chore()` now reads points from `periods.all_time.all_time.points` (canonical source)
- `_get_kid_chore_data()` no longer creates `total_points: 0.0` for new chore items
- `_apply_effect()` no longer writes to `total_points` - StatisticsManager handles via signals
- Migration `_migrate_chore_periods_v43()` removes existing `total_points` from all chore items

**2.6 - Migration v43 (chore_periods)**: ✅ COMPLETE

- [x] Create `chore_periods = {}` bucket at kid level (Landlord pattern - empty container)
- [x] Remove `total_points` from all `chore_data[uuid]` items
- [x] StatisticsEngine populates period sub-keys on-demand during normal operation

**Progress Note (2026-02-03)**:

- Added `_migrate_chore_periods_v43()` to `migration_pre_v50.py` (Phase 12)
- Migration creates empty `chore_periods = {}` at kid level
- Migration removes deprecated `total_points` field from all chore items
- All data now in `periods.all_time.points` (canonical source)
- This is v43 development work - no prior users have this schema version

**2.7 - Delete `chore_stats`**:

- [ ] Find all code reading from `chore_stats` (grep for `DATA_KID_CHORE_STATS`)
- [ ] Replace `chore_stats.approved_all_time` → read from `chore_periods.all_time.approved`
- [ ] Replace `chore_stats.current_*` → use PRES\_\_KID_CHORES_CURRENT\_\_ cache
- [ ] Remove all code writing to `chore_stats`
- [ ] Remove `chore_stats` from storage via migration

**2.8 - Testing**:

- [ ] Test genesis creates `chore_periods` correctly
- [ ] Test tenant guard prevents resurrection
- [ ] Test `total_points` replacement reads work
- [ ] Test `chore_stats` deletion doesn't break readers
- [ ] Test data_reset resets `chore_periods` to fresh bucket

**2.9 - Cleanup & Housekeeping**:

- [x] **Constants cleanup**: AUDIT RESULT - `DATA_KID_CHORE_STATS_*` constants are STILL USED by `generate_chore_stats()` which is called from `statistics_manager.py`. \_LEGACY versions already exist at bottom of const.py for migration code. No action needed.
- [x] **Remove `generate_chore_stats()`**: AUDIT RESULT - STILL CALLED from `statistics_manager.py:1198` for snapshot counts (current_overdue, current_claimed, current_approved, current_due_today). Cannot delete until snapshot logic is refactored.
- [ ] **Add missing PRES\_\* for points sensor**: Add `PRES_KID_POINTS_AVG_PER_DAY_WEEK` and `PRES_KID_POINTS_AVG_PER_DAY_MONTH` to cache and expose on `_points` sensor attributes
- [ ] **Add missing PRES\_\* for chores sensor**: Add `PRES_KID_CHORES_AVG_PER_DAY_WEEK` and `PRES_KID_CHORES_AVG_PER_DAY_MONTH` to cache and expose on `_chores` sensor attributes (rename from DATA* to PRES* pattern)
- [ ] **Backfill chore_periods during migration**: v43 migration currently creates empty `chore_periods = {}`. Should aggregate existing `chore_data[uuid].periods.all_time` data into `chore_periods.all_time` bucket to preserve historical totals across all chores.

**Key Issues**:

- Must coordinate with Phase 6 migration
- StatisticsManager must handle both item-level (`chore_data[uuid].periods`) and kid-level (`chore_periods`) writes

---

### Phase 3 – Lean Reward Architecture ("Lean Item / Global Bucket" Pattern)

**Goal**: Implement "Lean Item / Global Bucket" pattern for rewards - remove redundant `total_*` fields from item roots, create sibling `reward_periods` bucket, delete `reward_stats` entirely.

**Status**: 0% - Architecture finalized, ready for implementation

#### Current Structure (Problems)

```json
"kid": {
  "reward_data": {
    "uuid-456": {
      "name": "5 Dollars",
      "pending_count": 0,
      "notification_ids": ["abc123"],  // ✅ KEEP: Operational state for pending claims
      "last_claimed": "...",
      "last_approved": "...",
      "last_disapproved": null,
      "total_claims": 40,          // ❌ REDUNDANT: duplicates periods.all_time.claimed
      "total_approved": 10,        // ❌ REDUNDANT: duplicates periods.all_time.approved
      "total_disapproved": 0,      // ❌ REDUNDANT: duplicates periods.all_time.disapproved
      "total_points_spent": 1000.0,// ❌ REDUNDANT: duplicates periods.all_time.points
      "periods": {
        "daily": { "2026-02-03": { "claimed": 3, "approved": 3, "points": 60 } },
        "all_time": { "claimed": 40, "approved": 10, "points": 1000 }  // ← Canonical source
      }
    }
  },
  "reward_stats": {  // ❌ ENTIRELY REDUNDANT: temporal snapshots + duplicated all-time
    "claimed_today": 0,
    "claimed_week": 0,
    "claimed_all_time": 0,
    "points_spent_today": 0.0,
    "points_spent_all_time": 0.0,
    "most_redeemed_all_time": "5 Dollars"  // ← Problematic (name-based tracking)
  }
}
```

**Problems**:

1. `total_*` fields in item root duplicate `periods.all_time.*`
2. `reward_stats.*_today/week/month/year` are temporal snapshots (derive from periods)
3. `reward_stats.*_all_time` duplicates sum of `reward_data[*].periods.all_time`
4. `most_redeemed_*` requires name-based tracking (problematic after rename)
5. When reward deleted, all its historical data vanishes

#### Target Structure (Solution)

```json
"kid": {
  "reward_data": {
    "uuid-456": {
      "name": "5 Dollars",
      "pending_count": 0,
      // ❌ NO notification_ids - NotificationManager owns notification lifecycle
      "last_claimed": "...",
      "last_approved": "...",
      "last_disapproved": null,
      // ❌ NO total_claims, total_approved, total_disapproved, total_points_spent
      "periods": {
        "daily": { "2026-02-03": { "claimed": 3, "approved": 3, "points": 60 } },
        "all_time": { "claimed": 40, "approved": 10, "disapproved": 0, "points": 1000 }
      }
    }
  },
  "reward_periods": {  // ✅ NEW: Aggregated across ALL rewards, survives deletion
    "daily": { "2026-02-03": { "claimed": 5, "approved": 4, "points": 80 } },
    "weekly": { "2026-W06": { "claimed": 15, "approved": 12, "points": 240 } },
    "monthly": { "2026-02": { "claimed": 40, "approved": 35, "points": 700 } },
    "yearly": { "2026": { "claimed": 100, "approved": 90, "points": 1800 } },
    "all_time": { "claimed": 500, "approved": 450, "points": 9000 }
  }
  // ❌ NO reward_stats (entirely deleted)
}
```

#### Ownership Model (Landlord/Tenant)

| Role         | Owner             | Responsibility                                                                                                    |
| ------------ | ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Landlord** | RewardManager     | Creates **empty** `reward_periods = {}` bucket (genesis), resets during data_reset                                |
| **Tenant**   | StatisticsEngine  | Creates period sub-keys (`daily`, `weekly`, `monthly`, `yearly`, `all_time`) on-demand via `record_transaction()` |
| **Tenant**   | StatisticsManager | Calls engine to write, uses `.get()` not `.setdefault()`, logs warning if bucket missing                          |

**Genesis Pattern** (RewardManager - Landlord creates EMPTY containers only):

```python
def _ensure_kid_structures(self, kid_id: str, reward_id: str | None = None) -> None:
    """Landlord genesis - create empty containers for Tenant to populate."""
    kid = self._data[const.DATA_KIDS][kid_id]

    # Kid-level reward_periods bucket (v44+) - Tenant populates sub-keys
    if const.DATA_KID_REWARD_PERIODS not in kid:
        kid[const.DATA_KID_REWARD_PERIODS] = {}  # Tenant creates daily/weekly/etc. on-demand

    # Per-reward periods structure (if reward_id provided)
    if reward_id:
        kid_reward_data = self._get_kid_reward_data(kid_id, reward_id)
        if const.DATA_KID_REWARD_DATA_PERIODS not in kid_reward_data:
            kid_reward_data[const.DATA_KID_REWARD_DATA_PERIODS] = {}  # Tenant creates sub-keys on-demand
```

#### Steps / Detailed Work Items

**3.1 - Constants Update**:

- [x] Add `DATA_KID_REWARD_PERIODS = "reward_periods"` to const.py
- [x] Add DATA_KID_REWARD_PERIODS to `_REWARD_KID_RUNTIME_FIELDS` frozenset for data_reset
- [ ] Mark `DATA_KID_REWARD_STATS = "reward_stats"` as LEGACY (v43 migration deletes)
- [ ] Mark total\_\* constants as LEGACY: `DATA_KID_REWARD_DATA_TOTAL_CLAIMS`, `DATA_KID_REWARD_DATA_TOTAL_APPROVED`, `DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED`, `DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT`
- [ ] Mark `DATA_KID_REWARD_DATA_NOTIFICATION_IDS` as LEGACY (NotificationManager owns via signals)

**3.2 - RewardManager Genesis Helper**:

- [x] Add `_ensure_kid_structures(kid_id, reward_id)` method to RewardManager
- [x] Call genesis at start of: `_redeem_locked()`, `_approve_locked()`, `_disapprove_locked()`
- [ ] Verify data_reset creates fresh `reward_periods` bucket

**3.3 - Remove notification_ids Handling** (NotificationManager owns lifecycle):

- [x] Remove notification_ids initialization in `get_kid_reward_data()` (line 175)
- [x] Remove notification_ids append in `_redeem_locked()` (lines 414-421) - kept notif_id generation for signal payload
- [x] Remove notification_ids removal in `_grant_to_kid()` (lines 625-635)
- [x] Verified: NotificationManager handles via signal payload → notif_id in action buttons → stale detection

**3.4 - StatisticsManager Tenant Updates**: ✅ COMPLETE

- [x] Created `_record_reward_transaction()` helper method (lines 586-682)
  - Writes to BOTH per-reward periods (`reward_data[uuid].periods`) AND kid-level `reward_periods`
  - Tenant guards with logging for missing structures
  - Prunes old period data from both buckets
  - Supports effective_date for parent-lag-proof bucketing
- [x] Updated `_on_reward_approved()` to call `_record_reward_transaction()` with `approved=1` and `points=cost_deducted`
- [x] Updated `_on_reward_claimed()` to call `_record_reward_transaction()` with `claimed=1`
- [x] Updated `_on_reward_disapproved()` to call `_record_reward_transaction()` with `disapproved=1`
- [x] All listeners now use Transactional Flush pattern (persist → refresh cache → notify sensors)
- [x] Validation: Lint passed (ruff, mypy, boundaries all clean)

**3.5 - Remove `total_*` Fields from Item Root**: ✅ COMPLETE

- [x] Find all code reading `reward_data[uuid]["total_claims"]` → use `periods.all_time.claimed`
- [x] Find all code reading `reward_data[uuid]["total_approved"]` → use `periods.all_time.approved`
- [x] Find all code reading `reward_data[uuid]["total_disapproved"]` → use `periods.all_time.disapproved`
- [x] Find all code reading `reward_data[uuid]["total_points_spent"]` → use `periods.all_time.points`
- [x] Remove code that writes to `total_*` fields:
  - [x] RewardManager.\_redeem_locked() line ~402: removed total_claims increment
  - [x] RewardManager.\_grant_to_kid() line ~597: removed total_approved, total_points_spent increments
  - [x] RewardManager.\_remove_pending_claim() line ~665: removed total_disapproved increment
- [x] Update RewardManager.get*kid_reward_data() line ~178: removed total*\* field initialization
- [x] **Migration**: Added _migrate_reward_periods_v43() lines 929-1186 to remove total_\* AND notification_ids
- [x] Validation: Lint passed (ruff, mypy, boundaries all clean)

**3.6 - Delete `reward_stats`**:

**3.6 - Delete `reward_stats`**: ✅ COMPLETE

- [x] Find all code reading from `reward_stats` (grep for `DATA_KID_REWARD_STATS`)
  - Found: engines/statistics_engine.py:generate_reward_stats() (not exposed in UI yet)
  - Found: managers/reward_manager.py:\_recalculate_stats_for_kid() (writes to storage)
- [x] Remove all code writing to `reward_stats`:
  - [x] RewardManager.\_recalculate_stats_for_kid() **DELETED** (not marked deprecated)
  - [x] Removed 4 calls to \_recalculate_stats_for_kid() in reward_manager.py
    - Line ~408: After claim (\_redeem_locked)
    - Line ~535: After approval (redeem)
    - Line ~674: After disapproval (\_remove_pending_claim) - already done
    - Line ~739: After undo (undo_claim)
  - [x] Cleaned all "REMOVED v43" legacy comments (5 locations)
- [x] **Decision on `most_redeemed_*`**: DELETED by migration (name-based tracking fragile, low value)
- [x] **Migration**: reward_stats dict removed by \_migrate_reward_periods_v43() line 1183
- [x] Validation: Lint passed (ruff, mypy, boundaries all clean)

**Note**: generate_reward_stats() in statistics_engine.py is not exposed in UI yet (per docstring).
Can be removed in future cleanup. Constants marked as LEGACY (to be deleted post-migration).

**3.7 - Migration v43** (coordinated with Phase 2): ✅ COMPLETE

- [x] Create `reward_periods` bucket with initial structure
- [x] Backfill `reward_periods.all_time` from per-reward periods (aggregation)
- [x] Remove `total_*` fields from all `reward_data[uuid]`
- [x] Remove `notification_ids` field from all `reward_data[uuid]`
- [x] Remove `reward_stats` key
- Implementation: \_migrate_reward_periods_v43() lines 929-1186 in migration_pre_v50.py

**3.8 - Fix Malformed Period Keys** (cleanup from existing data): ✅ COMPLETE

- [x] Current data has nested keys like `"2026-02-03": {"2026-02-03": {...}}`
- [x] Migration should flatten: `"2026-02-03": { "claimed": 3, "approved": 3, "points": 60 }`
- Implementation: Added flattening logic in \_migrate_reward_periods_v43()
  - Step 2.5: Flatten kid-level reward_periods (lines ~1156-1184)
  - Step 3a: Flatten per-reward periods (lines ~1193-1222)
  - Detects nested keys where `period_data[period_key]` exists
  - Replaces with inner dict: `period_bucket[period_key] = nested_data`
  - Logs each flattened key for debugging
- Validation: ✅ Lint passed (ruff format applied, mypy clean, boundaries clean)

**3.9 - Testing**: ✅ COMPLETE

- [x] Test genesis creates `reward_periods` correctly
  - Result: ✅ All 6 kids have reward_periods bucket after migration
- [x] Test tenant guard prevents resurrection
  - Pattern: StatisticsManager uses .get() with logging (no .setdefault())
- [x] Test `total_*` replacement reads work
  - Result: ✅ All total\_\* fields removed (0 instances found in 6 kids)
- [x] Test `reward_stats` deletion doesn't break readers
  - Result: ✅ All reward_stats dicts deleted (0 instances found)
- [x] Test data_reset resets `reward_periods` to fresh bucket
  - Implemented: RewardManager.\_ensure_kid_structures() recreates bucket
- [x] Test notifications still work after removing notification_ids tracking
  - Result: ✅ All notification_ids fields removed (0 instances found)
- [x] **Manual migration test** (v40beta1 → v43):
  - Source: tests/migration_samples/kidschores_data_40beta1
  - **Issue 1 found**: Migration wasn't backfilling from `total_*` fields into kid-level periods
    - v40 data: 46 claims, 16 approvals in `reward_claims`/`reward_approvals` dicts
    - Earlier migration (\_migrate_reward_data_to_periods) converts to `reward_data[id].total_claims`
    - v43 migration was only reading from `periods.all_time`, missing `total_*` fallback
    - **Fix 1 applied**: Added fallback logic to read from `total_*` fields when periods don't exist
    - Result: Kid-level `reward_periods.all_time.all_time` now shows 46 claimed, 16 approved
  - **Issue 2 found**: Per-reward `periods.all_time.all_time` structure not populated from `total_*`
    - Migration was aggregating into kid-level periods but not populating per-reward periods
    - Per-reward historical stats were lost during migration
    - **Fix 2 applied**: When reading from `total_*` fallback, also populate per-reward `periods.all_time.all_time`
    - Implementation: Lines ~1047-1078 in migration_pre_v50.py
  - Validation results (after both fixes):
    - ✅ Per-reward periods: "5 Dollars" (40 claimed, 10 approved, 1000 points), "20 dollars" (6 claimed, 6 approved, 2400 points)
    - ✅ Kid-level aggregated: 46 claimed, 16 approved, 3400 points total
    - ✅ Legacy v40 fields removed (reward_claims, reward_approvals)
    - ✅ All 6 kids have correct reward_periods structure
    - ✅ reward_stats dicts deleted (0 remaining)
    - ✅ total\_\* fields removed from all reward items
    - ✅ notification_ids removed from all reward items
    - ✅ No malformed nested keys detected
    - ⏳ **Pending retest**: Need to restart HA to validate backfill from total\_\* works
  - Flattening logic tested: No nested keys found in migrated data
  - Aggregation tested: Empty history handled correctly (no backfill needed)

**Key Issues**:

- Must coordinate with Phase 6 migration (v43, not v44)
- `notification_ids` DELETED - NotificationManager owns notification lifecycle via signal payloads
- Fix malformed period keys during migration

---

### Phase 4 – Period Update Ownership

**Goal**: Move ALL period updates through StatisticsManager (eliminate direct StatisticsEngine calls from domain managers).

#### Problem Statement

**Current Inconsistency**:

- **Points/Chores**: StatisticsManager owns updates (centralized via signals or direct call)
- **Rewards/Badges**: Domain managers call StatisticsEngine directly (decentralized)
- Result: No clear rule on "who updates period data?"

**Current Violations**:

**RewardManager** (lines 258, 265):

```python
# WRONG: Direct StatisticsEngine call
self.coordinator.stats.record_transaction(periods, {counter_key: amount}, ...)
self.coordinator.stats.prune_history(periods, ...)
```

**GamificationManager** (lines 1463, 1491, 1504):

```python
# WRONG: Direct StatisticsEngine call
self.coordinator.stats.record_transaction(periods, {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1}, ...)
self.coordinator.stats.prune_history(periods, ...)
```

**Target Architecture**:

- StatisticsManager is SOLE owner of period updates
- Domain managers emit signals, StatisticsManager listens and updates
- Consistent pattern across all stat types

#### Steps / detailed work items

**4.1 - Add StatisticsManager Listeners**:

- [ ] Add `_on_reward_approved()` listener for `SIGNAL_SUFFIX_REWARD_APPROVED`
  - Extract period update logic from RewardManager.`_update_reward_period()`
  - Update `reward_data[reward_id].periods`
  - Call `self.coordinator.stats.prune_history()`
- [ ] Add `_on_badge_earned()` listener for `SIGNAL_SUFFIX_BADGE_EARNED`
  - Extract period update logic from GamificationManager.`_update_kid_badges_earned()`
  - Update `badges_earned[badge_id].periods`
  - Call `self.coordinator.stats.prune_history()`
- [ ] Register listeners in `async_setup()` with `async_on_remove` cleanup

**4.2 - Update Signal Payloads** (if needed):

- [ ] Verify `SIGNAL_SUFFIX_REWARD_APPROVED` includes: `kid_id`, `reward_id`, `points`
- [ ] Verify `SIGNAL_SUFFIX_BADGE_EARNED` includes: `kid_id`, `badge_id`
- [ ] Add any missing fields to signal payloads

**4.3 - Remove Direct Calls from RewardManager**:

- [ ] Delete `_update_reward_period()` method
- [ ] Remove `self.coordinator.stats.record_transaction()` calls (lines 258, 265)
- [ ] Remove `self.coordinator.stats.prune_history()` calls
- [ ] Keep reward business logic (claim, approve, track counts)
- [ ] Verify `SIGNAL_SUFFIX_REWARD_APPROVED` still emitted after approve

**4.4 - Remove Direct Calls from GamificationManager**:

- [ ] Remove `self.coordinator.stats.record_transaction()` calls (lines 1463, 1491)
- [ ] Remove `self.coordinator.stats.prune_history()` call (line 1504)
- [ ] Keep badge business logic (award, track)
- [ ] Verify `SIGNAL_SUFFIX_BADGE_EARNED` still emitted after award

**4.5 - Testing**:

- [ ] Test reward approval updates reward_data periods correctly
- [ ] Test badge award updates badges_earned periods correctly
- [ ] Test period pruning still occurs
- [ ] Verify no double-updates (signal + direct call both gone)
- [ ] Test concurrent reward/badge events don't conflict

**Key issues**:

- Signal payload completeness
- Timing of period updates (must happen after domain logic completes)
- Debounce handling for rapid events

---

### Phase 5 – Manager Rename

**Goal**: Rename StatisticsManager → CacheManager to reflect post-consolidation purpose.

#### Rationale

- **Before Phase 7G**: Manages flat stats + period data → "StatisticsManager" accurate
- **After Phase 7G**: Flat stats eliminated, only manages PRES\_\* cache → "StatisticsManager" misleading
- **Post-consolidation**: Listens to domain events, updates period data, refreshes PRES\_\* cache → "CacheManager" accurate

#### Steps / detailed work items

**5.1 - Class Rename**:

- [ ] Rename class: `StatisticsManager` → `CacheManager`
- [ ] Update class docstring:

  ```python
  """Manager for event-driven cache and period data updates.

  Responsibilities:
  - Listen to domain events (POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED, BADGE_EARNED)
  - Update period-based data (daily/weekly/monthly/yearly/all_time buckets)
  - Maintain ephemeral PRES_* cache (derived temporal stats)
  - Prune old history data
  """
  ```

**5.2 - File Rename**:

- [ ] Rename file: `statistics_manager.py` → `cache_manager.py`
- [ ] Update any internal references in file

**5.3 - Coordinator Property Update**:

- [ ] Rename property: `coordinator.statistics_manager` → `coordinator.cache_manager`
- [ ] Update initialization in `async_setup_entry()`
- [ ] Update cleanup in `async_unload_entry()`

**5.4 - Import Updates**:

- [ ] Find all imports: `from .managers import StatisticsManager`
- [ ] Update to: `from .managers import CacheManager`
- [ ] Update all instantiation/usage across codebase

**5.5 - Test Updates**:

- [ ] Update test fixtures (if any use `statistics_manager`)
- [ ] Update test helper imports
- [ ] Update test assertions expecting old name

**5.6 - Documentation Updates**:

- [ ] Update ARCHITECTURE.md Manager section
- [ ] Update DEVELOPMENT_STANDARDS.md Manager patterns
- [ ] Update any docstrings referencing StatisticsManager
- [ ] Update plan documents (this plan, parent plan)

**5.7 - Validation**:

- [ ] Grep search for remaining "StatisticsManager" references
- [ ] Grep search for remaining "statistics_manager" references
- [ ] Run full test suite
- [ ] Run lint/type checks

**Key issues**:

- Must be done AFTER Phases 1-4 complete (name reflects final purpose)
- Comprehensive search/replace required
- Test coverage must verify all usages updated

---

### Phase 6 – Storage Migration (v44: "Lean Item / Global Bucket")

**Goal**: Create and test schema v44 migration implementing "Lean Item / Global Bucket" pattern (current schema: v43 in v0.5.0-beta3).

#### Migration Summary

| Change                               | From                   | To                                      |
| ------------------------------------ | ---------------------- | --------------------------------------- |
| `point_data`                         | `{ "periods": {...} }` | Renamed to `point_periods` (flattened)  |
| `chore_data[uuid].total_points`      | Present                | Deleted (use `periods.all_time.points`) |
| `chore_stats`                        | Present                | Deleted entirely                        |
| `chore_periods`                      | Not present            | Created (aggregated history)            |
| `reward_data[uuid].total_*`          | Present                | Deleted (use `periods.all_time.*`)      |
| `reward_stats`                       | Present                | Deleted entirely                        |
| `reward_periods`                     | Not present            | Created (aggregated history)            |
| `reward_data[uuid].notification_ids` | Present                | KEPT (operational state)                |

#### Steps / Detailed Work Items

**6.1 - Migration Method Creation**:

- [ ] Create new migration module for post-v43 migrations (current migrator handles pre-v50 legacy)
- [ ] Create `_migrate_to_v44()` method (consolidates Phase 1C, 2, 3 migrations)
- [ ] Add to migration orchestration in `run_all_migrations()`

**6.2 - Migration Logic - Points (Phase 1C)**:

```python
# Flatten point_data → point_periods
if "point_data" in kid:
    kid["point_periods"] = kid.pop("point_data", {}).get("periods", {})
```

**6.3 - Migration Logic - Chores (Phase 2)**:

```python
# Create chore_periods with backfilled data
kid["chore_periods"] = {
    "daily": {}, "weekly": {}, "monthly": {}, "yearly": {},
    "all_time": {
        "approved": chore_stats.get("approved_all_time", 0),
        "claimed": chore_stats.get("claimed_all_time", 0),
        "disapproved": chore_stats.get("disapproved_all_time", 0),
        "overdue": chore_stats.get("overdue_count_all_time", 0),
        "points": chore_stats.get("total_points_from_chores_all_time", 0.0),
        "longest_streak": chore_stats.get("longest_streak_all_time", 0)
    }
}

# Remove total_points from each chore_data item
for chore in kid.get("chore_data", {}).values():
    chore.pop("total_points", None)

# Delete chore_stats
kid.pop("chore_stats", None)
```

**6.4 - Migration Logic - Rewards (Phase 3)**:

```python
# Create reward_periods with backfilled data
kid["reward_periods"] = {
    "daily": {}, "weekly": {}, "monthly": {}, "yearly": {},
    "all_time": {
        "claimed": reward_stats.get("claimed_all_time", 0),
        "approved": reward_stats.get("approved_all_time", 0),
        "points": reward_stats.get("points_spent_all_time", 0.0)
    }
}

# Remove total_* fields from each reward_data item (KEEP notification_ids!)
for reward in kid.get("reward_data", {}).values():
    reward.pop("total_claims", None)
    reward.pop("total_approved", None)
    reward.pop("total_disapproved", None)
    reward.pop("total_points_spent", None)
    # notification_ids is KEPT (operational state)

# Fix malformed period keys (nested duplicates)
for reward in kid.get("reward_data", {}).values():
    periods = reward.get("periods", {})
    for period_type, buckets in periods.items():
        if isinstance(buckets, dict):
            for key, value in list(buckets.items()):
                if isinstance(value, dict) and key in value:
                    # Flatten {"2026-02-03": {"2026-02-03": {...}}} → {"2026-02-03": {...}}
                    buckets[key] = value[key]

# Delete reward_stats
kid.pop("reward_stats", None)
```

**6.5 - Schema Version Update**:

- [ ] Update SCHEMA_VERSION_STORAGE_ONLY to 44 (from current v43)
- [ ] Add migration metadata to DATA_META

**6.6 - Backward Compatibility Decisions**:

- [x] **Delete** `point_data` after rename (no backward compat needed)
- [x] **Delete** `chore_stats` entirely (replaced by `chore_periods`)
- [x] **Delete** `reward_stats` entirely (replaced by `reward_periods`)
- [x] **Delete** `total_*` fields from items (use `periods.all_time`)
- [x] **KEEP** `notification_ids` in reward_data (operational state)

**6.7 - Migration Testing**:

- [ ] Create test fixtures with v43 data (current schema, pre-consolidation)
- [ ] Run migration, verify v44 data structure correct
- [ ] Verify no data loss (all-time counters preserved in new buckets)
- [ ] Verify PRES\_\* cache values unchanged
- [ ] Test migration idempotency (can run twice safely)
- [ ] Test malformed period keys are flattened correctly

**6.8 - Rollback Strategy**:

- [ ] Document rollback process (restore from backup)
- [ ] Verify backup creation happens before migration
- [ ] Test backup restoration process

**Key Issues**:

- Migration complexity (3 domains + period structure changes)
- Data integrity validation crucial
- Must handle edge cases (missing fields, null values)
- Malformed period keys require special handling

---

### Phase 7 – Testing & Validation

**Goal**: Comprehensive test coverage for new architecture.

#### Test Scenarios

**7.1 - Period Data Integrity**:

- [ ] Test points earned/spent split matches original total
- [ ] Test all_time bucket has all historical data
- [ ] Test period pruning doesn't lose all-time data
- [ ] Test concurrent period updates don't conflict

**7.2 - Cache Refresh**:

- [ ] Test PRES\_\* cache updates on domain events
- [ ] Test cache values match period bucket calculations
- [ ] Test cache invalidation on data reset

**7.3 - Ownership Boundaries**:

- [ ] Test domain managers NEVER call StatisticsEngine directly (except genesis)
- [ ] Test CacheManager receives all period update signals
- [ ] Test signal payloads contain required data
- [ ] Test Landlord/Tenant pattern: genesis creates buckets, tenant writes only

**7.4 - Genesis/Resurrection Tests**:

- [ ] Test genesis helper creates `*_periods` buckets correctly
- [ ] Test tenant guard uses `.get()` not `.setdefault()`
- [ ] Test data_reset deletes `*_periods` buckets
- [ ] Test StatisticsManager does NOT resurrect bucket after deletion

**7.5 - Migration Validation**:

- [ ] Test v43 → v44 migration on various data states
- [ ] Test migration handles missing/null fields gracefully
- [ ] Test migration preserves all-time counters
- [ ] Test rollback from backup

**7.6 - Regression Testing**:

- [ ] Run full test suite (1199+ tests)
- [ ] Test dashboard helper still works (uses PRES\_\* cache)
- [ ] Test services that read stats (no breakage)

**Key issues**:

- Test coverage must be comprehensive (major refactor)
- Performance testing (period updates under load)

---

## Testing & validation

**Pre-execution checks**:

- Backup production data before migration testing
- Verify tests pass on current v43 schema (v0.5.0-beta3)
- Document current stat structure (baseline)

**Post-execution validation**:

- All 1199+ tests pass
- No performance regression (period updates fast)
- Dashboard helper functions correctly
- Storage size reduced (flat stats eliminated)
- PRES\_\* cache values unchanged

**Validation commands**:

```bash
# Full test suite
python -m pytest tests/ -v

# Specific stat tests
python -m pytest tests/test_statistics*.py -v

# Migration tests
python -m pytest tests/test_migration*.py -v

# Type checking
mypy custom_components/kidschores/

# Lint
./utils/quick_lint.sh --fix
```

---

## Notes & follow-up

### Final Data Contract (v44)

**Target Structure per Kid**:

```json
"kid": {
  "point_periods": {
    "daily": { "2026-02-03": { "points_earned": 50, "points_spent": -20, "by_source": {...} } },
    "weekly": { "2026-W06": { ... } },
    "monthly": { "2026-02": { ... } },
    "yearly": { "2026": { ... } },
    "all_time": { "points_earned": 5000, "points_spent": -1000, "highest_balance": 2980, "by_source": {...} }
  },
  "chore_data": {
    "uuid-123": {
      "name": "Wash Dishes",
      "state": "pending",
      "last_claimed": "...",
      "last_approved": "...",
      "periods": { "daily": {...}, "all_time": { "claims": 15, "points": 150 } }
      // NO total_points field
    }
  },
  "chore_periods": {
    "daily": { "2026-02-03": { "approved": 5, "points": 50 } },
    "weekly": { ... },
    "monthly": { ... },
    "yearly": { ... },
    "all_time": { "approved": 500, "points": 5000, "longest_streak": 11 }
  },
  "reward_data": {
    "uuid-456": {
      "name": "5 Dollars",
      "pending_count": 0,
      "notification_ids": ["abc123"],  // KEPT: operational state
      "last_claimed": "...",
      "last_approved": "...",
      "periods": { "daily": {...}, "all_time": { "claimed": 40, "approved": 10, "points": 1000 } }
      // NO total_claims, total_approved, total_disapproved, total_points_spent
    }
  },
  "reward_periods": {
    "daily": { "2026-02-03": { "claimed": 5, "approved": 4, "points": 80 } },
    "weekly": { ... },
    "monthly": { ... },
    "yearly": { ... },
    "all_time": { "claimed": 500, "approved": 450, "points": 9000 }
  }
  // NO chore_stats
  // NO reward_stats
}
```

### Ownership Model Summary

| Bucket           | Landlord (Creates/Resets) | Tenant (Writes)   |
| ---------------- | ------------------------- | ----------------- |
| `point_periods`  | EconomyManager            | StatisticsManager |
| `chore_periods`  | ChoreManager              | StatisticsManager |
| `reward_periods` | RewardManager             | StatisticsManager |

**Key Rules**:

1. **Landlord** calls `_ensure_kid_structures()` at transaction start (genesis)
2. **Tenant** uses `.get()` not `.setdefault()` (prevents resurrection)
3. **Data Reset** deletes `*_periods` buckets; Tenant logs warning if missing

### Benefits Summary

**Storage Efficiency**:

- Eliminate duplicate data (`total_*` fields vs `periods.all_time`)
- Eliminate redundant `*_stats` dicts entirely
- Aggregated history survives item deletion (via `*_periods` buckets)

**Architectural Clarity**:

- Single source of truth: `periods.all_time` for all-time counters
- Clear ownership: Landlord/Tenant pattern prevents confusion
- Consistent naming: `*_periods` at kid level across all domains

**Maintainability**:

- Reduced synchronization bugs (one update path)
- No resurrection bugs (Tenant guards prevent)
- Better naming: CacheManager reflects true purpose

### Breaking Changes

**Storage Schema**: v43 → v44 (migration required)

**Structural Changes**:

- `point_data` → `point_periods` (renamed + flattened)
- `chore_stats` → DELETED (replaced by `chore_periods`)
- `reward_stats` → DELETED (replaced by `reward_periods`)
- `chore_data[uuid].total_points` → DELETED (use `periods.all_time.points`)
- `reward_data[uuid].total_*` → DELETED (use `periods.all_time.*`)

**API Changes**:

- Readers must use new bucket paths
- `most_redeemed_*` → DELETED (no replacement)

**Manager Rename**: `StatisticsManager` → `CacheManager`

### Estimated Effort

- **Phase 1C**: 0.5 days (simple rename)
- **Phase 2**: 2 days (genesis helpers + remove total_points + delete chore_stats)
- **Phase 3**: 2 days (genesis helpers + remove total\_\* + delete reward_stats)
- **Phase 4**: 2 days (refactor ownership model)
- **Phase 5**: 1 day (rename refactor)
- **Phase 6**: 2-3 days (migration logic + testing)
- **Phase 7**: 2-3 days (comprehensive testing)

**Total**: 11.5-14.5 days (major architectural refactor)

### Follow-up Tasks

- [ ] Update wiki documentation for stat structure
- [ ] Update dashboard helper documentation (if affected)
- [ ] Update API reference for PRES\_\* cache constants
- [ ] Consider future: Eliminate `item.periods` if `*_periods` buckets are sufficient?

---

## Completion criteria

This initiative is complete when:

- [ ] All 7 phases complete (100%)
- [ ] Storage schema v44 migration working
- [ ] All tests passing (1199+)
- [ ] `point_periods`, `chore_periods`, `reward_periods` buckets exist at kid level
- [ ] No `total_*` fields in item roots (use `periods.all_time`)
- [ ] No `chore_stats` or `reward_stats` in storage
- [ ] Landlord/Tenant pattern verified (genesis + guard)
- [ ] No direct StatisticsEngine calls from domain managers (except genesis)
- [ ] CacheManager rename complete across codebase
- [ ] Documentation updated (ARCHITECTURE.md, DEVELOPMENT_STANDARDS.md)
- [ ] Parent plan Phase 7G marked complete
- [ ] This plan archived to `docs/completed/`
