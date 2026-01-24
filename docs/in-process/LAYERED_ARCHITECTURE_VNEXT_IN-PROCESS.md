# Layered Architecture vNext - Strategic Plan

## Initiative snapshot

- **Name / Code**: LAYERED_ARCHITECTURE_VNEXT – Coordinator-to-Service Architecture Refactor
- **Target release / milestone**: v0.5.0 (Major architectural release)
- **Owner / driver(s)**: KidsChores Core Team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step               | Description                              | % complete | Quick notes                                   |
| -------------------------- | ---------------------------------------- | ---------- | --------------------------------------------- |
| Phase 0 – Event Foundation | Event infrastructure (signals, base mgr) | 100%       | ✅ COMPLETE 2026-01-24 (51 signals, 15 types) |
| Phase 1 – Infrastructure   | Verify renames, expand helpers           | 100%       | ✅ COMPLETE 2026-01-24 (8 cleanup helpers)    |
| Phase 2 – Notification     | Extract NotificationManager              | 0%         | First manager extraction (lowest risk)        |
| Phase 3 – Economy          | EconomyEngine + EconomyManager           | 0%         | Ledger system, point transactions             |
| Phase 4 – Chore            | ChoreEngine + ChoreManager               | 0%         | Refactor existing ChoreOperations mixin       |
| Phase 5 – Gamification     | GamificationEngine + GamificationManager | 0%         | Unify badges/achievements/challenges          |
| Phase 6 – Coordinator Slim | Reduce coordinator to routing only       | 0%         | Target: <1000 lines                           |
| Phase 7 – Testing & Polish | Integration tests, documentation         | 0%         | 95%+ coverage maintained                      |

1. **Key objective** – Transform the monolithic 10k+ line coordinator into a layered service architecture with clear separation between routing (Coordinator), state workflows (Managers), and pure logic (Engines). This enables testable units, decoupled features, and easier future feature additions.

2. **Summary of recent work**
   - Current state: `coordinator.py` (6,138 lines) + `coordinator_chore_operations.py` (3,971 lines) = 10,109 lines total
   - Already extracted: `ChoreOperations` mixin, `StatisticsEngine`, `RecurrenceEngine`, `KidsChoresStorageManager`
   - Already renamed: `entity_helpers.py` → `data_builders.py` ✅
   - **Phase 0 COMPLETE**: Event infrastructure implemented (51 signals, 15 TypedDicts, BaseManager) ✅
   - **Phase 1 COMPLETE**: Infrastructure cleanup (8 cleanup helpers moved to kc_helpers.py) ✅

3. **Next steps (short term)**
   - ✅ Phase 0 - Event Infrastructure COMPLETE (2026-01-24)
   - ✅ Phase 1 - Infrastructure Cleanup COMPLETE (2026-01-24)
   - **Next**: Implement Phase 2 - Notification Manager
     - Create `managers/notification_manager.py`
     - Consolidate notification functions from coordinator
     - Refactor to use BaseManager event patterns

4. **Risks / blockers**
   - **Breaking changes**: Service names remain stable, but internal method signatures will change
   - **Test coverage**: Must maintain 95%+ coverage throughout refactor
   - **Feature freeze**: Consider feature freeze during Phase 3-5 to prevent merge conflicts
   - **Migration complexity**: Existing ChoreOperations mixin must be carefully refactored
   - **Deferred edge cases**: CHORE_LOGIC_AUDIT analysis identified edge cases; these can be fixed post-refactor as needed

5. **References**
   - [\_SUP_EVENT_PATTERN.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md) – Event pattern analysis and decisions
   - [\_SUP_PHASE0_IMPL.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md) – **Phase 0 implementation guide (step-by-step)**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Current storage schema, data model
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Coding patterns, constants
   - [coordinator_chore_operations.py](../../custom_components/kidschores/coordinator_chore_operations.py) – Existing extraction pattern
   - [engines/](../../custom_components/kidschores/engines/) – Engine pattern reference (`schedule.py`, `statistics.py`)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) – Test patterns

6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Move from Mixins to Managers & Engines (composition over inheritance)
     - ✅ Managers communicate via Events (upstream) and method calls (downstream)
     - ✅ No ConfigurationManager – CRUD stays in coordinator with data_builders
     - ✅ Engines are stateless, pure Python – no coordinator/hass references
     - ✅ Managers are stateful, can emit/listen to events
     - ✅ Event bus: Use HA Dispatcher (`async_dispatcher_send`/`async_dispatcher_connect`)
     - ✅ Signal naming: Use `SIGNAL_SUFFIX_*` constants (not `EVENT_*`)
     - ✅ Multi-instance isolation: Scope signals via `entry_id` at runtime
     - ✅ Engines location: `engines/` directory (see `schedule.py`, `statistics.py`)
     - ✅ Reward events: Include `SIGNAL_SUFFIX_REWARD_DISAPPROVED` for symmetry
   - **Completion confirmation**: `[ ]` All follow-up items completed before marking done

