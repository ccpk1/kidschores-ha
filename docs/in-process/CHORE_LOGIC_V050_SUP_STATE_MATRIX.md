# Supporting: Chore Logic v0.5.0 — Full FSM State Matrix

_Supporting document for [CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md)_

## 1. Per-Kid Calculated State Resolution Table

This table defines the **complete** priority-ordered state resolution for `get_chore_status_context()`. The engine evaluates conditions top-to-bottom; the first match wins.

| Priority | State         | Guard Conditions                                                                                                                  | `can_claim` | `lock_reason`   | Dashboard UX                                          |
| -------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------- | --------------- | ----------------------------------------------------- |
| 1        | `approved`    | `is_approved_in_current_period == True`                                                                                           | `False`     | `None`          | ✅ Green check. Task complete for this period.        |
| 2        | `claimed`     | `has_pending_claim == True`                                                                                                       | `False`     | `None`          | 🟠 Orange clock. Awaiting parent approval.            |
| 3        | `not_my_turn` | `rotation_type is not None` AND `kid_id != rotation_current_kid_id` AND `state != overdue` AND `rotation_cycle_override == False` | `False`     | `"not_my_turn"` | 🔒 Grey lock. Shows "Current Turn: [Name]".           |
| 4        | `missed`      | `overdue_handling == mark_missed_and_lock` AND `now > due_date` AND `due_date is not None`                                        | `False`     | `"missed"`      | 🔴 Red X. Terminal for this cycle.                    |
| 5        | `overdue`     | `overdue_handling in RELAXED_TYPES` AND `now > due_date` AND `due_date is not None`                                               | `True`      | `None`          | 🟡 Yellow warning. Late but claimable.                |
| 6        | `waiting`     | `claim_restriction_enabled == True` AND `due_window_start is not None` AND `now < due_window_start`                               | `False`     | `"waiting"`     | ⏳ Grey hourglass. Shows countdown to `available_at`. |
| 7        | `due`         | `due_window_start is not None` AND `now >= due_window_start` AND `now <= due_date`                                                | `True`      | `None`          | 🟢 Green pulse. Active window — claim now!            |
| 8        | `pending`     | Default (no other condition met)                                                                                                  | `True`      | `None`          | ⬜ Default. Ready/upcoming.                           |

### Relaxed Overdue Types (Priority 5)

These types transition to `overdue` but remain claimable:

- `at_due_date`
- `at_due_date_clear_at_approval_reset`
- `at_due_date_clear_immediate_on_late`
- `at_due_date_mark_missed_and_reset` _(renamed from clear_and_mark_missed per D-02)_

## 2. Rotation Interaction Matrix

How rotation states interact with other calculated states:

| Scenario                          | Rotation Type | Kid's Relation to Turn | Time vs Due Date    | Resolved State                                        |
| --------------------------------- | ------------- | ---------------------- | ------------------- | ----------------------------------------------------- |
| Simple, my turn, before due       | `simple`      | Current turn holder    | Before due          | `due` or `pending`                                    |
| Simple, not my turn, before due   | `simple`      | Not turn holder        | Before due          | `not_my_turn`                                         |
| Simple, not my turn, overdue      | `simple`      | Not turn holder        | After due (relaxed) | `not_my_turn` (Priority 3 > 5)                        |
| Steal, not my turn, before due    | `steal`       | Not turn holder        | Before due          | `not_my_turn`                                         |
| **Steal, not my turn, AFTER due** | `steal`       | Not turn holder        | After due           | `overdue` (steal lifts P3 restriction)                |
| Steal, my turn, after due         | `steal`       | Current turn holder    | After due           | `overdue`                                             |
| Smart, not my turn                | `smart`       | Not turn holder        | Any (before due)    | `not_my_turn`                                         |
| Any rotation, override active     | Any           | Any                    | Any                 | Override bypasses `not_my_turn` → fall through to P4+ |
| Any rotation, already approved    | Any           | Any                    | Any                 | `approved` (P1 always wins)                           |
| Any rotation, already claimed     | Any           | Any                    | Any                 | `claimed` (P2 always wins)                            |

