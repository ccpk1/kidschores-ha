# Initiative Plan: Chore Logic v0.5.0 — Due Window Restrictions & Advanced Rotation

## Initiative snapshot

- **Name / Code**: Chore Logic v0.5.0 — Due Window Claim Restrictions + Advanced Rotation
- **Target release / milestone**: v0.5.0 (Schema v44 — extended in-place, no bump)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Phase 1 in-progress — design pivot applied (Rotation v2, 2 types + steal-as-overdue)

---

## ⚠️ APPROVAL CYCLE PROCESSING MODEL — MANDATORY VOCABULARY

> **This section defines the three independent processing lanes that govern a chore's lifecycle.**
> All plan phases, blueprint code, state matrix, and translations MUST use these precise terms.
> Never say "reset" without specifying WHICH lane is acting.

A chore's per-cycle lifecycle is governed by **three independent settings**, each controlling a separate lane of logic. These lanes share a common trigger point but execute distinct responsibilities:

### Lane 1: `approval_reset_type` — THE TRIGGER (When the boundary fires)

**Field**: `DATA_CHORE_APPROVAL_RESET_TYPE`
**Question answered**: "When does the chore's approval cycle boundary fire?"

| Value               | Trigger                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------ |
| `at_midnight_once`  | Fires once at midnight. Single-claim chore.                                                |
| `at_midnight_multi` | Fires at midnight. Multi-claim chore (kid can claim again after approval within same day). |
| `at_due_date_once`  | Fires when the configured due date/time is reached. Single-claim.                          |
| `at_due_date_multi` | Fires at due date/time. Multi-claim within cycle.                                          |
| `upon_completion`   | Fires immediately when the chore is approved (no time boundary).                           |
| `manual`            | Never fires automatically. Parent must manually trigger.                                   |

**This lane does NOT decide what happens.** It only decides **when** the boundary fires. The other two lanes decide what actions occur at that boundary.

### Lane 2: `overdue_handling_type` — THE OVERDUE POLICY (What happens past due date + at boundary)

**Field**: `DATA_CHORE_OVERDUE_HANDLING_TYPE`
**Question answered**: "What happens when the due date passes? And what happens to an overdue chore when the approval reset boundary fires?"

This lane has TWO moments of action:

1. **At due date**: Determines the chore's overdue state transition (e.g., mark as `overdue`, lock as `missed`, open steal window)
2. **At approval reset boundary**: Determines what happens to the overdue/missed state when Lane 1's trigger fires (e.g., clear overdue status, advance rotation turn, record missed stat)

| Value                                       | At Due Date                                                             | At Approval Reset Boundary                                                                           |
| ------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `never_overdue`                             | No state change                                                         | No action                                                                                            |
| `at_due_date`                               | Chore state → `overdue` (claimable)                                     | No automatic action (overdue persists)                                                               |
| `at_due_date_clear_at_approval_reset`       | Chore state → `overdue` (claimable)                                     | Overdue status cleared, chore state → `pending`                                                      |
| `at_due_date_clear_immediate_on_late`       | Chore state → `overdue` (claimable)                                     | If still overdue: clear + record late stat                                                           |
| `at_due_date_clear_and_mark_missed`         | Chore state → `overdue` (claimable)                                     | If still overdue: record missed stat, chore state → `pending`                                        |
| `at_due_date_mark_missed_and_lock`          | Chore state → `missed` (**locked**, not claimable)                      | Unlock missed state, chore state → `pending`                                                         |
| `at_due_date_allow_steal` _(rotation-only)_ | `not_my_turn` blocking lifts for all assigned kids (steal window opens) | If still overdue: record missed stat for turn-holder, chore state → `pending`, advance rotation turn |

### Lane 3: `approval_reset_pending_claim_action` — THE CLAIM POLICY (What happens to unapproved claims at boundary)

**Field**: `DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION`
**Question answered**: "If a kid has claimed but the parent hasn't approved yet when the approval reset boundary fires, what happens to that pending claim?"

| Value                  | Action at Approval Reset Boundary                      |
| ---------------------- | ------------------------------------------------------ |
| `hold_pending`         | Keep the pending claim intact across the boundary      |
| `clear_pending`        | Discard the pending claim, chore state → `pending`     |
| `auto_approve_pending` | Auto-approve the pending claim (as if parent approved) |

### Processing Order at Approval Reset Boundary

When Lane 1's trigger fires, the system processes in this order:

1. **Lane 3 (Claim Policy)** executes first — resolve any pending claims
2. **Lane 2 (Overdue Policy)** executes second — resolve any overdue/missed states
3. **Chore state reset** — the chore's approval cycle resets to `pending` for a new cycle

### ❌ Vocabulary Anti-Patterns

| ❌ NEVER Write         | ✅ ALWAYS Write                                                             | Why                                                         |
| ---------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| "midnight reset"       | "approval reset boundary (midnight for `at_midnight_once`)"                 | Specifies Lane 1                                            |
| "resets to pending"    | "chore state resets to `pending`" or "overdue policy clears overdue status" | Distinguishes chore state change from overdue policy action |
| "only midnight resets" | "only `at_midnight_*` approval reset types can trigger the unlock"          | Specifies which trigger types are compatible                |
| "reset at boundary"    | "at the approval reset boundary, the overdue policy [specific action]"      | Names the lane                                              |
| "overdue resets"       | "overdue policy clears the overdue status"                                  | Names the lane and the action                               |

---

