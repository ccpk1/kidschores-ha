# Phase 7: Platinum Architecture Refactoring

---

status: 🟡 IN-PROGRESS
target_release: v0.5.0
owner: Builder Agent
created: 2025-01-27
last_updated: 2025-01-27
handoff_from: User (Architectural Review)

---

## Initiative Snapshot

| Field               | Value                             |
| ------------------- | --------------------------------- |
| **Initiative Name** | Platinum Architecture Refactoring |
| **Code**            | PHASE7-PLATINUM                   |
| **Target Release**  | v0.5.0(bundled)                   |
| **Owner**           | Builder Agent                     |
| **Status**          | 🟡 IN-PROGRESS                    |
| **Prerequisites**   | Phase 6 Complete ✅               |

## Problem Statement

Phase 6 achieved the coordinator slimming goal (4,607 → 1,720 lines, -63%), but the architectural review identified 5 "gravity wells" preventing true Platinum-level modularity:

1. **Manager Coupling** - GamificationManager directly calls EconomyManager/RewardManager
2. **CRUD Lifecycle Leakage** - services.py bypasses managers, writes directly to `_data`
3. **Reliability Gap** - `_dirty_kids` tracking is in-memory only, lost on restart
4. **Helper/Utility Bloat** - kc_helpers.py mixes pure logic with HA-bound code
5. **Statistics Passivity** - StatisticsManager is reactive, not a stateful data provider

## Summary Table

| Phase                                  | Description                                                                  | %   | Quick Notes                                     |
| -------------------------------------- | ---------------------------------------------------------------------------- | --- | ----------------------------------------------- |
| Phase 7.1 – Helper/Utility Split       | Decompose kc_helpers.py into pure \_utils and HA-bound \_helpers             | 0%  | Foundation for engine purity                    |
| Phase 7.2 – Event-Driven Awards        | Remove direct economy_manager calls from GamificationManager                 | 0%  | Decouple manager interactions                   |
| Phase 7.3 – Manager-Owned CRUD         | Move create/update/delete from services.py AND options_flow.py into managers | 0%  | **THE BIG WIN** - 27+ locations, single DB path |
| Phase 7.4 – Persisted Evaluation Queue | Replace \_dirty_kids with persisted queue                                    | 0%  | Reliability improvement                         |
| Phase 7.5 – Statistics Provider        | Transform StatisticsManager into stateful cache                              | 0%  | Performance optimization                        |
| Phase 7.6 – Final Validation           | Integration testing and documentation                                        | 0%  | Quality gates                                   |

---

## Phase 7.1 – Helper/Utility Split

**Goal:** Decompose `kc_helpers.py` (2,358 lines) into pure Python utilities (`_utils/`) and HA-bound helpers (`_helpers/`), enabling engines to remain unit-testable without Home Assistant mocking.

### Current State Analysis

`kc_helpers.py` currently contains:

- **Pure Python Functions** (can be extracted):
  - Date/time: `dt_today_local`, `dt_now_iso`, `dt_parse`, `dt_add_interval`, `dt_next_schedule`, `dt_to_utc`, `dt_format_duration`, etc. (~20 functions, ~600 lines)
  - String parsing: `parse_points_adjust_values` (~30 lines)
  - Math/calculation helpers (point rounding, multipliers)

- **HA-Bound Functions** (require `hass` object):
  - Entity registry: `get_integration_entities`, `parse_entity_reference`, `remove_entities_by_item_id` (~150 lines)
  - Authorization: `is_kid_authorized`, `is_parent_authorized`, etc. (~90 lines)
  - Device info: `build_kid_device_info`, `build_system_device_info` (~80 lines)
  - Entity lookups: `get_kid_by_name`, `get_chore_by_name`, etc. (~200 lines)

### Target Structure

```
custom_components/kidschores/
├── utils/                    # Pure Python (ZERO HA imports)
│   ├── __init__.py           # Re-exports for convenience
│   ├── dt_utils.py           # Date/time parsing, formatting, scheduling
│   └── math_utils.py         # Point rounding, multiplier arithmetic
│
├── helpers/                  # HA-Bound (requires hass object)
│   ├── __init__.py           # Re-exports for convenience
│   ├── entity_helpers.py     # Registry lookups, unique_id parsing
│   ├── auth_helpers.py       # Permission and user validation
│   └── device_helpers.py     # DeviceInfo construction
│
├── kc_helpers.py             # DEPRECATED - imports from utils/ and helpers/
│                             # Preserved for backwards compatibility during transition
```

### Steps

- [ ] **7.1.1** Create `utils/` directory structure
  - Create `custom_components/kidschores/utils/__init__.py`
  - Create `custom_components/kidschores/utils/dt_utils.py`
  - Create `custom_components/kidschores/utils/math_utils.py`

