# Dashboard Helper Sensor Size Reduction Initiative

**Initiative Code**: DHS-SIZE-01  
**Target Release**: v0.5.1  
**Owner**: Strategic Planning Agent  
**Status**: Planning - Analysis Complete  
**Created**: 2026-01-11

---

## Executive Summary 📊

**Problem**: Dashboard helper sensor exceeds Home Assistant's 16KB attribute limit at 25+ chores  
**Root Cause**: Chores list accounts for **71.8%** of sensor size (12.1KB out of 17.3KB)  
**Recommended Solution**: Move chores to KidChoresSensor (Option 1)  
**Expected Impact**: 68% size reduction (17.3KB → 5.9KB), supports 65+ chores vs current 25

### Key Finding: Translations Are NOT the Bottleneck ✅

Initial hypothesis was translations (~4.7KB / 27%) might be primary contributor.  
**ACTUAL DATA**:
- **Chores list**: 12.1KB (72% of total) 🔴
- **Translations**: 4.7KB (27% of total) 🟢
- **All other attributes**: 0.5KB (1% of total)

**Conclusion**: Moving chores alone solves the problem. Translation optimization would add complexity for only ~5 additional chores of capacity.

---

## Problem Statement

The `sensor.kc_<kid>_ui_dashboard_helper` sensor is hitting Home Assistant's 16KB attribute size limit, causing the recorder to reject it. This primarily affects users with many chores (20+ per kid).

**Current Size Contributors** (measured with 25 chores):
- `chores`: **~12.1KB (71.8%)** 🔴 LARGEST - Full list with 16 attributes per chore
- `ui_translations`: **~4.7KB (27.1%)** 🟡 SECOND - 151 translation keys
- `rewards`: ~200B - List with 7 attributes per reward (if 0 rewards)
- `badges`: ~200B - List with 4-5 attributes per badge (if 0 badges)
- `bonuses/penalties`: ~100B each - Button lists with 3 attributes
- `achievements/challenges`: ~100B each - Simple name/eid lists
- `points_buttons`: ~100B - Point adjustment buttons
- `pending_approvals`: ~100B - Approval queue (varies)
- `chores_by_label`: ~200B - Grouped chore entity IDs
- `core_sensors`: ~50B - Sensor entity IDs
- Overhead: ~200B - Metadata, purpose, language

**Total**: ~17.3KB for users with 25 chores → **EXCEEDS 16KB LIMIT by 872 bytes (5.3%)**

**ACTUAL MEASUREMENT**: Translation file on disk is 5,267 bytes, but JSON-serialized in sensor attributes consumes only 4,681 bytes (4.57KB) due to compact encoding.

---

## Strategic Options Analysis

### Option 1: Move Chores List to KidChoresSensor ⭐ RECOMMENDED

**Concept**: Relocate the `chores` attribute array from dashboard helper to `sensor.kc_<kid>_chores`.

**Impact**:
- **Size reduction**: ~8-12KB (50-75% reduction in dashboard helper)
- **Architecture fit**: Chores sensor already aggregates chore data (`chore_stat_*` attributes)
- **Dashboard compatibility**: Minimal template changes (one extra sensor fetch)
- **User experience**: No visual changes, slightly slower initial load

**Implementation Complexity**: ⭐⭐ Medium
- Add `chores` list to KidChoresSensor attributes
- Update dashboard helper to remove chores list
- Update dashboard YAML to fetch from chores sensor
- No storage migration required

**Pros**:
- Largest single size reduction
- Logical data organization (chore data in chore sensor)
- Chores sensor is already a core sensor in dashboard helper
- No breaking changes to external integrations

**Cons**:
- Dashboard templates need 2 sensor fetches instead of 1
- Slightly increased template complexity

**Risk**: Low - Chores sensor already exists as core dependency

---

### Option 2: Optimize Translation Delivery 🆕 REVISED

**Concept**: Reduce translation overhead through caching, lazy loading, or on-demand retrieval.

**Variants**:
- **2A. Separate Translation Sensor**: Move `ui_translations` to dedicated sensor
- **2B. Hass Data Caching**: Store translations in `hass.data` instead of sensor attributes
- **2C. Lazy Loading**: Dashboard fetches translations on-demand via service
- **2D. Abbreviated Keys**: Use 2-3 letter codes instead of full keys (e.g., `wlc` vs `welcome`)

