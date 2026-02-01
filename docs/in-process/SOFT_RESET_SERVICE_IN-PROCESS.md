# Soft Reset Service Implementation Plan

## Initiative snapshot

- **Name / Code**: Soft Reset Service (`reset_transactional_data`)
- **Target release / milestone**: v0.5.0-beta4 or v0.5.1
- **Owner / driver(s)**: Strategic Planning Agent
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                    | Description                                       | % complete | Quick notes                                      |
| ------------------------------- | ------------------------------------------------- | ---------- | ------------------------------------------------ |
| Phase 1 – Research & Validation | Audit existing reset services and data structures | 100%       | Research complete, validated all data structures |
| Phase 2 – Service Constants     | Add constants for new service and backup tag      | 0%         | Translation keys, service names, backup tags     |
| Phase 3 – Manager Methods       | Implement stat reset methods in managers          | 0%         | 3 new methods needed across 2 managers           |
| Phase 4 – Service Handler       | Implement orchestration service handler           | 0%         | Coordinates all reset operations                 |
| Phase 5 – Service Registration  | Register service and schema                       | 0%         | services.yaml + services.py registration         |
| Phase 6 – Testing               | Comprehensive test coverage                       | 0%         | Service tests + manager method tests             |

1. **Key objective** – Implement a "soft reset" service that clears all transactional data (points, stats, streaks, progress) while preserving structural definitions (chore/reward/badge templates, kid profiles).
2. **Summary of recent work** – Phase 1 research completed. Validated that existing `reset_all_chores` only resets states, not stats. Identified all data structures that need resetting.
3. **Next steps (short term)** – Phase 2: Add constants. Phase 3: Implement manager methods.
4. **Risks / blockers** – None currently identified. All required infrastructure exists.
5. **References**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage structure
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constant naming and Manager patterns
   - [services.py](../../custom_components/kidschores/services.py) - Existing reset service patterns
6. **Decisions & completion check**
   - **Decisions captured**:
     - Service name: `reset_transactional_data` (clearer than "soft_reset")
     - Creates backup with tag `const.BACKUP_TAG_SOFT_RESET`
     - Preserves all structure definitions (chores, rewards, badges, kids, penalties, bonuses, achievements, challenges)
     - Resets all runtime/transactional data (points, stats, streaks, counts, progress, awarded badges)
     - Does NOT reset reward_stats (aggregated stats) - handled by clearing reward_data per kid
     - Achievements and challenges: Reset progress fields only, preserve definitions
   - **Completion confirmation**: `[ ]` All follow-up items completed before marking done

---

## Research Findings (Phase 1)

### What Existing Reset Services Actually Do

#### `reset_all_chores()` - ChoreManager

**Resets**:

- Chore state → `PENDING`
- `approval_period_start` → now
- Overdue notifications → cleared

**Does NOT reset**:

- Per-kid chore stats (`DATA_KID_CHORE_DATA`)
- Period-based counters (daily/weekly/monthly)
- Total counts, points, streaks

#### `reset_rewards()` - RewardManager

**Resets**:

- Clears entire `reward_data[reward_id]` dict per kid
- This removes: pending_count, notification_ids, timestamps, counters, periods

**Correctly resets all reward tracking**.

#### `reset_penalties()` - EconomyManager

**Resets**:

- Clears `penalty_applies` dict per kid
- Removes "times applied" counters

**Does NOT restore points** (as documented).

#### `reset_bonuses()` - EconomyManager

**Resets**:

- Clears `bonus_applies` dict per kid
- Removes "times applied" counters

**Does NOT remove points** (as documented).

#### `remove_awarded_badges()` - GamificationManager

**Resets**:

- Removes badge from kid's `badges_earned` dict
- Removes kid from badge's `earned_by` list
- Updates point multiplier for cumulative badges

**Correctly removes awarded badges**.

### What's Missing

The following data structures are **NOT** reset by any existing service:

#### Per-Kid Runtime Data (`DATA_KID_*`)

- `points` → Should reset to 0
- `points_multiplier` → Should reset to 1.0
- `ledger` → Should clear to []
- `current_streak` → Should reset to 0
- `overall_chore_streak` → Should reset to 0
- `last_chore_date` → Should reset to None
- `last_streak_date` → Should reset to None
- `point_stats` → Should reset all counters
- `chore_data` → Should clear (per-chore stats for kid)

#### Achievement Progress (`DATA_ACHIEVEMENTS`)

**Preserve**:

- `internal_id`, `name`, `description`, `icon`, `labels`
- `type`, `criteria`, `target_value`, `reward_points`
- `assigned_kids`, `selected_chore_id`

**Reset**:

- `current_value` → 0
- `current_streak` → 0
- `progress` → 0.0
- `awarded` → False (if tracked)
- `last_awarded_date` → None
- `baseline` → 0 or reset to initial value

