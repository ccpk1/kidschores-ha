# Supporting: Chore Logic v0.5.0 — Full FSM State Matrix

_Supporting document for [CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md)_
_Updated 2026-02-11: All 16 decisions reflected. See also [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md) for implementation specs._

## 1. Per-Kid Calculated State Resolution Table

This table defines the **complete** priority-ordered state resolution for `resolve_kid_chore_state()`. The engine evaluates conditions top-to-bottom; the first match wins.

| Priority | State         | Guard Conditions                                                                                                                                                            | `can_claim` | `lock_reason`   | Dashboard UX                                          |
| -------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | --------------- | ----------------------------------------------------- |
| 1        | `approved`    | `is_approved_in_current_period == True`                                                                                                                                     | `False`     | `None`          | ✅ Green check. Task complete for this period.        |
| 2        | `claimed`     | `has_pending_claim == True`                                                                                                                                                 | `False`     | `None`          | 🟠 Orange clock. Awaiting parent approval.            |
| 3        | `not_my_turn` | `is_rotation_mode(chore)` AND `kid_id != rotation_current_kid_id` AND NOT (`rotation_steal` AND `now > due_date`) AND `rotation_cycle_override == False`                    | `False`     | `"not_my_turn"` | 🔒 Grey lock. Shows "Current Turn: [Name]".           |
| 4        | `missed`      | `overdue_handling == mark_missed_and_lock` AND `now > due_date` AND `due_date is not None`                                                                                  | `False`     | `"missed"`      | 🔴 Red X. Terminal for this cycle — midnight resets.  |
| 5        | `overdue`     | `overdue_handling in RELAXED_TYPES` AND `now > due_date` AND `due_date is not None`                                                                                         | `True`      | `None`          | 🟡 Yellow warning. Late but claimable.                |
| 6        | `waiting`     | `claim_restriction_enabled == True` AND `due_window_start is not None` AND `now < due_window_start`                                                                         | `False`     | `"waiting"`     | ⏳ Grey hourglass. Shows countdown to `available_at`. |
| 7        | `due`         | `due_window_start is not None` AND `now >= due_window_start` AND `now <= due_date`                                                                                          | `True`      | `None`          | 🟢 Green pulse. Active window — claim now!            |
| 8        | `pending`     | Default (no other condition met)                                                                                                                                            | `True`      | `None`          | ⬜ Default. Ready/upcoming.                           |

### Relaxed Overdue Types (Priority 5)

These types transition to `overdue` but remain claimable:

- `at_due_date`
- `at_due_date_clear_at_approval_reset`
- `at_due_date_clear_immediate_on_late`
- `at_due_date_clear_and_mark_missed` _(existing: records miss then resets to pending at boundary)_

### Strict Overdue Type (Priority 4)

- `at_due_date_mark_missed_and_lock` _(NEW D-02: records miss, locks state, only midnight resets)_

## 2. Rotation Interaction Matrix

How rotation states interact with other calculated states. **Logic Adapter** (`is_single_claimer_mode()`, `is_rotation_mode()`) determines behavioral category (D-12). All rotation types require ≥ 2 assigned kids (D-14).

| Scenario                          | Rotation Type | Kid's Relation to Turn | Time vs Due Date    | Override | Resolved State                                                       |
| --------------------------------- | ------------- | ---------------------- | ------------------- | -------- | -------------------------------------------------------------------- |
| Simple, my turn, before due       | `simple`      | Current turn holder    | Before due          | N/A      | `due` or `pending`                                                   |
| Simple, not my turn, before due   | `simple`      | Not turn holder        | Before due          | `False`  | `not_my_turn`                                                        |
| Simple, not my turn, overdue      | `simple`      | Not turn holder        | After due (relaxed) | `False`  | `not_my_turn` (P3 > P5)                                             |
| Steal, not my turn, before due    | `steal`       | Not turn holder        | Before due          | `False`  | `not_my_turn`                                                        |
| **Steal, not my turn, AFTER due** | `steal`       | Not turn holder        | After due           | `False`  | `overdue` (**steal exception**: P3 skips → falls to P5)             |
| Steal, my turn, after due         | `steal`       | Current turn holder    | After due           | N/A      | `overdue`                                                            |
| Smart, not my turn                | `smart`       | Not turn holder        | Any (before due)    | `False`  | `not_my_turn`                                                        |
| Any rotation, override active     | Any           | Not turn holder        | Any                 | `True`   | **Override bypasses P3** → fall through to P4+ (D-15)               |
| Any rotation, already approved    | Any           | Any                    | Any                 | Any      | `approved` (P1 always wins)                                         |
| Any rotation, already claimed     | Any           | Any                    | Any                 | Any      | `claimed` (P2 always wins)                                          |
| Override + approve                | Any           | Any (override active)  | N/A                 | `True`   | After approval: **override cleared** → `rotation_cycle_override = False` (D-15) |

### Key Steal Mechanic Detail

For `rotation_steal`, Priority 3 has an **additional guard**:

```
P3: not_my_turn IF is_rotation_mode(chore)
                AND kid_id != rotation_current_kid_id
                AND NOT (criteria == rotation_steal AND now > due_date)  ← STEAL EXCEPTION
                AND rotation_cycle_override == False
```

When `rotation_type == "steal"` and `now > due_date`, the `not_my_turn` condition does NOT match, allowing the state to fall through to P5 (`overdue` / claimable).

### Override Lifecycle (D-15)

```
open_rotation_cycle service → rotation_cycle_override = True
  → Any kid can claim (P3 bypassed)
  → Parent approves
  → _advance_rotation() runs
  → rotation_cycle_override = False (automatic, D-15)
  → Normal turn-based rotation resumes
```