- [ ] **7.1.2** Extract date/time utilities to `dt_utils.py`
  - Move functions: `dt_today_local`, `dt_today_iso`, `dt_now_local`, `dt_now_iso`, `dt_to_utc`, `dt_parse_duration`, `dt_format_duration`, `dt_time_until`, `dt_parse_date`, `dt_format_short`, `dt_format`, `dt_parse`, `dt_add_interval`, `dt_next_schedule`, `parse_daily_multi_times`
  - Ensure ZERO imports from `homeassistant.*`
  - Update imports in `kc_helpers.py` to re-export from `utils.dt_utils`
  - File: Lines ~1355-2100 of current kc_helpers.py

- [ ] **7.1.3** Extract math utilities to `math_utils.py`
  - Move functions: `parse_points_adjust_values` (line ~652)
  - Any point rounding, multiplier calculations
  - Ensure ZERO imports from `homeassistant.*`

- [ ] **7.1.4** Create `helpers/` directory structure
  - Create `custom_components/kidschores/helpers/__init__.py`
  - Create `custom_components/kidschores/helpers/entity_helpers.py`
  - Create `custom_components/kidschores/helpers/auth_helpers.py`
  - Create `custom_components/kidschores/helpers/device_helpers.py`

- [ ] **7.1.5** Extract entity registry helpers to `entity_helpers.py`
  - Move functions: `get_integration_entities`, `parse_entity_reference`, `remove_entities_by_item_id`
  - Include all entity lookup functions: `get_kid_by_name`, `get_chore_by_name`, `get_reward_by_name`, etc.
  - File: Lines ~80-240, ~650-840 of current kc_helpers.py

- [ ] **7.1.6** Extract authorization helpers to `auth_helpers.py`
  - Move functions: `is_kid_authorized`, `is_parent_authorized`, `get_all_authorized_kids`, etc.
  - File: Lines ~530-620 of current kc_helpers.py

- [ ] **7.1.7** Extract device helpers to `device_helpers.py`
  - Move functions: `build_kid_device_info`, `build_system_device_info`
  - File: Lines ~840-920 of current kc_helpers.py

- [ ] **7.1.8** Update `kc_helpers.py` as compatibility shim
  - Keep `kc_helpers.py` but import and re-export from `utils/` and `helpers/`
  - Add deprecation comments pointing to new locations
  - Ensures existing imports continue to work during transition

- [ ] **7.1.9** Update engine imports
  - Engines (`engines/*.py`) should ONLY import from `utils/`
  - Verify: `from custom_components.kidschores.utils import dt_utils`
  - Verify: NO `from homeassistant.*` imports in engines

- [ ] **7.1.10** Run validation suite
  - `python -m pytest tests/ -v --tb=line`
  - `MYPYPATH=/workspaces/core python -m mypy custom_components/kidschores/`
  - `ruff check custom_components/kidschores/`

### Key Issues / Dependencies

- **Backwards Compatibility**: Must maintain `kc_helpers.py` as shim to avoid breaking 50+ import sites
- **Circular Imports**: Careful sequencing needed - `utils/` must have ZERO dependencies on other kidschores modules
- **Engine Purity**: After completion, engines must compile with `homeassistant.*` imports removed

---

## Phase 7.2 – Event-Driven Awards

**Goal:** Remove direct `economy_manager.deposit()` calls from GamificationManager. Instead, GamificationManager emits events, and EconomyManager listens and handles award deposits.

### Current State Analysis

GamificationManager currently makes 3 direct calls to EconomyManager:

- Line 289: `await self.coordinator.economy_manager.deposit(...)` (achievement awards)
- Line 351: `await self.coordinator.economy_manager.deposit(...)` (challenge awards)
- Line 1848: `await self.coordinator.economy_manager.deposit(...)` (badge awards)

### Target Architecture

```
GamificationManager                    EconomyManager
      │                                      │
      ├─ award_badge()                       │
      │    ├─ Update badge progress          │
      │    └─ emit(BADGE_EARNED) ──────────► listen(BADGE_EARNED)
      │                                      │    └─ deposit(badge_points)
      │                                      │
      ├─ award_achievement()                 │
      │    ├─ Update achievement progress    │
      │    └─ emit(ACHIEVEMENT_UNLOCKED) ──► listen(ACHIEVEMENT_UNLOCKED)
      │                                      │    └─ deposit(achievement_points)
      │                                      │
      └─ award_challenge()                   │
           ├─ Update challenge progress      │
           └─ emit(CHALLENGE_COMPLETED) ───► listen(CHALLENGE_COMPLETED)
                                             │    └─ deposit(challenge_points)
```

### Steps

