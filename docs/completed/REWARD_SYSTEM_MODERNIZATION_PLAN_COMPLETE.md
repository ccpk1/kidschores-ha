# Reward System Modernization Plan

**Status**: ✅ Complete (All 6 Phases Done)
**Created**: December 30, 2025
**Revised**: December 30, 2025
**Target Version**: v0.4.1+
**Progress**: All Phases Complete - Ready for Manual Testing & Release

---

## Executive Summary

Modernize the reward handling system to use period-based tracking (aligned with `chore_data` and `point_data` patterns) while preserving multi-claim behavior. Remove automatic midnight reset of pending reward claims. Use **Option A: Date-keyed counters** for historical tracking with retention cleanup.

---

## Design Decisions (Confirmed Dec 30, 2025)

| Question                | Decision                                                                            |
| ----------------------- | ----------------------------------------------------------------------------------- |
| Dual-write vs deprecate | **Deprecate after migration** - no dual-write, legacy fields only used in migration |
| Approved today display  | Use `last_approved` timestamp comparison (not `redeemed_rewards[]`)                 |
| Stats granularity       | **Per-reward stats** as sensor attributes                                           |
| Period boundaries       | **Calendar week/month** (ISO format: "2025-W01", "2025-01")                         |
| Reset approach          | **No automatic reset** - date-keyed counters auto-partition by period               |
| Cleanup                 | Reuse existing `cleanup_period_data()` helper from kc_helpers.py                    |

---

## Current vs Target State

| Aspect               | Current (Legacy)                                 | Target (Modern)                                          |
| -------------------- | ------------------------------------------------ | -------------------------------------------------------- |
| **Pending tracking** | `pending_rewards[]` list per kid                 | `reward_data[id].pending_count`                          |
| **Global queue**     | `DATA_PENDING_REWARD_APPROVALS` stored list      | Computed dynamically from `reward_data`                  |
| **Multi-claim**      | ✅ Supported (list allows duplicates)            | ✅ Supported (pending_count increment)                   |
| **Midnight reset**   | ❌ Clears all pending claims                     | ✅ Removed - claims persist until resolved               |
| **Statistics**       | Separate `reward_claims{}`, `reward_approvals{}` | Integrated in `reward_data[id].periods`                  |
| **Period stats**     | N/A                                              | `periods.daily["2025-12-30"].approved = 2`               |
| **Retention**        | N/A                                              | Uses `cleanup_period_data()` with configurable retention |

---

## Data Structure Design

### New: `reward_data` Structure (Per-Kid)

Aligns with existing `chore_data` and `point_data` patterns:

```python
# kid_info["reward_data"][reward_id] structure:
{
    # Pending workflow state
    "pending_count": 2,           # Pending claims awaiting approval
    "notification_ids": ["abc", "def"],  # For notification matching

    # Timestamps for display/filtering
    "last_claimed": "2025-12-30T10:00:00+00:00",
    "last_approved": "2025-12-29T15:30:00+00:00",
    "last_disapproved": None,

    # All-time counters (never reset)
    "total_claims": 5,
    "total_approved": 3,
    "total_disapproved": 1,
    "total_points_spent": 150,

    # Period-based historical data (date-keyed, with retention cleanup)
    "periods": {
        "daily": {
            "2025-12-30": {"claimed": 3, "approved": 2, "disapproved": 1, "points": 50},
            "2025-12-29": {"claimed": 1, "approved": 1, "disapproved": 0, "points": 25},
        },
        "weekly": {
            "2025-W01": {"claimed": 7, "approved": 5, "disapproved": 2, "points": 120},
        },
        "monthly": {
            "2025-12": {"claimed": 15, "approved": 12, "disapproved": 3, "points": 300},
        },
        "yearly": {
            "2025": {"claimed": 50, "approved": 45, "disapproved": 5, "points": 1100},
        },
    }
}
```

### Period ID Formats (Aligned with Existing Patterns)

| Period  | Format     | Example        |
| ------- | ---------- | -------------- |
| Daily   | ISO date   | `"2025-12-30"` |
| Weekly  | ISO week   | `"2025-W01"`   |
| Monthly | Year-month | `"2025-12"`    |
| Yearly  | Year       | `"2025"`       |

### Retention Cleanup Integration