#### Challenge Progress (`DATA_CHALLENGES`)

**Preserve**:

- `internal_id`, `name`, `description`, `icon`, `labels`
- `type`, `criteria`, `target_value`, `reward_points`
- `assigned_kids`, `selected_chore_id`
- `start_date`, `end_date`, `required_daily`

**Reset**:

- `count` → 0
- `daily_counts` → {}
- `progress` → 0.0
- `awarded` → False (if tracked)

---

## Detailed phase tracking

### Phase 1 – Research & Validation

- **Goal**: Understand what existing reset services do and identify gaps
- **Steps / detailed work items**
  1. ✅ Audit `reset_all_chores()` implementation
  2. ✅ Audit `reset_rewards()` implementation
  3. ✅ Audit `reset_penalties()` implementation
  4. ✅ Audit `reset_bonuses()` implementation
  5. ✅ Audit `remove_awarded_badges()` implementation
  6. ✅ Identify all kid data structures in `const.py`
  7. ✅ Validate achievement/challenge data structures
  8. ✅ Review `build_kid()` to understand default values
  9. ✅ Document what needs to be reset vs preserved
- **Key issues**
  - None - research phase complete

### Phase 2 – Service Constants

- **Goal**: Add all constants needed for the new service
- **Steps / detailed work items**
  1. Add `SERVICE_RESET_TRANSACTIONAL_DATA = "reset_transactional_data"` to const.py (~line 3558 with other SERVICE\_\* constants)
  2. Add `BACKUP_TAG_SOFT_RESET = "soft_reset"` to const.py (~line 4104 with other BACKUP*TAG*\* constants)
  3. Add translation keys:
     - `TRANS_KEY_NOTIF_TITLE_SOFT_RESET = "notif_title_soft_reset"` (~line 1803)
     - `TRANS_KEY_NOTIF_MESSAGE_SOFT_RESET = "notif_message_soft_reset"` (~line 2053)
  4. Add corresponding entries to `translations/en.json`:
     ```json
     "notif_title_soft_reset": "Transactional Data Reset",
     "notif_message_soft_reset": "All points, stats, and progress have been reset. Chore and reward definitions preserved."
     ```
  5. Add service description to `services.yaml`
- **Key issues**
  - None anticipated

### Phase 3 – Manager Methods

- **Goal**: Implement new reset methods in managers
- **Steps / detailed work items**

  #### 3A: EconomyManager.reset_all_kid_points_and_stats()
  - File: `custom_components/kidschores/managers/economy_manager.py`
  - Location: After `reset_bonuses()` method (~line 982)
  - Implementation:

    ```python
    def reset_all_kid_points_and_stats(self) -> None:
        """Reset all kid points, ledgers, streaks, and chore_data stats.

        Preserves kid profiles (names, user IDs, notification settings).
        Used by soft reset service to clear runtime data.
        """
        for kid_id in self._data.get(const.DATA_KIDS, {}):
            kid = self._data[const.DATA_KIDS][kid_id]

            # Reset points and multipliers to defaults
            kid[const.DATA_KID_POINTS] = const.DEFAULT_ZERO
            kid[const.DATA_KID_POINTS_MULTIPLIER] = const.DEFAULT_KID_POINTS_MULTIPLIER

            # Clear transaction ledger
            kid[const.DATA_KID_LEDGER] = []

            # Reset streak tracking
            kid[const.DATA_KID_CURRENT_STREAK] = 0
            kid[const.DATA_KID_OVERALL_CHORE_STREAK] = 0
            kid[const.DATA_KID_LAST_CHORE_DATE] = None
            kid[const.DATA_KID_LAST_STREAK_DATE] = None

            # Clear per-chore stats for this kid
            kid[const.DATA_KID_CHORE_DATA] = {}

            # Note: point_stats managed by StatisticsManager
            # Note: reward_data cleared by RewardManager.reset_rewards()
            # Note: penalty_applies cleared by reset_penalties()
            # Note: bonus_applies cleared by reset_bonuses()
            # Note: badges_earned cleared by GamificationManager.remove_awarded_badges()

        const.LOGGER.info("Reset all kid points, ledgers, streaks, and chore stats")
    ```

  #### 3B: GamificationManager.reset_achievement_progress()
  - File: `custom_components/kidschores/managers/gamification_manager.py`
  - Location: After `remove_awarded_badges_by_id()` method (~line 1850)
  - Implementation:

    ```python
    def reset_achievement_progress(self) -> None:
        """Reset all achievement progress for all kids.

        Preserves achievement definitions, resets runtime progress.
        Used by soft reset service.
        """
        for achievement_id in self._data.get(const.DATA_ACHIEVEMENTS, {}):
            achievement = self._data[const.DATA_ACHIEVEMENTS][achievement_id]

            # Reset progress tracking
            achievement[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = 0
            achievement[const.DATA_ACHIEVEMENT_CURRENT_STREAK] = 0
            achievement[const.DATA_ACHIEVEMENT_PROGRESS] = 0.0

            # Reset awarded status if field exists
            if const.DATA_ACHIEVEMENT_AWARDED in achievement:
                achievement[const.DATA_ACHIEVEMENT_AWARDED] = False

            # Clear last awarded date
            achievement[const.DATA_ACHIEVEMENT_LAST_AWARDED_DATE] = None

            # Reset baseline to 0 (or could preserve initial baseline)
            achievement[const.DATA_ACHIEVEMENT_BASELINE] = 0

        const.LOGGER.info("Reset all achievement progress")
    ```

  #### 3C: GamificationManager.reset_challenge_progress()
  - File: `custom_components/kidschores/managers/gamification_manager.py`
  - Location: After `reset_achievement_progress()` method
  - Implementation:

    ```python
    def reset_challenge_progress(self) -> None:
        """Reset all challenge progress for all kids.

        Preserves challenge definitions and time windows, resets runtime progress.
        Used by soft reset service.
        """
        for challenge_id in self._data.get(const.DATA_CHALLENGES, {}):
            challenge = self._data[const.DATA_CHALLENGES][challenge_id]

            # Reset progress tracking
            challenge[const.DATA_CHALLENGE_COUNT] = 0
            challenge[const.DATA_CHALLENGE_DAILY_COUNTS] = {}
            challenge[const.DATA_CHALLENGE_PROGRESS] = 0.0

            # Reset awarded status if field exists
            if const.DATA_CHALLENGE_AWARDED in challenge:
                challenge[const.DATA_CHALLENGE_AWARDED] = False

        const.LOGGER.info("Reset all challenge progress")
    ```