- [ ] **7.2.1** Add event payload fields for award points
  - Update `SIGNAL_SUFFIX_BADGE_EARNED` payload to include `badge_points: float`
  - Update `SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED` payload to include `achievement_points: float`
  - Update `SIGNAL_SUFFIX_CHALLENGE_COMPLETED` payload to include `challenge_points: float`
  - File: `gamification_manager.py` emit() calls

- [ ] **7.2.2** Add EconomyManager event listeners
  - Add `listen(SIGNAL_SUFFIX_BADGE_EARNED, self._on_badge_earned)` in `async_setup()`
  - Add `listen(SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED, self._on_achievement_unlocked)` in `async_setup()`
  - Add `listen(SIGNAL_SUFFIX_CHALLENGE_COMPLETED, self._on_challenge_completed)` in `async_setup()`
  - File: `managers/economy_manager.py`

- [ ] **7.2.3** Implement EconomyManager award handlers

  ```python
  async def _on_badge_earned(self, payload: dict[str, Any]) -> None:
      """Handle badge earned event - deposit award points."""
      kid_id = payload.get("kid_id")
      badge_id = payload.get("badge_id")
      badge_points = payload.get("badge_points", 0.0)
      if badge_points > 0 and kid_id:
          await self.deposit(
              kid_id=kid_id,
              amount=badge_points,
              source=const.POINTS_SOURCE_BADGES,
              reference_id=badge_id,
          )
  ```

  - Similar handlers for `_on_achievement_unlocked` and `_on_challenge_completed`

- [ ] **7.2.4** Remove direct deposit calls from GamificationManager
  - Remove `await self.coordinator.economy_manager.deposit(...)` at line 289
  - Remove `await self.coordinator.economy_manager.deposit(...)` at line 351
  - Remove `await self.coordinator.economy_manager.deposit(...)` at line 1848
  - File: `managers/gamification_manager.py`

- [ ] **7.2.5** Update event emissions with award amounts
  - `award_badge()`: Include `badge_points=badge_info.get(const.DATA_BADGE_REWARD_POINTS, 0)`
  - `award_achievement()`: Include `achievement_points=achievement_info.get(const.DATA_ACHIEVEMENT_REWARD_POINTS, 0)`
  - `award_challenge()`: Include `challenge_points=challenge_info.get(const.DATA_CHALLENGE_REWARD_POINTS, 0)`

- [ ] **7.2.6** Update tests to verify event-driven flow
  - Test that badge earn emits event with points
  - Test that EconomyManager deposits points on receiving event
  - Verify no infinite loops (EconomyManager ignores gamification-sourced events)
  - File: `tests/test_gamification_*.py`

- [ ] **7.2.7** Run validation suite
  - `python -m pytest tests/test_gamification*.py tests/test_economy*.py -v`
  - `python -m pytest tests/ -v --tb=line`

### Key Issues / Dependencies

- **Event Ordering**: GamificationManager must emit AFTER updating progress data
- **Loop Prevention**: EconomyManager already skips gamification-sourced point changes (existing logic)
- **Async Timing**: Events are synchronous callbacks, but deposit() is async - need `hass.async_create_task()`

---

## Phase 7.3 – Manager-Owned CRUD (The "Pivot to Manager")

**Goal:** Move entity creation/update/deletion from BOTH `services.py` AND `options_flow.py` into domain managers. This creates a **single path to the database** - the hallmark of professional architecture.

### Current State Analysis (Critical!)

**The Problem:** UI (options_flow.py) and Services (services.py) are both "touching the database" directly.

**`options_flow.py` (4,778 lines)** - The bigger offender:

- **21+ direct `_data[...]` writes** across Kids, Parents, Chores, Rewards, Badges, Bonuses, Penalties
- **21+ `_persist()` calls** scattered throughout flow handlers
- Lines: 387, 440, 555, 581, 586, 722, 950, 978, 999, 1014, 1101, 1225, 1876, 2069, 2340, 2622, 2683, 2792, 2864, 2969, 3060

**`services.py` (2,420 lines)**:

- 6 direct `_data[...]` writes
- 6 `_persist()` calls
- Lines: 495, 503, 645, 825, 1412, 1532

### The Layered Architecture Target

| Layer              | Component           | Responsibility                                        |
| :----------------- | :------------------ | :---------------------------------------------------- |
| **Presentation**   | `options_flow.py`   | Display forms, collect strings/numbers, show errors   |
| **Presentation**   | `services.py`       | Handle automation calls, validate input               |
| **Service**        | `ChoreManager`      | Decide _to_ write, trigger persistence, fire events   |
| **Logic/Library**  | `data_builders.py`  | Ensure dict has right keys/types (The "Schema")       |
| **Infrastructure** | `entity_helpers.py` | Talk to Home Assistant registries (HA-bound)          |
| **Infrastructure** | `dt_utils.py`       | Format timestamps (Pure Python)                       |
| **Hub**            | `Coordinator`       | Hold memory (`_data`) and provide `_persist()` method |

