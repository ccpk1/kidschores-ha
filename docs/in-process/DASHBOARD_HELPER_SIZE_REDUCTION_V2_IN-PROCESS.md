# Dashboard Helper Sensor Size Reduction Initiative (v2)

**Initiative Code**: DHS-SIZE-01  
**Target Release**: v0.5.1  
**Owner**: Strategic Planning Agent  
**Status**: Planning - Ready for Implementation  
**Created**: 2026-01-11  
**Updated**: 2026-01-11 (Revised after analysis)

---

## Executive Summary 📊

**Problem**: Dashboard helper sensor exceeds Home Assistant's 16KB attribute limit at 25+ chores  
**Root Cause**: Chores list with 16 attributes per chore accounts for **71.8%** of sensor size  
**Recommended Solution**: Minimal chore attributes (Option 1A) - reduce from 16 → 6 fields  
**Expected Impact**: 67% per-chore reduction, 48% total size reduction, supports 70+ chores vs current 23

### Critical Insight: Don't Duplicate What Already Exists ✅

Each chore status sensor (`sensor.kc_kid_chore_name`) already has ALL display data:
- Due dates, timestamps, streaks, points
- Button entity IDs, can_claim/can_approve flags  
- Labels, descriptions, configuration

**Dashboard helper only needs fields for sorting/filtering**, not display!

---

## Problem Statement

The `sensor.kc_<kid>_ui_dashboard_helper` sensor is hitting Home Assistant's 16KB attribute size limit, causing the recorder to reject it with warnings in logs. This affects users with 23+ chores.

**Current Size (with 25 chores)**:
- Dashboard helper: **17,256 bytes** (exceeds 16KB by 872 bytes / 5.3%)
  - `chores`: **12,387 bytes (71.8%)** 🔴 PRIMARY BOTTLENECK
  - `ui_translations`: **4,681 bytes (27.1%)** 🟢 MANAGEABLE
  - Other attributes: **188 bytes (1.1%)**

**Per-Chore Overhead**:
- Current: 16 attributes = **494 bytes** per chore
- Many fields duplicate data already on chore sensors

---

## Strategic Options Analysis

### Option 1A: Minimal Chore Attributes ⭐⭐⭐ RECOMMENDED

**Approach**: Keep chores in dashboard helper but reduce attributes from 16 → 6 fields. Dashboard fetches remaining details from individual chore sensors via `state_attr(chore.eid, 'field')`.

**Why This Works**: 
- Chore status sensors already have all display data (due_date, streaks, timestamps, buttons)
- Dashboard helper only needs fields for **sorting/filtering**, not display
- Leverages existing data instead of duplicating it

**Minimal Chore Attributes** (6 fields, 164 bytes each):
```json
{
  "eid": "sensor.kc_sarah_chore_take_out_trash",
  "name": "Take out Trash",
  "status": "pending",
  "labels": ["Kitchen", "Evening"],
  "primary_group": "today",
  "is_today_am": false
}
```

**Why These 6 Fields?**

| Field | Purpose | Available on Chore Sensor? |
|-------|---------|---------------------------|
| `eid` | Lookup the chore sensor for full details | N/A (is the sensor) |
| `name` | Display in list | ✅ Yes (`chore_name`) |
| `status` | Color coding & grouping (pending/claimed/approved/overdue) | ❌ Computed only |
| `labels` | Filter chores by label | ✅ Yes, but needed for filtering |
| `primary_group` | Group into today/this_week/other sections | ❌ Computed only |
| `is_today_am` | Sort into AM/PM subgroups | ❌ Computed only |

**Fields Moved to Chore Sensor Lookups** (10 removed fields):
- `due_date` → `state_attr(chore.eid, 'due_date')`
- `claimed_by` → `state_attr(chore.eid, 'claimed_by')` (SHARED_FIRST chores)
- `completed_by` → `state_attr(chore.eid, 'completed_by')` (SHARED chores)
- `approval_reset_type` → `state_attr(chore.eid, 'approval_reset_type')`
- `last_approved` → `state_attr(chore.eid, 'last_approved')`
- `last_claimed` → `state_attr(chore.eid, 'last_claimed')`
- `approval_period_start` → `state_attr(chore.eid, 'approval_period_start')`
- `can_claim` → `state_attr(chore.eid, 'can_claim')`
- `can_approve` → `state_attr(chore.eid, 'can_approve')`
- `completion_criteria` → `state_attr(chore.eid, 'completion_criteria')`