- **Key issues**
  - Verify point_stats handling: Should StatisticsManager have a reset method or is clearing chore_data sufficient?
  - Decision: Clearing `chore_data` is sufficient since point_stats are derived from chore_data periods

### Phase 4 – Service Handler

- **Goal**: Implement orchestration handler that calls all reset methods
- **Steps / detailed work items**
  1. Add handler to `services.py` after `handle_reset_all_data()` (~line 2297)
  2. Implementation pattern:

     ```python
     async def handle_reset_transactional_data(_call: ServiceCall):
         """Handle soft reset - clear transactional data, preserve structure."""
         entry_id = get_first_kidschores_entry(hass)
         if not entry_id:
             const.LOGGER.warning("Reset Transactional Data: No entry found")
             return

         coordinator = _get_coordinator_by_entry_id(hass, entry_id)

         # Step 1: Create backup before reset
         try:
             backup_name = await bh.create_timestamped_backup(
                 hass,
                 coordinator.store,
                 const.BACKUP_TAG_SOFT_RESET,
                 coordinator.config_entry,
             )
             if backup_name:
                 const.LOGGER.info("Created pre-reset backup: %s", backup_name)
         except Exception as err:
             const.LOGGER.warning("Failed to create backup: %s", err)

         # Step 2: Reset states using existing services
         await coordinator.chore_manager.reset_all_chores()
         await coordinator.reward_manager.reset_rewards()  # All kids, all rewards
         await coordinator.economy_manager.reset_penalties()  # All kids, all penalties
         await coordinator.economy_manager.reset_bonuses()  # All kids, all bonuses
         coordinator.gamification_manager.remove_awarded_badges()  # All kids, all badges

         # Step 3: Reset stats using new methods
         coordinator.economy_manager.reset_all_kid_points_and_stats()  # NEW
         coordinator.gamification_manager.reset_achievement_progress()  # NEW
         coordinator.gamification_manager.reset_challenge_progress()  # NEW

         # Step 4: Persist and refresh
         coordinator._persist()
         await coordinator.async_request_refresh()

         const.LOGGER.info("Soft reset complete. All transactional data cleared.")
     ```

- **Key issues**
  - None - follows existing service patterns

### Phase 5 – Service Registration

- **Goal**: Register service with Home Assistant
- **Steps / detailed work items**
  1. Add service schema to `services.py` (near other RESET\_\* schemas ~line 171):
     ```python
     RESET_TRANSACTIONAL_DATA_SCHEMA = vol.Schema({})
     ```
  2. Add service registration (after `SERVICE_RESET_ALL_DATA` registration ~line 2294):
     ```python
     hass.services.async_register(
         const.DOMAIN,
         const.SERVICE_RESET_TRANSACTIONAL_DATA,
         handle_reset_transactional_data,
         schema=RESET_TRANSACTIONAL_DATA_SCHEMA,
     )
     ```
  3. Add to `services.yaml` (after `reset_all_data` ~line 228):
     ```yaml
     reset_transactional_data:
       name: "Reset Transactional Data"
       description: >
         Soft reset: Resets all points, stats, streaks, and progress while preserving
         chore/reward/badge definitions and kid profiles. Creates backup before reset.
         Use this for starting fresh (new school year, new points system) without
         losing your setup.
       fields: {}
     ```