### Target Pattern

```python
# BEFORE (options_flow.py or services.py):
chore_dict = db.build_chore(user_input)
coordinator._data[const.DATA_CHORES][internal_id] = dict(chore_dict)  # UI touching DB!
coordinator._persist()  # UI managing persistence!

# AFTER (options_flow.py or services.py):
internal_id = await coordinator.chore_manager.create_chore(user_input)
# That's it. The Manager handles everything else.

# INSIDE ChoreManager:
async def create_chore(self, user_input: dict[str, Any]) -> str:
    """Create a new chore entity.

    Single path to database for both UI (options_flow) and Services.
    """
    # 1. Logic Layer: Use data_builders to validate and construct
    chore_dict = db.build_chore(user_input)
    internal_id = chore_dict[const.DATA_CHORE_INTERNAL_ID]

    # 2. Storage Layer: Manager writes to shared data object
    self.coordinator._data[const.DATA_CHORES][internal_id] = dict(chore_dict)

    # 3. Persistence: Manager triggers save
    self.coordinator._persist()

    # 4. Side Effects: Manager fires "CREATED" event
    self.emit(const.SIGNAL_SUFFIX_CHORE_CREATED, chore_id=internal_id)

    return internal_id
```

**Why this is better:**

- **DRY:** Both `services.py` and `options_flow.py` call the _exact same_ method
- **Consistency:** Default values, validation, events all in one place
- **Testability:** Test the Manager once, not every UI path

### Steps

#### A. Create Manager CRUD Methods (Foundation)

- [ ] **7.3.1** Add `create_chore()` method to ChoreManager

  ```python
  async def create_chore(self, user_input: dict[str, Any]) -> str:
      """Create a new chore entity.

      Single path to database for both UI and Services.

      Args:
          user_input: Validated chore data from flow/service

      Returns:
          The internal_id of the created chore
      """
      chore_dict = db.build_chore(user_input)
      internal_id = chore_dict[const.DATA_CHORE_INTERNAL_ID]
      self.coordinator._data[const.DATA_CHORES][internal_id] = dict(chore_dict)
      self.coordinator._persist()
      self.emit(const.SIGNAL_SUFFIX_CHORE_CREATED, chore_id=internal_id)
      return internal_id
  ```

  - File: `managers/chore_manager.py`

- [ ] **7.3.2** Add `update_chore()` method to ChoreManager
  - Accept `chore_id` and `user_input`
  - Use `db.build_chore(user_input, existing=current_chore)`
  - Emit `SIGNAL_SUFFIX_CHORE_UPDATED` signal

- [ ] **7.3.3** Add `delete_chore()` method to ChoreManager
  - Remove from `_data`
  - Call `entity_helpers.remove_entities_by_item_id(chore_id)`
  - Emit `SIGNAL_SUFFIX_CHORE_DELETED` signal

- [ ] **7.3.4** Add CRUD methods to RewardManager
  - `create_reward()`, `update_reward()`, `delete_reward()`

- [ ] **7.3.5** Add CRUD methods to EconomyManager (for Bonus/Penalty)
  - `create_bonus()`, `update_bonus()`, `delete_bonus()`
  - `create_penalty()`, `update_penalty()`, `delete_penalty()`

- [ ] **7.3.6** Add CRUD methods to GamificationManager (for Badges)
  - `create_badge()`, `update_badge()`, `delete_badge()`

- [ ] **7.3.7** Add KidManager or use Coordinator for Kid/Parent CRUD
  - Consider: Kids/Parents are "system" entities, may stay in Coordinator
  - OR create a new `PersonManager` for consistency

#### B. Update services.py (6 locations)

- [ ] **7.3.8** Update `handle_create_chore` (line ~645)
  - Replace: `coordinator._data[...] = ...` + `_persist()`
  - With: `await coordinator.chore_manager.create_chore(data_input)`

- [ ] **7.3.9** Update `handle_update_chore` (line ~825)
  - Replace with `await coordinator.chore_manager.update_chore(chore_id, data_input)`

- [ ] **7.3.10** Update `handle_create_reward` (line ~1412)
  - Replace with `await coordinator.reward_manager.create_reward(data_input)`

- [ ] **7.3.11** Update `handle_update_reward` (line ~1532)
  - Replace with `await coordinator.reward_manager.update_reward(reward_id, data_input)`

#### C. Update options_flow.py (21+ locations) - THE BIG WIN