```python
# After reward approval, call cleanup (same as chores):
kh.cleanup_period_data(
    coordinator=self,
    periods_data=reward_entry.get(const.DATA_KID_REWARD_DATA_PERIODS, {}),
    period_keys={
        "daily": const.DATA_KID_REWARD_DATA_PERIODS_DAILY,
        "weekly": const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY,
        "monthly": const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY,
        "yearly": const.DATA_KID_REWARD_DATA_PERIODS_YEARLY,
    },
    retention_daily=self.config_entry.options.get(const.CONF_RETENTION_DAILY, 7),
    retention_weekly=self.config_entry.options.get(const.CONF_RETENTION_WEEKLY, 5),
    retention_monthly=self.config_entry.options.get(const.CONF_RETENTION_MONTHLY, 3),
    retention_yearly=self.config_entry.options.get(const.CONF_RETENTION_YEARLY, 3),
)
```

### Computed Pending Approvals

```python
def get_pending_reward_approvals_computed(self) -> list[dict[str, Any]]:
    """Compute pending reward approvals dynamically from reward_data."""
    pending = []
    for kid_id, kid_info in self.kids_data.items():
        reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
        for reward_id, entry in reward_data.items():
            if reward_id not in self.rewards_data:
                continue  # Skip deleted rewards
            pending_count = entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
            if pending_count > 0:
                pending.append({
                    "kid_id": kid_id,
                    "reward_id": reward_id,
                    "pending_count": pending_count,
                    "timestamp": entry.get(const.DATA_KID_REWARD_DATA_LAST_CLAIMED, ""),
                    "notification_ids": entry.get(const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS, []),
                })
    return pending
```

---

## Implementation Phases

### Phase 1: Update Constants (const.py) ✅ COMPLETE

Previous work added basic constants, plus period-based constants aligned with `chore_data` and `point_data` patterns.

**Already Done:**

- [x] Add `DATA_KID_REWARD_DATA` base constant
- [x] Add `DATA_KID_REWARD_DATA_PENDING_COUNT`
- [x] Add `DATA_KID_REWARD_DATA_LAST_CLAIMED`
- [x] Add `DATA_KID_REWARD_DATA_LAST_APPROVED`
- [x] Add `DATA_KID_REWARD_DATA_LAST_DISAPPROVED`
- [x] Add `DATA_KID_REWARD_DATA_TOTAL_CLAIMS`
- [x] Add `DATA_KID_REWARD_DATA_TOTAL_APPROVED`
- [x] Add `DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT`

**Period Constants Added:**

- [x] Add `DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED`
- [x] Add `DATA_KID_REWARD_DATA_NOTIFICATION_IDS`
- [x] Add `DATA_KID_REWARD_DATA_PERIODS` = "periods"
- [x] Add `DATA_KID_REWARD_DATA_PERIODS_DAILY` = "daily"
- [x] Add `DATA_KID_REWARD_DATA_PERIODS_WEEKLY` = "weekly"
- [x] Add `DATA_KID_REWARD_DATA_PERIODS_MONTHLY` = "monthly"
- [x] Add `DATA_KID_REWARD_DATA_PERIODS_YEARLY` = "yearly"
- [x] Add `DATA_KID_REWARD_DATA_PERIOD_CLAIMED` = "claimed"
- [x] Add `DATA_KID_REWARD_DATA_PERIOD_APPROVED` = "approved"
- [x] Add `DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED` = "disapproved"
- [x] Add `DATA_KID_REWARD_DATA_PERIOD_POINTS` = "points"

### Phase 2: Revise Coordinator Methods (coordinator.py) ✅ COMPLETE

Revised to deprecate-after-migration pattern with period-based tracking.

**Methods Revised:**

- [x] `_get_kid_reward_data()` - Initialize full structure including periods dict
- [x] `_increment_reward_period_counter()` - NEW helper to increment all period buckets
- [x] `redeem_reward()` - Increment period `claimed` counter on claim, track notification_ids
- [x] `approve_reward()` - Increment period `approved` + `points`, call cleanup_period_data()
- [x] `disapprove_reward()` - Increment period `disapproved`, increment total_disapproved
- [x] `reset_rewards()` - Cleared of all legacy writes (only uses reward_data now)
- [x] `_award_badge()` - Updated to use reward_data for badge-granted rewards
- [x] `_reset_daily_reward_statuses()` - Now a no-op (period-based tracking is date-keyed)
- [x] `_cleanup_pending_reward_approvals()` - Updated to clean reward_data per kid
- [x] `_normalize_kid_reward_data()` - Renamed from `_normalize_kid_lists`, ensures reward_data exists
- [x] Notification resend check - Uses `reward_data.pending_count` instead of legacy `pending_rewards` list

