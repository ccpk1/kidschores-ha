# Stats Consolidation & Cache Ownership - Implementation Plan

## Initiative snapshot

- **Name / Code**: Stats Consolidation & Cache Ownership (Phase 7G from Data Reset V2)
- **Target release / milestone**: v0.5.0-beta3 (current release)
- **Owner / driver(s)**: Strategic Planning Agent → Builder Agent
- **Status**: Not started (plan complete, ready for handoff)
- **Breaking Change**: Yes - Storage schema v43→v44, API changes, manager rename

## Summary & immediate steps

| Phase / Step                      | Description                                        | % complete | Quick notes                                                                                                               |
| --------------------------------- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – point_stats Migration   | Consolidate flat point_stats into period buckets   | 95%        | Migration done, cache refresh timing fix in progress (!final piece - need to ensure debounce is working for performance!) |
| Phase 2 – chore_stats Cleanup     | Remove derived fields, keep all-time counters      | 0%         | Delete current*overdue/claimed/approved (use PRES*\* cache)                                                               |
| Phase 3 – reward_stats Cleanup    | Remove temporal snapshots, keep all-time counters  | 0%         | Delete today/week/month/year (derive from periods)                                                                        |
| Phase 4 – Period Update Ownership | Centralize ALL period updates in StatisticsManager | 0%         | Move reward/badge updates from domain managers to listeners                                                               |
| Phase 5 – Manager Rename          | Rename StatisticsManager → CacheManager            | 0%         | Post-consolidation name reflects true purpose                                                                             |
| Phase 6 – Storage Migration       | Schema v44 migration for flat stats elimination    | 0%         | Backfill earned/spent, move fields, update SCHEMA_VERSION                                                                 |
| Phase 7 – Testing & Validation    | Comprehensive test coverage for new architecture   | 0%         | Period data integrity, cache refresh, ownership boundaries                                                                |

1. **Key objective** – Eliminate flat `*_stats` structures (point_stats, chore_stats, reward_stats) by consolidating into period buckets, then centralize ALL period updates through single ownership model (StatisticsManager → CacheManager).

2. **Summary of recent work** – None yet. This is a spin-off from DATA_RESET_SERVICE_V2 Phase 7G (deferred due to scope).

3. **Next steps (short term)** – Phase 1 discovery: Audit all code reading/writing point_stats, create migration strategy.

4. **Risks / blockers** –
   - **Breaking change**: Storage schema v51 required
   - **Migration complexity**: Backfilling earned/spent from existing points_total
   - **Testing burden**: Must validate period data integrity across all stat types
   - **Coordination**: Touches 4 managers (Statistics, Reward, Gamification, Economy)

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
   - **Completion confirmation**: `[ ]` All phases complete, migration tested, documentation updated

---

## Tracking expectations

- **Summary upkeep**: Update summary table percentages and notes after each phase completion
- **Detailed tracking**: Use phase sections below for granular progress, blockers, and technical details

---

## Detailed phase tracking

### Phase 1 – point_stats Migration

**Goal**: Move all-time point data from flat `point_stats` into `point_data.periods.all_time` structure.

**Status**: 95% complete - Migration v43 deployed in v0.5.0-beta3, cache refresh timing fix in progress (final issue: sensor attributes show stale data after points transactions until user interaction triggers refresh).

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
- [ ] **IN PROGRESS**: Fix cache refresh timing in `_on_points_changed()` - cache must refresh BEFORE `async_set_updated_data()` to ensure sensor attributes show fresh values immediately

**1.7 - Testing**:

- [ ] Test migration on sample data (KC 3.x → v42 → v51)
- [ ] Verify earned/spent split matches original points_total
- [ ] Verify all_time bucket has all point_stats data
- [ ] Verify PRES\_\* cache values unchanged after migration
- [ ] Test new transaction recording (earned/spent separate)

**Key issues**:

- Backfill accuracy depends on by_source data integrity
- Must handle missing/null point_stats gracefully
- Backward compatibility decision: keep or delete `points_total`?

---

### Phase 2 – chore_stats Cleanup

**Goal**: Remove derived fields from `chore_stats`, keep only incrementally maintained all-time counters.

#### Problem Statement

**Current Structure**:

```json
"chore_stats": {
  // Incrementally maintained (KEEP)
  "approved_all_time": 28,
  "completed_all_time": 0,
  "claimed_all_time": 16,
  "disapproved_all_time": 9,
  "overdue_count_all_time": 314,
  "longest_streak_all_time": 11,
  "total_points_from_chores_all_time": 589.0,

  // Derived snapshots (DELETE)
  "current_overdue": 3,      // count(chore.state == "overdue")
  "current_claimed": 0,      // count(chore.state == "claimed")
  "current_approved": 3,     // count(chore.state == "approved")

  // Cannot track (DELETE)
  "most_completed_chore_all_time": null  // no per-chore completion counter
}
```