- [ ] **7.3.12** Update Kid create flow (line ~387)
  - Replace: `coordinator._data[const.DATA_KIDS][internal_id] = dict(kid_data)`
  - With: `await coordinator.create_kid(user_input)` or Manager equivalent

- [ ] **7.3.13** Update Kid edit flow (line ~440)
  - Replace with Manager update method

- [ ] **7.3.14** Update Parent create flow (line ~555)
  - Replace with Manager/Coordinator method

- [ ] **7.3.15** Update Parent edit flow (line ~722)
  - Replace with Manager/Coordinator method

- [ ] **7.3.16** Update Chore create flows (lines ~950, 978, 999, 1014)
  - Replace ALL with `await coordinator.chore_manager.create_chore()`

- [ ] **7.3.17** Update Chore edit flows (lines ~1101, 1225, 1876, 2069)
  - Replace ALL with `await coordinator.chore_manager.update_chore()`

- [ ] **7.3.18** Update Badge create/edit flows (line ~2340)
  - Replace with `await coordinator.gamification_manager.create_badge()`

- [ ] **7.3.19** Update Reward create flow (line ~2622)
  - Replace with `await coordinator.reward_manager.create_reward()`

- [ ] **7.3.20** Update Reward edit flow (line ~2683)
  - Replace with `await coordinator.reward_manager.update_reward()`

- [ ] **7.3.21** Update Bonus create/edit flows (lines ~2792, 2864)
  - Replace with `await coordinator.economy_manager.create_bonus()` / `update_bonus()`

- [ ] **7.3.22** Update Penalty create/edit flows (lines ~2969, 3060)
  - Replace with `await coordinator.economy_manager.create_penalty()` / `update_penalty()`

#### D. Signal Constants and Final Cleanup

- [ ] **7.3.23** Add new signal constants to `const.py`

  ```python
  SIGNAL_SUFFIX_CHORE_CREATED = "chore_created"
  SIGNAL_SUFFIX_CHORE_UPDATED = "chore_updated"
  SIGNAL_SUFFIX_CHORE_DELETED = "chore_deleted"
  SIGNAL_SUFFIX_REWARD_CREATED = "reward_created"
  SIGNAL_SUFFIX_REWARD_UPDATED = "reward_updated"
  SIGNAL_SUFFIX_REWARD_DELETED = "reward_deleted"
  SIGNAL_SUFFIX_BADGE_CREATED = "badge_created"
  SIGNAL_SUFFIX_BADGE_UPDATED = "badge_updated"
  SIGNAL_SUFFIX_BADGE_DELETED = "badge_deleted"
  SIGNAL_SUFFIX_BONUS_CREATED = "bonus_created"
  SIGNAL_SUFFIX_BONUS_UPDATED = "bonus_updated"
  SIGNAL_SUFFIX_BONUS_DELETED = "bonus_deleted"
  SIGNAL_SUFFIX_PENALTY_CREATED = "penalty_created"
  SIGNAL_SUFFIX_PENALTY_UPDATED = "penalty_updated"
  SIGNAL_SUFFIX_PENALTY_DELETED = "penalty_deleted"
  ```

- [ ] **7.3.24** Run validation suite
  - `python -m pytest tests/test_*_services.py tests/test_options_flow*.py -v`
  - `python -m pytest tests/ -v --tb=line`

### Config Flow: The Special Case

**Config Flow (`config_flow.py`) is unique** because the integration is not yet fully loaded when it runs.

**Recommendation:** Keep Config Flow using `data_builders.py` directly to prepare the _initial_ data structure.

- Once `config_entry` is created, it saves to disk
- The moment `async_setup_entry` runs, Managers are initialized
- Config Flow is "done" at that point

**Do NOT refactor Config Flow** - it's the "birth" of the integration and acceptable as-is.

### Registry Operations: The Helper Pattern

**Where do entity registry operations go?**

Registry operations (deleting entities from HA) should be **triggered by the Manager** but **executed by a Helper**.

```python
# Inside ChoreManager.delete_chore():
async def delete_chore(self, chore_id: str) -> None:
    """Delete a chore and clean up HA entities."""
    # 1. Remove from data
    del self.coordinator._data[const.DATA_CHORES][chore_id]

    # 2. Persist
    self.coordinator._persist()

    # 3. Clean up HA registry (delegated to helper)
    await entity_helpers.remove_entities_by_item_id(
        self.hass, self.coordinator.config_entry.entry_id, chore_id
    )

    # 4. Emit event
    self.emit(const.SIGNAL_SUFFIX_CHORE_DELETED, chore_id=chore_id)
```

**Why not in Coordinator?** If registry cleanup is in Coordinator, it becomes a dumping ground. By moving to Manager, "Chore Deletion" is a feature of the "Chore Domain."

### Key Issues / Dependencies

