# Badge Evaluation Flow Analysis

> **Purpose**: Detailed analysis of badge handling in coordinator.py (lines 3941-4690) to understand data flow, storage patterns, and method interactions before optimization work.

---

## 1. Architecture Overview

### 1.1 Two-Tier Data Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ BADGE DATA (Static Configuration)                                           │
│ Location: self.badges_data[badge_id]                                       │
│ Purpose: Stores badge definition (name, type, thresholds, tracked chores)  │
│ Updated: Only when admin edits badge configuration                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ KID BADGE PROGRESS (Runtime State)                                          │
│ Location: self.kids_data[kid_id][DATA_KID_BADGE_PROGRESS][badge_id]        │
│ Purpose: Tracks per-kid, per-badge progress toward earning                 │
│ Updated: Every time _check_badges_for_kid() runs                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Storage Constants

| Constant                                   | Value                | Description                 |
| ------------------------------------------ | -------------------- | --------------------------- |
| `DATA_KID_BADGE_PROGRESS`                  | `"badge_progress"`   | Top-level key on kid record |
| `DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY`  | `"last_update_day"`  | ISO date of last evaluation |
| `DATA_KID_BADGE_PROGRESS_CRITERIA_MET`     | `"criteria_met"`     | Boolean: threshold reached  |
| `DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS` | `"overall_progress"` | Float 0.0-1.0 for UI        |
| `DATA_KID_BADGE_PROGRESS_STATUS`           | `"status"`           | `in_progress` or `earned`   |

---

## 2. Method Analysis

### 2.1 `_check_badges_for_kid(kid_id)` — Main Entry Point

**Location**: Lines 3952-4227

**Purpose**: Evaluate ALL badges for a single kid and update progress

**Called From**:

1. `update_kid_points()` — After points change (line 3519)
2. `approve_reward()` — After reward approval (line 3875)
3. `_award_badge()` — Recursive call after awarding (line 4690)
4. `_recalculate_all_badges()` — Global recalculation (line 5192)

**Flow**:

```
_check_badges_for_kid(kid_id)
    │
    ├─► _manage_badge_maintenance(kid_id)        # Initialize/reset progress
    ├─► _manage_cumulative_badge_maintenance()   # Cumulative-specific maintenance
    │
    └─► FOR each badge in self.badges_data:
            │
            ├─► Skip if kid not in assigned_to list
            │
            ├─► IF badge_type == CUMULATIVE:
            │       └─► _get_cumulative_badge_progress()
            │           └─► _award_badge() if criteria met
            │
            └─► ELSE (Periodic badge):
                    │
                    ├─► Get tracked_chores via _get_badge_in_scope_chores_list()
                    ├─► Lookup handler from target_type_handlers map
                    ├─► Call handler: _handle_badge_target_*()
                    │       ↓ Returns updated progress dict
                    ├─► Store: kid_info[DATA_KID_BADGE_PROGRESS][badge_id] = progress
                    └─► IF criteria_met AND not already earned:
                            └─► _award_badge(kid_id, badge_id)
```

**Key Pattern — Day-Boundary Rollover**:
All handlers check if `last_update_day != today`:

- If different day: Roll "today's" values into cycle accumulator
- Then: Calculate fresh "today" values from helper functions

---

### 2.2 `_get_badge_in_scope_chores_list(badge_info, kid_id)` — Chore Filtering

**Location**: Lines 4229-4273

**Purpose**: Get list of chore IDs this badge should evaluate

**Logic**:

```python
IF badge_type in INCLUDE_TRACKED_CHORES_BADGE_TYPES:
    IF badge has tracked_chores configured:
        RETURN intersection of (tracked_chores ∩ kid_assigned_chores)
    ELSE:
        RETURN all chores assigned to this kid
ELSE:
    RETURN empty list  # Cumulative badges don't track chores
```

**Data Read**:

- `badge_info[DATA_BADGE_TRACKED_CHORES][DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES]`
- `self.chores_data` — Full chores registry
- `chore_info[DATA_CHORE_ASSIGNED_KIDS]` — Per-chore assignment

---

### 2.3 Target Type Handler Map

**Location**: Lines 3973-4062

All 17 target types map to 4 handler functions:

| Handler                                 | Target Types          | Count |
| --------------------------------------- | --------------------- | ----- |
| `_handle_badge_target_points`           | POINTS, POINTS_CHORES | 2     |
| `_handle_badge_target_chore_count`      | CHORE_COUNT           | 1     |
| `_handle_badge_target_daily_completion` | DAYS\_\* variants     | 9     |
| `_handle_badge_target_streak`           | STREAK\_\* variants   | 5     |

---

### 2.4 `_handle_badge_target_points(...)` — Points Handler