**Impact**:
| Metric | Current | After Option 1A | Improvement |
|--------|---------|-----------------|-------------|
| **Per-chore size** | 494 bytes | 164 bytes | **67% reduction** |
| **25 chores total** | 17,256 bytes | 9,006 bytes | **48% reduction** |
| **Max chores** | 23 chores | 70 chores | **3x capacity** |
| **Headroom** | -872 bytes | +7,378 bytes | ✅ **Plenty** |

**Dashboard YAML Changes**:
- Update chores card template (~10-15 lines)
- Change from `chore.due_date` to `state_attr(chore.eid, 'due_date')`
- All other cards unchanged

**Pros**:
- ✅ Massive size reduction (67% per chore)
- ✅ No new sensors needed
- ✅ Data already exists on chore sensors
- ✅ Solves 16KB limit for 99% of users (70 chores max)
- ✅ Keeps everything in dashboard helper (simpler architecture)
- ✅ Minimal backend changes (just remove fields from calculation)

**Cons**:
- Dashboard templates need updates (~10-15 Jinja2 changes)
- Slightly more template lookups (negligible performance impact)
- Must carefully preserve computed fields (status, primary_group, is_today_am)

**Risk**: Low - Chore sensors guaranteed to exist (dashboard helper created last)

**ROI**: **45** (Highest benefit with minimal complexity)

---

### Option 1B: Move Chores to KidChoresSensor (Alternative)

**Approach**: Move entire `chores` list from dashboard helper to `KidChoresSensor` attributes.

**Why Reconsider This**: Both sensors have the same 16KB limit!

**Impact**:
- **Savings**: 3,815 bytes (move from 4.9KB overhead to 1KB overhead)
- **Capacity**: 23 → 30 chores max (modest improvement)
- **Dashboard changes**: Fetch chores from separate sensor

**Analysis**: Option 1A is superior - reduces duplication instead of moving it.

**ROI**: **20** (Some benefit, but Option 1A is 2x better)

---

### Option 2: Also Move Badges to Badge Sensors (Additive)

**Approach**: After Option 1A, move `badges` list to badge sensors if still hitting limits.

**Impact**:
- **Size reduction**: ~1-2KB additional
- **Total capacity**: 70 → 80+ chores

**When to use**: Only if Option 1A insufficient (affects <1% of users)

**ROI**: **15** (Minor benefit for edge cases)

---

### Option 3: Translation Optimization (NOT RECOMMENDED)

**Approach**: Reduce translation overhead (separate sensor, caching, compression).

**Impact**:
- **Size reduction**: ~4.7KB (27% of total)
- **Capacity gain**: +4 chores (16% increase)

**Why NOT Recommended**: 10x less benefit than Option 1A, significant complexity.

**ROI**: **5** (High effort, low benefit)

---

## Recommended Implementation Plan

**Phase 1: Backend Minimal Chore Attributes** (Days 1-2)

Goal: Modify dashboard helper to output minimal 6-field chore objects.

Steps:
- [ ] Update `_calculate_chore_attributes()` in `sensor.py` (~line 2760)
  - Keep: eid, name, status, labels, primary_group, is_today_am
  - Remove: 10 fields now on chore sensors
- [ ] Test with 10, 25, 50 chore scenarios
- [ ] Verify size reduction: 25 chores should be ~9KB total
- [ ] Run `./utils/quick_lint.sh --fix`, `mypy`, `pytest`

**Phase 2: Dashboard YAML Updates** (Days 3-4)

Goal: Update dashboard templates to fetch from `state_attr(chore.eid, 'field')`.