---

## Architectural Overview

### Current State (Monolithic)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ KidsChoresDataCoordinator (10,109 lines)                                │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ChoreOperations (Mixin) - 3,971 lines                               │ │
│ │ - claim_chore, approve_chore, disapprove_chore                      │ │
│ │ - recurring chore handling                                          │ │
│ │ - overdue detection                                                 │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ + Storage persistence                                                   │
│ + Point management (update_kid_points)                                  │
│ + Reward operations (redeem, approve, disapprove)                       │
│ + Badge/Achievement/Challenge evaluation                                │
│ + Penalty/Bonus application                                             │
│ + All notification dispatch                                             │
│ + Entity cleanup/orphan removal                                         │
│ + Translation sensor management                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Target State (Layered)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 1: ORCHESTRATION (Coordinator) ~800 lines                         │
│ - Entry point for HA services                                           │
│ - Storage persistence (_persist)                                        │
│ - Property accessors (kids_data, chores_data, etc.)                     │
│ - Routes calls to appropriate Manager                                   │
│ - Entity lifecycle (CRUD dispatch)                                      │
└─────────────────────────────────────────────────────────────────────────┘
                              │ calls ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 2: SERVICE (Managers) - Stateful, orchestrate workflows           │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│ │NotificationMgr  │ │  EconomyMgr     │ │     GamificationMgr         │ │
│ │- send methods   │ │- deposit/withdraw│ │- evaluate all criteria      │ │
│ │- localization   │ │- NSF validation │ │- badge/achievement/challenge ││
│ │- aggregation    │ │- ledger entries │ │- maintenance (decay)        │ │
│ └─────────────────┘ └─────────────────┘ └─────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                         ChoreMgr                                    │ │
│ │ - claim/approve/disapprove workflows                                │ │
│ │ - permission checks                                                 │ │
│ │ - calls EconomyMgr for points, NotificationMgr for alerts           │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                              │ calls ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 3: DOMAIN (Engines) - Stateless, pure logic                       │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│ │  ChoreEngine    │ │  EconomyEngine  │ │   GamificationEngine        │ │
│ │- state machine  │ │- math/precision │ │- criteria evaluation        │ │
│ │- recurrence calc│ │- NSF checks     │ │- progress calculation       │ │
│ │- shared logic   │ │- ledger create  │ │- goal matching              │ │
│ └─────────────────┘ └─────────────────┘ └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                              │ uses ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 4: INFRASTRUCTURE (Shared Utilities)                              │
│ ┌────────────────────┐ ┌────────────────────┐ ┌──────────────────────┐  │
│ │ RecurrenceEngine   │ │ StatisticsEngine   │ │   data_builders.py   │  │
│ │ (schedule_engine)  │ │ (period tracking)  │ │ (entity factories)   │  │
│ └────────────────────┘ └────────────────────┘ └──────────────────────┘  │
│ ┌────────────────────┐ ┌────────────────────┐                           │
│ │   kc_helpers.py    │ │  type_defs.py      │                           │
│ │ (lookups, auth)    │ │ (TypedDicts)       │                           │
│ └────────────────────┘ └────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Event Flow Example: Parent Approves Chore

```
1. services.py → coordinator.approve_chore(kid_id, chore_id, parent_name)
2. coordinator → chore_manager.approve(kid_id, chore_id, parent_name)
3. chore_manager:
   a. chore_engine.validate_approval(chore_data, kid_data) → {valid: True, points: 10}
   b. chore_engine.transition_state(CLAIMED → APPROVED)
   c. economy_manager.deposit(kid_id, 10, source="chore_approval")
   d. notification_manager.send_approval(kid_id, chore_name, points)
   e. emit EVENT_CHORE_APPROVED
4. economy_manager (in deposit):
   a. economy_engine.create_transaction(kid_data, 10) → LedgerEntry
   b. Update kid_data["points"]
   c. emit EVENT_POINTS_CHANGE
5. gamification_manager (listening to EVENT_POINTS_CHANGE):
   a. gamification_engine.evaluate(kid_data, all_criteria) → [Badge "Saver" earned]
   b. notification_manager.send_badge_earned(kid_id, "Saver")
```

---

## Detailed phase tracking

### Phase 0 – Event Infrastructure (Foundation) ✅ COMPLETE