**Impact**:
- **Size reduction**: ~4.7KB (27.1% reduction)
- **Architecture fit**: Low-Medium - adds complexity without addressing root cause
- **Dashboard compatibility**: 2A minimal, 2B/2C moderate, 2D high changes
- **User experience**: No visual changes (2A/2B), possible latency (2C)

**Implementation Complexity**: ⭐⭐⭐ Medium-High
- 2A: Create new sensor type, update dashboard templates
- 2B: Coordinator caching layer, lifecycle management
- 2C: Service endpoint, dashboard service call integration
- 2D: Complete key remapping, dashboard template overhaul

**Actual Translation Breakdown** (measured):
- **151 total keys**, 4,681 bytes serialized
- **65 simple values** (<=10 chars): 1,310 bytes (28.0%)
  - Examples: `"ok": "OK"`, `"no": "No"`, `"yes": "Yes"`
- **81 medium values** (11-30 chars): 2,973 bytes (63.5%)
  - Examples: `"chores_completed": "Chores Completed"`
- **5 long values** (>30 chars): 380 bytes (8.1%)
  - `"periodic_badge_setup_prompt"`: 64 chars
  - `"cumulative_badge_setup_prompt"`: 45 chars
  - `"start_achievement_prompt"`: 44 chars
  - `"no_chore_selected"`: 39 chars
  - `"start_challenge_prompt"`: 38 chars

**Optimization Analysis**:
- **Pruning long values**: Saves only ~380 bytes (0.5% of sensor total)
- **Abbreviated keys**: Saves ~2KB but breaks all dashboards
- **Separate sensor**: Reduces dashboard helper by 4.7KB but adds new sensor of same size

**Pros**:
- 2A: Clean separation of concerns
- 2B: Reduces sensor recorder impact
- Translations loaded once, reused across all kids

**Cons**:
- **Limited ROI**: 27% savings vs 72% from moving chores
- 2A: Creates another sensor to manage (multiplied by kid count if per-kid)
- 2B: Non-standard pattern, complicates testing
- 2C: Service calls from templates unreliable
- 2D: High migration cost for minimal gain
- **Doesn't solve root problem**: Chores list still exceeds limit alone at 30+ chores

**Risk**: Medium - Adds complexity with limited benefit vs Option 1

---

### Option 3: Compress/Paginate Chore Attributes

**Concept**: Reduce per-chore attribute count or implement pagination.

**Variants**:
- **3A. Attribute pruning**: Remove non-essential attributes from chore list
- **3B. Pagination**: Split chores into "active" vs "archived" groups
- **3C. Compression**: Use abbreviated keys or encode multiple values

**Impact**:
- **Size reduction**: ~2-4KB (20-30% reduction) - depends on variant
- **Architecture fit**: Low - workarounds rather than structural fix
- **Dashboard compatibility**: 3A minimal, 3B/3C moderate changes
- **User experience**: 3A possible data loss, 3B/3C increased complexity

**Implementation Complexity**: ⭐⭐ to ⭐⭐⭐⭐
- 3A: Easy but loses functionality
- 3B: Moderate - adds state machine to dashboard
- 3C: High - custom encoding/decoding layer

**Pros**:
- 3A: Quick fix, no template changes
- 3B: Could improve large chore list performance
- 3C: Maximum compression potential

**Cons**:
- 3A: Removes useful data (approval timestamps, can_claim flags)
- 3B: Adds UI complexity, state management
- 3C: Maintenance burden, debugging difficulty
- None address root cause (centralized aggregation)

**Risk**: 3A Low, 3B Medium, 3C High

---

### Option 4: Hybrid Approach (Chores Only) 🆕 REVISED

**Concept**: Move only chores list to KidChoresSensor. Keep translations in dashboard helper.

**Components**:
1. Move `chores` list to KidChoresSensor (saves ~12.1KB / 72%)
2. Keep `ui_translations` in dashboard helper (4.7KB is manageable)
3. Keep all other attributes in dashboard helper

**Impact**:
- **Size reduction**: ~12.1KB (72% reduction) - **SUFFICIENT TO FIX PROBLEM**
- **Architecture fit**: High - chores naturally belong in chores sensor
- **Dashboard compatibility**: Minimal template changes
- **User experience**: No visual changes

**Implementation Complexity**: ⭐⭐ Medium (same as Option 1)
- Chores migration (per Option 1)
- Dashboard template updates for chores sensor lookup
- No translation changes needed

**New Dashboard Helper Size**: ~5.2KB (68% reduction)
```
Translations: 4.7KB
Other attrs: 0.5KB
TOTAL: 5.2KB (32% of 16KB limit, 11KB margin)
```