## ⚠️ ROTATION DESIGN v2 — AUTHORITATIVE REFERENCE

> **This section is the single source of truth for rotation behavior.**
> All plan phases, blueprint code, state matrix, and translations MUST align with this section.
> Updated 2026-02-12 after design pivot: 3 rotation criteria → 2 criteria + 1 overdue type.

### What Changed (Design Pivot)

| Before (v1)                                                                           | After (v2)                                                              |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 3 `completion_criteria` values: `rotation_simple`, `rotation_steal`, `rotation_smart` | **2** `completion_criteria` values: `rotation_simple`, `rotation_smart` |
| "Steal" was a separate criteria type                                                  | "Steal" moved to **overdue handling**: `at_due_date_allow_steal`        |
| Steal logic checked `criteria == rotation_steal`                                      | Steal logic checks `overdue_handling == at_due_date_allow_steal`        |

### Rotation Type Definitions

#### `rotation_simple` — Strict Turn-Based, Fixed Order

- **Who can claim**: ONLY the current turn-holder. All other assigned kids see `not_my_turn` and cannot claim.
- **Turn advancement**: Round-robin by `assigned_kids` list index. After approval, turn advances to `assigned_kids[(current_index + 1) % len]`.
- **Parent override**: The parent "Approve" button can manually approve any kid (not just the turn-holder). After parent-approved completion, turn advances normally from the kid who completed.
- **After pure miss (no one claims)**: When the approval reset boundary fires (Lane 1 — midnight for `at_midnight_once`), the overdue policy (Lane 2) executes: records a missed stat for the skipped turn-holder, clears the overdue status, resets chore state to `pending`, and advances the turn to the next kid in order. Only the skipped turn-holder gets the overdue/missed stat.
- **Use case**: Strict fairness for siblings. "It's your turn, no exceptions."

#### `rotation_smart` — Strict Turn-Based, Fairness-Weighted Order

- **Who can claim**: ONLY the current turn-holder. All other assigned kids see `not_my_turn` and cannot claim. (Same blocking behavior as `rotation_simple`.)
- **Turn advancement**: Fairness-weighted selection. The system picks the next turn-holder using these criteria (ascending priority):
  1. Fewest all-time approved completions for this chore
  2. Oldest `last_approved_timestamp` (tie-break: longest since last completion wins)
  3. List position in `assigned_kids` (final tie-break)
- **Parent override**: Same as `rotation_simple` — parent can approve any kid.
- **After pure miss**: Same as `rotation_simple` — when the approval reset boundary fires, the overdue policy records the missed stat, clears overdue status, resets chore state to `pending`, and advances the turn to the next kid (per fairness algorithm). Skipped holder gets the stat.
- **Use case**: Self-balancing fairness. A kid who missed several turns gets re-prioritized automatically.

### Overdue Handling Type: `at_due_date_allow_steal`

This is a **7th overdue handling type** (not a completion criteria). It controls what happens when a rotation chore's due date passes without the turn-holder claiming.

- **Pre-overdue**: Normal rotation blocking applies. Only the turn-holder can claim.
- **At due date (overdue)**: The `not_my_turn` blocking **lifts for all assigned kids**. Any assigned kid can now claim the chore. This is the "steal" window.
- **Notifications**: When the steal window opens, ALL assigned kids receive a notification (not just the turn-holder). The notification indicates the chore is available for anyone.
- **Overdue stat**: Only the skipped turn-holder gets the `overdue` stat. The kid who steals does NOT get an overdue mark.
- **After steal (someone claims)**: Normal `_advance_rotation()` runs from the kid who completed. Turn advances to the next kid per the rotation type's algorithm (round-robin for simple, fairness-weighted for smart).
- **After pure miss (no one claims, including steal window)**: When the approval reset boundary fires (Lane 1 — midnight, since `at_midnight_once` is the only compatible `approval_reset_type`), the overdue policy (Lane 2) for `at_due_date_allow_steal` executes: records a missed stat for the original turn-holder, clears the overdue status, resets chore state to `pending`, and advances the turn to the next kid. The chore begins a fresh cycle with the new turn-holder.

### Compatibility Matrix

`at_due_date_allow_steal` has strict compatibility requirements:

| Setting               | Allowed Values                             | Reason                                                                                   |
| --------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `completion_criteria` | `rotation_simple` or `rotation_smart` ONLY | Steal is a rotation-only mechanic. Non-rotation chores have no turn to steal.            |
| `approval_reset_type` | `at_midnight_once` ONLY                    | Multi-claim and due-date resets create ambiguity about what "one steal per cycle" means. |

**Validation rule (V-05)**: If `overdue_handling == at_due_date_allow_steal`, then:

1. `completion_criteria` MUST be a rotation type (`rotation_simple` or `rotation_smart`)
2. `approval_reset_type` MUST be `at_midnight_once`
3. A due date MUST be configured (steal window needs a trigger point)

### Real-World Scenario: "Dishes Rotation with Steal"

> **Setup**: 3 kids (Alice, Bob, Charlie). Chore: "Wash Dishes." `rotation_simple` + `at_due_date_allow_steal` + `at_midnight_once`. Due time: 7 PM daily.
>
> **Monday**: Alice's turn. She claims at 6 PM, parent approves. Turn advances to Bob.
>
> **Tuesday**: Bob's turn. He forgets. At 7:01 PM the steal window opens. All 3 kids get notified: "Dishes is available!" Charlie claims at 7:30 PM. Parent approves. Turn advances to Charlie+1 = Alice. Bob gets the overdue stat. Charlie does NOT.
>
> **Wednesday**: Alice's turn. Nobody claims. 7 PM passes (steal window opens). Still nobody claims by midnight. At the approval reset boundary (midnight): overdue policy records Alice's missed stat, clears overdue status, resets chore state to `pending`, and advances the turn to Bob.
>
> **Thursday**: Bob's turn (fairness note: Bob has fewest completions if using `rotation_smart`).