- **Goal**: Implement event communication infrastructure for manager-to-manager communication. All architectural decisions are now resolved (see section 6 above).
- **Completion Date**: 2026-01-24
- **Validation Results**: Lint ✅ | MyPy ✅ (0 errors) | Tests ✅ (902 passed)
- **Steps / detailed work items**
  1. - [x] Add 51 `SIGNAL_SUFFIX_*` constants to `const.py` (line 60):
     - Economy (2): `POINTS_CHANGED`, `TRANSACTION_FAILED`
     - Chore (6): `CHORE_CLAIMED/APPROVED/DISAPPROVED/OVERDUE/STATUS_RESET/RESCHEDULED`
     - Reward (4): `REWARD_CLAIMED/APPROVED/DISAPPROVED/STATUS_RESET`
     - Penalty/Bonus (4): `PENALTY_APPLIED/STATUS_RESET`, `BONUS_APPLIED/STATUS_RESET`
     - Gamification (9): Badge (3), Achievement (2), Challenge (3), progress events
     - CRUD Lifecycle (27): 9 entity types × 3 operations each
     - Uses past-tense naming convention per Event Architecture Standards

  2. - [x] Add `get_event_signal()` helper to `kc_helpers.py` (line 210):
     - Function signature: `def get_event_signal(entry_id: str, suffix: str) -> str`
     - Returns: `f"{const.DOMAIN}_{entry_id}_{suffix}"`
     - Full docstring with multi-instance isolation explanation

  3. - [x] Create `managers/base_manager.py`:
     - Abstract base class with `emit()` and `listen()` methods
     - Uses `async_dispatcher_send` / `async_dispatcher_connect` from HA
     - Automatic cleanup via `entry.async_on_unload`
     - Uses absolute imports per lint requirements

  4. - [x] Create `managers/__init__.py`:
     - Exports `BaseManager` for now
     - Will export concrete managers in later phases

  5. - [x] Add 15 event payload TypedDicts to `type_defs.py`:
     - `PointsChangedEvent`, `TransactionFailedEvent` (economy)
     - `ChoreClaimedEvent`, `ChoreApprovedEvent`, `ChoreDisapprovedEvent`, `ChoreOverdueEvent`, `ChoreRescheduledEvent` (chore)
     - `RewardApprovedEvent`, `RewardDisapprovedEvent` (reward)
     - `BadgeEarnedEvent`, `BadgeRevokedEvent` (badge)
     - `AchievementUnlockedEvent`, `ChallengeCompletedEvent` (gamification)
     - `PenaltyAppliedEvent`, `BonusAppliedEvent` (economy)

  6. - [x] Create test file `tests/test_event_infrastructure.py`:
     - 8 tests covering: signal formatting, multi-instance isolation, BaseManager emit/listen
     - All tests passing

  7. - [x] Run validation suite:
     - `./utils/quick_lint.sh --fix` ✅ (all auto-fixes applied)
     - `mypy custom_components/kidschores/` ✅ (0 errors)
     - `pytest tests/test_event_infrastructure.py -v` ✅ (8 passed)
     - `pytest tests/ -v --tb=line` ✅ (902 passed, no regressions)

- **Key issues resolved**
  - ✅ Placement: Constants added at line 60 (after Storage section) per guidelines
  - ✅ Placement: Helper added at line 210 (after Entity Registry section) per guidelines
  - ✅ Imports: `base_manager.py` uses absolute imports to satisfy TID252
  - ✅ TypedDicts: Properly exported in `__all__`
  - ✅ No circular imports: managers import from const/kc_helpers, not coordinator

---

### Phase 1 – Infrastructure Cleanup

- **Goal**: Solidify existing helpers and prepare the foundation for manager extraction.
- **Steps / detailed work items**
  1. - [x] Verify `data_builders.py` naming (already renamed from `entity_helpers.py`)
     - File: `custom_components/kidschores/data_builders.py` (2,288 lines)
     - Run: `grep -r "entity_helpers" custom_components/kidschores/` ✅ No results (only stale pycache)
  2. - [x] Expand `kc_helpers.py` with cleanup methods:
     - Added 8 stateless cleanup helper functions:
       - `cleanup_chore_from_kid_data()` - Remove chore refs from kid data
       - `cleanup_orphaned_reward_data()` - Prune invalid reward_data entries
       - `cleanup_orphaned_kid_refs_in_chores()` - Clean kid refs from chore assignments
       - `cleanup_orphaned_kid_refs_in_gamification()` - Clean kid refs from achievements/challenges
       - `cleanup_orphaned_chore_refs_in_kids()` - Clean chore refs from all kids
       - `cleanup_orphaned_kid_refs_in_parents()` - Clean kid refs from parent associations
       - `cleanup_deleted_chore_in_gamification()` - Clear invalid selected_chore_id
       - `remove_entities_by_item_id()` - HA entity registry cleanup
     - Coordinator methods now delegate to helpers, reducing code duplication
     - File: `custom_components/kidschores/kc_helpers.py` (2,336 lines, +291)
  3. - [x] Verify `engines/__init__.py` exports (already exists):
     - Exports: `RecurrenceEngine`, `StatisticsEngine`, `calculate_next_due_date_from_chore_info` ✅
     - File: `custom_components/kidschores/engines/__init__.py`
  4. - [x] Run full test suite: `pytest tests/ -v --tb=line`
     - 902 tests passed ✅
     - No regressions from cleanup helper migration