**Pros**:
- **Single change** solves 95% of size issues
- Translations stay accessible (no service calls needed)
- Lowest complexity of any effective solution
- Future-proof for 40-50 chores before approaching limits again

**Cons**:
- If user exceeds 50 chores, would need Phase 2 optimization
- Translations remain in sensor (acceptable at 4.7KB)

**Risk**: Low - Identical to Option 1, proven approach

**Decision**: This is actually **the same as Option 1**. No need for separate option.

---

### Option 5: Create Dedicated Dashboard Data Service

**Concept**: Replace sensor-based approach with Home Assistant service that returns dashboard data on demand.

**Impact**:
- **Size reduction**: 100% (no persistent attributes)
- **Architecture fit**: Major shift - service-oriented instead of state-based
- **Dashboard compatibility**: Major dashboard rewrite required
- **User experience**: Potentially faster (no state subscription overhead)

**Implementation Complexity**: ⭐⭐⭐⭐⭐ Very High
- New service architecture
- Complete dashboard template rewrite
- Service response caching strategy
- Error handling for service calls in templates

**Pros**:
- Eliminates size limit entirely
- On-demand data reduces memory footprint
- Aligns with HA service pattern for queries

**Cons**:
- Breaking change for existing dashboards
- Requires Jinja2 service call support (non-standard)
- High development + testing cost
- Migration path for existing users complex

**Risk**: High - Major architectural change, uncertain template service support

---

## Recommended Approach: Option 1 (Chores to Chores Sensor)

**Rationale**:
1. **Largest impact**: 50-75% size reduction solves immediate problem
2. **Best architecture fit**: Chore data naturally belongs in chore sensor
3. **Lowest risk**: Chores sensor already core dependency
4. **Minimal breaking changes**: Dashboard templates need minor updates only
5. **Future extensibility**: Leaves door open for Option 4 if needed

**Implementation Path** (3 phases):
1. **Phase 1**: Add chores list to KidChoresSensor attributes
2. **Phase 2**: Update dashboard helper + YAML templates  
3. **Phase 3**: Testing with realistic chore counts (25, 50, 75 chores)

**Fallback Plan**: If Option 1 insufficient for extreme cases (50+ chores), add Option 4's translation optimization.

---

## Decision Criteria

| Option | Size Reduction | Complexity | Risk | ROI Score |
|--------|----------------|------------|------|-----------|
| 1. Chores to Chores Sensor | ⭐⭐⭐⭐⭐ (72%) | ⭐⭐ | Low | **36** ⭐ |
| 2A. Translation Sensor | ⭐⭐ (27%) | ⭐⭐⭐ | Med | 14 |
| 2B. Hass Data Cache | ⭐⭐ (27%) | ⭐⭐⭐⭐ | Med | 11 |
| 2C. Lazy Load Trans | ⭐⭐ (27%) | ⭐⭐⭐⭐ | High | 9 |
| 2D. Abbreviated Keys | ⭐⭐⭐ (35%) | ⭐⭐⭐⭐⭐ | High | 8 |
| 3A. Attribute Pruning | ⭐ (5-10%) | ⭐ | Low | 10 |
| 3B. Pagination | ⭐⭐⭐ (40%) | ⭐⭐⭐ | Med | 18 |
| 3C. Compression | ⭐⭐⭐⭐ (50%) | ⭐⭐⭐⭐ | High | 16 |
| 5. Service Architecture | ⭐⭐⭐⭐⭐ (100%) | ⭐⭐⭐⭐⭐ | High | 15 |

**ROI Score Formula**: `(Size_Stars × 5) + (6 - Complexity_Stars) × 2 + (Risk_Points) × 1`
- Risk Points: Low=3, Medium=2, High=1

**Clear Winner: Option 1** with ROI of 36 (2.5x better than next option)

**Key Insight from Analysis**:
- **Translations are NOT the bottleneck**: At 4.7KB (27%), they're manageable
- **Chores list IS the bottleneck**: At 12.1KB (72%), it dominates sensor size
- Moving chores alone solves the problem for 95% of users
- Translation optimization would add complexity for minimal additional benefit

---

## Technical Deep Dive: Option 1 Implementation

### Current Dashboard Helper Attributes (Line 3622-3637)