**Kept These Changes:**

- [x] `get_pending_reward_approvals_computed()` - Already correct
- [x] `_create_kid()` - Initialize `reward_data: {}`
- [x] `pending_reward_approvals` property - Uses computed method

**Helper Added:**

- [x] `_get_kid_reward_data()` - Initialize structure for reward_id (updated with periods)
- [x] `_increment_reward_period_counter()` - NEW: Increment counters across all period buckets

**Remaining Legacy Usages (11 total - kept for migration compatibility):**

- Initialization code in `_first_refresh()` and `_create_kid()` that sets up empty legacy fields
- These are needed for backward compatibility with older data versions

### Phase 3: Migration (migration_pre_v42.py) ✅ COMPLETE

Migrate legacy fields to new structure. After migration, legacy fields are NOT written to.

- [x] Define migration function `_migrate_reward_data_to_periods()`
- [x] Migrate `pending_rewards[]` → `reward_data[id].pending_count`
- [x] Migrate `redeemed_rewards[]` → (used for approved today, can derive from timestamps)
- [x] Migrate `reward_claims{}` → `reward_data[id].total_claims`
- [x] Migrate `reward_approvals{}` → `reward_data[id].total_approved`
- [x] Helper method `_create_empty_reward_entry()` for initializing reward_data entries
- [x] Initialize `periods: {}` structure for each reward_id with history
- [x] No schema version bump (building for v42)

**Tests Updated:**

- [x] `test_service_redeem_reward_success` - Checks modern reward_data structure
- [x] `test_service_reset_rewards_all` - Uses reward_data instead of reward_claims

### Phase 4: Sensor Updates ✅ COMPLETE

Update sensors to use new data structure instead of legacy fields.

- [x] `KidRewardStatusSensor.native_value` - Use `reward_data.pending_count` for "Claimed" status
- [x] `KidRewardStatusSensor.native_value` - Use `last_approved` timestamp for "Approved today" display
- [x] `KidRewardStatusSensor.extra_state_attributes` - Use `reward_data.total_claims` and `total_approved`
- [x] `KidDashboardHelperSensor` - Update reward claims/approvals to use `reward_data` structure
- [x] Added `dt_util` import for timestamp comparison
- [ ] (Future) Update `extra_state_attributes` to expose per-reward period stats:
  - `claimed_today`, `claimed_this_week`, `claimed_this_month`
  - `approved_today`, `approved_this_week`, `approved_this_month`
  - `disapproved_today`, `disapproved_this_week`, `disapproved_this_month`
  - `points_spent_today`, `points_spent_this_week`, `points_spent_this_month`

### Phase 5: Button/Flow Updates ✅ COMPLETE

Buttons and flows already work correctly with modernized data:

- [x] Buttons call `coordinator.approve_reward()` and `coordinator.disapprove_reward()` - updated in Phase 2
- [x] Buttons use `coordinator.pending_reward_approvals` property - returns computed data from `reward_data`
- [x] No direct legacy constant usage in button.py, options_flow.py, or flow_helpers.py
- [x] config_flow.py no longer initializes legacy field (removed in Phase 6)

**Finding**: Buttons were already abstracted through coordinator methods and properties, so no direct code changes needed.

### Phase 6: Cleanup & Testing ✅ COMPLETE

**Legacy Field Cleanup:**

- [x] Remove `DATA_KID_PENDING_REWARDS` initialization from `_create_kid()` ✅
- [x] Remove `DATA_KID_REDEEMED_REWARDS` initialization from `_create_kid()` ✅
- [x] Remove `DATA_KID_REWARD_CLAIMS` initialization from `_create_kid()` ✅
- [x] Remove `DATA_KID_REWARD_APPROVALS` initialization from `_create_kid()` ✅
- [x] Remove `DATA_PENDING_REWARD_APPROVALS` initialization from `_first_refresh()` ✅
- [x] Renamed legacy constants to use `_DEPRECATED` suffix per standards:
  - `DATA_KID_PENDING_REWARDS` → `DATA_KID_PENDING_REWARDS_DEPRECATED` ✅
  - `DATA_KID_REDEEMED_REWARDS` → `DATA_KID_REDEEMED_REWARDS_DEPRECATED` ✅
  - `DATA_KID_REWARD_CLAIMS` → `DATA_KID_REWARD_CLAIMS_DEPRECATED` ✅
  - `DATA_KID_REWARD_APPROVALS` → `DATA_KID_REWARD_APPROVALS_DEPRECATED` ✅
  - `DATA_PENDING_REWARD_APPROVALS` → `DATA_PENDING_REWARD_APPROVALS_DEPRECATED` ✅