- **Key issues resolved**
  - ✅ `data_builders.py` naming verified (no source code references to old name)
  - ✅ Cleanup helpers are now stateless, reusable functions
  - ✅ Type compatibility: Used `cast()` for TypedDict → dict[str, Any] conversions
  - ✅ Coordinator reduced by ~100 lines (delegation pattern)

---

### Phase 2 – Notification Manager ("The Voice")

- **Goal**: Extract all notification logic into a dedicated manager. This is the lowest-risk extraction since notifications are side effects with no return values.
- **Steps / detailed work items**
  1. - [ ] Create `managers/notification_manager.py`:
     - Consolidate: `notification_helper.py` functions → manager methods
     - Consolidate: `coordinator._notify_kid()`, `_notify_parents()`, `_notify_*_translated()`
     - Add: `send_kc_notification()` as primary dispatch method
  2. - [ ] Define NotificationManager interface:
     ```python
     class NotificationManager:
         def __init__(self, hass: HomeAssistant, coordinator: Coordinator):
             ...
         async def send_kid_notification(self, kid_id, title_key, message_key, ...): ...
         async def send_parent_notification(self, kid_id, title_key, message_key, ...): ...
         async def clear_notification(self, tag: str): ...
         def build_chore_actions(self, kid_id, chore_id): ...
         def build_reward_actions(self, kid_id, reward_id, notif_id): ...
     ```
  3. - [ ] Move localization loading from coordinator:
     - `_convert_notification_key()` → manager method
     - `_format_notification_text()` → manager method
     - `_translate_action_buttons()` → manager method
  4. - [ ] Update coordinator to use NotificationManager:
     - Replace direct `_notify_*` calls with `self.notification_manager.send_*`
     - Inject manager in coordinator `__init__`
  5. - [ ] Retain `notification_helper.py` as thin wrapper for backward compat:
     - `async_send_notification()` delegates to manager
     - `ParsedAction` dataclass stays (used by action handler)
  6. - [ ] Update imports in `coordinator.py`, `coordinator_chore_operations.py`
  7. - [ ] Tests:
     - Move notification tests to `tests/test_notification_manager.py`
     - Verify all notification scenarios still work
- **Key issues**
  - Must handle both translated and non-translated notification paths
  - Action button building is tightly coupled with notification dispatch

---

### Phase 3 – Economy Stack ("The Bank")

- **Goal**: Centralize all point operations with transaction history and validation.
- **Steps / detailed work items**

  **3A. EconomyEngine (pure logic)**
  1. - [ ] Create `engines/economy_engine.py`:

     ```python
     @dataclass
     class LedgerEntry:
         timestamp: datetime
         amount: float
         balance_after: float
         source: str  # "chore_approval", "reward_redemption", "penalty", "bonus"
         reference_id: str | None  # chore_id, reward_id, etc.

     class EconomyEngine:
         @staticmethod
         def create_transaction(current_balance: float, delta: float, source: str, ref_id: str | None = None) -> LedgerEntry:
             """Create immutable transaction record."""

         @staticmethod
         def validate_sufficient_funds(balance: float, cost: float) -> bool:
             """NSF check - returns False if insufficient."""

         @staticmethod
         def calculate_with_multiplier(base_points: float, multiplier: float) -> float:
             """Apply badge multiplier to points."""

         @staticmethod
         def round_points(value: float, precision: int = 2) -> float:
             """Consistent point rounding."""
     ```

  2. - [ ] Add `LedgerEntry` TypedDict to `type_defs.py`
  3. - [ ] Unit tests for engine (pure Python, no HA mocking needed)

  **3B. EconomyManager (stateful workflow)** 4. - [ ] Create `managers/economy_manager.py`:

  ```python
  class EconomyManager:
      def __init__(self, hass, coordinator, notification_manager):
          ...

      def deposit(self, kid_id: str, amount: float, *, source: str, reference_id: str | None = None) -> float:
          """Add points, emit EVENT_POINTS_CHANGE."""

      def withdraw(self, kid_id: str, amount: float, *, source: str, reference_id: str | None = None) -> float:
          """Deduct points with NSF check, emit EVENT_POINTS_CHANGE."""

      def get_balance(self, kid_id: str) -> float:
          """Current point balance."""

      def get_ledger(self, kid_id: str, limit: int = 50) -> list[LedgerEntry]:
          """Recent transaction history."""
  ```

  5. - [ ] Refactor `coordinator.update_kid_points()`:
     - Current location: `coordinator.py` lines 1431-1608
     - Keep as thin wrapper calling `economy_manager.deposit/withdraw`
     - Gamification checks move to event listener (Phase 5)
  6. - [ ] Update storage schema for ledger (optional, can be in-memory first):
     - If persisted: increment `SCHEMA_VERSION` to 43
     - Add migration: `_migrate_to_v43()` to initialize empty ledgers
  7. - [ ] Tests: `tests/test_economy_manager.py`, `tests/test_economy_engine.py`