- **Scope:** This is the LARGEST phase - 27+ locations to update across 2 files (7,200 lines total)
- **Execution Order:** Create ALL manager methods FIRST, then update callers
- **Entity Creation:** Sensor entity creation (`create_chore_entities`) may need to move into Manager or be called by Manager
- **Validation Location:** Keep validation in flows/services (via `db.validate_*()`) - managers trust validated input
- **Transaction Scope:** Manager methods must be atomic (write + persist + emit together)
- **Config Flow Exception:** Do NOT refactor config_flow.py - it's the special "birth" case

### Estimated Effort

| Component               | Locations               | Effort   |
| ----------------------- | ----------------------- | -------- |
| Manager CRUD methods    | 7 managers × 3 ops      | Medium   |
| services.py updates     | 6 locations             | Low      |
| options_flow.py updates | 21 locations            | High     |
| Signal constants        | 15 new constants        | Low      |
| Tests                   | Update mocks/assertions | Medium   |
| **Total**               | ~50 changes             | **High** |

**Recommendation:** Split into sub-phases:

- 7.3a: ChoreManager CRUD + services.py + options_flow chore paths
- 7.3b: RewardManager CRUD + paths
- 7.3c: EconomyManager (Bonus/Penalty) CRUD + paths
- 7.3d: GamificationManager (Badge) CRUD + paths
- 7.3e: Kid/Parent CRUD + paths

---

## Phase 7.4 – Persisted Evaluation Queue

**Goal:** Replace transient `_dirty_kids` with a persisted `pending_evaluations` queue stored in storage metadata, ensuring restart resilience.

### Current State Analysis

`GamificationManager._dirty_kids` (line 78):

- Type: `set[str]` (in-memory only)
- Used in: `_mark_dirty()`, `_evaluate_dirty_kids()`
- **Risk**: Lost if HA restarts during 2.0-second debounce window

### Target Design

```python
# Storage structure addition in meta section:
{
  "meta": {
    "version": 42,
    "pending_evaluations": ["kid-uuid-1", "kid-uuid-2"],  # NEW
    ...
  }
}

# GamificationManager changes:
- Rename _dirty_kids → _pending_evaluations
- On _mark_dirty(): Add to set AND persist to meta
- On _evaluate_dirty_kids(): Clear from meta after evaluation
- On async_setup(): Check meta for pending, process immediately
```

### Steps

- [ ] **7.4.1** Add storage schema support for pending_evaluations
  - Add `DATA_META_PENDING_EVALUATIONS = "pending_evaluations"` constant
  - Update `_init_storage_structure()` to include empty list in meta
  - File: `const.py`, `coordinator.py`

- [ ] **7.4.2** Rename `_dirty_kids` to `_pending_evaluations`
  - Update variable name throughout GamificationManager
  - Update terminology in comments/docstrings: "dirty" → "pending" or "stale"
  - File: `managers/gamification_manager.py`

- [ ] **7.4.3** Add `_persist_pending()` method

  ```python
  def _persist_pending(self) -> None:
      """Persist pending evaluation queue to storage meta."""
      self.coordinator._data[const.DATA_META][const.DATA_META_PENDING_EVALUATIONS] = list(self._pending_evaluations)
      self.coordinator._persist()
  ```

- [ ] **7.4.4** Update `_mark_dirty()` to persist

  ```python
  def _mark_dirty(self, kid_id: str) -> None:
      """Mark a kid for re-evaluation (persisted)."""
      self._pending_evaluations.add(kid_id)
      self._persist_pending()  # NEW: Persist to storage
      self._schedule_evaluation()
  ```

- [ ] **7.4.5** Update `_evaluate_dirty_kids()` to clear from storage

  ```python
  async def _evaluate_dirty_kids(self) -> None:
      """Batch evaluate all pending kids."""
      kids_to_evaluate = self._pending_evaluations.copy()
      self._pending_evaluations.clear()
      self._persist_pending()  # Clear from storage
      # ... rest of evaluation logic
  ```

- [ ] **7.4.6** Add startup recovery in `async_setup()`

  ```python
  async def async_setup(self) -> None:
      # ... existing subscription code ...

      # Recover any pending evaluations from storage
      pending = self.coordinator._data.get(const.DATA_META, {}).get(
          const.DATA_META_PENDING_EVALUATIONS, []
      )
      if pending:
          const.LOGGER.info(
              "GamificationManager: Recovering %d pending evaluations from storage",
              len(pending),
          )
          self._pending_evaluations.update(pending)
          self._schedule_evaluation()
  ```

- [ ] **7.4.7** Update tests
  - Test that marking dirty persists to storage
  - Test that restart recovers pending evaluations
  - Test that completed evaluation clears storage
  - File: `tests/test_gamification_*.py`