### Terminology Reference

| Term               | Meaning                                                                                                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Turn-holder**    | The kid whose `kid_id == rotation_current_kid_id`. Only they can claim.                                                                                                                 |
| **Steal window**   | Period after due date when `at_due_date_allow_steal` lifts turn blocking.                                                                                                               |
| **Steal**          | When a non-turn-holder claims during the steal window.                                                                                                                                  |
| **Pure miss**      | No one claims (not even during steal window). At the approval reset boundary: overdue policy records missed stat, clears overdue status, resets chore state → `pending`, advances turn. |
| **Turn advance**   | Updating `rotation_current_kid_id` to the next kid after approval/miss.                                                                                                                 |
| **Cycle override** | `rotation_cycle_override=True` — manual service that lets any kid claim.                                                                                                                |

---

## Summary & immediate steps

| Phase / Step                      | Description                                                      | % complete | Quick notes                                                             |
| --------------------------------- | ---------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------- |
| Phase 1 – Foundation              | Constants, types, validation rules (no schema migration)         | 100%       | ✅ COMPLETE — rotation_steal removed, allow_steal added, all tests pass |
| Phase 2 – Engine & State Machine  | 8-tier FSM, claim restrictions, rotation resolution              | 0%         | Core logic; ready to start                                              |
| Phase 3 – Manager Orchestration   | Rotation advancement, missed lock, scanner updates, new services | 0%         | Depends on Phase 2 engine                                               |
| Phase 4 – UX & Dashboard Contract | UI Manager attributes, flow helpers, notification wiring         | 0%         | Depends on Phase 3 signals                                              |
| Phase 5 – Testing & Validation    | Full test coverage for all new paths                             | 0%         | Service-based + engine unit tests                                       |

1. **Key objective** – Introduce two new chore management capabilities: (a) **Due Window Claim Restrictions** that prevent kids from claiming chores before a configurable window opens, and (b) **Advanced Rotation Logic** that extends shared_first chores into a disciplined turn-based system with two sub-types (`rotation_simple`, `rotation_smart`), plus a steal mechanic delivered via overdue handling (`at_due_date_allow_steal`). Both features extend the existing FSM with three new calculated states (`waiting`, `not_my_turn`, `missed` as a locked terminal state).