**Why all-time counters are Data (MUST persist)**:

- Incremented on specific events (cannot recompute after pruning chore period data)
- Historical peaks (longest_streak_all_time) cannot recompute from current state

**Why current\_\* are Derived (DELETE)**:

- Already computed in PRES_KID_CHORES_CURRENT_OVERDUE, etc.
- Can ALWAYS recompute by iterating chores and counting by state
- No pruning risk (chores exist until manually deleted)

#### Steps / detailed work items

**2.1 - Code Audit**:

- [ ] Find all code reading `current_overdue`, `current_claimed`, `current_approved`
- [ ] Verify these reads can use PRES\_\* cache instead
- [ ] Find all code writing to these fields
- [ ] Find code reading/writing `most_completed_chore_all_time`

**2.2 - Migration v44 Update** (or separate v45 if phased):

- [ ] Remove `current_overdue`, `current_claimed`, `current_approved` from chore_stats
- [ ] Remove `most_completed_chore_all_time`
- [ ] Keep all `*_all_time` counters unchanged

**2.3 - Reader Updates**:

- [ ] Replace `chore_stats.current_overdue` → PRES_KID_CHORES_CURRENT_OVERDUE
- [ ] Replace `chore_stats.current_claimed` → PRES_KID_CHORES_CURRENT_CLAIMED
- [ ] Replace `chore_stats.current_approved` → PRES_KID_CHORES_CURRENT_APPROVED
- [ ] Remove any code using `most_completed_chore_all_time` (or fix if valuable)

**2.4 - Writer Updates**:

- [ ] Remove code that writes to `current_*` fields (let PRES\_\* cache handle)
- [ ] Keep code that increments `*_all_time` counters

**2.5 - Testing**:

- [ ] Verify PRES*\* cache provides correct current*\* counts
- [ ] Verify migration removes fields without data loss
- [ ] Test that all-time counters still increment correctly

**Key issues**: None anticipated (straightforward cleanup).

---

### Phase 3 – reward_stats Cleanup

**Goal**: Eliminate all temporal snapshots, keep only incrementally maintained all-time counters.

#### Problem Statement

**Current Structure**:

```json
"reward_stats": {
  // Temporal snapshots (DELETE)
  "claimed_today": 0,
  "claimed_week": 0,
  "claimed_month": 0,
  "claimed_year": 1,
  "approved_today": 0,
  "approved_week": 0,
  "approved_month": 0,
  "approved_year": 1,
  "points_spent_today": 0.0,
  "points_spent_week": 0.0,
  "points_spent_month": 0.0,
  "points_spent_year": 20.0,

  // Incrementally maintained (KEEP)
  "claimed_all_time": 0,
  "approved_all_time": 0,
  "points_spent_all_time": 0.0,

  // Problematic tracking (EVALUATE)
  "most_redeemed_all_time": "5 Dollars",
  "most_redeemed_week": null,
  "most_redeemed_month": null
}
```

**Why all-time counters are Data (MUST persist)**:

- Incremented on specific events (cannot recompute after pruning reward period data)

**Why temporal fields are Derived (DELETE)**:

- Can derive from `reward_data.periods.daily/weekly/monthly/yearly` buckets
- Duplicates data already in period structure

**Why "most redeemed" is Problematic (DECISION NEEDED)**:

- Requires tracking redemption count per reward name (not currently stored per-reward)
- `most_redeemed_week/month`: Temporal snapshots (no value)
- **Decision**: Keep `most_redeemed_all_time` if useful, or delete if not properly tracked

#### Steps / detailed work items

**3.1 - Code Audit**:

- [ ] Find all code reading temporal fields (`*_today`, `*_week`, `*_month`, `*_year`)
- [ ] Find all code reading `most_redeemed_*` fields
- [ ] Determine if reward_data periods can provide temporal data

**3.2 - Decision on most_redeemed**:

- [ ] **Option A**: Delete (not properly tracked, no value)
- [ ] **Option B**: Keep most_redeemed_all_time, implement proper tracking
  - Add `reward_data[reward_id].all_time_redemption_count` field
  - Track highest count in reward_stats
- [ ] Document decision rationale

**3.3 - Migration v44 Update** (or separate v45 if phased):

- [ ] Remove all `*_today`, `*_week`, `*_month`, `*_year` fields
- [ ] Remove `most_redeemed_*` fields (or implement proper tracking)
- [ ] Keep `claimed_all_time`, `approved_all_time`, `points_spent_all_time`

**3.4 - Reader Updates**:

- [ ] Update code to derive temporal stats from `reward_data.periods` buckets
- [ ] Remove code reading `most_redeemed_*` (or update to use new tracking)