- [ ] **7.4.8** Run validation suite
  - `python -m pytest tests/test_gamification*.py -v`
  - `python -m pytest tests/ -v --tb=line`

### Key Issues / Dependencies

- **Storage Version**: May need SCHEMA_VERSION increment if adding new meta field
- **Performance**: Each mark_dirty() now triggers persist - acceptable since debounce batches
- **Migration**: Existing storage files need default empty list for new field

---

## Phase 7.5 – Statistics Provider

**Goal:** Transform StatisticsManager from a reactive event listener into a stateful data provider with in-memory cache, moving calculation cost from sensor refresh to event time.

### Current State Analysis

StatisticsManager (381 lines) currently:

- Listens to events and updates `kid_info[const.DATA_KID_POINT_STATS]`
- Recalculates stats on each event
- Sensors query coordinator data directly

### Target Design

```python
# StatisticsManager with cache:
class StatisticsManager:
    _stats_cache: dict[str, KidStats]  # kid_id → computed stats

    def _on_points_changed(self, payload):
        # Update raw data AND refresh cache
        self._update_cache(kid_id)

    def get_stats(self, kid_id: str) -> KidStats:
        """Get cached stats - no recalculation."""
        return self._stats_cache.get(kid_id, DEFAULT_STATS)
```

### Steps

- [ ] **7.5.1** Add `_stats_cache` to StatisticsManager
  - Type: `dict[str, dict[str, Any]]` (kid_id → aggregated stats)
  - Initialize in `__init__()`
  - File: `managers/statistics_manager.py`

- [ ] **7.5.2** Add `_update_cache()` method

  ```python
  def _update_cache(self, kid_id: str) -> None:
      """Update cached stats for a kid."""
      kid_info = self._get_kid(kid_id)
      if kid_info:
          self._stats_cache[kid_id] = {
              "point_stats": self._stats_engine.generate_point_stats(kid_info),
              "chore_stats": self._stats_engine.generate_chore_stats(kid_info),
              "reward_stats": self._stats_engine.generate_reward_stats(kid_info),
              "last_updated": kh.dt_now_iso(),
          }
  ```

- [ ] **7.5.3** Update event handlers to refresh cache
  - `_on_points_changed()`: Call `self._update_cache(kid_id)`
  - `_on_chore_approved()`: Call `self._update_cache(kid_id)`
  - `_on_reward_approved()`: Call `self._update_cache(kid_id)`

- [ ] **7.5.4** Add public `get_stats()` method

  ```python
  def get_stats(self, kid_id: str) -> dict[str, Any]:
      """Get cached stats for a kid.

      Returns cached data without recalculation.
      If cache miss, generates and caches on first access.
      """
      if kid_id not in self._stats_cache:
          self._update_cache(kid_id)
      return self._stats_cache.get(kid_id, {})
  ```

- [ ] **7.5.5** Add cache initialization in `async_setup()`

  ```python
  async def async_setup(self) -> None:
      # ... existing subscriptions ...

      # Initialize cache for all existing kids
      for kid_id in self._coordinator.kids_data:
          self._update_cache(kid_id)
  ```

- [ ] **7.5.6** Update sensors to use cache
  - Identify sensors that query point_stats
  - Update to call `coordinator.statistics_manager.get_stats(kid_id)`
  - File: `sensor.py` or relevant sensor files

- [ ] **7.5.7** Run validation suite
  - `python -m pytest tests/test_statistics*.py -v`
  - `python -m pytest tests/ -v --tb=line`

### Key Issues / Dependencies

- **Cache Invalidation**: Must invalidate on kid deletion
- **Memory Usage**: Cache size proportional to number of kids (acceptable)
- **First Access**: Initial cache build on startup may be slow for large families

---

## Phase 7.6 – Final Validation

**Goal:** Comprehensive validation that all architectural improvements work together correctly.

### Steps

- [ ] **7.6.1** Run full test suite
  - `python -m pytest tests/ -v --tb=line`
  - Target: 1098+ tests pass

- [ ] **7.6.2** Run mypy strict checking
  - `MYPYPATH=/workspaces/core python -m mypy custom_components/kidschores/`
  - Target: 0 errors

- [ ] **7.6.3** Run lint checks
  - `ruff check custom_components/kidschores/`
  - Target: All checks pass

- [ ] **7.6.4** Verify coordinator line count
  - `wc -l custom_components/kidschores/coordinator.py`
  - Target: Maintain ~1,700 lines (no regression)

- [ ] **7.6.5** Verify engine purity
  - Check `engines/*.py` for `homeassistant.*` imports
  - Target: ZERO HA imports in engine files (only `utils/` imports)

- [ ] **7.6.6** Document architecture changes
  - Update `docs/ARCHITECTURE.md` with new module structure
  - Document `utils/` vs `helpers/` split
  - Document event-driven award flow