- **Key issues**
  - `update_kid_points()` currently triggers badge/achievement/challenge checks inline
  - Must preserve existing behavior while enabling event-based evaluation

---

### Phase 4 – Chore Stack ("The Job")

- **Goal**: Refactor the existing ChoreOperations mixin into Engine + Manager pattern.
- **Steps / detailed work items**

  **4A. ChoreEngine (pure logic)**
  1. - [ ] Create `engines/chore_engine.py`:

     ```python
     class ChoreEngine:
         # State machine transitions
         VALID_TRANSITIONS = {
             PENDING: [CLAIMED, OVERDUE, SKIPPED],
             CLAIMED: [APPROVED, APPROVED_IN_PART, DISAPPROVED, PENDING],
             APPROVED: [PENDING],  # Reset for recurrence
             ...
         }

         @staticmethod
         def can_transition(current_state: str, target_state: str) -> bool:
             """Validate state transition is allowed."""

         @staticmethod
         def calculate_points(chore_data: ChoreData, kid_data: KidData) -> float:
             """Calculate points including any multipliers."""

         @staticmethod
         def is_shared_chore(chore_data: ChoreData) -> bool:
             """Check if chore is shared vs independent."""

         @staticmethod
         def get_next_due_date(chore_data: ChoreData, from_date: date | None = None) -> date | None:
             """Wrapper around RecurrenceEngine for chore context."""
     ```

  2. - [ ] Extract from `coordinator_chore_operations.py`:
     - State transition validation (scattered across methods)
     - Point calculation logic
     - Shared chore determination
  3. - [ ] Unit tests for ChoreEngine (pure Python)

  **4B. ChoreManager (stateful workflow)** 4. - [ ] Create `managers/chore_manager.py`:

  ```python
  class ChoreManager:
      def __init__(self, hass, coordinator, economy_manager, notification_manager):
          ...

      async def claim(self, kid_id: str, chore_id: str, user_name: str) -> None:
          """Kid claims chore - validates, transitions state, notifies parents."""

      async def approve(self, kid_id: str, chore_id: str, parent_name: str) -> None:
          """Parent approves - awards points, emits EVENT_CHORE_APPROVED."""

      async def disapprove(self, kid_id: str, chore_id: str, parent_name: str, reason: str | None) -> None:
          """Parent disapproves - notifies kid, resets state."""

      async def complete_for_kid(self, kid_id: str, chore_id: str, parent_name: str) -> None:
          """Parent completes chore on behalf of kid."""

      async def skip(self, kid_id: str, chore_id: str, reason: str | None) -> None:
          """Skip chore for this cycle."""

      async def process_recurring(self) -> None:
          """Called by coordinator on schedule to advance recurring chores."""

      async def process_overdue(self) -> None:
          """Called by coordinator to detect and handle overdue chores."""
  ```

  5. - [ ] Refactor `coordinator_chore_operations.py`:
     - Keep ChoreOperations mixin as thin wrapper during transition
     - Gradually move method bodies to ChoreManager
     - Final state: ChoreOperations delegates all to ChoreManager
  6. - [ ] Update coordinator to inject ChoreManager
  7. - [ ] Tests: `tests/test_chore_manager.py`, `tests/test_chore_engine.py`

- **Key issues**
  - ChoreOperations (3,971 lines) is the largest extraction
  - Must handle approval locks (`_get_approval_lock`) for race conditions
  - Shared chore logic is complex (multi-kid approval tracking)