**Deprecated Constant Isolation (per ARCHITECTURE.md standards):**

Deprecated constants should ONLY exist in:

1. **const.py** - Constant definitions only
2. **migration_pre_v42.py** - Migration code that reads legacy data

Cleaned up unnecessary usages:

- [x] Removed `DATA_PENDING_REWARD_APPROVALS_DEPRECATED: []` from config_flow.py `_create_entry()` ✅
- [x] Removed `DATA_PENDING_REWARD_APPROVALS_DEPRECATED: []` from storage_manager.py default structure ✅
- [x] Removed dead `get_pending_reward_approvals()` method from storage_manager.py ✅
- [x] Updated test_storage_manager.py to use modern structure (not deprecated fields) ✅
- [x] Updated test_entity_naming_final.py mock to use modern `DATA_KID_REWARD_DATA` ✅

**Verification:**

```bash
grep -r "DATA_PENDING_REWARD_APPROVALS_DEPRECATED" --include="*.py" | sort
# Results: Only in const.py (5 definitions) and migration_pre_v42.py (5 usages for migration)
```

**Testing:**

- [x] Run full test suite to verify no regressions (679 passed, 17 skipped) ✅
- [x] Run linting (all checks passed) ✅
- [ ] Add/update tests for new behavior (future enhancement)
- [ ] Verify no midnight clearing of pending claims (manual testing needed)
- [ ] Verify period counters increment correctly (manual testing needed)
- [ ] Verify retention cleanup works (existing tests cover this)

---

## Behavioral Changes Summary

### What Changes:

1. **No midnight reset** - Pending reward claims persist until approved/disapproved
2. **Data structure** - From lists to period-based dict (aligned with chore_data pattern)
3. **Pending queue** - Computed dynamically instead of stored
4. **Period stats** - Track approvals per day/week/month/year (date-keyed)
5. **Retention cleanup** - Old period entries pruned using existing helper
6. **"Approved today" display** - Uses `last_approved` timestamp, not `redeemed_rewards[]`

### What Stays the Same:

1. **Multi-claim** - Kids can still claim same reward multiple times
2. **Points check** - Must have enough points to claim
3. **Approval flow** - Parents still approve/disapprove
4. **Notifications** - Same notification behavior

### Migration Approach:

1. **One-time migration** converts legacy fields to new structure
2. **Legacy fields deprecated** - Only used in migration script
3. **No dual-write** - After migration, only new structure is written

---

## Risk Assessment

| Risk                       | Impact | Mitigation                                          |
| -------------------------- | ------ | --------------------------------------------------- |
| Data migration failure     | High   | Backup before migration, test with sample data      |
| Dashboard breakage         | Medium | Update dashboard helper attributes                  |
| Button/sensor state issues | Medium | Comprehensive testing of state transitions          |
| Period ID format mismatch  | Low    | Use same format as chore_data (ISO date/week/month) |

---

## Definition of Done

- [x] Phase 1: All period constants added to const.py ✅
- [x] Phase 2: Coordinator methods use period-based structure (no dual-write) ✅
- [x] Phase 3: Migration converts legacy → modern structure ✅
- [x] Phase 4: Sensors use timestamps for display ✅
- [x] Phase 5: Buttons work with computed pending ✅
- [x] Phase 6: All tests pass ✅
- [x] `./utils/quick_lint.sh --fix` passes ✅
- [x] `python -m pytest tests/ -v --tb=line` passes (679 passed, 17 skipped) ✅
- [ ] Verified: Pending claims persist across midnight (manual testing needed)
- [ ] Verified: Multi-claim still works (covered by existing tests)
- [ ] Verified: Points check still enforced (covered by existing tests)
- [ ] Verified: Period counters increment correctly (manual testing needed)
- [ ] Verified: Retention cleanup works (covered by existing tests)