- **Key issues**
  - None

### Phase 6 – Testing

- **Goal**: Comprehensive test coverage for new functionality
- **Steps / detailed work items**
  1. Create `tests/test_soft_reset_service.py`
  2. Test scenarios:
     - Service calls all manager methods in correct order
     - Backup created before reset
     - Points reset to 0, multiplier to 1.0
     - Ledger cleared
     - Streaks reset
     - chore_data cleared
     - Achievements progress reset, definitions preserved
     - Challenges progress reset, definitions preserved
     - reward_data cleared by reset_rewards
     - penalties cleared by reset_penalties
     - bonuses cleared by reset_bonuses
     - badges removed by remove_awarded_badges
     - Structure preserved (kid names, chore definitions, etc.)
  3. Unit tests for new manager methods:
     - `test_reset_all_kid_points_and_stats()`
     - `test_reset_achievement_progress()`
     - `test_reset_challenge_progress()`
  4. Integration test using `scenario_full` fixture
  5. Verify backup file created with correct tag
- **Key issues**
  - None - standard test patterns

---

## Testing & validation

- **Tests to execute**:
  - `pytest tests/test_soft_reset_service.py -v`
  - `pytest tests/ -k "reset" -v` (all reset tests)
  - Full suite: `pytest tests/ -v`
- **Outstanding tests**: All tests (Phase 6 not started)
- **Validation commands**:
  - `./utils/quick_lint.sh --fix` (code quality)
  - `mypy custom_components/kidschores/` (type checking)

---

## Notes & follow-up

### Architectural Considerations

1. **Signal-First Architecture**: This service coordinates multiple managers but does NOT emit signals itself. Each manager method handles its own signaling if needed.

2. **Backup Strategy**: Uses existing `create_timestamped_backup()` with new `BACKUP_TAG_SOFT_RESET` tag for easy identification.

3. **Atomicity**: Not transactional - if service fails midway, data may be partially reset. Backup allows recovery.

4. **Performance**: Should complete in <2 seconds for typical family setup (4 kids, 20 chores, 10 achievements). Larger setups may take longer.

### Data Preservation Guarantee

The following structures are **NEVER** modified by this service:

**Kids**: Profile data preserved

- `internal_id`, `name`, `ha_user_id`, `mobile_notify_service`
- `use_persistent_notifications`, `dashboard_language`
- Shadow kid linkage (`is_shadow`, `linked_parent_id`)

**Parents**: Completely untouched

**Chores**: All definition fields preserved

- `name`, `description`, `icon`, `labels`, `points`
- `recurring_frequency`, `completion_criteria`, `assigned_kids`
- `applicable_days`, `due_date`, `auto_approve`
- All notification settings

**Rewards**: All definition fields preserved

- `name`, `description`, `icon`, `labels`, `cost`

**Badges**: All definition fields preserved

- `name`, `description`, `icon`, `type`, `threshold`, `multiplier`
- Maintenance rules, reset frequency

**Penalties**: All definition fields preserved

- `name`, `description`, `icon`, `labels`, `points_deducted`

**Bonuses**: All definition fields preserved

- `name`, `description`, `icon`, `labels`, `points_awarded`

**Achievements**: Definition fields preserved

- `name`, `description`, `icon`, `labels`, `type`, `criteria`
- `target_value`, `reward_points`, `assigned_kids`, `selected_chore_id`

**Challenges**: Definition fields preserved

- `name`, `description`, `icon`, `labels`, `type`, `criteria`
- `target_value`, `reward_points`, `assigned_kids`, `selected_chore_id`
- `start_date`, `end_date`, `required_daily`

**System Settings**: Config entry options completely untouched

- Points theme, intervals, retention settings, etc.

### Use Cases

1. **New School Year**: Start fresh with same chores but reset all progress
2. **New Points System**: Test different point values without losing setup
3. **Family Milestone**: Reset for major life changes (new house, new baby)
4. **Testing**: Validate points/badge logic with clean slate
5. **Behavior Reset**: Clear all history after addressing behavioral issues

### Future Enhancements

- **Selective Reset**: Add optional parameters to reset only certain domains (e.g., only achievements, only rewards)
- **Scheduled Reset**: Allow automation-triggered resets (e.g., first day of school year)
- **Partial Reset by Kid**: Reset one kid's data without affecting others
- **Reset History**: Track when resets occurred for audit purposes

---

## Template usage notice

This plan follows the `PLAN_TEMPLATE.md` structure. Once complete, rename to `SOFT_RESET_SERVICE_COMPLETE.md` and move to `docs/completed/`.