---

### Phase 5 – Gamification Stack ("The Game")

- **Goal**: Unify badges, achievements, and challenges into a single evaluation framework.
- **Steps / detailed work items**

  **5A. GamificationEngine (pure logic)**
  1. - [ ] Create `engines/gamification_engine.py`:

     ```python
     @dataclass
     class Criterion:
         """Generic goal definition."""
         type: str  # "points", "chore_count", "streak", "daily_completion"
         target: int | float
         scope: str | None  # specific chore_id or None for all
         period: str | None  # "daily", "weekly", etc.

     @dataclass
     class EvaluationResult:
         """Result of evaluating a criterion."""
         criterion_id: str
         met: bool
         current_value: int | float
         target_value: int | float
         progress_pct: float

     class GamificationEngine:
         @staticmethod
         def evaluate_criterion(kid_data: KidData, criterion: Criterion) -> EvaluationResult:
             """Pure evaluation - does not modify state."""

         @staticmethod
         def calculate_badge_progress(kid_data: KidData, badge_data: BadgeData) -> dict:
             """Badge-specific progress calculation."""

         @staticmethod
         def calculate_achievement_progress(kid_data: KidData, achievement_data: dict) -> dict:
             """Achievement-specific progress."""

         @staticmethod
         def calculate_challenge_progress(kid_data: KidData, challenge_data: dict) -> dict:
             """Challenge-specific progress with deadline awareness."""
     ```

  2. - [ ] Extract from `coordinator.py`:
     - `_check_badges_for_kid()` (lines 2250-2535) → engine evaluate
     - `_handle_badge_target_*()` methods → engine helpers
     - `_check_achievements_for_kid()` (lines 4958-5060) → engine evaluate
     - `_check_challenges_for_kid()` (lines 5157-5230) → engine evaluate
  3. - [ ] Unit tests for engine

  **5B. GamificationManager (stateful workflow)** 4. - [ ] Create `managers/gamification_manager.py`:

  ```python
  class GamificationManager:
      def __init__(self, hass, coordinator, economy_manager, notification_manager):
          ...
          # Subscribe to events
          async_dispatcher_connect(hass, EVENT_POINTS_CHANGE, self._on_points_change)
          async_dispatcher_connect(hass, EVENT_CHORE_APPROVED, self._on_chore_approved)

      async def _on_points_change(self, kid_id: str, new_balance: float) -> None:
          """React to point changes - check for newly unlocked badges."""

      async def _on_chore_approved(self, kid_id: str, chore_id: str) -> None:
          """React to chore completion - update streaks, check achievements."""

      async def evaluate_all(self, kid_id: str) -> list[str]:
          """Full evaluation - returns list of newly earned badge/achievement IDs."""

      async def award_badge(self, kid_id: str, badge_id: str) -> None:
          """Award badge - update kid data, process badge rewards, notify."""

      async def process_maintenance(self) -> None:
          """Daily/weekly badge maintenance - handle decay, periodic resets."""
  ```

  5. - [ ] Refactor coordinator badge/achievement/challenge methods:
     - `_award_badge()` → `gamification_manager.award_badge()`
     - `_award_achievement()` → manager method
     - `_award_challenge()` → manager method
     - `_manage_badge_maintenance()` → `gamification_manager.process_maintenance()`
  6. - [ ] Tests: `tests/test_gamification_manager.py`, `tests/test_gamification_engine.py`

- **Key issues**
  - Badge logic is highly complex (cumulative vs periodic, maintenance)
  - Must preserve existing badge maintenance behavior exactly
  - Challenge deadlines add temporal complexity

---

### Phase 6 – Coordinator Slim Down

- **Goal**: Reduce coordinator to pure routing and storage, delegating all business logic to managers.
- **Steps / detailed work items**
  1. - [ ] Audit remaining coordinator methods:
     - Identify any methods not yet delegated to managers
     - Document which manager should own each
  2. - [ ] Move CRUD operations pattern:
     - `delete_*_entity()` methods stay (use `data_builders` + persist)
     - Entity creation stays (routing to `data_builders`)
     - Keep property accessors (`kids_data`, `chores_data`, etc.)
  3. - [ ] Remove inheritance from `ChoreOperations`:

     ```python
     # Before
     class KidsChoresDataCoordinator(ChoreOperations, DataUpdateCoordinator):

     # After
     class KidsChoresDataCoordinator(DataUpdateCoordinator):
         def __init__(self, ...):
             self.chore_manager = ChoreManager(...)
             self.economy_manager = EconomyManager(...)
             self.gamification_manager = GamificationManager(...)
             self.notification_manager = NotificationManager(...)
     ```

  4. - [ ] Update service handlers in `services.py`:
     - Services call `coordinator.chore_manager.claim()` instead of `coordinator.claim_chore()`
     - Or keep coordinator as facade: `coordinator.claim_chore()` → `self.chore_manager.claim()`
  5. - [ ] Delete `coordinator_chore_operations.py` after migration complete
  6. - [ ] Target line count: coordinator.py < 1000 lines
  7. - [ ] Full regression test suite