2. **Summary of recent work**
   - ✅ **Phase 1 Foundation COMPLETE** (2026-02-12 evening):
     - Removed `COMPLETION_CRITERIA_ROTATION_STEAL` constant from `const.py`, `en.json`, `data_builders.py`, `migration_pre_v50.py`
     - Added `OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL` constant + translation key
     - Fixed rotation_simple/smart descriptions per three-lane vocabulary
     - Validation gates: ✅ Lint passed (9.8/10), ✅ Tests 100% (1257 passed), ✅ MyPy 0 errors
   - Design pivot applied (2026-02-12): reduced from 3 rotation criteria to 2, moved steal mechanic to overdue handling.
   - Schema stays at **v44** — extend existing `_migrate_to_schema_44()` to backfill new fields (D-13)
   - **Criteria Overload pattern** (D-12): Rotation types are new `completion_criteria` values (`rotation_simple`, `rotation_smart`). Logic Adapter methods (`is_single_claimer_mode()`, `is_rotation_mode()`) prevent gremlin code across ~60 check sites
   - **Steal mechanic** (D-06 revised): NOT a completion criteria. Delivered as `at_due_date_allow_steal` overdue handling type. Only compatible with rotation criteria + `at_midnight_once` `approval_reset_type`.
   - **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` L784-788 immutability guard is incorrect and must be removed. Data transition logic handles field cleanup on criteria change.
   - Existing `clear_and_mark_missed` and new `mark_missed_and_lock` are **two distinct strategies** (6th overdue type). `at_due_date_allow_steal` is the **7th overdue type**.
   - All rotation types require **≥ 2 assigned kids** (D-14)
   - Both `rotation_simple` and `rotation_smart` enforce **strict turn blocking** — only the turn-holder can claim
   - No rotation code exists yet (greenfield)

3. **Next steps (short term)**
   - ✅ **Phase 1 code corrections COMPLETE** (rotation_steal removed, allow_steal added, all tests pass)
   - **Ready to start Phase 2**: Engine & State Machine implementation
   - Blueprint document updated for implementer reference: [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md)

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

   ### Resolved Decisions (updated 2026-02-12 — design pivot applied)

   | ID       | Question                                                       | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Impact                                                                                                                                                                                                                                                                                                                        |
   | -------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **D-01** | Schema version                                                 | ✅ **v44** (no bump).                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Migration extended in-place (D-13).                                                                                                                                                                                                                                                                                           |
   | **D-02** | Existing `clear_and_mark_missed` vs new `mark_missed_and_lock` | ✅ **Two distinct strategies**. Existing = "at due date: record miss → at approval reset boundary: overdue policy resets chore state to `pending`." New = "at due date: lock in `missed` state → at approval reset boundary: overdue policy unlocks `missed` state, resets chore state to `pending`."                                                                                                                                                                    | Add 6th overdue type `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK`. Existing unchanged.                                                                                                                                                                                                                                          |
   | **D-03** | `mark_missed_and_lock` approval reset type compatibility       | ✅ **`at_midnight_*` approval reset types only**.                                                                                                                                                                                                                                                                                                                                                                                                                        | Validation rule: reject `upon_completion`, `at_due_date_*`, `manual` reset types.                                                                                                                                                                                                                                             |
   | **D-04** | `claim_restriction_enabled` scope                              | ✅ **Per-chore boolean**. Existing `can_claim` calculated attribute will be used.                                                                                                                                                                                                                                                                                                                                                                                        | Per-chore field in storage + flow. `can_claim` is a calculated boolean attribute on the kid chore status sensor.                                                                                                                                                                                                              |
   | **D-05** | Rotation as completion criteria                                | ✅ **REVISED (v2)**: Two `completion_criteria` values: `rotation_simple`, `rotation_smart`. ~~`rotation_steal` removed as criteria~~ — steal mechanic moved to overdue handling (D-06).                                                                                                                                                                                                                                                                                  | Two new constants (not three). Engine uses Logic Adapter pattern (D-12) to treat rotation as shared_first-like.                                                                                                                                                                                                               |
   | **D-06** | Steal mechanic placement                                       | ✅ **REVISED (v2)**: Steal is an **overdue handling type** (`at_due_date_allow_steal`), NOT a completion criteria. Valid only with rotation criteria + `at_midnight_once` `approval_reset_type`. At due date, `not_my_turn` blocking lifts for all assigned kids.                                                                                                                                                                                                        | New 7th overdue type constant. New validation rule V-05 (rotation + at_midnight_once required). FSM P3 steal exception checks `overdue_handling` not `criteria`.                                                                                                                                                              |
   | **D-07** | CHORE_MISSED signal                                            | ✅ **Extend existing** payload with optional `due_date` and `reason` fields.                                                                                                                                                                                                                                                                                                                                                                                             | Backward compatible.                                                                                                                                                                                                                                                                                                          |
   | **D-08** | Smart rotation stats query                                     | ✅ **StatsEngine or StatsManager** provides the query API.                                                                                                                                                                                                                                                                                                                                                                                                               | New public method for per-chore approved counts across kids.                                                                                                                                                                                                                                                                  |
   | **D-09** | "The Nudge" notification                                       | ✅ **Same as existing `notify_on_due_window`**. No new notification type.                                                                                                                                                                                                                                                                                                                                                                                                | No work needed.                                                                                                                                                                                                                                                                                                               |
   | **D-10** | Migration home                                                 | ✅ **`migration_pre_v50.py`** v44 section.                                                                                                                                                                                                                                                                                                                                                                                                                               | Extend existing `_migrate_to_schema_44()` to backfill new fields (D-13).                                                                                                                                                                                                                                                      |
   | **D-11** | `completion_criteria` mutability                               | ✅ **Mutable**. Users CAN change `completion_criteria` when editing a chore via options flow. The `services.py` immutability guard (L784-788) is incorrect and must be **removed**. When criteria changes, **data transition logic** handles cleanup (e.g., clear rotation fields when switching away from rotation; initialize `rotation_current_kid_id` when switching TO rotation).                                                                                   | Remove immutability guard from `services.py`. Add `_handle_criteria_transition()` method to ChoreManager. Add `completion_criteria` to `UPDATE_CHORE_SCHEMA`.                                                                                                                                                                 |
   | **D-12** | Data model: rotation as criteria value vs. separate field      | ✅ **Option A — Criteria Overload**. Rotation types are new `completion_criteria` values: `rotation_simple`, `rotation_smart`. UI is one-click — no separate `rotation_type` field. **Logic Adapter** pattern in `ChoreEngine` prevents "gremlin code": `is_single_claimer_mode()` → True for `shared_first` + all rotation types; `is_rotation_mode()` → True for `rotation_*` only. All existing `shared_first` checks use `is_single_claimer_mode()` adapter instead. | ~60 existing criteria check sites across 10 production files. The Logic Adapter pattern makes most transparent — existing three-way branches (INDEPENDENT / SHARED_FIRST / SHARED) become (INDEPENDENT / single_claimer / SHARED) and rotation chores automatically get correct behavior. See "Logic Adapter audit" in Notes. |
   | **D-13** | Existing chore field backfill strategy                         | ✅ **Extend v44 migration** in `migration_pre_v50.py` to backfill new fields on existing chores.                                                                                                                                                                                                                                                                                                                                                                         | Add backfill step to `_migrate_to_schema_44()`: set `claim_restriction_enabled=False`, `rotation_current_kid_id=None`, `rotation_cycle_override=False` on all existing chores.                                                                                                                                                |
   | **D-14** | Rotation minimum kids                                          | ✅ **All rotation types require ≥ 2 assigned kids**. Turn-taking with 1 kid is meaningless for any rotation variant.                                                                                                                                                                                                                                                                                                                                                     | Validation rule V-03 applies to `rotation_simple` AND `rotation_smart` uniformly. Error message in `data_builders.py`.                                                                                                                                                                                                        |
   | **D-15** | `rotation_cycle_override` clear trigger                        | ✅ **Approval action clears the override** (not a boundary event). Next approval of any kid on the chore clears `rotation_cycle_override = False`. The override is for "let anyone claim THIS cycle's instance." Once approved, normal rotation resumes.                                                                                                                                                                                                                 | Handled in `_advance_rotation()` — which already resets `rotation_cycle_override = False` after approval. No additional timer/scanner logic needed.                                                                                                                                                                           |
   | **D-16** | Where `can_claim` attribute lives                              | ✅ **Calculated boolean on the kid chore status sensor** (`KidChoreStatusSensor.extra_state_attributes`). Pipeline: `ChoreEngine.can_claim_chore()` → `ChoreManager.can_claim_chore()` → sensor attribute. Dashboard helper does NOT include it — documented to fetch via `state_attr(chore.eid, 'can_claim')`. `ATTR_CAN_CLAIM` constant already exists.                                                                                                                | New blocking conditions (waiting, not_my_turn, missed) integrate into existing `ChoreEngine.can_claim_chore()`. No new sensor or attribute needed — extend existing logic.                                                                                                                                                    |
   | **D-17** | Turn after pure miss (no steal)                                | ✅ **(NEW v2)** Turn **advances to next kid** when the approval reset boundary fires and the overdue policy executes. The skipped kid does NOT get another chance. Only the skipped turn-holder gets the missed/overdue stat.                                                                                                                                                                                                                                            | `_process_approval_boundary_resets()` must call `_advance_rotation()` after midnight unlock. Ensures rotation never stalls.                                                                                                                                                                                                   |
   | **D-18** | Turn after steal                                               | ✅ **(NEW v2)** Normal `_advance_rotation()` runs from the completer (the kid who stole). Turn advances to the next kid relative to the completer's position, NOT back to the original turn-holder.                                                                                                                                                                                                                                                                      | Same `_advance_rotation()` code path as normal approval. No special steal-specific turn logic needed.                                                                                                                                                                                                                         |
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps.
- **Detailed tracking**: Use the phase-specific sections below for granular progress.

---

## Detailed phase tracking

### Phase 1 – Foundation (Constants, Types, Validation, Migration)

- **Goal**: Establish the data model, constants, type definitions, Logic Adapter static methods, validation rules, and v44 migration extension. No behavioral logic — purely structural.
- **Status**: ~80% complete. Phase 1 code was implemented before design pivot. Corrections needed: remove `rotation_steal`, add `at_due_date_allow_steal`, fix translations.

- **Steps / detailed work items**
  1. **Add new constants to `const.py`** ✅ (needs correction)
     - File: `custom_components/kidschores/const.py`
     - **6th overdue handling constant** (D-02): ✅ Done
       - `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK = "at_due_date_mark_missed_and_lock"`
     - **7th overdue handling constant** (D-06 revised): ⬜ NEW — must add
       - `OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL = "at_due_date_allow_steal"`
       - Add to `OVERDUE_HANDLING_TYPE_OPTIONS` list
     - **Completion criteria constants** (D-05 revised): 🔧 Needs correction
       - `COMPLETION_CRITERIA_ROTATION_SIMPLE = "rotation_simple"` ✅ Done
       - ~~`COMPLETION_CRITERIA_ROTATION_STEAL = "rotation_steal"`~~ ❌ **REMOVE** — steal is now an overdue type
       - `COMPLETION_CRITERIA_ROTATION_SMART = "rotation_smart"` ✅ Done
       - Update `COMPLETION_CRITERIA_OPTIONS` to have 5 entries (not 6)
     - **Translation keys**: 🔧 Needs correction
       - Remove `TRANS_KEY_CRITERIA_ROTATION_STEAL`
       - Add `TRANS_KEY_OVERDUE_AT_DUE_DATE_ALLOW_STEAL`
     - **All other constants** (storage keys, states, signals, services, ATTRs): ✅ Done — no changes needed

  2. **Update `type_defs.py` — ChoreData TypedDict** ✅ Done
     - 3 new `NotRequired` fields added. No changes needed for design pivot.

  3. **Update `data_builders.py` — Build & Validate** ✅ (needs V-04→V-05 correction)
     - Build defaults: ✅ Done
     - Validation rules:
       - **V-01**: `mark_missed_and_lock` requires `AT_MIDNIGHT_*` reset ✅ Done
       - **V-02**: `claim_restriction_enabled` requires `due_window_offset` ✅ Done
       - **V-03**: All rotation types require ≥ 2 assigned kids ✅ Done
       - ~~**V-04**: `rotation_steal` requires due date~~ ❌ **REMOVE** — steal is no longer a criteria
       - **V-05**: ⬜ **NEW** — `at_due_date_allow_steal` requires: (a) rotation criteria, (b) `at_midnight_once` reset, (c) due date configured

  4. **Extend v44 migration to backfill new fields** (D-13) ✅ Done
     - No changes needed for design pivot. 3 fields backfilled correctly.

  5. **Update translations `en.json`** 🔧 Needs correction
     - File: `custom_components/kidschores/translations/en.json`
     - **Remove**: `rotation_steal` entries from `selector.completion_criteria.options` and `entity.sensor.kid_chore_status_sensor.state`
     - **Add**: `at_due_date_allow_steal` entry in `selector.overdue_handling_type.options`
     - **Fix rotation descriptions** (currently incorrect):
       - `rotation_simple` → "Rotation Simple (Turn-holder only, strict order)" ← currently says "Turn priority, stealing allowed" which is WRONG
       - `rotation_smart` → "Rotation Smart (Turn-holder only, fairness-weighted)" ← currently says "Only turn-holder can claim" which is acceptable but add "fairness-weighted"
     - **Add new overdue description**: `at_due_date_allow_steal` → "Allow Steal (Rotation — any kid can claim after due date)"

- **Key issues**
  - The 2 new `completion_criteria` values (not 3) must be updated in `COMPLETION_CRITERIA_OPTIONS`, `_COMPLETION_CRITERIA_VALUES` in services.py, and flow_helpers selectors
  - The new 7th overdue type `at_due_date_allow_steal` must be added to `OVERDUE_HANDLING_TYPE_OPTIONS`
  - D-14 resolved: All rotation types require ≥ 2 kids. V-03 validation rule applies uniformly.
  - **V-05 is critical**: `at_due_date_allow_steal` has the tightest compatibility constraints of any overdue type

---

### Phase 2 – Engine & State Machine (+ Logic Adapters)

- **Goal**: Implement the Logic Adapter static methods, the 8-tier priority state resolution, claim restriction logic, rotation-aware can_claim checks, and criteria transition helpers in `chore_engine.py`. Pure computation — no storage writes, no HA imports.

- **Steps / detailed work items**
  1. **Implement Logic Adapter static methods** (D-12 — the "gremlin prevention" pattern)
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - Two new static methods following existing `is_shared_chore()` signature pattern:

       ```
       is_single_claimer_mode(chore_data) -> bool
         Returns True if criteria in (shared_first, rotation_simple, rotation_smart)
         Replaces all existing "== SHARED_FIRST" checks for claim-blocking, reset-all-kids, etc.

       is_rotation_mode(chore_data) -> bool
         Returns True if criteria in (rotation_simple, rotation_smart)
         Used for rotation-specific logic (turn advancement, override, steal-via-overdue)
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

       | Priority | State         | Condition                                                                                                                                                                 |
       | -------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
       | 1        | `approved`    | `is_approved_in_current_period` is True                                                                                                                                   |
       | 2        | `claimed`     | `has_pending_claim == True`                                                                                                                                               |
       | 3        | `not_my_turn` | `is_rotation_mode(chore)` AND `kid_id != rotation_current_kid_id` AND NOT (`overdue_handling == allow_steal` AND `now > due_date`) AND `rotation_cycle_override == False` |
       | 4        | `missed`      | `overdue_handling == mark_missed_and_lock` AND `now > due_date` AND `due_date is not None`                                                                                |
       | 5        | `overdue`     | Relaxed overdue type AND `now > due_date` AND `due_date is not None`                                                                                                      |
       | 6        | `waiting`     | `claim_restriction_enabled == True` AND `due_window_start is not None` AND `now < due_window_start`                                                                       |
       | 7        | `due`         | `due_window_start is not None` AND `now >= due_window_start` AND `now <= due_date`                                                                                        |
       | 8        | `pending`     | Default / fallback                                                                                                                                                        |

     - Input: chore dict, kid_id, current timestamp, per-kid state context (approved/claimed flags)
     - Output: `tuple[str, str | None]` — (calculated_state, lock_reason)
     - Must be a pure function — no side effects, no storage access beyond the passed dict
     - **Steal exception** (P3): When `overdue_handling == at_due_date_allow_steal` + `now > due_date`, the `not_my_turn` condition does NOT match, allowing fallthrough to P5 (overdue / claimable by anyone)

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
       - Used by BOTH `rotation_simple` and `rotation_smart`-after-miss (round-robin fallback)
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
  - The steal exception in P3 now checks **`overdue_handling`** (not `criteria`). This is simpler — it's a single field check, no need to handle a third rotation criteria type.
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
       - If `rotation_simple` → call `ChoreEngine.calculate_next_turn_simple()`
       - If `rotation_smart` → query StatsEngine/StatsManager for approved counts (D-08) → call `ChoreEngine.calculate_next_turn_smart()`
       - Update `rotation_current_kid_id` in chore data
       - Reset `rotation_cycle_override` to `False` (D-15 resolved: next approval clears override)
       - After `_persist()`: emit `SIGNAL_SUFFIX_ROTATION_ADVANCED` with payload:
         ```
         {"chore_id": str, "previous_kid_id": str, "new_kid_id": str, "method": "simple"|"smart"|"manual"}
         ```
     - **D-18**: After a steal, the same `_advance_rotation()` runs — turn advances from the completer, not back to the original turn-holder. No special steal path needed.

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
       - **D-17**: For rotation chores: If the missed kid was the current turn holder, advance rotation to the next kid. This ensures rotation never stalls on a missed turn.
       - For `at_due_date_allow_steal` chores: If no one claimed during the steal window, the original turn-holder gets the overdue stat and turn advances to next kid at midnight.
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
     - **Add** `_COMPLETION_CRITERIA_VALUES` validation to the update schema (same as create). Values: `independent`, `shared_all`, `shared_first`, `rotation_simple`, `rotation_smart` (5 total — no `rotation_steal`)
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

  9. **Wire missed + steal notifications**
     - File: `custom_components/kidschores/managers/notification_manager.py`
     - Subscribe to `SIGNAL_SUFFIX_CHORE_MISSED`
     - Handler: Check chore's `notify_on_overdue` flag (reuse existing — missed is a stricter form of overdue) → dispatch notification using `TRANS_KEY_NOTIF_TITLE_CHORE_MISSED` / `TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED`
     - **Steal window notification** (D-06 revised): When `at_due_date_allow_steal` chore goes overdue, notify ALL assigned kids (not just turn-holder) that the chore is available for anyone to claim. Reuse existing overdue notification path but expand recipient list.
     - No new notification flag needed — `notify_on_overdue` gates both overdue and missed notifications

  10. **Add `services.yaml` entries for new services**
      - File: `custom_components/kidschores/services.yaml`
      - Add descriptions, field definitions, and examples for all 3 new rotation services