Steps:
- [ ] Update chores card template (`kc_dashboard_all.yaml` lines 82-503)
  - Replace `chore.due_date` with `state_attr(chore.eid, 'due_date')`
  - Replace `chore.can_claim` with `state_attr(chore.eid, 'can_claim')`
  - Replace `chore.can_approve` with `state_attr(chore.eid, 'can_approve')`
  - Replace `chore.last_approved` with `state_attr(chore.eid, 'last_approved')`
  - Replace `chore.completion_criteria` with `state_attr(chore.eid, 'completion_criteria')`
  - ~10-15 total replacements
- [ ] Update approval actions card (uses pending_approvals, not chores list - no changes needed)
- [ ] Test rendering with Jinja2 template tool
- [ ] Verify all chore details still display correctly

**Phase 3: Testing & Validation** (Day 5)

Goal: Ensure no regressions across user scenarios.

Steps:
- [ ] Test with 10 chores (typical user)
- [ ] Test with 25 chores (current failure point)
- [ ] Test with 50 chores (power users)
- [ ] Test with 70 chores (new capacity limit)
- [ ] Monitor sensor sizes in diagnostics
- [ ] Check for recorder warnings in logs
- [ ] Verify dashboard cards render correctly (all chore details visible)
- [ ] Test label filtering still works
- [ ] Test grouping (today/this_week/other, AM/PM) still works

**Phase 4: Documentation** (Day 6)

Goal: Communicate changes to users.

Steps:
- [ ] Update CHANGELOG.md
  - Breaking change: Dashboard v0.5.1 requires integration v0.5.1+
  - Note: Custom dashboards must update chore attribute lookups
- [ ] Create migration snippet for custom dashboards
- [ ] Update integration diagnostics to report sensor sizes
- [ ] Add warning logs if dashboard helper >12KB or approaching limit

---

## Field Analysis: What's on Chore Sensors?

**Chore Status Sensor Attributes** (from `sensor.py` lines 553-666):

**Identity & Meta**:
- `purpose`, `kid_name`, `chore_name`, `chore_icon`, `description`
- `assigned_kids`, `labels`

**Configuration**:
- `default_points`, `completion_criteria`, `approval_reset_type`
- `recurring_frequency`, `applicable_days`, `due_date`
- `custom_frequency_interval`, `custom_frequency_unit`

**Statistics**:
- `points_earned`, `approvals_count`, `claims_count`, `disapproved_count`, `overdue_count`
- `current_streak`, `highest_streak`, `last_longest_streak_date`
- `approvals_today` (for multi-approval chores)

**Timestamps**:
- `last_claimed`, `last_approved`, `last_disapproved`, `last_overdue`

**State Info**:
- `global_state` (for SHARED chores)
- `can_claim`, `can_approve`

**UI Integration**:
- `approve_button_entity_id`, `disapprove_button_entity_id`, `claim_button_entity_id`

**Total**: 30+ attributes per chore sensor (comprehensive chore metadata)

---

## Critical Computed Fields (Must Keep in Dashboard Helper)

These THREE fields are computed on-the-fly and NOT stored anywhere:

1. **`status`**: Computed from timestamps using coordinator helpers
   - Logic: `is_approved_in_current_period()` → approved
   - Else: `has_pending_claim()` → claimed
   - Else: `is_overdue()` → overdue
   - Else: pending
   - **Note**: Chore sensor has `native_value` (state) but dashboard needs this for all chores in list

2. **`primary_group`**: Computed from status + due_date + recurring_frequency
   - Logic: overdue → "today"
   - Due today → "today"
   - Due before next Monday 7am → "this_week"
   - Else → "other"
   - **Purpose**: Groups chores into dashboard sections

3. **`is_today_am`**: Computed from due_date hour
   - Logic: `due_date.hour < 12` → True, else False
   - Only set if due date is today
   - **Purpose**: Subgroup today chores into AM/PM

**Why Not Add to Chore Sensor?**
- `status`: Chore sensor already exposes this as `native_value` (sensor state)
- `primary_group`: Dashboard-specific grouping logic (not sensor responsibility)
- `is_today_am`: Dashboard-specific display preference

---