## 3. Claim Restriction + Rotation Compound Scenarios

| Claim Restriction | Rotation            | Time Phase    | Override | Resolved State                                                  |
| ----------------- | ------------------- | ------------- | -------- | --------------------------------------------------------------- |
| Enabled           | None                | Before window | N/A      | `waiting`                                                       |
| Enabled           | None                | In window     | N/A      | `due`                                                           |
| Enabled           | Simple, my turn     | Before window | N/A      | `waiting` (P6 matches — my turn so P3 doesn't apply)           |
| Enabled           | Simple, not my turn | Before window | `False`  | `not_my_turn` (P3 > P6)                                         |
| Enabled           | Simple, my turn     | In window     | N/A      | `due`                                                           |
| Enabled           | Simple, not my turn | In window     | `False`  | `not_my_turn` (P3 > P7)                                         |
| Disabled          | Simple, not my turn | Any           | `False`  | `not_my_turn`                                                   |
| Enabled           | Steal, not my turn  | After due     | `False`  | `overdue` (steal lifts P3)                                      |
| Enabled           | Any, not my turn    | Any           | `True`   | Override lifts P3 → falls to P4/5/6/7/8 per time phase         |

## 4. Transition Triggers

What causes state transitions at runtime:

| From State      | To State        | Trigger                                        | Actor                                          |
| --------------- | --------------- | ---------------------------------------------- | ---------------------------------------------- |
| `pending`       | `waiting`       | Time passes, recalculated on sensor update     | Scanner / sensor poll                          |
| `waiting`       | `due`           | `now >= due_window_start`, recalculated        | Scanner / sensor poll                          |
| `pending`/`due` | `claimed`       | Kid presses "Claim" button                     | Service call (gated by `can_claim`)            |
| `claimed`       | `approved`      | Parent approves                                | Service call → `_advance_rotation()` if needed |
| `claimed`       | `pending`       | Parent disapproves                             | Service call                                   |
| `pending`/`due` | `overdue`       | `now > due_date` (relaxed policy)              | Scanner                                        |
| `pending`/`due` | `missed`        | `now > due_date` (strict `mark_missed_and_lock`) | Scanner (D-02)                               |
| `missed`        | `pending`       | Midnight reset boundary                        | Midnight rollover (only exit path, D-03)       |
| `overdue`       | `claimed`       | Kid claims late (relaxed)                      | Service call                                   |
| `not_my_turn`   | `pending`/`due` | Turn advances to this kid                      | Approval of current turn holder → `_advance_rotation()` |
| `not_my_turn`   | `overdue`       | `rotation_steal` + `now > due_date`            | Scanner (steal lifts P3 restriction)           |
| `not_my_turn`   | `pending`/`due` | `open_rotation_cycle` service called           | Override → P3 bypassed                         |
| `approved`      | `pending`       | Approval reset boundary (midnight/due_date)    | Reset handler                                  |

### Rotation-Specific Transitions

| Trigger                         | Action on Rotation State                                                        |
| ------------------------------- | ------------------------------------------------------------------------------- |
| Kid approved (any rotation)     | `_advance_rotation()`: next turn calculated, override cleared (D-15)            |
| Kid missed (turn holder, midnight reset) | Turn auto-advances to next kid after midnight unlock                    |
| Kid deleted (was turn holder)   | Turn set to `remaining_kids[0]` (resilience)                                    |
| `set_rotation_turn` service     | Manual override of current turn holder                                          |
| `reset_rotation` service        | Reset to `assigned_kids[0]`, clear override                                     |
| `open_rotation_cycle` service   | `rotation_cycle_override = True` → any kid can claim                            |
| Criteria change → rotation      | `rotation_current_kid_id = assigned_kids[0]`, `override = False` (D-11 transition) |
| Criteria change → non-rotation  | `rotation_current_kid_id = None`, `override = False` (D-11 transition)          |

## 5. Global State Aggregation (for multi-kid chores)

The existing `compute_global_state()` aggregates per-kid states. With new states:

| Per-Kid States (across assigned kids)                                     | Global State                                                             |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| All `approved`                                                            | `approved`                                                               |
| Any `claimed`, rest various                                               | `claimed` (or `claimed_in_part` for SHARED)                              |
| Mix of `not_my_turn` + `pending`/`due`                                    | **Turn-holder's state dominates** (other kids' `not_my_turn` is cosmetic) |
| Current turn kid is `missed`                                              | `missed` (turn holder's state is authoritative for rotation)             |
| Mix of states (SHARED)                                                    | Follow existing precedence: overdue > approved_in_part > claimed_in_part |

**Note**: For rotation chores (`is_rotation_mode()`), `compute_global_state()` should prioritize the **current turn holder's** state. Other kids' `not_my_turn` states are purely cosmetic display states and should not affect the global aggregation.

## 6. Criteria Mutability — Transition Matrix (D-11)

When `completion_criteria` changes via edit, the engine computes field changes:

| Old Category    | New Category    | Field Changes                                                                       |
| --------------- | --------------- | ----------------------------------------------------------------------------------- |
| Non-rotation    | Rotation        | Set `rotation_current_kid_id = assigned_kids[0]`, `rotation_cycle_override = False` |
| Rotation        | Non-rotation    | Clear `rotation_current_kid_id = None`, `rotation_cycle_override = False`           |
| Rotation        | Diff. Rotation  | **Keep existing turn** — no field changes (seamless type switch)                    |
| Same category   | Same category   | No field changes                                                                    |

**Validation on transition**: Switching TO any rotation type validates V-03 (≥ 2 kids). Switching TO `rotation_steal` validates V-04 (due date required).