- **Key issues** (Phase 3)
  - The `approve_chore()` method is ~400 lines with complex locking. `_advance_rotation()` must be a clean extraction called after state change but within the same persist operation
  - The scanner runs every ~5 minutes. For `missed` lock detection, there's up to 5 minutes of delay. Acceptable for v0.5.0.
  - `open_rotation_cycle` cycle boundary definition (D-15) affects how the override flag is cleared. "Next approval" is cleanest — handled in `_advance_rotation()` which already resets the flag
  - Removing the immutability guard (Step 5) changes the service contract. Existing automation YAML calling `update_chore` with `completion_criteria` will now succeed instead of erroring — this is the desired behavior per D-11
  - **Steal window (D-06 revised)**: The steal mechanic is now entirely in the FSM (P3 steal exception checks `overdue_handling`). No special manager logic needed — the FSM naturally unblocks non-turn-holders when `at_due_date_allow_steal` + overdue.

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
       - Add `rotation_simple`, `rotation_smart` entries with clear labels (2 new entries, NOT 3)
     - **Update `OVERDUE_HANDLING_OPTIONS`** to include 7th type:
       - Add `at_due_date_allow_steal` entry — label must clearly indicate rotation-only + at_midnight_once constraint
     - Note: HA config flows do not support conditional visibility. All overdue types will appear for all chore types. Use clear labeling and translation text to guide users. Consider adding validation error V-05 feedback when incompatible combo selected.

  3. **Update options flow for chore editing** (D-11 — criteria is mutable)
     - File: `custom_components/kidschores/options_flow.py`
     - Ensure `claim_restriction_enabled` is included in the chore edit step
     - `completion_criteria` is already editable in the options flow (confirmed). The form already shows the selector with current value pre-filled.
     - **Add criteria transition handling**: When user changes `completion_criteria` in the edit form:
       - After form submission, detect if criteria changed
       - Delegate to `chore_manager._handle_criteria_transition()` to apply field changes
       - Show appropriate validation errors (e.g., switching to rotation with only 1 kid assigned)
     - **Add overdue handling validation**: When user selects `at_due_date_allow_steal`:
       - Validate rotation criteria + `at_midnight_once` reset (V-05)
       - Show error if incompatible combination detected

  4. **Update dashboard template documentation**
     - File: `docs/DASHBOARD_TEMPLATE_GUIDE.md`
     - Document new chore attributes (`lock_reason`, `turn_kid_name`, `available_at`)
     - Provide example Jinja2 snippets for:
       - Rotation display: "Current Turn: {{ turn_kid_name }}"
       - Waiting countdown: "Available at {{ available_at }}"
       - Lock reason tooltip/icon mapping
     - Note: Actual dashboard YAML changes are in separate repo (`kidschores-ha-dashboard`)