## Performance Considerations

**Template Lookup Cost**:
- Current: 1 sensor attribute access (`dashboard_helper.chores[i].due_date`)
- Proposed: 2 accesses (`dashboard_helper.chores[i].eid` + `state_attr(eid, 'due_date')`)

**Impact**: Negligible
- Home Assistant caches state objects in memory
- `state_attr()` is a fast dict lookup (not a database query)
- Dashboard renders once per page load
- Trade-off: 2x lookups for 67% size reduction = excellent ROI

---

## Success Metrics

**Must Have**:
- ✅ Dashboard helper size ≤ 16KB with 70 chores
- ✅ No recorder warnings in logs
- ✅ All chore details visible on dashboard
- ✅ Label filtering works
- ✅ Grouping (today/week/other, AM/PM) works

**Nice to Have**:
- Dashboard render time < 1 second (same as before)
- Integration diagnostics show sensor sizes
- Warning logs if approaching 16KB limit

---

## Rollout Plan

**v0.5.1-beta1** (Week 1):
- Backend changes (minimal chore attributes)
- Dashboard YAML updates
- Beta testing with 10-25-50 chore scenarios

**v0.5.1-rc1** (Week 2):
- Bug fixes from beta
- Documentation updates
- Community testing

**v0.5.1 GA** (Week 3):
- Public release
- Monitor GitHub issues for regressions

---

## Appendix: Size Calculations

**Current Chore Object** (16 attributes):
```json
{
  "eid": "sensor.kc_sarah_chore_take_out_trash",
  "name": "Take out Trash",
  "status": "pending",
  "labels": ["Kitchen", "Evening"],
  "due_date": "2026-01-11T18:00:00+00:00",
  "is_today_am": false,
  "primary_group": "today",
  "claimed_by": null,
  "completed_by": null,
  "approval_reset_type": "at_midnight_once",
  "last_approved": "2026-01-10T22:00:00+00:00",
  "last_claimed": "2026-01-10T19:30:00+00:00",
  "approval_period_start": "2026-01-10T00:00:00+00:00",
  "can_claim": true,
  "can_approve": false,
  "completion_criteria": "independent"
}
```
**Size**: 494 bytes

**Minimal Chore Object** (6 attributes):
```json
{
  "eid": "sensor.kc_sarah_chore_take_out_trash",
  "name": "Take out Trash",
  "status": "pending",
  "labels": ["Kitchen", "Evening"],
  "primary_group": "today",
  "is_today_am": false
}
```
**Size**: 164 bytes

**Savings**: 330 bytes per chore (67% reduction)

---

## References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, storage schema
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Naming conventions
- [Dashboard Helper Chores Sensor Capacity Analysis](./DASHBOARD_HELPER_SIZE_REDUCTION_SUP_CHORES_SENSOR_CAPACITY.md) - Original 48KB assumption (incorrect)
- [Translation Analysis](./DASHBOARD_HELPER_SIZE_REDUCTION_SUP_TRANSLATION_ANALYSIS.md) - Translation size breakdown
- [Dashboard YAML File](../../kidschores-ha-dashboard/files/kc_dashboard_all.yaml) - Template requiring updates

---

## Decisions & Completion Check

**Key Decisions**:
1. ✅ Use minimal chore attributes (Option 1A) instead of moving to chores sensor (Option 1B)
2. ✅ Keep 6 fields: eid, name, status, labels, primary_group, is_today_am
3. ✅ Fetch 10 display fields from chore sensors via `state_attr()`
4. ✅ Dashboard YAML must update ~10-15 template lookups

**Completion Requirements**:
- [ ] Backend: Reduce chore attributes from 16 → 6 fields
- [ ] Backend: Dashboard helper size ≤ 16KB with 70 chores
- [ ] Dashboard: Update Jinja2 templates to use `state_attr()`
- [ ] Testing: All chore details visible, grouping/filtering works
- [ ] Documentation: CHANGELOG, migration guide, size monitoring

**Sign-off Required**: ✅ Ready for KidsChores Plan Agent (implementation)

---

**END OF PLAN**