- **Key issues**
  - Backward compatibility for any external integrations calling coordinator methods
  - Careful ordering of manager initialization (dependency injection)

---

### Phase 7 – Testing & Polish

- **Goal**: Ensure 95%+ coverage, update documentation, prepare release.
- **Steps / detailed work items**
  1. - [ ] Coverage audit per module:
     - `engines/*.py` – 95%+ (mostly pure Python)
     - `managers/*.py` – 95%+ (some HA mocking needed)
     - `coordinator.py` – 95%+ (integration level)
  2. - [ ] Update `docs/ARCHITECTURE.md`:
     - Add layered architecture diagram
     - Document manager responsibilities
     - Update data flow examples
  3. - [ ] Update `docs/DEVELOPMENT_STANDARDS.md`:
     - Add section on engine vs manager patterns
     - Document event bus usage
  4. - [ ] Create migration guide for contributors:
     - How to add new features in layered architecture
     - When to create engine vs manager
  5. - [ ] Performance benchmarking:
     - Compare startup time before/after
     - Compare service call latency
  6. - [ ] Update dashboard helper if needed:
     - Ensure `sensor.kc_<kid>_ui_dashboard_helper` still populates correctly

- **Key issues**
  - Test refactoring may be significant if tests were tightly coupled to coordinator internals

---

## Testing & validation

- **Unit tests**: Each engine should have pure Python unit tests (no HA fixtures needed)
- **Integration tests**: Managers tested with mock coordinator/hass
- **End-to-end tests**: Full service call → state change → notification flow
- **Commands to run**:

  ```bash
  # Quick lint
  ./utils/quick_lint.sh --fix

  # Type checking
  mypy custom_components/kidschores/

  # Full test suite with coverage
  pytest tests/ -v --cov=custom_components.kidschores --cov-report=term-missing

  # Specific manager tests
  pytest tests/test_notification_manager.py tests/test_economy_manager.py -v
  ```

---

## Notes & follow-up

### What We Are NOT Doing

- **No ConfigurationManager**: CRUD operations remain in coordinator, using `data_builders.py` and `kc_helpers.py`
- **No complex DI framework**: Managers communicate via method calls (downstream) or Events (upstream)
- **No breaking service API**: External service names (`kidschores.approve_chore`) remain unchanged

### File Size Targets

| File                               | Current | Target |
| ---------------------------------- | ------- | ------ |
| `coordinator.py`                   | 6,138   | <1,000 |
| `coordinator_chore_operations.py`  | 3,971   | DELETE |
| `managers/chore_manager.py`        | N/A     | ~1,500 |
| `managers/economy_manager.py`      | N/A     | ~500   |
| `managers/gamification_manager.py` | N/A     | ~1,500 |
| `managers/notification_manager.py` | N/A     | ~800   |
| `engines/chore_engine.py`          | N/A     | ~400   |
| `engines/economy_engine.py`        | N/A     | ~200   |
| `engines/gamification_engine.py`   | N/A     | ~600   |

### Implementation Order Rationale

1. **Notifications first**: Side-effect only, no return values, lowest risk
2. **Economy second**: Central to all operations, enables event-based gamification
3. **Chores third**: Largest extraction, benefits from economy manager being ready
4. **Gamification last**: Becomes event listener rather than inline call

### Dependencies Between Managers

```
NotificationManager ← (used by all managers)
       ↑
EconomyManager ← (emits events, used by ChoreManager)
       ↑
ChoreManager ← (uses EconomyManager for points)
       ↑
GamificationManager ← (listens to events from Economy/Chore)
```

---

## Phase 0 Pre-Handoff Checklist

**Purpose**: Ensure builder agent has all context needed for successful Phase 0 implementation.

### Documentation Review

- [x] Main plan (`LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md`) reviewed
  - All architectural decisions documented
  - Phase 0 steps clearly defined
  - Dependencies and risks identified
- [x] Implementation guide (`LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md`) complete
  - 56 signal suffix constants defined with past-tense naming
  - 15 event payload TypedDicts specified
  - Event Architecture Standards documented
  - 7 implementation steps with exact code blocks
  - Validation commands for each step
  - **Critical**: Placement instructions specify exact line numbers and context