**Location**: Lines 4275-4318

**Purpose**: Track accumulated points toward threshold

**Key Helper Call**:

```python
total_points_all_sources, total_points_chores, _, _, points_map, _, _ = (
    kh.get_today_chore_and_point_progress(kid_info, tracked_chores)
)
```

**Day Rollover Logic**:

```python
if last_update_day != today_local_iso:
    points_cycle_count += progress[POINTS_TODAY]   # Roll into accumulator
    progress[POINTS_TODAY] = 0                      # Reset today's counter
```

**Progress Fields Updated**:
| Field | Value |
|-------|-------|
| `POINTS_TODAY` | Points earned today |
| `POINTS_CYCLE_COUNT` | Accumulated from prior days |
| `CHORES_COMPLETED` | `{chore_id: points_today}` map |
| `TRACKED_CHORES` | Chore IDs being monitored |
| `OVERALL_PROGRESS` | `min((cycle + today) / threshold, 1.0)` |
| `CRITERIA_MET` | `(cycle + today) >= threshold` |

---

### 2.5 `_handle_badge_target_chore_count(...)` — Chore Count Handler

**Location**: Lines 4320-4363

**Purpose**: Track total chore completions toward threshold

**Key Helper Call**:

```python
_, _, chore_count_today, _, _, count_map, _ = (
    kh.get_today_chore_and_point_progress(kid_info, tracked_chores)
)
```

**Progress Fields Updated**:
| Field | Value |
|-------|-------|
| `CHORES_TODAY` | Chores completed today |
| `CHORES_CYCLE_COUNT` | Accumulated from prior days |
| `CHORES_COMPLETED` | `{chore_id: count_today}` map |
| `OVERALL_PROGRESS` | `min((cycle + today) / threshold, 1.0)` |
| `CRITERIA_MET` | `(cycle + today) >= threshold` |

---

### 2.6 `_handle_badge_target_daily_completion(...)` — Daily Completion Handler

**Location**: Lines 4365-4426

**Purpose**: Track number of DAYS where completion criteria was met

**Key Helper Call**:

```python
criteria_met, approved_count, total_count = (
    kh.get_today_chore_completion_progress(
        kid_info, tracked_chores,
        percent_required=percent_required,
        require_no_overdue=require_no_overdue,
        only_due_today=only_due_today,
        count_required=min_count,
    )
)
```

**Day Rollover Logic**:

```python
if last_update_day != today_local_iso:
    if progress[TODAY_COMPLETED]:
        days_cycle_count += 1           # Yesterday counted!
    progress[TODAY_COMPLETED] = False   # Reset for new day
```

**Progress Fields Updated**:
| Field | Value |
|-------|-------|
| `TODAY_COMPLETED` | Boolean: criteria met today |
| `DAYS_CYCLE_COUNT` | Number of days where criteria was met |
| `DAYS_COMPLETED` | `{iso_date: True}` historical record |
| `APPROVED_COUNT` | Today's approved chores count |
| `TOTAL_COUNT` | Today's total chores count |
| `OVERALL_PROGRESS` | `min((cycle + 1_if_today) / threshold, 1.0)` |
| `CRITERIA_MET` | `(cycle + 1_if_today) >= threshold` |

---

### 2.7 `_handle_badge_target_streak(...)` — Streak Handler

**Location**: Lines 4428-4505

**Purpose**: Track CONSECUTIVE days meeting criteria (streak breaks reset to 0)

**Key Helper Call**: Same as daily completion

**Day Rollover Logic** (More Complex):

```python
if last_update_day != today_local_iso:
    if progress[TODAY_COMPLETED]:
        yesterday_iso = adjust_datetime_by_interval(today, -1 day)
        if days_completed.get(yesterday_iso):
            streak += 1                 # Continue streak
        else:
            streak = 1 if criteria_met else 0  # Restart or break
    else:
        streak = 0                      # No completion yesterday = broken
    progress[TODAY_COMPLETED] = False
```

**Progress Fields Updated**:
| Field | Value |
|-------|-------|
| `TODAY_COMPLETED` | Boolean: criteria met today |
| `DAYS_CYCLE_COUNT` | **USED AS STREAK COUNT** |
| `DAYS_COMPLETED` | `{iso_date: True}` for streak continuity check |
| `OVERALL_PROGRESS` | `min(streak / threshold, 1.0)` |
| `CRITERIA_MET` | `streak >= threshold` |

**Critical Insight**: `DAYS_COMPLETED` dict is REQUIRED for streak validation — it's checked to see if yesterday was completed.

---

### 2.8 `_award_badge(kid_id, badge_id)` — Badge Awarding

**Location**: Lines 4507-4690

