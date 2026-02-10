# Initiative Plan: Chore Logic v0.5.0 — Due Window Restrictions & Advanced Rotation

## Initiative snapshot

- **Name / Code**: Chore Logic v0.5.0 — Due Window Claim Restrictions + Advanced Rotation
- **Target release / milestone**: v0.5.0 (Schema v44 — extended in-place, no bump)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Not started — all 16 decisions resolved (2026-02-11); blueprint created

## Summary & immediate steps

| Phase / Step                      | Description                                                      | % complete | Quick notes                            |
| --------------------------------- | ---------------------------------------------------------------- | ---------- | -------------------------------------- |
| Phase 1 – Foundation              | Constants, types, validation rules (no schema migration)         | 0%         | No external deps; pure data model work |
| Phase 2 – Engine & State Machine  | 8-tier FSM, claim restrictions, rotation resolution              | 0%         | Core logic; depends on Phase 1         |
| Phase 3 – Manager Orchestration   | Rotation advancement, missed lock, scanner updates, new services | 0%         | Depends on Phase 2 engine              |
| Phase 4 – UX & Dashboard Contract | UI Manager attributes, flow helpers, notification wiring         | 0%         | Depends on Phase 3 signals             |
| Phase 5 – Testing & Validation    | Full test coverage for all new paths                             | 0%         | Service-based + engine unit tests      |

1. **Key objective** – Introduce two new chore management capabilities: (a) **Due Window Claim Restrictions** that prevent kids from claiming chores before a configurable window opens, and (b) **Advanced Rotation Logic** that extends shared_first chores into a disciplined turn-based system with three sub-types (simple, steal, smart). Both features extend the existing FSM with three new calculated states (`waiting`, `not_my_turn`, `missed` as a locked terminal state).