- [x] Event pattern guide (`LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md`) reviewed
  - Home Assistant Dispatcher pattern explained
  - BaseManager abstract class design documented
  - Multi-instance isolation strategy defined

### File Structure Verification

- [x] Target directories confirmed:
  - `custom_components/kidschores/managers/` exists (empty, ready for files)
  - `custom_components/kidschores/engines/` exists (has `schedule.py`, `statistics.py` as examples)
- [x] Target files identified for modification:
  - `custom_components/kidschores/const.py` (~3587 lines, organized sections)
  - `custom_components/kidschores/kc_helpers.py` (~1870 lines, organized sections)
  - `custom_components/kidschores/type_defs.py` (existing TypedDicts, will add more)
- [x] No existing event infrastructure to conflict with:
  - `grep "SIGNAL_SUFFIX_"` returns 0 matches ✅
  - `grep "async_dispatcher"` returns 0 matches ✅

### Constant Placement Instructions

**Critical Success Factor**: Avoid adding constants in the middle of existing groupings.

- [x] **`const.py` placement verified**:
  - **Location**: Line 60 (after Storage section, before Float Precision section)
  - **Context lines documented**: Clear before/after markers in implementation guide
  - **Section header**: New "Event Infrastructure (Phase 0)" section created
  - **Why this location**: Groups all integration infrastructure together (Storage, Events, Schema)

- [x] **`kc_helpers.py` placement verified**:
  - **Location**: Line 210 (after Entity Registry Utilities, before Get Coordinator)
  - **Context lines documented**: Clear section boundary markers
  - **Section header**: New "Event Signal Helpers" section
  - **Why this location**: Foundational infrastructure, close to top for easy reference

### Test Strategy

- [x] Test file structure defined:
  - `tests/test_event_infrastructure.py` (5 tests specified)
  - Tests cover: `get_event_signal()` formatting, multi-instance isolation, BaseManager emit/listen
  - Uses AsyncMock and Home Assistant test fixtures
- [x] Validation commands documented:
  - Lint: `./utils/quick_lint.sh --fix`
  - Type check: `mypy custom_components/kidschores/`
  - Unit tests: `pytest tests/test_event_infrastructure.py -v`
  - Full regression: `pytest tests/ -v --tb=line`

### Implementation Readiness

- [x] All code blocks ready in implementation guide:
  - Step 1: 56 constants with groupings and comments
  - Step 2: `get_event_signal()` function with full docstring
  - Step 3: `BaseManager` abstract class (complete implementation)
  - Step 4: `managers/__init__.py` exports
  - Step 5: 15 TypedDict definitions with field descriptions
  - Step 6: Test file with 5 test cases
  - Step 7: Validation command sequence
- [x] No blockers identified:
  - No feature dependencies
  - No schema changes required
  - No migration logic needed
  - No external library additions

### Builder Agent Handoff Package

**Files to Reference**:

1. **Main Plan**: `docs/in-process/LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md`
2. **Implementation Guide**: `docs/in-process/LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md` ⭐ (PRIMARY)
3. **Event Pattern**: `docs/in-process/LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md`
4. **Development Standards**: `docs/DEVELOPMENT_STANDARDS.md` (constants, logging, types)
5. **Architecture Reference**: `docs/ARCHITECTURE.md` (data model context)

**Key Instruction for Builder**:

> Follow `LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md` steps 1-7 sequentially. Pay special attention to placement instructions in Steps 1-2 to avoid disrupting existing constant groupings. Use exact context lines provided to locate insertion points. Validate after each step.

**Estimated Effort**: 2-3 focused sessions (~4-6 hours total)

**Success Criteria**:

- All 56 constants added in correct location (line 60 of `const.py`)
- `get_event_signal()` helper added in correct location (line 210 of `kc_helpers.py`)
- `BaseManager` abstract class created with emit/listen methods
- 15 event payload TypedDicts added to `type_defs.py`
- Test file created with 5 passing tests
- All validation commands pass (lint 9.5+/10, mypy 0 errors, pytest 100% pass)

---

## Implementation Notes (Tracking)

### Dependencies Between Managers

```
NotificationManager ← (used by all managers)
       ↑
EconomyManager ← (emits events, used by ChoreManager)
       ↑
ChoreManager ← (uses EconomyManager for points)
       ↑
GamificationManager ← (listens to events from Economy/Chore)
```

---

> **Template usage notice:** This plan follows the structure from `docs/PLAN_TEMPLATE.md`. Move to `docs/completed/` when all phases complete.