**Purpose**: Grant badge to kid, process rewards/bonuses/points, notify

**Updates**:

1. Badge record: `badge_info[DATA_BADGE_EARNED_BY].append(kid_id)`
2. Kid record: Via `_update_badges_earned_for_kid()`
3. Awards processing: Points, multipliers, rewards, bonuses
4. Notifications: Kid and parent notifications

**Recursive Call**: Calls `_check_badges_for_kid(kid_id)` at end to re-evaluate in case new state unlocks more badges.

---

## 3. Helper Functions (kc_helpers.py)

### 3.1 `get_today_chore_and_point_progress(kid_info, tracked_chores)`

**Location**: kc_helpers.py line 323

**Purpose**: Get TODAY's points/chores/streak from kid's chore data

**Data Source**: `kid_info[DATA_KID_CHORE_DATA][chore_id][DATA_KID_CHORE_DATA_PERIODS][daily][today_iso]`

**Returns**:

```python
(
    total_points_all_sources,  # From kid's point_stats
    total_points_chores,       # Sum of points from tracked chores today
    total_chore_count,         # Count of completions today
    longest_chore_streak,      # Longest streak from any chore
    points_per_chore,          # {chore_id: points}
    count_per_chore,           # {chore_id: count}
    streak_per_chore,          # {chore_id: streak}
)
```

**Performance Note**: Iterates `tracked_chores` list and does dict lookups for each.

---

### 3.2 `get_today_chore_completion_progress(kid_info, tracked_chores, **kwargs)`

**Location**: kc_helpers.py line 400

**Purpose**: Check if completion criteria is met for TODAY

**Data Source**:

- `kid_info[DATA_KID_APPROVED_CHORES]` — List of approved chore IDs
- `kid_info[DATA_KID_OVERDUE_CHORES]` — List of overdue chore IDs
- `kid_info[DATA_KID_CHORE_DATA][chore_id]` — For due dates and overdue timestamps

**Logic**:

1. If `only_due_today`: Filter to chores due today
2. Count approved chores from filtered list
3. Check count_required OR percent_required
4. If `require_no_overdue`: Check no chore went overdue today

**Returns**: `(criteria_met: bool, approved_count: int, total_count: int)`

---

## 4. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         BADGE EVALUATION TRIGGER                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  update_kid_points()  │  approve_reward()  │  _award_badge()  │  manual recalc  │
└────────────┬────────────────────┬────────────────────┬────────────────┬─────────┘
             │                    │                    │                │
             └────────────────────┴────────────────────┴────────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │   _check_badges_for_kid()    │
                           │        (main entry)          │
                           └──────────────┬───────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
              ▼                           ▼                           ▼
    ┌─────────────────┐       ┌─────────────────────┐     ┌─────────────────────┐
    │  Maintenance    │       │  Get Tracked Chores │     │   Handler Lookup    │
    │  Functions      │       │  (scope filtering)  │     │   (17 target types) │
    └────────┬────────┘       └─────────┬───────────┘     └──────────┬──────────┘
             │                          │                            │
             │                          └────────────┬───────────────┘
             │                                       │
             │                                       ▼
             │                         ┌─────────────────────────────────┐
             │                         │  Handler: _handle_badge_*()     │
             │                         │  ┌───────────────────────────┐  │
             │                         │  │ 1. Call kc_helpers to get │  │
             │                         │  │    TODAY's data           │  │
             │                         │  │ 2. Check day rollover     │  │
             │                         │  │ 3. Update progress fields │  │
             │                         │  │ 4. Calculate criteria_met │  │
             │                         │  └───────────────────────────┘  │
             │                         └──────────────┬──────────────────┘
             │                                        │
             │                                        ▼
             │                         ┌─────────────────────────────────┐
             │                         │  Store progress in kid record   │
             │                         │  kid_info[badge_progress][id]   │
             │                         └──────────────┬──────────────────┘
             │                                        │
             │                                        ▼
             │                         ┌─────────────────────────────────┐
             │                         │  IF criteria_met AND not earned │
             │                         │  └──► _award_badge()            │
             │                         └─────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                    STORAGE LOCATIONS                               │
    ├────────────────────────────────────────────────────────────────────┤
    │  Kid Badge Progress:                                               │
    │    self.kids_data[kid_id]["badge_progress"][badge_id] = {         │
    │        "last_update_day": "2025-12-23",                           │
    │        "points_today": 50,                                         │
    │        "points_cycle_count": 200,                                  │
    │        "chores_today": 3,                                          │
    │        "chores_cycle_count": 15,                                   │
    │        "days_cycle_count": 5,  (or streak count for streak badges)│
    │        "today_completed": true,                                    │
    │        "days_completed": {"2025-12-22": true, "2025-12-21": true}, │
    │        "overall_progress": 0.75,                                   │
    │        "criteria_met": false,                                      │
    │        "status": "in_progress",                                    │
    │        "tracked_chores": ["chore-uuid-1", "chore-uuid-2"],        │
    │        ...                                                         │
    │    }                                                               │
    │                                                                    │
    │  Badge Earned Record:                                              │
    │    self.badges_data[badge_id]["earned_by"] = [kid_id1, kid_id2]   │
    └────────────────────────────────────────────────────────────────────┘