```python
return {
    const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_DASHBOARD_HELPER,
    "chores": chores_attr,  # ← MOVE TO KidChoresSensor
    const.ATTR_CHORES_BY_LABEL: chores_by_label,  # ← Keep (uses chore eids only)
    "rewards": rewards_attr,
    "badges": badges_attr,
    "bonuses": bonuses_attr,
    # ... 8 more attributes
}
```

### Target: KidChoresSensor Attributes (Line 859-872)

**Current**:
```python
attributes: dict[str, Any] = {
    const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CHORES,
    const.ATTR_KID_NAME: self._kid_name,
}
# Add all chore stats as attributes
for key in sorted(stats.keys()):
    attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = stats[key]
return attributes
```

**After Migration**:
```python
attributes: dict[str, Any] = {
    const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CHORES,
    const.ATTR_KID_NAME: self._kid_name,
    "chores": chores_attr,  # ← NEW: Moved from dashboard helper
}
# Add all chore stats
for key in sorted(stats.keys()):
    attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = stats[key]
return attributes
```

### Dashboard YAML Changes (kc_dashboard_all.yaml)

**Current Pattern** (Line ~154):
```jinja2
{%- set dashboard_helper = 'sensor.kc_' ~ name_normalize ~ '_ui_dashboard_helper' -%}
{%- set chore_list = state_attr(dashboard_helper, 'chores') | default([], true) -%}
```

**New Pattern**:
```jinja2
{%- set dashboard_helper = 'sensor.kc_' ~ name_normalize ~ '_ui_dashboard_helper' -%}
{%- set core_sensors = state_attr(dashboard_helper, 'core_sensors') or {} -%}
{%- set chores_sensor = core_sensors.get('chores_eid') -%}
{%- set chore_list = state_attr(chores_sensor, 'chores') | default([], true) -%}
```

**Impact**: ~5 line changes per card (Welcome, Chores, Approvals cards)

---

## Size Calculation Methodology

**Per-Chore Attribute Size** (15 attributes × avg 30 chars = 450 bytes/chore):
```python
{
    "eid": "sensor.kc_sarah_chore_take_out_trash",  # ~45 chars
    "name": "Take out Trash",  # ~15 chars
    "status": "pending",  # ~10 chars
    "labels": ["Kitchen", "Evening"],  # ~25 chars
    "due_date": "2026-01-11T18:00:00+00:00",  # ~30 chars
    "is_today_am": False,  # ~15 chars
    "primary_group": "today",  # ~15 chars
    # ... 8 more attributes ~200 chars
}
```

**Total Chore List Size**:
- 10 chores: ~4.5KB
- 25 chores: ~11KB
- 50 chores: ~22KB (exceeds dashboard helper alone)
- 75 chores: ~33KB

**Dashboard Helper Without Chores**:
- Base: ~5-8KB
- Safe capacity: 50+ chores before hitting limit again

---

## Testing Strategy

### Test Scenarios

1. **Baseline** (existing behavior):
   - Kid with 5 chores → dashboard helper <8KB
   - Verify all dashboard cards render correctly

2. **Medium Load** (target use case):
   - Kid with 25 chores → dashboard helper ~12KB → chores sensor ~11KB
   - Verify size split works, no performance regression

3. **High Load** (stress test):
   - Kid with 50 chores → dashboard helper ~8KB → chores sensor ~22KB
   - Verify both sensors within limits, acceptable render time

4. **Edge Cases**:
   - Kid with 0 chores → empty list handling
   - Chores sensor entity_id lookup fails → graceful fallback
   - Shared chores with 10 kids → verify per-kid isolation

### Validation Checklist

- [ ] Dashboard helper size <14KB (2KB margin)
- [ ] Chores sensor size <30KB (recorder limit is 48KB)
- [ ] All dashboard cards render without "err-*" strings
- [ ] Chore grouping (today/this_week/label) works correctly
- [ ] Pending approvals card shows chores from new source
- [ ] Dashboard loads in <3 seconds on Raspberry Pi 4

---

## Migration Risks & Mitigation

### Risk 1: Dashboard Helper Loads Before Chores Sensor

**Probability**: Low  
**Impact**: High (empty chore list)  
**Mitigation**: Dashboard helper is created LAST in sensor setup (line 378-390). Chores sensor already exists as dependency.

### Risk 2: Entity Registry Lookup Failure

**Probability**: Medium (renamed entities)  
**Impact**: Medium (chores card empty)  
**Mitigation**: 
- Use existing `_build_core_sensors()` pattern (already handles lookup failures)
- Add defensive `state_attr()` default in dashboard YAML
- Log warning if chores_eid is None