2. **Summary of recent work** – Architecture specification drafted. Codebase research completed. All 16 decisions resolved (2026-02-11):
   - Schema stays at **v44** — extend existing `_migrate_to_schema_44()` to backfill new fields (D-13)
   - **Criteria Overload pattern** (D-12): Rotation types are new `completion_criteria` values (`rotation_simple`, `rotation_steal`, `rotation_smart`). Logic Adapter methods (`is_single_claimer_mode()`, `is_rotation_mode()`) prevent gremlin code across ~60 check sites
   - **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` L784-788 immutability guard is incorrect and must be removed. Data transition logic handles field cleanup on criteria change.
   - Existing `clear_and_mark_missed` and new `mark_missed_and_lock` are **two distinct strategies** (6th overdue type)
   - `SIGNAL_SUFFIX_CHORE_MISSED` and `_record_missed_chore()` already exist — will extend payload
   - All rotation types require **≥ 2 assigned kids** (D-14)
   - `rotation_cycle_override` cleared by **next approval** (D-15) — approval reset handles the override
   - `can_claim` is a **calculated boolean attribute on the kid chore status sensor** (D-16) — engine → manager → sensor pipeline
   - No rotation code exists yet (greenfield)

3. **Next steps (short term)**
   - All decisions resolved — ready to begin Phase 1 implementation
   - Begin Phase 1: constants, types, Logic Adapters, migration extension
   - Blueprint document created for implementer reference: [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md)

4. **Risks / blockers**
   - Risk: ~60 criteria check sites need audit for Logic Adapter adoption. `chore_manager.py` has 25 sites — highest refactoring density
   - Risk: Smart rotation depends on StatsEngine/StatsManager query that doesn't yet exist
   - Risk: `is_shared_chore()` in engine has **zero production callers** (dead code). All callers inline their own checks — this validates the Logic Adapter approach but means broader refactoring

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Data model, storage, versioning
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Naming, patterns, signal rules
   - [QUALITY_REFERENCE.md](../QUALITY_REFERENCE.md) — Platinum quality requirements
   - [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md) — Test patterns
   - [migration_pre_v50.py](../../custom_components/kidschores/migration_pre_v50.py) — v44 migration section (if migration needed)
   - Supporting doc: [CHORE_LOGIC_V050_SUP_STATE_MATRIX.md](CHORE_LOGIC_V050_SUP_STATE_MATRIX.md) — Full FSM state matrix
   - Supporting doc: [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md) — Detailed implementation blueprint with code samples

6. **Decisions & completion check**

   ### Resolved Decisions (2026-02-11 — complete)

   | ID       | Question                                                       | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Impact                                                                                                                                                                                                                                                                                                                        |
   | -------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **D-01** | Schema version                                                 | ✅ **v44** (no bump).                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Migration extended in-place (D-13).                                                                                                                                                                                                                                                                                           |
   | **D-02** | Existing `clear_and_mark_missed` vs new `mark_missed_and_lock` | ✅ **Two distinct strategies**. Existing = "signal miss → reset to pending at boundary." New = "signal miss → lock in `missed` state → midnight resets."                                                                                                                                                                                                                                                                                                                                   | Add 6th overdue type `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK`. Existing unchanged.                                                                                                                                                                                                                                          |
   | **D-03** | `mark_missed_and_lock` reset compatibility                     | ✅ **AT*MIDNIGHT*\* only**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Validation rule: reject `upon_completion`, `at_due_date_*`, `manual` reset types.                                                                                                                                                                                                                                             |
   | **D-04** | `claim_restriction_enabled` scope                              | ✅ **Per-chore boolean**. Existing `can_claim` calculated attribute will be used.                                                                                                                                                                                                                                                                                                                                                                                                          | Per-chore field in storage + flow. `can_claim` is a calculated boolean attribute on the kid chore status sensor.                                                                                                                                                                                                               |
   | **D-05** | Rotation as completion criteria                                | ✅ **New `completion_criteria` values** (`rotation_simple`, `rotation_steal`, `rotation_smart`).                                                                                                                                                                                                                                                                                                                                                                                           | Three new constants. Engine uses Logic Adapter pattern (D-12) to treat rotation as shared_first-like.                                                                                                                                                                                                                         |
   | **D-06** | `rotation_steal` without due date                              | ✅ **Require due date** in validation.                                                                                                                                                                                                                                                                                                                                                                                                                                                     | New validation rule in `data_builders.py`.                                                                                                                                                                                                                                                                                    |
   | **D-07** | CHORE_MISSED signal                                            | ✅ **Extend existing** payload with optional `due_date` and `reason` fields.                                                                                                                                                                                                                                                                                                                                                                                                               | Backward compatible.                                                                                                                                                                                                                                                                                                          |
   | **D-08** | Smart rotation stats query                                     | ✅ **StatsEngine or StatsManager** provides the query API.                                                                                                                                                                                                                                                                                                                                                                                                                                 | New public method for per-chore approved counts across kids.                                                                                                                                                                                                                                                                  |
   | **D-09** | "The Nudge" notification                                       | ✅ **Same as existing `notify_on_due_window`**. No new notification type.                                                                                                                                                                                                                                                                                                                                                                                                                  | No work needed.                                                                                                                                                                                                                                                                                                               |
   | **D-10** | Migration home                                                 | ✅ **`migration_pre_v50.py`** v44 section.                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Extend existing `_migrate_to_schema_44()` to backfill new fields (D-13).                                                                                                                                                                                                                                                      |
   | **D-11** | `completion_criteria` mutability                               | ✅ **Mutable**. Users CAN change `completion_criteria` when editing a chore via options flow. The `services.py` immutability guard (L784-788) is incorrect and must be **removed**. When criteria changes, **data transition logic** handles cleanup (e.g., clear rotation fields when switching away from rotation; initialize `rotation_current_kid_id` when switching TO rotation).                                                                                                     | Remove immutability guard from `services.py`. Add `_handle_criteria_transition()` method to ChoreManager. Add `completion_criteria` to `UPDATE_CHORE_SCHEMA`.                                                                                                                                                                 |
   | **D-12** | Data model: rotation as criteria value vs. separate field      | ✅ **Option A — Criteria Overload**. Rotation types are new `completion_criteria` values: `rotation_simple`, `rotation_steal`, `rotation_smart`. UI is one-click — no separate `rotation_type` field. **Logic Adapter** pattern in `ChoreEngine` prevents "gremlin code": `is_single_claimer_mode()` → True for `shared_first` + all rotation types; `is_rotation_mode()` → True for `rotation_*` only. All existing `shared_first` checks use `is_single_claimer_mode()` adapter instead. | ~60 existing criteria check sites across 10 production files. The Logic Adapter pattern makes most transparent — existing three-way branches (INDEPENDENT / SHARED_FIRST / SHARED) become (INDEPENDENT / single_claimer / SHARED) and rotation chores automatically get correct behavior. See "Logic Adapter audit" in Notes. |
   | **D-13** | Existing chore field backfill strategy                         | ✅ **Extend v44 migration** in `migration_pre_v50.py` to backfill new fields on existing chores.                                                                                                                                                                                                                                                                                                                                                                                           | Add backfill step to `_migrate_to_schema_44()`: set `claim_restriction_enabled=False`, `rotation_current_kid_id=None`, `rotation_cycle_override=False` on all existing chores.                                                                                                                                                |
   | **D-14** | Rotation minimum kids                                          | ✅ **All rotation types require ≥ 2 assigned kids**. Turn-taking with 1 kid is meaningless for any rotation variant.                                                                                                                                                                                                                                                                                                                                                                       | Validation rule V-03 applies to `rotation_simple`, `rotation_steal`, AND `rotation_smart` uniformly. Error message in `data_builders.py`.                                                                                                                                                                                     |
   | **D-15** | `rotation_cycle_override` reset trigger                        | ✅ **Approval reset handles the override**. Next approval of any kid on the chore clears `rotation_cycle_override = False`. The override is for "let anyone claim THIS cycle's instance." Once approved, normal rotation resumes.                                                                                                                                                                                                                                                           | Handled in `_advance_rotation()` — which already resets `rotation_cycle_override = False` after approval. No additional timer/scanner logic needed.                                                                                                                                                                           |
   | **D-16** | Where `can_claim` attribute lives                              | ✅ **Calculated boolean on the kid chore status sensor** (`KidChoreStatusSensor.extra_state_attributes`). Pipeline: `ChoreEngine.can_claim_chore()` → `ChoreManager.can_claim_chore()` → sensor attribute. Dashboard helper does NOT include it — documented to fetch via `state_attr(chore.eid, 'can_claim')`. `ATTR_CAN_CLAIM` constant already exists.                                                                                                                                  | New blocking conditions (waiting, not_my_turn, missed) integrate into existing `ChoreEngine.can_claim_chore()`. No new sensor or attribute needed — extend existing logic.                                                                                                                                                     |

   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps.
- **Detailed tracking**: Use the phase-specific sections below for granular progress.

---

## Detailed phase tracking

### Phase 1 – Foundation (Constants, Types, Validation, Migration)

- **Goal**: Establish the data model, constants, type definitions, Logic Adapter static methods, validation rules, and v44 migration extension. No behavioral logic — purely structural.

- **Steps / detailed work items**
  1. **Add new constants to `const.py`**
     - File: `custom_components/kidschores/const.py`
     - **6th overdue handling constant** (D-02):
       - `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK = "at_due_date_mark_missed_and_lock"`
       - Add to `OVERDUE_HANDLING_OPTIONS` list
     - **New completion criteria constants** (D-05 + D-12 = Option A):
       - `COMPLETION_CRITERIA_ROTATION_SIMPLE = "rotation_simple"`
       - `COMPLETION_CRITERIA_ROTATION_STEAL = "rotation_steal"`
       - `COMPLETION_CRITERIA_ROTATION_SMART = "rotation_smart"`
       - Add all three to `COMPLETION_CRITERIA_OPTIONS` list
     - **New chore data storage keys**:
       - `DATA_CHORE_CLAIM_RESTRICTION_ENABLED = "claim_restriction_enabled"`
       - `DATA_CHORE_ROTATION_CURRENT_KID_ID = "rotation_current_kid_id"`
       - `DATA_CHORE_ROTATION_CYCLE_OVERRIDE = "rotation_cycle_override"`
     - **New chore states** (display-only, calculated at runtime):
       - `CHORE_STATE_WAITING = "waiting"`
       - `CHORE_STATE_NOT_MY_TURN = "not_my_turn"`
       - `CHORE_STATE_MISSED = "missed"` (verify if already present as constant)
     - **New signal suffix**:
       - `SIGNAL_SUFFIX_ROTATION_ADVANCED = "rotation_advanced"`
     - **New service constants**:
       - `SERVICE_SET_ROTATION_TURN = "set_rotation_turn"`
       - `SERVICE_RESET_ROTATION = "reset_rotation"`
       - `SERVICE_OPEN_ROTATION_CYCLE = "open_rotation_cycle"`
       - `SERVICE_FIELD_ROTATION_KID_ID = "rotation_kid_id"`
     - **Config flow field constants**:
       - `CFOF_CHORES_INPUT_CLAIM_RESTRICTION = "claim_restriction_enabled"`
     - **Dashboard helper ATTR constants**:
       - `ATTR_CHORE_LOCK_REASON = "lock_reason"`
       - `ATTR_CHORE_TURN_KID_NAME = "turn_kid_name"`
       - `ATTR_CHORE_AVAILABLE_AT = "available_at"`
       - `ATTR_CAN_CLAIM` already exists in `const.py` (confirmed D-16). No new constant needed — extend existing `can_claim_chore()` logic.
     - **Translation keys**:
       - `TRANS_KEY_CHORE_STATE_WAITING`, `TRANS_KEY_CHORE_STATE_NOT_MY_TURN`, `TRANS_KEY_CHORE_STATE_MISSED`
       - `TRANS_KEY_ROTATION_SIMPLE`, `TRANS_KEY_ROTATION_STEAL`, `TRANS_KEY_ROTATION_SMART`
       - `TRANS_KEY_NOTIF_TITLE_CHORE_MISSED`, `TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED` (verify if already present)
       - Service description translation keys for 3 new services
     - Validation: Run `./utils/quick_lint.sh --fix` after constants added

  2. **Update `type_defs.py` — ChoreData TypedDict**
     - File: `custom_components/kidschores/type_defs.py`
     - Add to `ChoreData` as `NotRequired` fields:
       - `claim_restriction_enabled: NotRequired[bool]`
       - `rotation_current_kid_id: NotRequired[str | None]` — UUID of kid whose turn it is
       - `rotation_cycle_override: NotRequired[bool]`
     - Validate: `mypy custom_components/kidschores/type_defs.py`

  3. **Update `data_builders.py` — Build & Validate**
     - File: `custom_components/kidschores/data_builders.py`
     - In `build_chore()`: Add default values for new fields:
       - `claim_restriction_enabled` → `False`
       - `rotation_current_kid_id` → `None`
       - `rotation_cycle_override` → `False`
       - **Rotation genesis**: If `completion_criteria` starts with `"rotation_"`, auto-set `rotation_current_kid_id = assigned_kids[0]`
     - In `validate_chore_data()`: Add new validation rules:
       - **V-01**: If `overdue_handling == mark_missed_and_lock`, then `approval_reset` must be `AT_MIDNIGHT_*` only (D-03). Reject `upon_completion`, `at_due_date_*`, `manual`.
       - **V-02**: If `claim_restriction_enabled == True`, then `due_window_offset` must parse to duration > 0.
       - **V-03**: All rotation types require `assigned_kids` with `len >= 2` (D-14 resolved: all types).
       - **V-04**: `rotation_steal` requires a due date (D-06).
     - Validate: `mypy custom_components/kidschores/data_builders.py`

  4. **Extend v44 migration to backfill new fields** (D-13)
     - File: `custom_components/kidschores/migration_pre_v50.py`
     - In `_migrate_to_schema_44()`: Add new backfill step after existing tweaks:
       - Iterate all chores in `self.coordinator._data[DATA_CHORES]`
       - For each chore, use `.setdefault()` to add:
         - `claim_restriction_enabled` → `False`
         - `rotation_current_kid_id` → `None`
         - `rotation_cycle_override` → `False`
       - Log count of chores backfilled
     - Note: Existing chores will all have non-rotation `completion_criteria` values — no rotation genesis needed during migration

  5. **Update translations `en.json`**
     - File: `custom_components/kidschores/translations/en.json`
     - Add translations for: new states, rotation criteria labels, 6th overdue type label, validation error messages, 3 new service names/descriptions/fields
     - Run `./utils/quick_lint.sh --fix`

- **Key issues**
  - The 3 new `completion_criteria` values must be added atomically to `COMPLETION_CRITERIA_OPTIONS`, `_COMPLETION_CRITERIA_VALUES` in services.py, and flow_helpers selectors
  - The existing 5 overdue types appear in `flow_helpers.py` selector options and `OVERDUE_HANDLING_OPTIONS` — the 6th type must be added alongside
  - D-14 resolved: All rotation types require ≥ 2 kids. V-03 validation rule applies uniformly.

---

### Phase 2 – Engine & State Machine (+ Logic Adapters)

- **Goal**: Implement the Logic Adapter static methods, the 8-tier priority state resolution, claim restriction logic, rotation-aware can_claim checks, and criteria transition helpers in `chore_engine.py`. Pure computation — no storage writes, no HA imports.

- **Steps / detailed work items**
  1. **Implement Logic Adapter static methods** (D-12 — the "gremlin prevention" pattern)
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - Two new static methods following existing `is_shared_chore()` signature pattern:

       ```
       is_single_claimer_mode(chore_data) -> bool
         Returns True if criteria in (shared_first, rotation_simple, rotation_steal, rotation_smart)
         Replaces all existing "== SHARED_FIRST" checks for claim-blocking, reset-all-kids, etc.

       is_rotation_mode(chore_data) -> bool
         Returns True if criteria.startswith("rotation_")
         Used for rotation-specific logic (turn advancement, override, steal)
       ```

     - **Audit note**: ~60 existing criteria check sites across 10 production files currently inline their own checks. The existing `is_shared_chore()` has **zero production callers** (dead code — validates the adapter approach). Key refactoring targets:
       - `chore_manager.py` — 25 sites (highest density)
       - `chore_engine.py` — 10 sites
       - `options_flow.py` — 6 sites
       - `flow_helpers.py` — 5 sites
       - `sensor.py` — 4 sites
     - **Implementation strategy**: Add adapters first. Then update existing checks incrementally — each caller that currently checks `== SHARED_FIRST` should switch to `is_single_claimer_mode()`. Rotation chores automatically get correct behavior with zero per-site changes.
     - Note: Also update `is_shared_chore()` to include rotation types, since rotation chores ARE multi-kid shared chores.

  2. **Implement `get_chore_status_context()` — 8-tier FSM**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - New static method that resolves a **per-kid** chore state:

       | Priority | State         | Condition                                                                                                                                                            |
       | -------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
       | 1        | `approved`    | `is_approved_in_current_period` is True                                                                                                                              |
       | 2        | `claimed`     | `has_pending_claim == True`                                                                                                                                          |
       | 3        | `not_my_turn` | `is_rotation_mode(chore)` AND `kid_id != rotation_current_kid_id` AND (criteria is NOT `rotation_steal` OR `now <= due_date`) AND `rotation_cycle_override == False` |
       | 4        | `missed`      | `overdue_handling == mark_missed_and_lock` AND `now > due_date` AND `due_date is not None`                                                                           |
       | 5        | `overdue`     | Relaxed overdue type AND `now > due_date` AND `due_date is not None`                                                                                                 |
       | 6        | `waiting`     | `claim_restriction_enabled == True` AND `due_window_start is not None` AND `now < due_window_start`                                                                  |
       | 7        | `due`         | `due_window_start is not None` AND `now >= due_window_start` AND `now <= due_date`                                                                                   |
       | 8        | `pending`     | Default / fallback                                                                                                                                                   |

     - Input: chore dict, kid_id, current timestamp, per-kid state context (approved/claimed flags)
     - Output: `tuple[str, str | None]` — (calculated_state, lock_reason)
     - Must be a pure function — no side effects, no storage access beyond the passed dict
     - **Steal exception** (P3): When `rotation_steal` + `now > due_date`, the `not_my_turn` condition does NOT match, allowing fallthrough to P5 (overdue / claimable by anyone)

  3. **Update `can_claim_chore()` — Add new blocking conditions**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - Add three new early-return blocks **before** the existing checks:
       - If calculated state is `missed` → return `(False, "missed")`
       - If calculated state is `waiting` → return `(False, "waiting")`
       - If calculated state is `not_my_turn` → return `(False, "not_my_turn")`
     - Current return type is already `tuple[bool, str]` — the string is the reason
     - Existing checks (now using `is_single_claimer_mode()` instead of `== SHARED_FIRST`) remain unchanged
     - **Key**: For rotation chores, `is_single_claimer_mode()` returns True, so the existing "only one kid can claim" check still applies after the rotation-specific guards

  4. **Add rotation helper methods to engine**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - `calculate_next_turn_simple(assigned_kids: list[str], current_kid_id: str) -> str`
       - Returns `assigned_kids[(current_index + 1) % len(assigned_kids)]`
       - **Resilience**: If `current_kid_id` not in list, return `assigned_kids[0]`
     - `calculate_next_turn_smart(assigned_kids: list[str], approved_counts: dict[str, int], last_approved_timestamps: dict[str, str | None]) -> str`
       - Sort by: (1) ascending approved count, (2) ascending last_approved timestamp (oldest first / None first), (3) list-order position as final tie-break
       - Return first kid in sorted result
     - Both are **pure static functions** — no HA imports, no side effects

  5. **Add criteria transition helper** (D-11 — support mutable criteria)
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - `get_criteria_transition_actions(old_criteria: str, new_criteria: str, chore_data: dict) -> dict[str, Any]`
       - Returns dict of field changes needed when switching criteria:
         - **Non-rotation → rotation**: Set `rotation_current_kid_id = assigned_kids[0]`, `rotation_cycle_override = False`
         - **Rotation → non-rotation**: Clear `rotation_current_kid_id = None`, `rotation_cycle_override = False`
         - **Rotation → different rotation**: Keep existing `rotation_current_kid_id` (turn doesn't reset)
         - **Any → any** (same type category): No field changes needed
       - Pure function — manager calls this and applies the returned changes

  6. **Integrate with existing `compute_global_state()`**
     - The existing `compute_global_state()` aggregates per-kid states into a single chore-level state
     - For rotation chores: Global state primarily reflects the **turn-holder's** state. Other kids' `not_my_turn` is cosmetic.
     - Update `compute_global_state()` to handle new states: `missed` → maps like `overdue`, `waiting` → maps like `pending`, `not_my_turn` → ignored for global aggregation

- **Key issues**
  - The Logic Adapter refactoring of ~60 existing check sites could be done as a **preparatory sub-initiative** before the FSM work, or incrementally within this phase. Recommend: Add adapters first, then convert callers file-by-file with targeted tests.
  - `rotation_steal` logic is the most complex P3 guard — the steal exception must be carefully coded to avoid accidentally unblocking non-steal rotation chores
  - `get_chore_status_context()` needs per-kid state (approved flag, claimed flag) as parameters — these come from the manager, not the engine
  - The criteria transition helper is critical for D-11 — without it, changing from `rotation_simple` to `independent` would leave orphan `rotation_current_kid_id` in storage

---

### Phase 3 – Manager Orchestration

- **Goal**: Wire the engine logic into the ChoreManager's workflows: rotation advancement on approval, missed-lock enforcement in the scanner, criteria transition handling, new management services, and cross-manager signal communication.

- **Steps / detailed work items**
  1. **Implement `_advance_rotation()` in ChoreManager**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Called inside `approve_chore()` after successful approval, before `_persist()`
     - Logic:
       - If `not ChoreEngine.is_rotation_mode(chore)` → return (no-op)
       - If `rotation_simple` or `rotation_steal` → call `ChoreEngine.calculate_next_turn_simple()`
       - If `rotation_smart` → query StatsEngine/StatsManager for approved counts (D-08) → call `ChoreEngine.calculate_next_turn_smart()`
       - Update `rotation_current_kid_id` in chore data
       - Reset `rotation_cycle_override` to `False` (D-15 resolved: next approval clears override)
       - After `_persist()`: emit `SIGNAL_SUFFIX_ROTATION_ADVANCED` with payload:
         ```
         {"chore_id": str, "previous_kid_id": str, "new_kid_id": str, "method": "simple"|"smart"|"manual"}
         ```

  2. **Update time scanner for `missed` lock transitions**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - In `_run_time_scanner()`: Add a new detection path for `mark_missed_and_lock`
     - When `now > due_date` AND `overdue_handling == mark_missed_and_lock` AND kid's state is still claimable (pending/due):
       - Set kid's chore state to `missed` in storage
       - Call `_record_missed_chore()` for stat tracking (already exists)
       - Extend signal payload with `due_date` and `reason: "strict_lock"` fields (D-07)
       - Do **NOT** reset to pending — the `missed` state persists until midnight
     - This path is distinct from the existing `clear_and_mark_missed` path which records miss then resets

  3. **Update midnight reset to clear `missed` lock**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - In `_process_approval_boundary_resets()` for AT*MIDNIGHT*\* chores:
       - If kid state is `missed` (from `mark_missed_and_lock`), reset to `pending`
       - Recalculate next due date (existing reschedule logic)
       - For rotation chores: If the missed kid was the current turn holder, advance rotation
       - This is the ONLY exit path from the `missed` lock state

  4. **Implement criteria transition handling** (D-11 — criteria is mutable)
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - New method `_handle_criteria_transition(chore_id: str, old_criteria: str, new_criteria: str) -> None`:
       - Calls `ChoreEngine.get_criteria_transition_actions()` to get field changes
       - Applies returned changes to chore data in storage
       - If transitioning TO rotation: validates `assigned_kids >= 2` (else rejects with error)
       - If transitioning FROM rotation: clears rotation fields
       - Emits `SIGNAL_SUFFIX_CHORE_UPDATED` after persist
     - Called from `update_chore()` when `completion_criteria` field has changed

  5. **Remove immutability guard from services.py** (D-11)
     - File: `custom_components/kidschores/services.py`
     - **Remove** the block at L784-788 that raises `HomeAssistantError(translation_key=TRANS_KEY_ERROR_COMPLETION_CRITERIA_IMMUTABLE)` when `completion_criteria` is in update data
     - **Add** `completion_criteria` to `UPDATE_CHORE_SCHEMA` (currently excluded)
     - **Add** `_COMPLETION_CRITERIA_VALUES` validation to the update schema (same as create)
     - Update the update handler to detect criteria changes and call `_handle_criteria_transition()` before applying other updates
     - Remove/deprecate `TRANS_KEY_ERROR_COMPLETION_CRITERIA_IMMUTABLE` constant and translation

  6. **Implement rotation resilience on kid deletion**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - In the existing `KID_DELETED` signal handler:
       - For each chore where `rotation_current_kid_id == deleted_kid_id`:
         - If `assigned_kids` still has members: set `rotation_current_kid_id = assigned_kids[0]`
         - If `assigned_kids` is now empty after removal: clear rotation metadata
       - Persist after changes

  7. **Register new management services**
     - File: `custom_components/kidschores/services.py`
     - **`set_rotation_turn`** (`SERVICE_SET_ROTATION_TURN`):
       - Fields: `chore_id` (required), `kid_id` (required)
       - Validates: `ChoreEngine.is_rotation_mode(chore)`, kid is in assigned_kids
       - Delegates to `chore_manager.set_rotation_turn(chore_id, kid_id)`
       - Emits `ROTATION_ADVANCED` with `method: "manual"`
     - **`reset_rotation`** (`SERVICE_RESET_ROTATION`):
       - Fields: `chore_id` (required)
       - Resets `rotation_current_kid_id` to `assigned_kids[0]`, clears `rotation_cycle_override`
       - Delegates to `chore_manager.reset_rotation(chore_id)`
     - **`open_rotation_cycle`** (`SERVICE_OPEN_ROTATION_CYCLE`):
       - Fields: `chore_id` (required)
       - Sets `rotation_cycle_override = True`
       - D-15 resolved: Override cleared on next approval (handled in `_advance_rotation()`)
       - Delegates to `chore_manager.open_rotation_cycle(chore_id)`
     - Add schemas with vol.Schema, handler functions, register in `async_setup_services()`

  8. **Add StatsEngine/StatsManager query method** (D-08)
     - File: `custom_components/kidschores/engines/stats_engine.py` or `managers/statistics_manager.py`
     - New method: `get_chore_approved_counts(chore_id: str, kid_ids: list[str]) -> dict[str, int]`
       - Returns `{kid_id: all_time_approved_count}` from period buckets
     - New method: `get_chore_last_approved_timestamps(chore_id: str, kid_ids: list[str]) -> dict[str, str | None]`
       - Returns `{kid_id: last_approved_iso_timestamp}` for smart rotation tie-breaking
     - Used by `_advance_rotation()` for smart rotation selection

  9. **Wire missed notification** — currently unwired
     - File: `custom_components/kidschores/managers/notification_manager.py`
     - Subscribe to `SIGNAL_SUFFIX_CHORE_MISSED`
     - Handler: Check chore's `notify_on_overdue` flag (reuse existing — missed is a stricter form of overdue) → dispatch notification using existing `TRANS_KEY_NOTIF_TITLE_CHORE_MISSED` / `TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED`
     - No new notification flag needed — `notify_on_overdue` gates both overdue and missed notifications

  10. **Add `services.yaml` entries for new services**
      - File: `custom_components/kidschores/services.yaml`
      - Add descriptions, field definitions, and examples for all 3 new rotation services

- **Key issues**
  - The `approve_chore()` method is ~400 lines with complex locking. `_advance_rotation()` must be a clean extraction called after state change but within the same persist operation
  - The scanner runs every ~5 minutes. For `missed` lock detection, there's up to 5 minutes of delay. Acceptable for v0.5.0.
  - `open_rotation_cycle` cycle boundary definition (D-15) affects how the override flag is cleared. "Next approval" is cleanest — handled in `_advance_rotation()` which already resets the flag
  - Removing the immutability guard (Step 5) changes the service contract. Existing automation YAML calling `update_chore` with `completion_criteria` will now succeed instead of erroring — this is the desired behavior per D-11

---

### Phase 4 – UX & Dashboard Contract

- **Goal**: Expose new states and rotation metadata through the UI Manager's dashboard helper, update config/options flow for new chore settings, and ensure dashboard has everything it needs.

- **Steps / detailed work items**
  1. **Update `KidDashboardHelper` chore attributes**
     - File: `custom_components/kidschores/managers/ui_manager.py`
     - For each chore in the kid's dashboard list, add to the existing 6-field dict:
       - `lock_reason` (str | None) — `"waiting"`, `"not_my_turn"`, `"missed"`, or `None`
       - `turn_kid_name` (str | None) — resolve `rotation_current_kid_id` to kid name (if `is_rotation_mode()`)
       - `available_at` (str | None) — ISO datetime of `due_window_start` (if `claim_restriction_enabled` and state is `waiting`)
       - `can_claim` already exists as a sensor attribute on `KidChoreStatusSensor` (confirmed D-16). Dashboard helper documents that consumers should use `state_attr(chore.eid, 'can_claim')`. Consider adding `can_claim` to dashboard helper dict for convenience.
     - Existing 6 fields (`eid`, `name`, `state`, `labels`, `grouping`, `is_am_pm`) remain unchanged

  2. **Update flow helpers — Chore creation/edit form**
     - File: `custom_components/kidschores/helpers/flow_helpers.py`
     - **Add `claim_restriction_enabled`** as a `BooleanSelector` in `build_chore_schema()`
       - Default: `False`
       - Position: After `due_window_offset` (logically grouped)
     - **Update `COMPLETION_CRITERIA_OPTIONS`** to include rotation types:
       - Add `rotation_simple`, `rotation_steal`, `rotation_smart` entries with clear labels
     - **Update `OVERDUE_HANDLING_OPTIONS`** to include 6th type:
       - Add `at_due_date_mark_missed_and_lock` entry
     - Note: HA config flows do not support conditional visibility. Rotation fields will appear for all chore types. Use clear labeling and translation text to guide users.

  3. **Update options flow for chore editing** (D-11 — criteria is mutable)
     - File: `custom_components/kidschores/options_flow.py`
     - Ensure `claim_restriction_enabled` is included in the chore edit step
     - `completion_criteria` is already editable in the options flow (confirmed). The form already shows the selector with current value pre-filled.
     - **Add criteria transition handling**: When user changes `completion_criteria` in the edit form:
       - After form submission, detect if criteria changed
       - Delegate to `chore_manager._handle_criteria_transition()` to apply field changes
       - Show appropriate validation errors (e.g., switching to rotation with only 1 kid assigned)

  4. **Update dashboard template documentation**
     - File: `docs/DASHBOARD_TEMPLATE_GUIDE.md`
     - Document new chore attributes (`lock_reason`, `turn_kid_name`, `available_at`)
     - Provide example Jinja2 snippets for:
       - Rotation display: "Current Turn: {{ turn_kid_name }}"
       - Waiting countdown: "Available at {{ available_at }}"
       - Lock reason tooltip/icon mapping
     - Note: Actual dashboard YAML changes are in separate repo (`kidschores-ha-dashboard`)

- **Key issues**
  - The dashboard YAML is in `kidschores-ha-dashboard` repo. Phase 4 only defines the **contract** — actual dashboard YAML changes are a separate initiative
  - The flow helpers show all options for all chore types, including rotation options for non-rotation chores. Clear translation text is critical to avoid user confusion
  - Criteria transition in the options flow must validate the new criteria against existing chore state — e.g., switching to `rotation_steal` requires a due date (V-04 from Phase 1)

---

### Phase 5 – Testing & Validation

- **Goal**: Achieve 95%+ test coverage for all new code paths. Use service-based tests as primary validation method, with engine unit tests for pure computation.

- **Steps / detailed work items**
  1. **Engine unit tests — Logic Adapters & FSM**
     - File: `tests/test_chore_engine.py` (new or extend existing)
     - Test Logic Adapters:
       - `is_single_claimer_mode()` — True for shared_first, rotation_simple, rotation_steal, rotation_smart; False for independent, shared
       - `is_rotation_mode()` — True for rotation\_\*; False for shared_first, independent, shared
       - Updated `is_shared_chore()` — True for shared, shared_first, AND all rotation types
     - Test `get_chore_status_context()` — all 8 priority tiers with edge cases:
       - Approved takes precedence over everything
       - `not_my_turn` takes precedence over `missed` (P3 > P4)
       - `missed` takes precedence over `overdue` (P4 > P5)
       - `waiting` only applies when `claim_restriction_enabled`
       - `due` window boundaries (exactly at start, exactly at end)
       - **Steal exception**: `rotation_steal` + overdue → `not_my_turn` does NOT match → falls to `overdue`
     - Test `can_claim_chore()` — new blocking conditions:
       - Blocked when `missed`, `waiting`, `not_my_turn`
       - `rotation_steal`: Blocked before overdue, unblocked after due date
       - `rotation_cycle_override = True`: Temporarily unblocks `not_my_turn`
     - Test rotation helpers:
       - `calculate_next_turn_simple()` — wrap-around, single kid fallback, removed kid resilience
       - `calculate_next_turn_smart()` — lowest count wins, tie-break by timestamp, tie-break by list order
     - Test criteria transition helper:
       - Non-rotation → rotation: returns `rotation_current_kid_id = assigned_kids[0]`
       - Rotation → non-rotation: returns `rotation_current_kid_id = None`
       - Rotation → different rotation: keeps existing turn
       - Same category → no field changes

  2. **Service-based integration tests**
     - File: `tests/test_service_rotation.py` (new)
     - Test scenarios using Stårblüm Family fixtures:
       - Create `rotation_simple` chore → Claim → Approve → Verify turn advanced to next kid
       - Create `rotation_steal` chore → Let overdue → Non-turn kid claims → Verify accepted
       - `set_rotation_turn` service → Verify turn changed, signal emitted
       - `reset_rotation` service → Verify reset to `assigned_kids[0]`
       - `open_rotation_cycle` service → Verify override enables any kid to claim
       - Approve after override → Verify override cleared (D-15 dependent)
     - Test `claim_restriction_enabled`:
       - Create chore with restriction + due_window → Attempt claim before window → Verify rejected with "waiting" reason
       - Advance time into window → Attempt claim → Verify accepted
     - Test `mark_missed_and_lock`:
       - Create chore with lock strategy → Advance past due date → Verify state is `missed`
       - Attempt claim in `missed` state → Verify rejected
       - Trigger midnight reset → Verify state returns to `pending`
     - Test criteria transition (D-11):
       - `update_chore` service with `completion_criteria: rotation_simple` on existing `shared_first` chore → Verify `rotation_current_kid_id` set
       - `update_chore` service with `completion_criteria: independent` on existing `rotation_simple` chore → Verify rotation fields cleared
       - `update_chore` service with `completion_criteria: rotation_steal` + 1 kid assigned → Verify validation error

  3. **Validation rule tests**
     - File: `tests/test_data_builders.py` (extend)
     - V-01: `mark_missed_and_lock` + `upon_completion` reset → Validation error
     - V-01: `mark_missed_and_lock` + `at_midnight_once` → Valid
     - V-02: `claim_restriction_enabled=True` + no due_window_offset → Validation error
     - V-03: Any rotation type + only 1 assigned kid → Validation error (D-14 dependent)
     - V-04: `rotation_steal` + no due date → Validation error

  4. **Migration tests**
     - File: `tests/test_migration.py` (extend)
     - Test extended v44 migration: Verify new fields backfilled on existing chores
       - `claim_restriction_enabled = False` on all chores
       - `rotation_current_kid_id = None` on all chores
       - `rotation_cycle_override = False` on all chores
     - Test idempotency: Run migration twice → no errors, no duplicate fields

  5. **Dashboard helper attribute tests**
     - File: `tests/test_ui_manager.py` (extend)
     - Verify `lock_reason`, `turn_kid_name`, `available_at` appear in chore attributes
     - Verify `turn_kid_name` resolves UUID to correct kid name
     - Verify `available_at` is ISO formatted when state is `waiting`
     - Verify `lock_reason` is `None` for normal (unlocked) chores

  6. **Run full validation suite**
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/ -v --tb=line`