- [ ] **7.6.7** Update AGENTS.md
  - Add guidance for new module locations
  - Update import patterns

---

## Decisions & Completion Check

### Decisions to Capture

| Decision Point           | Options                       | Selected     | Rationale                                 |
| ------------------------ | ----------------------------- | ------------ | ----------------------------------------- |
| kc_helpers.py fate       | Delete / Keep as shim         | Keep as shim | Backwards compatibility during transition |
| CRUD validation location | Manager / Service             | Service      | Managers trust validated input            |
| Cache persistence        | Memory-only / Storage         | Memory-only  | Stats are derivable from raw data         |
| Terminology              | "dirty" / "stale" / "pending" | "pending"    | Clearer intent                            |

### Completion Requirements

| Requirement               | Verification Method                                   |
| ------------------------- | ----------------------------------------------------- |
| All tests pass            | `pytest tests/ -v` → 1098+ passed                     |
| MyPy clean                | `mypy custom_components/kidschores/` → 0 errors       |
| Lint clean                | `ruff check` → All checks passed                      |
| Engine purity             | `grep "from homeassistant" engines/*.py` → No results |
| No coordinator regression | `wc -l coordinator.py` → ~1,700 lines                 |

### Sign-off

- [ ] All phases complete
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Ready for release

---

## References

| Document                                                                                     | Use For                            |
| -------------------------------------------------------------------------------------------- | ---------------------------------- |
| [ARCHITECTURE.md](../ARCHITECTURE.md)                                                        | Current data model, storage schema |
| [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)                                      | Naming conventions, patterns       |
| [AGENTS.md](../../AGENTS.md)                                                                 | Agent guidance, quick reference    |
| [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) | Test patterns                      |
| [Phase 6 Plan](./PHASE6_COORDINATOR_SLIM_IN-PROCESS.md)                                      | Prior refactoring context          |

---

## Appendix: Code Locations

### Files to Create

| File                        | Purpose             | Approx Lines |
| --------------------------- | ------------------- | ------------ |
| `utils/__init__.py`         | Re-exports          | ~20          |
| `utils/dt_utils.py`         | Date/time utilities | ~600         |
| `utils/math_utils.py`       | Math helpers        | ~50          |
| `helpers/__init__.py`       | Re-exports          | ~20          |
| `helpers/entity_helpers.py` | Registry helpers    | ~400         |
| `helpers/auth_helpers.py`   | Authorization       | ~100         |
| `helpers/device_helpers.py` | DeviceInfo builders | ~100         |

### Files to Modify

| File                      | Change Type                             | Lines Affected     |
| ------------------------- | --------------------------------------- | ------------------ |
| `kc_helpers.py`           | Refactor to shim                        | All (2,358 → ~100) |
| `gamification_manager.py` | Remove direct calls, add badge CRUD     | ~100               |
| `economy_manager.py`      | Add event listeners, bonus/penalty CRUD | ~200               |
| `chore_manager.py`        | Add chore CRUD methods                  | ~150               |
| `reward_manager.py`       | Add reward CRUD methods                 | ~100               |
| `services.py`             | Use manager CRUD (6 locations)          | ~60                |
| `options_flow.py`         | **Use manager CRUD (21 locations)**     | ~200               |
| `statistics_manager.py`   | Add cache                               | ~100               |
| `const.py`                | Add constants, signals                  | ~40                |

### The "Single Path to Database" Principle

After Phase 7.3, all data writes follow this path:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ options_flow.py │────▶│                 │     │                 │
│   (UI Forms)    │     │                 │     │                 │
└─────────────────┘     │    MANAGER      │────▶│   COORDINATOR   │
                        │  (Single Entry) │     │   (Storage Hub) │
┌─────────────────┐     │                 │     │                 │
│  services.py    │────▶│  - create_*()   │     │  - _data        │
│  (Automations)  │     │  - update_*()   │     │  - _persist()   │
└─────────────────┘     │  - delete_*()   │     │                 │
                        └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │  Event Bus      │
                        │  (Side Effects) │
                        └─────────────────┘
```

This ensures:

- **Consistency:** Same behavior for UI and Services
- **Auditability:** One place to add logging/validation
- **Testability:** Test manager once, not every caller

---

**Handoff Button**:

```
┌─────────────────────────────────────────────────────────┐
│  🔧 READY FOR BUILDER AGENT                             │
│                                                          │
│  Plan: PHASE7_PLATINUM_ARCHITECTURE_IN-PROCESS.md        │
│  Start: Phase 7.1 – Helper/Utility Split                 │
│  Validation: pytest, mypy, ruff after each phase         │
└─────────────────────────────────────────────────────────┘
```