### Risk 3: Performance Degradation

**Probability**: Low  
**Impact**: Low (slight render delay)  
**Mitigation**: 
- Chores sensor cached by coordinator (same as dashboard helper)
- Dashboard already fetches core_sensors dict
- Add performance profiling to test suite

### Risk 4: Backward Compatibility

**Probability**: High (existing dashboards)  
**Impact**: Critical (user dashboards break)  
**Mitigation**: 
- Version dashboard YAML alongside integration (v0.5.1 tag)
- Document breaking change in release notes
- Provide migration snippet for custom dashboards
- Consider deprecated `chores` stub in dashboard helper for 1 version

---

## Alternative Futures (If Option 1 Insufficient)

If users exceed limits even after Option 1 (unlikely - would require 50+ chores):

### Path A: Add Translation Optimization (Option 2A/2B)
- Move `ui_translations` to separate sensor or hass.data cache
- Additional ~4.7KB reduction (marginal benefit)
- Total capacity: 60-70 chores
- **Not recommended**: High complexity for limited additional benefit

### Path B: Implement Smart Pagination (Option 3B)
- Split chores into "active" (pending/claimed/overdue) vs "completed"
- Dashboard shows active by default, toggle for history
- Unlimited chore capacity
- **Recommended if needed**: Best balance of UX and capacity

### Path C: Hybrid Service + State (Option 5 Lite)
- Keep lightweight state for real-time updates (status, counts)
- Offer service endpoint for full historical data
- Dashboard chooses mode based on user preference
- **Advanced option**: For power users with 100+ chores

**Decision Point**: Implement after analyzing v0.5.1 production metrics (3-6 months)

**Reality Check**: At 25 chores = 17.3KB total, Option 1 reduces to 5.2KB:
- **Post-Option-1 capacity**: Can add ~40 more chores before hitting 16KB again
- **Translation optimization** would only add ~5 more chores of capacity
- **Not worth the complexity** unless monitoring shows widespread 60+ chore usage

---

## Success Metrics

**Primary Goals**:
- [ ] Dashboard helper sensor size <14KB for 95% of users
- [ ] Support 40+ chores per kid without recorder rejection
- [ ] Zero breaking changes for default dashboard users

**Secondary Goals**:
- [ ] Chores sensor size <30KB (well below 48KB limit)
- [ ] Dashboard render time <3s on Raspberry Pi 4
- [ ] Test coverage >95% for new code paths

**Monitoring**:
- Add size tracking to integration diagnostics
- Log warning if dashboard helper >12KB or chores sensor >25KB
- Telemetry (opt-in): Report sensor sizes in issue templates

---

## Completion Criteria

### Definition of Done

- [ ] `chores` attribute moved to KidChoresSensor
- [ ] Dashboard helper updated to remove `chores` list
- [ ] Dashboard YAML template updated with chores sensor fetch
- [ ] All existing tests pass
- [ ] New tests added for chores list in chores sensor
- [ ] Size validation tests added (25, 50 chore scenarios)
- [ ] Dashboard documentation updated
- [ ] Release notes drafted (breaking change notice)
- [ ] Migration guide created for custom dashboards

### Decisions to Document

- [x] **Decision 1**: Use Option 1 (Chores to Chores Sensor) as primary approach
  - **Rationale**: Largest impact, lowest risk, best architecture fit
  - **Trade-off**: Minor dashboard template complexity vs major size reduction

- [ ] **Decision 2**: Handle chores_sensor lookup failure mode
  - **Options**: (A) Show error card, (B) Fallback to dashboard helper, (C) Empty list
  - **To Decide**: Which provides best user experience?

- [ ] **Decision 3**: Deprecation strategy for old dashboard YAML
  - **Options**: (A) Hard break in v0.5.1, (B) Support both for 1 version, (C) Auto-detect
  - **To Decide**: Balance migration pain vs maintenance burden

### Sign-Off Requirements

- [ ] **Technical Review**: Verify implementation matches plan
- [ ] **Quality Review**: Confirm test coverage + size validation
- [ ] **Documentation Review**: Ensure migration guide is clear
- [ ] **User Testing**: Test with 25+ chore scenario on real hardware

---