- **Key issues**
  - Smart rotation tests need StatsEngine/StatsManager fixtures with pre-populated chore stats per kid
  - The scanner's 5-minute interval makes time-sensitive tests tricky — use `freezegun` or `async_fire_time_changed` to control time
  - Test coverage for rotation + missed + claim_restriction combinations could be combinatorially large — focus on the priority-order edge cases documented in the FSM state matrix
  - Criteria transition tests (Step 2) are critical for D-11 — must verify field cleanup is complete when switching criteria types

---

## Testing & validation

- Tests to execute:
  - `pytest tests/test_chore_engine.py -v` — Engine unit tests (adapters, FSM, rotation helpers)
  - `pytest tests/test_service_rotation.py -v` — Service-based rotation + criteria transition tests
  - `pytest tests/test_data_builders.py -v` — Validation rule tests
  - `pytest tests/test_migration.py -v` — v44 migration extension tests
  - `pytest tests/test_ui_manager.py -v` — Dashboard helper tests
  - `pytest tests/ -v --tb=line` — Full suite
- Outstanding: All tests — pending implementation
- Coverage target: 95%+ for all new modules

---

## Notes & follow-up

### Architecture context

- **Engine-Manager separation is critical**: All state resolution, `can_claim` logic, and Logic Adapters must be pure functions in `chore_engine.py`. The manager orchestrates workflows and writes to storage.
- **Signal-first communication**: `_advance_rotation()` emits `ROTATION_ADVANCED` after `_persist()`. Other managers (Statistics, Notification, UI) react to signals — never direct calls.
- **Rotation is a shared_first extension via Criteria Overload** (D-12): Rotation types (`rotation_simple`, `rotation_steal`, `rotation_smart`) are `completion_criteria` values, not a separate field. The Logic Adapter pattern (`is_single_claimer_mode()`, `is_rotation_mode()`) prevents gremlin code — existing `shared_first` checks use the adapter and automatically include rotation types.
- **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` immutability guard at L784-788 is incorrect and must be removed. A `get_criteria_transition_actions()` engine method and `_handle_criteria_transition()` manager method handle field cleanup when criteria changes.
- **Two distinct "missed" strategies coexist**:
  - `clear_and_mark_missed` — Records miss stat, then resets to pending at approval boundary (existing)
  - `mark_missed_and_lock` — Records miss stat, locks state to `missed`, prevents further claims until midnight (new)
- **v44 migration extended** (D-13): `_migrate_to_schema_44()` backfills new fields on existing chores rather than relying on `.get()` defaults.

### Logic Adapter audit (D-12 implementation context)

**~60 existing `completion_criteria` check sites across 10 production files** need updating to use Logic Adapters. Key findings:

| File                             | Check Sites | Primary Pattern                                                                          |
| -------------------------------- | ----------- | ---------------------------------------------------------------------------------------- |
| `managers/chore_manager.py`      | **25**      | Three-way branching (INDEPENDENT / SHARED_FIRST / SHARED) — heaviest target              |
| `engines/chore_engine.py`        | **10**      | Stateless routing + `is_shared_chore()` definition (zero callers — dead code)            |
| `options_flow.py`                | **6**       | Gating per-kid UI steps (INDEPENDENT only)                                               |
| `helpers/flow_helpers.py`        | **5**       | Form building + data transformation                                                      |
| `sensor.py`                      | **4**       | Entity creation gating + attribute routing                                               |
| `data_builders.py`               | **3**       | Validation + build defaults                                                              |
| `services.py`                    | **3**       | Service input validation                                                                 |
| `schedule_engine.py`             | **2**       | Per-kid vs chore-level date/day routing                                                  |
| `helpers/entity_helpers.py`      | **1**       | Orphaned sensor cleanup (**potential bug**: checks `SHARED` only, misses `SHARED_FIRST`) |
| `managers/statistics_manager.py` | **1**       | Daily snapshot due-date lookup                                                           |

**Adapter adoption strategy**: Add `is_single_claimer_mode()` and `is_rotation_mode()` in Phase 2 Step 1. Then incrementally convert callers file-by-file in Phase 2-3. The three-way branches (INDEPENDENT / SHARED_FIRST / SHARED) become (INDEPENDENT / single_claimer / SHARED) — rotation chores automatically get correct SHARED_FIRST-like behavior with zero per-site logic changes.

### Dependencies

- Phase 2 depends on Phase 1 (constants and types must exist)
- Phase 3 depends on Phase 2 (engine methods must exist for manager to call)
- Phase 4 depends on Phase 3 (signals and services must exist for UX to expose)
- Phase 5 can begin partially in parallel with Phase 3 (engine tests don't need manager)

### Follow-up tasks (separate initiatives)

- Dashboard YAML updates in `kidschores-ha-dashboard` to consume new attributes
- Crowdin sync for new translation keys
- Wiki documentation for rotation feature and missed lock feature
- Consider automation blueprints for "missed chore" → penalty workflow
- Evaluate precision scheduling for missed lock detection (currently ~5 min scanner delay)
- **Potential bug**: `entity_helpers.py` `cleanup_orphaned_shared_state_sensors()` checks only `SHARED` but shared state sensors are created for both `SHARED` and `SHARED_FIRST` — may orphan SHARED_FIRST sensors. Worth fixing in this initiative.

### Estimated file impact

| File                                                          | Change Type | Estimated Scope                                                                                                      |
| ------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------- |
| `const.py`                                                    | Modify      | ~30 new constants                                                                                                    |
| `type_defs.py`                                                | Modify      | 3 new TypedDict fields                                                                                               |
| `data_builders.py`                                            | Modify      | 3 new defaults + 4 validation rules                                                                                  |
| `engines/chore_engine.py`                                     | Modify      | ~250 lines new (Logic Adapters + FSM + rotation helpers + transition helper)                                         |
| `managers/chore_manager.py`                                   | Modify      | ~350 lines new (rotation advancement, scanner, missed lock, criteria transition, + adapter adoption across 25 sites) |
| `engines/stats_engine.py` or `managers/statistics_manager.py` | Modify      | ~30 lines (new query methods)                                                                                        |
| `managers/ui_manager.py`                                      | Modify      | ~40 lines (3-4 new dashboard attributes)                                                                             |
| `managers/notification_manager.py`                            | Modify      | ~30 lines (missed notification wiring)                                                                               |
| `helpers/flow_helpers.py`                                     | Modify      | ~30 lines (new selectors/options)                                                                                    |
| `options_flow.py`                                             | Modify      | ~20 lines (claim restriction + criteria transition handling)                                                         |
| `services.py`                                                 | Modify      | ~100 lines (3 new services + remove immutability guard + add criteria to update schema)                              |
| `services.yaml`                                               | Modify      | ~30 lines (service descriptions)                                                                                     |
| `migration_pre_v50.py`                                        | Modify      | ~20 lines (v44 extension for new field backfill)                                                                     |
| `translations/en.json`                                        | Modify      | ~40 new keys, remove `completion_criteria_immutable`                                                                 |
| `tests/test_chore_engine.py`                                  | New/Modify  | ~400 lines (adapters + FSM + rotation + transition)                                                                  |
| `tests/test_service_rotation.py`                              | New         | ~500 lines (rotation services + criteria transition + claim restriction + missed lock)                               |
| `tests/test_data_builders.py`                                 | Modify      | ~100 lines                                                                                                           |
| `tests/test_migration.py`                                     | Modify      | ~50 lines                                                                                                            |
| `tests/test_ui_manager.py`                                    | Modify      | ~80 lines                                                                                                            |