- **Key issues** (Phase 4)
  - The dashboard YAML is in `kidschores-ha-dashboard` repo. Phase 4 only defines the **contract** — actual dashboard YAML changes are a separate initiative
  - The flow helpers show all options for all chore types, including rotation options for non-rotation chores and `at_due_date_allow_steal` for non-rotation chores. Clear translation text is critical to avoid user confusion. Validation rule V-05 catches invalid combos on save.
  - Criteria transition in the options flow must validate the new criteria against existing chore state — e.g., switching to `rotation_simple` requires ≥ 2 assigned kids (V-03). Switching to `at_due_date_allow_steal` overdue handling requires rotation criteria + `at_midnight_once` (V-05).

---

### Phase 5 – Testing & Validation

- **Goal**: Achieve 95%+ test coverage for all new code paths. Use service-based tests as primary validation method, with engine unit tests for pure computation.

- **Steps / detailed work items**
  1. **Engine unit tests — Logic Adapters & FSM**
     - File: `tests/test_chore_engine.py` (new or extend existing)
     - Test Logic Adapters:
       - `is_single_claimer_mode()` — True for shared_first, rotation_simple, rotation_smart; False for independent, shared
       - `is_rotation_mode()` — True for rotation_simple, rotation_smart; False for shared_first, independent, shared
       - Updated `is_shared_chore()` — True for shared, shared_first, AND all rotation types
     - Test `get_chore_status_context()` — all 8 priority tiers with edge cases:
       - Approved takes precedence over everything
       - `not_my_turn` takes precedence over `missed` (P3 > P4)
       - `missed` takes precedence over `overdue` (P4 > P5)
       - `waiting` only applies when `claim_restriction_enabled`
       - `due` window boundaries (exactly at start, exactly at end)
       - **Steal exception**: `overdue_handling == at_due_date_allow_steal` + overdue → `not_my_turn` does NOT match → falls to `overdue`
       - **Non-steal rotation + overdue**: `rotation_simple` with relaxed overdue → `not_my_turn` still wins (P3 > P5)
     - Test `can_claim_chore()` — new blocking conditions:
       - Blocked when `missed`, `waiting`, `not_my_turn`
       - `at_due_date_allow_steal`: Blocked before overdue, unblocked after due date
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
       - Create `rotation_simple` + `at_due_date_allow_steal` → Let overdue → Non-turn kid claims → Verify accepted (steal window open)
       - Create `rotation_simple` + relaxed overdue (NOT allow_steal) → Let overdue → Non-turn kid claims → Verify REJECTED (no steal window, P3 still blocks)
       - `set_rotation_turn` service → Verify turn changed, signal emitted
       - `reset_rotation` service → Verify reset to `assigned_kids[0]`
       - `open_rotation_cycle` service → Verify override enables any kid to claim
       - Approve after override → Verify override cleared (D-15 dependent)
       - After steal → Verify turn advances from completer, not original turn-holder (D-18)
       - After pure miss → Midnight reset → Verify turn advances to next kid (D-17)
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

  3. **Validation rule tests**
     - File: `tests/test_data_builders.py` (extend)
     - V-01: `mark_missed_and_lock` + `upon_completion` reset → Validation error
     - V-01: `mark_missed_and_lock` + `at_midnight_once` → Valid
     - V-02: `claim_restriction_enabled=True` + no due_window_offset → Validation error
     - V-03: Any rotation type + only 1 assigned kid → Validation error (D-14 dependent)
     - V-05: `at_due_date_allow_steal` + non-rotation criteria → Validation error
     - V-05: `at_due_date_allow_steal` + rotation_simple + `at_midnight_multi` → Validation error
     - V-05: `at_due_date_allow_steal` + rotation_simple + `at_midnight_once` → Valid
     - V-05: `at_due_date_allow_steal` + no due date → Validation error

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
- **Rotation is a shared_first extension via Criteria Overload** (D-12): Rotation types (`rotation_simple`, `rotation_smart`) are `completion_criteria` values, not a separate field. The Logic Adapter pattern (`is_single_claimer_mode()`, `is_rotation_mode()`) prevents gremlin code — existing `shared_first` checks use the adapter and automatically include rotation types.
- **Steal is an overdue handling type** (D-06 revised): `at_due_date_allow_steal` is a 7th overdue handling value, NOT a completion criteria. The FSM P3 steal exception checks `overdue_handling == at_due_date_allow_steal` (not `criteria == rotation_steal`). This simplifies the criteria set (2 rotation types, not 3) and makes steal orthogonal to rotation type.
- **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` immutability guard at L784-788 is incorrect and must be removed. A `get_criteria_transition_actions()` engine method and `_handle_criteria_transition()` manager method handle field cleanup when criteria changes.
- **Two distinct "missed" strategies coexist**:
  - `clear_and_mark_missed` — Records miss stat, then resets to pending at approval boundary (existing)
  - `mark_missed_and_lock` — Records miss stat, locks state to `missed`, prevents further claims until midnight (new)
- **`at_due_date_allow_steal`** (D-06 revised) — At due date, lifts `not_my_turn` blocking for rotation chores. Any assigned kid can claim. Only the original turn-holder gets the overdue stat. After steal: turn advances from completer (D-18). After pure miss: turn advances to next kid at midnight (D-17).
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

| File                                                          | Change Type | Estimated Scope                                                                                                         |
| ------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| `const.py`                                                    | Modify      | ~28 new constants (2 rotation criteria + 1 overdue + states + services + attrs), remove rotation_steal, add allow_steal |
| `type_defs.py`                                                | Modify      | 3 new TypedDict fields                                                                                                  |
| `data_builders.py`                                            | Modify      | 3 new defaults + 4 validation rules (V-01 thru V-03, V-05). Remove old V-04 (rotation_steal due date).                  |
| `engines/chore_engine.py`                                     | Modify      | ~250 lines new (Logic Adapters + FSM + rotation helpers + transition helper)                                            |
| `managers/chore_manager.py`                                   | Modify      | ~350 lines new (rotation advancement, scanner, missed lock, criteria transition, + adapter adoption across 25 sites)    |
| `engines/stats_engine.py` or `managers/statistics_manager.py` | Modify      | ~30 lines (new query methods)                                                                                           |
| `managers/ui_manager.py`                                      | Modify      | ~40 lines (3-4 new dashboard attributes)                                                                                |
| `managers/notification_manager.py`                            | Modify      | ~40 lines (missed notification + steal-window-open notification to all assigned kids)                                   |
| `helpers/flow_helpers.py`                                     | Modify      | ~30 lines (new selectors/options — 2 rotation criteria + 7th overdue type)                                              |
| `options_flow.py`                                             | Modify      | ~20 lines (claim restriction + criteria transition + overdue validation V-05)                                           |
| `services.py`                                                 | Modify      | ~100 lines (3 new services + remove immutability guard + add criteria to update schema)                                 |
| `services.yaml`                                               | Modify      | ~30 lines (service descriptions)                                                                                        |
| `migration_pre_v50.py`                                        | Modify      | ~20 lines (v44 extension for new field backfill)                                                                        |
| `translations/en.json`                                        | Modify      | ~40 new keys, remove `rotation_steal` entries, add `at_due_date_allow_steal` entries, fix rotation descriptions         |
| `tests/test_chore_engine.py`                                  | New/Modify  | ~400 lines (adapters + FSM + rotation + transition)                                                                     |
| `tests/test_service_rotation.py`                              | New         | ~550 lines (rotation services + steal-via-overdue + criteria transition + claim restriction + missed lock)              |
| `tests/test_data_builders.py`                                 | Modify      | ~120 lines (V-01 thru V-03, V-05 including allow_steal combos)                                                          |
| `tests/test_migration.py`                                     | Modify      | ~50 lines                                                                                                               |
| `tests/test_ui_manager.py`                                    | Modify      | ~80 lines                                                                                                               |