```

---

## 5. Performance Implications

### 5.1 Current Bottlenecks

| Operation                                  | Frequency              | Cost                                     |
| ------------------------------------------ | ---------------------- | ---------------------------------------- |
| `_check_badges_for_kid()`                  | On EVERY points change | Loops all badges × 2 helper calls each   |
| `_get_badge_in_scope_chores_list()`        | Per badge              | Loops all chores to filter               |
| `kh.get_today_chore_and_point_progress()`  | Per badge              | Loops tracked_chores, nested dict access |
| `kh.get_today_chore_completion_progress()` | Per badge              | Similar iteration + date checks          |

### 5.2 Key Insight: Incremental Model

**The system DOES use incremental tracking**:

- Progress accumulators (`*_cycle_count`) persist across days
- Day rollover only adds today's value to accumulator
- Helper functions only read TODAY's data, not historical

**However, redundant work occurs**:

1. Same helper functions called multiple times per kid (once per badge)
2. `_get_badge_in_scope_chores_list()` filters chores repeatedly
3. `get_today_chore_and_point_progress()` iterates chores for each badge

### 5.3 Optimization Opportunity

**Pre-calculate ONCE per kid**:

```python
# Instead of calling helpers per-badge, compute once:
today_stats = {
    "points_all_sources": int,
    "points_from_chores": int,
    "chore_count": int,
    "approved_chores": set,
    "overdue_chores": set,
    "chores_due_today": set,
    "per_chore_data": {chore_id: {points, count, streak, was_overdue_today}}
}
```

Then handlers just read from this pre-computed structure.

---

## 6. Summary Table: Methods and Data

| Method                                  | Reads                       | Writes                     | Calls                                                                             |
| --------------------------------------- | --------------------------- | -------------------------- | --------------------------------------------------------------------------------- |
| `_check_badges_for_kid`                 | `badges_data`, `kids_data`  | `kid[badge_progress]`      | maintenance funcs, handlers, `_award_badge`                                       |
| `_get_badge_in_scope_chores_list`       | `badge_info`, `chores_data` | Nothing                    | —                                                                                 |
| `_handle_badge_target_points`           | `kid_info` via helper       | `progress` dict (returned) | `kh.get_today_chore_and_point_progress`                                           |
| `_handle_badge_target_chore_count`      | `kid_info` via helper       | `progress` dict (returned) | `kh.get_today_chore_and_point_progress`                                           |
| `_handle_badge_target_daily_completion` | `kid_info` via helper       | `progress` dict (returned) | `kh.get_today_chore_completion_progress`                                          |
| `_handle_badge_target_streak`           | `kid_info` via helper       | `progress` dict (returned) | `kh.get_today_chore_completion_progress`                                          |
| `_award_badge`                          | `badges_data`, `kids_data`  | Both badge and kid records | `_update_badges_earned_for_kid`, notifications, recursive `_check_badges_for_kid` |

---

## 7. Questions Answered

### Q: Does badge evaluation scan history?

**A: NO** — Handlers call helpers that read only TODAY's data from `kid_info`. Progress accumulators persist the historical state.

### Q: Where is progress stored?

**A**: `self.kids_data[kid_id]["badge_progress"][badge_id]` — A dict per badge per kid.

### Q: When is progress incremented?

**A**: On day rollover — when `last_update_day != today`, the handler adds today's value to the cycle accumulator before resetting today's counter.

### Q: What triggers badge checks?

**A**: Points changes, reward approvals, badge awards (recursive), and manual recalculation.

### Q: Why is streak special?

**A**: Streak handlers use `days_completed` dict to verify yesterday was completed. If not, streak resets to 0. This dict grows over time (potential cleanup needed).

---

## 8. Next Steps for Optimization

1. **Pre-compute per-kid daily stats** before badge loop
2. **Cache chore filtering** results across badges with same scope
3. **Consider batching** badge checks instead of per-event triggers
4. **Prune `days_completed` dict** to prevent unbounded growth
5. **Profile helper functions** to identify hotspots

---

_Document created: 2025-12-23_
_For: Phase 1 Badge Optimization Planning_