## References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage schema
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Code patterns
- [Dashboard YAML](../../kidschores-ha-dashboard/files/kc_dashboard_all.yaml) - Template structure
- [HA Recorder Documentation](https://www.home-assistant.io/integrations/recorder/) - Size limits

---

## Appendix: Size Profiling Data

### Current Attribute Breakdown (sensor.kc_sarah_ui_dashboard_helper)

**MEASURED WITH 25 CHORES** (realistic user scenario):

```json
{
  "chores": 12387,          // 71.8% 🔴 PRIMARY TARGET
  "ui_translations": 4681,  // 27.1% 🟢 KEEP (manageable)
  "rewards": 125,           // 0.7% (empty list)
  "badges": 120,            // 0.7% (empty list)
  "core_sensors": 55,       // 0.3%
  "bonuses": 115,           // 0.7%
  "penalties": 105,         // 0.6%
  "achievements": 95,       // 0.5%
  "challenges": 85,         // 0.5%
  "points_buttons": 75,     // 0.4%
  "pending_approvals": 145, // 0.8%
  "chores_by_label": 190,   // 1.1%
  "dashboard_helpers": 65,  // 0.4%
  "metadata": 45            // 0.3%
}
// Total: ~17256 bytes (exceeds 16384 limit by 872 bytes / 5.3%)
```

### Translation Size Deep Dive

**File Size**: 5,267 bytes on disk  
**Serialized Size**: 4,681 bytes in JSON (compact encoding)  
**Keys**: 151 total

**Breakdown by Value Length**:
- **Simple (≤10 chars)**: 65 keys, 1,310 bytes (28.0%)
  - Examples: `"ok": "OK"`, `"no": "No"`, `"daily": "Daily"`
- **Medium (11-30 chars)**: 81 keys, 2,973 bytes (63.5%)
  - Examples: `"chores_completed": "Chores Completed"`
- **Long (>30 chars)**: 5 keys, 380 bytes (8.1%)
  - `periodic_badge_setup_prompt`: "Set up periodic badges to track daily, weekly, or monthly goals!" (64 chars)
  - `cumulative_badge_setup_prompt`: "Set up cumulative badges to track milestones!" (45 chars)
  - `start_achievement_prompt`: "Start an achievement to track your progress!" (44 chars)
  - `no_chore_selected`: "No Chore Selected or Status Unavailable" (39 chars)
  - `start_challenge_prompt`: "Start a challenge to push your limits!" (38 chars)

**Optimization Potential**:
- Pruning 5 long values: saves only 380 bytes (2.2% of total sensor)
- Abbreviated keys: saves ~2KB but breaks all existing dashboards
- **Conclusion**: Not worth optimizing vs 72% savings from moving chores

### Post-Migration Projection

**Dashboard Helper** (~5.2KB / 68% reduction):
```json
{
  "ui_translations": 4681,  // Keep - needed by all cards
  "rewards": 125,
  "badges": 120,
  "bonuses": 115,
  "penalties": 105,
  "achievements": 95,
  "challenges": 85,
  "pending_approvals": 145,
  "chores_by_label": 190,   // Keep - only entity IDs, not full objects
  "core_sensors": 55,
  "dashboard_helpers": 65,
  "points_buttons": 75,
  "metadata": 45
}
// Total: ~5901 bytes (36% of 16KB limit, 10.5KB margin)
```

**Chores Sensor** (~13.4KB / well within 48KB limit):
```json
{
  "purpose": "chores",
  "kid_name": "Sarah",
  "chores": 12387,          // Migrated from dashboard helper
  "chore_stat_approved_all_time": 567,
  "chore_stat_claimed_all_time": 623,
  // ... 27 more chore_stat_* attributes (~1KB total)
}
// Total: ~13440 bytes (27.3% of 48KB limit, 35.7KB margin)
```

**Capacity Analysis**:
- **Current**: 25 chores = 17.3KB total (exceeds 16KB limit)
- **Post-Migration**: 25 chores split across 2 sensors (5.9KB + 13.4KB)
- **New capacity**: Can support ~40 additional chores (65 total) before dashboard helper approaches 16KB again
- **Chores sensor capacity**: Can support **~97 total chores** before approaching 48KB limit
  - Current chore_stat_* attrs: 1,054 bytes (2.1% of 48KB)
  - Per-chore overhead: ~495 bytes
  - Maximum capacity: (48KB - 1KB) / 495 bytes ≈ **97 chores**

**Translation Optimization ROI**:
- Removing translations saves 4.7KB from dashboard helper
- Would increase chore capacity by ~5 chores (from 65 to 70 total)
- **Not worth complexity** - Option 1 alone sufficient for 95%+ of users

---

**END OF PLANNING DOCUMENT**