### Key Steal Mechanic Detail

For `rotation_steal`, Priority 3 has an **additional guard**:

```
P3: not_my_turn IF rotation_type is not None
                AND kid_id != rotation_current_kid_id
                AND (rotation_type != "steal" OR now <= due_date)  ← STEAL EXCEPTION
                AND state != overdue
                AND rotation_cycle_override == False
```

When `rotation_type == "steal"` and `now > due_date`, the `not_my_turn` condition does NOT match, allowing the state to fall through to P5 (`overdue` / claimable).

## 3. Claim Restriction + Rotation Compound Scenarios

| Claim Restriction | Rotation            | Time Phase    | Resolved State                                                 |
| ----------------- | ------------------- | ------------- | -------------------------------------------------------------- |
| Enabled           | None                | Before window | `waiting`                                                      |
| Enabled           | None                | In window     | `due`                                                          |
| Enabled           | Simple, my turn     | Before window | `waiting` (P6 > P7, but P3 doesn't match because it's my turn) |
| Enabled           | Simple, not my turn | Before window | `not_my_turn` (P3 > P6)                                        |
| Enabled           | Simple, my turn     | In window     | `due`                                                          |
| Enabled           | Simple, not my turn | In window     | `not_my_turn` (P3 > P7)                                        |
| Disabled          | Simple, not my turn | Any           | `not_my_turn`                                                  |
| Enabled           | Steal, not my turn  | After due     | `overdue` (steal lifts P3)                                     |

## 4. Transition Triggers

What causes state transitions at runtime:

| From State      | To State        | Trigger                                     | Actor                             |
| --------------- | --------------- | ------------------------------------------- | --------------------------------- |
| `pending`       | `waiting`       | Time passes, recalculated on sensor update  | Scanner                           |
| `waiting`       | `due`           | `now >= due_window_start`, recalculated     | Scanner                           |
| `pending`/`due` | `claimed`       | Kid presses "Claim" button                  | Service call                      |
| `claimed`       | `approved`      | Parent approves                             | Service call                      |
| `claimed`       | `pending`       | Parent disapproves                          | Service call                      |
| `pending`/`due` | `overdue`       | `now > due_date` (relaxed policy)           | Scanner                           |
| `pending`/`due` | `missed`        | `now > due_date` (strict lock policy)       | Scanner                           |
| `missed`        | `pending`       | Midnight reset boundary                     | Midnight rollover                 |
| `overdue`       | `claimed`       | Kid claims late (relaxed)                   | Service call                      |
| `not_my_turn`   | `pending`/`due` | Turn advances to this kid                   | Approval of current turn holder   |
| `not_my_turn`   | `overdue`       | `rotation_steal` + `now > due_date`         | Scanner (steal lifts restriction) |
| `approved`      | `pending`       | Approval reset boundary (midnight/due_date) | Reset handler                     |

## 5. Global State Aggregation (for multi-kid chores)

The existing `compute_global_state()` aggregates per-kid states. With new states:

| Per-Kid States (across assigned kids)                                     | Global State                                                             |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| All `approved`                                                            | `approved`                                                               |
| Any `claimed`, rest various                                               | `claimed` (or `claimed_in_part` for SHARED)                              |
| All `not_my_turn` (impossible for rotation — only one kid is not current) | N/A                                                                      |
| Mix of `not_my_turn` + `pending`/`due`                                    | `pending` (the active kid's state dominates)                             |
| Any `missed` (for shared_first rotation)                                  | `missed` if current turn holder missed                                   |
| Mix of states (SHARED)                                                    | Follow existing precedence: overdue > approved_in_part > claimed_in_part |

**Note**: For rotation chores (shared_first), only the current turn holder's state is meaningful for the global state. Other kids' `not_my_turn` states are cosmetic.