**3.5 - Testing**:

- [ ] Verify temporal stats derivable from reward_data periods
- [ ] Verify migration removes fields without data loss
- [ ] Verify all-time counters still increment correctly

**Key issues**:

- Decision on most_redeemed tracking
- Ensure reward_data periods have sufficient granularity for temporal derivation

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

### Phase 6 – Storage Migration

**Goal**: Create and test schema v44 migration for flat stats elimination (current schema: v43 in v0.5.0-beta3).

#### Steps / detailed work items

**6.1 - Migration Method Creation**:

- [ ] Create new migration module for post-v43 migrations (current migrator handles pre-v50 legacy)
- [ ] Create `_migrate_to_v44()` method (consolidates Phase 1-3 migrations)
- [ ] Add to migration orchestration in `run_all_migrations()`

**6.2 - Migration Logic**:

- [ ] Implement point_stats → point_data.periods.all_time migration (Phase 1)
- [ ] Implement chore_stats cleanup (Phase 2)
- [ ] Implement reward_stats cleanup (Phase 3)
- [ ] Update SCHEMA_VERSION_STORAGE_ONLY to 44 (from current v43)
- [ ] Add migration metadata to DATA_META

**6.3 - Backward Compatibility**:

- [ ] Decide: Delete point_stats or set to empty dict?
- [ ] Decide: Keep points_total or delete after earned/spent split?
- [ ] Document compatibility decisions

**6.4 - Migration Testing**:

- [ ] Create test fixtures with v43 data (current schema, pre-consolidation)
- [ ] Run migration, verify v44 data structure correct
- [ ] Verify no data loss
- [ ] Verify PRES\_\* cache values unchanged
- [ ] Test migration idempotency (can run twice safely)

**6.5 - Rollback Strategy**:

- [ ] Document rollback process (restore from backup)
- [ ] Verify backup creation happens before migration
- [ ] Test backup restoration process

**Key issues**:

- Migration complexity (3 stat types + period structure changes)
- Data integrity validation crucial
- Must handle edge cases (missing fields, null values)

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

- [ ] Test domain managers NEVER call StatisticsEngine directly
- [ ] Test CacheManager receives all period update signals
- [ ] Test signal payloads contain required data

**7.4 - Migration Validation**:

- [ ] Test v43 → v44 migration on various data states
- [ ] Test migration handles missing/null fields gracefully
- [ ] Test migration preserves all-time counters
- [ ] Test rollback from backup

**7.5 - Regression Testing**:

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

### Benefits Summary

**Storage Efficiency**:

- Eliminate duplicate data (point_stats vs point_data.periods)
- Eliminate derived temporal snapshots (can calculate on-demand)
- Clear separation: incrementally maintained data vs derived snapshots

**Architectural Clarity**:

- Single source of truth for period-based data
- Clear ownership: CacheManager owns ALL period updates
- Consistent pattern: Domain managers emit signals, CacheManager updates

**Maintainability**:

- Reduced synchronization bugs (one update path)
- Clear separation: Data vs derived cache
- Better naming: CacheManager reflects true purpose

### Breaking Changes

**Storage Schema**: v43 → v44 (migration required for v0.5.0-beta3)

**API Changes**:

- `point_stats.*` → `point_data.periods.all_time.all_time.*`
- `chore_stats.current_*` → PRES*KID_CHORES_CURRENT*\* cache
- `reward_stats.*_today/week/month/year` → derive from reward_data.periods

**Manager Rename**: `StatisticsManager` → `CacheManager`

### Estimated Effort

- **Phase 1**: 2-3 days (complex migration logic)
- **Phase 2**: 1 day (straightforward cleanup)
- **Phase 3**: 1 day (straightforward cleanup)
- **Phase 4**: 2 days (refactor ownership model)
- **Phase 5**: 1 day (rename refactor)
- **Phase 6**: 2 days (migration testing)
- **Phase 7**: 2-3 days (comprehensive testing)

**Total**: 11-15 days (major architectural refactor)

### Follow-up Tasks

- [ ] Update wiki documentation for stat structure
- [ ] Update dashboard helper documentation (if affected)
- [ ] Update API reference for PRES\_\* cache constants
- [ ] Consider future: Eliminate reward_data.periods if not used?

---

## Completion criteria

This initiative is complete when:

- [ ] All 7 phases complete (100%)
- [ ] Storage schema v51 migration working
- [ ] All tests passing (1199+)
- [ ] No direct StatisticsEngine calls from domain managers
- [ ] CacheManager rename complete across codebase
- [ ] Documentation updated (ARCHITECTURE.md, DEVELOPMENT_STANDARDS.md)
- [ ] Parent plan Phase 7G marked complete
- [ ] This plan archived to `docs/completed/`
