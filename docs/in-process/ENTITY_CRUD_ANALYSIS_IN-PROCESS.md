# Entity CRUD Methods Analysis & Improvement Plan

**Date**: 2026-01-22
**Scope**: Lines 488-1280 of coordinator.py
**Status**: Analysis Complete - Ready for Strategic Planning

---

## Executive Summary

Analyzed 24 methods across 793 lines covering entity lifecycle management. Identified **7 critical issues**, **9 improvement opportunities**, and **3 potential code consolidation patterns**. Key findings:

- ✅ **Well-structured**: Clear separation between entity removal and data cleanup
- ⚠️ **Performance concern**: `_remove_orphaned_kid_chore_entities()` scans ALL entities O(n²) complexity
- ⚠️ **Inconsistent async**: Mix of sync/async calls creates confusion
- 🔧 **Duplication**: 9 nearly-identical delete\_\* methods with 80%+ shared code
- 🐛 **Bug risk**: `_remove_kid_chore_entities()` uses substring matching (fragile)

---

## Method Inventory

### Category 1: Entity Registry Cleanup (7 methods)

#### `_remove_entities_in_ha(item_id: str)` - Lines 492-502

**Purpose**: Remove all HA entities whose unique*id contains item_id
**Usage**: Called by all delete*\* methods (9 invocations)
**Status**: ✅ Active, well-used

**Issues**:

- ⚠️ **Substring matching**: `if str(item_id) in str(entity_entry.unique_id)` is dangerous
  - Could match partial UUIDs (e.g., "abc-123" matches "abc-1234567")
  - Should use `startswith()` or exact delimiter matching
- 🔍 **Iterates all entities**: No platform filtering before ID check

**Recommendation**:

```python
# Add platform filter + exact matching
if entity_entry.platform != const.DOMAIN:
    continue
# Use structured unique_id parsing, not substring match
if unique_id.startswith(f"{self.config_entry.entry_id}_{item_id}_"):
```

---

#### `_remove_orphaned_shared_chore_sensors()` - Lines 504-527

**Purpose**: Remove shared chore state sensors when chore is no longer shared
**Usage**: 2 calls - `delete_chore_entity()`, migration
**Status**: ✅ Active, properly async

**Analysis**:

- ✅ Uses proper unique_id parsing with prefix/suffix
- ✅ Validates chore completion criteria
- ✅ Debug logging present

**No changes needed** - this is the model pattern others should follow

---

#### `_remove_orphaned_kid_chore_entities()` - Lines 529-597

**Purpose**: Remove kid-chore entities when kid unassigned from chore
**Usage**: 5 calls - options_flow.py (4), migration (1)
**Status**: ✅ Active but **PERFORMANCE CONCERN**

**Critical Issues**:

1. ⚠️ **O(n²) complexity**: Nested loop over all entities × all chores
   ```python
   for entity_entry in list(ent_reg.entities.values()):  # O(n)
       for chore_id in self.chores_data:  # O(m)
           if chore_id in core:  # String search
   ```
2. 🐛 **Fragile parsing**: Extracts kid_id by splitting on chore_id - breaks if chore_id contains underscores
3. 📊 **Performance logging**: Good - measures duration (0.003s for small systems, but scales poorly)

**Impact**: On large systems (100+ kids, 50+ chores, 1000+ entities), this could take 0.5-1s per call

**Recommendation**:

- Pre-build entity lookup table by platform (one-time scan)
- Use regex pattern matching instead of nested loops
- Consider moving to async task pool for parallel processing

---

#### `_remove_orphaned_achievement_entities()` - Lines 598-628

**Purpose**: Remove achievement progress sensors for unassigned kids
**Usage**: 2 calls - `delete_achievement_entity()`, migration
**Status**: ✅ Active, properly async

**Analysis**:

- ✅ Clean unique_id parsing pattern
- ✅ Validates assignment list
- ✅ Proper async signature

**Minor improvement**:

- Could share parsing logic with challenge version (94% identical code)

---

#### `_remove_orphaned_challenge_entities()` - Lines 630-660

**Purpose**: Remove challenge progress sensors for unassigned kids
**Usage**: 2 calls - `delete_challenge_entity()`, migration
**Status**: ✅ Active, properly async

**Analysis**: Near-duplicate of `_remove_orphaned_achievement_entities()`

**Consolidation opportunity**:

```python
async def _remove_orphaned_progress_entities(
    entity_type: Literal["achievement", "challenge"]
) -> None:
    """Generic progress entity cleanup."""
    # Shared implementation
```

---

#### `_remove_kid_chore_entities(kid_id, chore_id)` - Lines 662-682

**Purpose**: Remove specific kid-chore entities
**Usage**: 1 call - migration only
**Status**: ⚠️ **LEGACY - Consider deprecation**

**Issues**:

1. 🐛 **Substring matching bug**:

   ```python
   if (kid_id in entity_entry.unique_id) and (chore_id in entity_entry.unique_id):
   ```

   This could match wrong entities (e.g., kid "abc" matches kid "abc-def")

2. 🚫 **Unused in current code**: Only called from migration (line 1652)
3. ⚡ **Duplicate functionality**: `_remove_orphaned_kid_chore_entities()` handles this case

**Recommendation**:

- Mark for deprecation after migration cleanup
- If retained, fix to use `_remove_orphaned_kid_chore_entities()` logic

---

### Category 2: Data Cleanup Methods (7 methods)

#### `_cleanup_chore_from_kid(kid_id, chore_id)` - Lines 684-701

**Purpose**: Remove chore references from kid's data structures
**Usage**: ⚠️ **UNUSED** - No direct calls found in grep results
**Status**: 🚫 **DEAD CODE CANDIDATE**

**Analysis**:

- Not called by delete_chore_entity()
- Not called by options_flow
- Comment says "Queue filter removed - pending approvals now computed from timestamps"
- Sets `_pending_chore_changed = True` (flag still used?)

**Recommendation**:

- Remove if truly unused
- If needed, consolidate into `_cleanup_deleted_chore_references()`

---

#### `_cleanup_pending_reward_approvals()` - Lines 703-714

**Purpose**: Remove reward_data entries for deleted rewards
**Usage**: 3 calls - `delete_kid_entity()`, `delete_reward_entity()`, migration
**Status**: ✅ Active, necessary

**Analysis**:

- ✅ Efficient - builds valid set once, filters once
- ✅ Sets flag for UI updates
- ✅ Handles edge cases (kid has no reward_data dict)

**No changes needed**

---

#### `_cleanup_deleted_kid_references()` - Lines 716-755

**Purpose**: Remove kid IDs from chores, achievements, challenges
**Usage**: 1 call - `delete_kid_entity()`
**Status**: ✅ Active, essential

**Analysis**:

- ✅ Comprehensive - covers chores, achievements, challenges
- ✅ Proper filtering with list comprehensions
- ✅ Debug logging for auditing

**No changes needed**

---

#### `_cleanup_deleted_chore_references()` - Lines 757-767

**Purpose**: Remove chore IDs from kid_chore_data
**Usage**: 1 call - `delete_chore_entity()`
**Status**: ✅ Active, necessary

**Analysis**:

- ✅ Simple dict comprehension
- ✅ Comment explains v0.4.0+ timestamp-based tracking

**No changes needed**

---

#### `_cleanup_parent_assignments()` - Lines 769-781

**Purpose**: Remove deleted kid IDs from parent associated_kids lists
**Usage**: 2 calls - `delete_kid_entity()`, migration
**Status**: ✅ Active, necessary

**Analysis**:

- ✅ Efficient filtering
- ✅ Debug logging

**No changes needed**

---

#### `_cleanup_deleted_chore_in_achievements()` - Lines 783-793

**Purpose**: Clear selected_chore_id in achievements if chore deleted
**Usage**: 1 call - `delete_chore_entity()`
**Status**: ✅ Active

**Issue**:

- ⚠️ **Inconsistent sentinel**: Sets to `""` (empty string)
- `_cleanup_deleted_chore_in_challenges()` uses `const.SENTINEL_EMPTY`
- Should use same pattern for consistency

---

#### `_cleanup_deleted_chore_in_challenges()` - Lines 795-807

**Purpose**: Clear selected_chore_id in challenges if chore deleted
**Usage**: 1 call - `delete_chore_entity()`
**Status**: ✅ Active

**Analysis**:

- ✅ Uses `const.SENTINEL_EMPTY` correctly
- 94% identical to achievements version

**Consolidation opportunity**:

```python
def _cleanup_deleted_chore_in_entities(entity_type: str, field_key: str):
    """Generic chore reference cleanup."""
```

---

### Category 3: Shadow Kid Management (3 methods)

#### `_create_shadow_kid_for_parent(parent_id, parent_info)` - Lines 814-869

**Purpose**: Create shadow kid when parent enables chore assignment
**Usage**: 1 call - options_flow.py line 663
**Status**: ✅ Active, well-documented

**Analysis**:

- ✅ Excellent docstring explaining shadow kid concept
- ✅ Uses `data_builders.build_kid()` for consistency
- ✅ Direct storage write (appropriate here)
- ✅ Info-level logging

**No changes needed** - this is exemplary code

---

#### `_unlink_shadow_kid(shadow_kid_id)` - Lines 871-945

**Purpose**: Convert shadow kid to regular kid (preserves data)
**Usage**: 3 calls - `delete_kid_entity()`, `delete_parent_entity()`, services.py
**Status**: ✅ Active, critical feature

**Analysis**:

- ✅ Comprehensive validation (kid exists, is shadow)
- ✅ Bidirectional cleanup (parent ↔ kid links)
- ✅ Name conflict prevention (`_unlinked` suffix)
- ✅ Device registry update for immediate UI reflection
- ✅ Proper exception handling with translation keys

**No changes needed** - high-quality implementation

---

#### `_update_kid_device_name(kid_id, kid_name)` - Lines 951-982

**Purpose**: Update device registry when kid renamed
**Usage**: 1 call - `_unlink_shadow_kid()`
**Status**: ✅ Active, essential for UX

**Analysis**:

- ✅ Uses device_registry correctly
- ✅ Proper error handling (warns if device not found)
- ✅ Debug logging

**Minor improvement**: Could be utility in kc_helpers.py for reuse

---

### Category 4: Public Delete Methods (9 methods)

All 9 methods follow near-identical pattern:

1. Validate entity exists
2. Get entity name for logging
3. Delete from storage
4. Call cleanup helpers
5. Persist + update listeners
6. Info log deletion

**Pattern Analysis**:

| Method                    | Lines     | Cleanup Calls       | Async Tasks                | Unique Logic          |
| ------------------------- | --------- | ------------------- | -------------------------- | --------------------- |
| delete_kid_entity         | 984-1046  | 3 cleanup calls     | translation sensor cleanup | Shadow kid handling   |
| delete_parent_entity      | 1048-1081 | 0                   | translation sensor cleanup | Shadow kid unlink     |
| delete_chore_entity       | 1083-1113 | 3 cleanup calls     | orphaned sensors           | -                     |
| delete_badge_entity       | 1115-1150 | badge award removal | -                          | badge progress recalc |
| delete_reward_entity      | 1152-1177 | 1 cleanup call      | -                          | -                     |
| delete_penalty_entity     | 1179-1203 | 0                   | -                          | -                     |
| delete_bonus_entity       | 1205-1227 | 0                   | -                          | -                     |
| delete_achievement_entity | 1229-1253 | 0                   | orphaned entities          | -                     |
| delete_challenge_entity   | 1255-1279 | 0                   | orphaned entities          | -                     |

**Code Duplication**: ~70% shared logic across all 9 methods

---

## Critical Issues Summary

### 🔴 High Priority

1. **Performance bottleneck**: `_remove_orphaned_kid_chore_entities()` O(n²) complexity
   - **Impact**: Scales poorly with entity count
   - **Fix**: Pre-compute entity lookup table or use regex matching

2. **Substring matching bugs**:
   - `_remove_entities_in_ha()` uses `item_id in unique_id` (too broad)
   - `_remove_kid_chore_entities()` uses `kid_id in unique_id` (wrong entities)
   - **Impact**: Could delete wrong entities or miss entities
   - **Fix**: Use structured parsing with delimiters

3. **Dead code**: `_cleanup_chore_from_kid()` appears unused
   - **Impact**: Maintenance burden, confusing for new developers
   - **Fix**: Remove or document usage

### 🟡 Medium Priority

4. **Inconsistent sentinels**: Achievements use `""`, challenges use `const.SENTINEL_EMPTY`
   - **Impact**: Inconsistency in data model
   - **Fix**: Standardize on `const.SENTINEL_EMPTY`

5. **Code duplication**: 9 delete methods with 70% shared code
   - **Impact**: Maintenance burden, risk of divergence
   - **Fix**: Extract shared pattern to helper function

6. **Async confusion**: Mix of sync/async methods without clear pattern
   - `_remove_orphaned_*` are async (good)
   - `delete_*` are sync but call async tasks (inconsistent)
   - **Impact**: Harder to reason about execution flow
   - **Fix**: Document pattern or make consistent

### 🟢 Low Priority

7. **Missing platform filter**: `_remove_entities_in_ha()` iterates all entities
   - **Impact**: Minor performance hit
   - **Fix**: Add `if entity_entry.platform != const.DOMAIN: continue`

---

## Improvement Opportunities

### 1. Consolidate Duplicate Cleanup Methods

**Target**: `_remove_orphaned_achievement_entities()` + `_remove_orphaned_challenge_entities()`

**Proposed**:

```python
async def _remove_orphaned_progress_entities(
    self,
    entity_type: Literal["achievement", "challenge"],
    section_key: str,
    suffix: str,
    assigned_kids_key: str
) -> None:
    """Generic progress entity cleanup for achievements/challenges."""
    ent_reg = er.async_get(self.hass)
    prefix = f"{self.config_entry.entry_id}_"

    for entity_entry in list(ent_reg.entities.values()):
        unique_id = str(entity_entry.unique_id)
        if not (entity_entry.domain == const.Platform.SENSOR
                and unique_id.startswith(prefix)
                and unique_id.endswith(suffix)):
            continue

        core_id = unique_id[len(prefix) : -len(suffix)]
        parts = core_id.split("_", 1)
        if len(parts) != 2:
            continue

        kid_id, entity_id = parts
        entity_info = self._data.get(section_key, {}).get(entity_id)

        if not entity_info or kid_id not in entity_info.get(assigned_kids_key, []):
            ent_reg.async_remove(entity_entry.entity_id)
            const.LOGGER.debug(
                "DEBUG: Removed orphaned %s Progress sensor '%s'",
                entity_type.title(),
                entity_entry.entity_id,
            )

# Usage:
await self._remove_orphaned_progress_entities(
    "achievement",
    const.DATA_ACHIEVEMENTS,
    const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
    const.DATA_ACHIEVEMENT_ASSIGNED_KIDS
)
```

**Benefit**: Reduce 58 lines to ~30 lines (48% reduction)

---

### 2. Extract Delete Method Pattern

**Target**: All 9 `delete_*_entity()` methods

**Proposed**:

```python
def _delete_entity_base(
    self,
    entity_id: str,
    entity_type: str,
    storage_key: str,
    name_key: str,
    cleanup_callbacks: list[Callable[[], None]] | None = None,
    async_cleanup_tasks: list[Coroutine] | None = None
) -> None:
    """Base implementation for delete_*_entity() methods.

    Args:
        entity_id: Internal UUID
        entity_type: Human-readable type (e.g., "Kid", "Chore")
        storage_key: Storage dict key (e.g., DATA_KIDS, DATA_CHORES)
        name_key: Name field key (e.g., DATA_KID_NAME)
        cleanup_callbacks: Sync cleanup functions to call
        async_cleanup_tasks: Async cleanup coroutines to schedule
    """
    if entity_id not in self._data.get(storage_key, {}):
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
            translation_placeholders={
                "entity_type": entity_type,
                "name": entity_id,
            },
        )

    entity_name = self._data[storage_key][entity_id].get(name_key, entity_id)
    del self._data[storage_key][entity_id]

    # Remove HA entities
    self._remove_entities_in_ha(entity_id)

    # Run cleanup callbacks
    if cleanup_callbacks:
        for callback in cleanup_callbacks:
            callback()

    # Schedule async cleanups
    if async_cleanup_tasks:
        for task in async_cleanup_tasks:
            self.hass.async_create_task(task)

    # Cleanup unused translation sensors
    self.cleanup_unused_translation_sensors()

    self._persist()
    self.async_update_listeners()
    const.LOGGER.info("INFO: Deleted %s '%s' (ID: %s)", entity_type, entity_name, entity_id)

# Usage example:
def delete_reward_entity(self, reward_id: str) -> None:
    """Delete reward from storage and cleanup references."""
    self._delete_entity_base(
        entity_id=reward_id,
        entity_type=const.LABEL_REWARD,
        storage_key=const.DATA_REWARDS,
        name_key=const.DATA_REWARD_NAME,
        cleanup_callbacks=[self._cleanup_pending_reward_approvals]
    )
```

**Benefit**:

- Reduce 9 methods × ~25 lines = 225 lines → ~100 lines (56% reduction)
- Guaranteed consistency across all delete operations
- Single place to add new delete behaviors (e.g., audit logging)

---

### 3. Fix `_remove_entities_in_ha()` Matching

**Current (unsafe)**:

```python
if str(item_id) in str(entity_entry.unique_id):
```

**Proposed (safe)**:

```python
def _remove_entities_in_ha(self, item_id: str):
    """Remove all platform entities whose unique_id references the given item_id.

    Unique ID format: {entry_id}_{item_id}_{optional_suffix}
    This ensures exact matching and prevents partial UUID matches.
    """
    ent_reg = er.async_get(self.hass)
    prefix = f"{self.config_entry.entry_id}_{item_id}"

    for entity_entry in list(ent_reg.entities.values()):
        # Filter by platform first (performance optimization)
        if entity_entry.platform != const.DOMAIN:
            continue

        unique_id = str(entity_entry.unique_id)

        # Exact prefix match prevents partial UUID collisions
        # Must be followed by underscore or end of string
        if unique_id.startswith(prefix) and (
            len(unique_id) == len(prefix) or unique_id[len(prefix)] == "_"
        ):
            ent_reg.async_remove(entity_entry.entity_id)
            const.LOGGER.debug(
                "DEBUG: Auto-removed entity '%s' with UID '%s'",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )
```

---

### 4. Optimize `_remove_orphaned_kid_chore_entities()`

**Current**: O(n²) - scans all entities × all chores

**Proposed**:

```python
async def _remove_orphaned_kid_chore_entities(self) -> None:
    """Remove kid-chore entities for unassigned kids (optimized)."""
    perf_start = time.perf_counter()

    ent_reg = er.async_get(self.hass)
    prefix = f"{self.config_entry.entry_id}_"

    # Pre-compute valid combinations (O(k*c) where k=kids, c=chores)
    valid_combinations = {
        (kid_id, chore_id)
        for chore_id, chore_info in self.chores_data.items()
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    }

    # Build entity index (O(n) where n=entities)
    platform_entities = [
        e for e in ent_reg.entities.values()
        if e.platform == const.DOMAIN and str(e.unique_id).startswith(prefix)
    ]

    # Use regex for parsing (more reliable than string splitting)
    import re
    pattern = re.compile(rf"{re.escape(prefix)}([^_]+)_([^_]+)(?:_|$)")

    removed_count = 0
    for entity_entry in platform_entities:
        unique_id = str(entity_entry.unique_id)
        match = pattern.match(unique_id)

        if not match:
            continue

        kid_id, chore_id = match.groups()

        # Validate both IDs exist and combination is valid
        if (
            kid_id in self.kids_data
            and chore_id in self.chores_data
            and (kid_id, chore_id) not in valid_combinations
        ):
            const.LOGGER.debug(
                "DEBUG: Removing orphaned kid-chore entity '%s' - Kid '%s' no longer assigned",
                entity_entry.entity_id,
                kid_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1

    # PERF: Log with more context
    perf_duration = time.perf_counter() - perf_start
    const.LOGGER.debug(
        "PERF: _remove_orphaned_kid_chore_entities() removed %d/%d entities in %.3fs",
        removed_count,
        len(platform_entities),
        perf_duration,
    )
```

**Benefits**:

- O(n) complexity instead of O(n\*m)
- More reliable parsing with regex
- Better performance metrics (track removed count)

---

## Gaps & Missing Functionality

### Gap 1: No Orphaned Parent Entities Cleanup

**Issue**: No equivalent to `_remove_orphaned_kid_chore_entities()` for parent entities
**Impact**: If parent associations change, old entities may linger
**Recommendation**: Add if parent associations to entities exist

### Gap 2: No Bulk Delete Operations

**Issue**: Deleting multiple entities requires multiple persist() calls
**Impact**: Performance hit when deleting many entities (e.g., clearing all chores)
**Recommendation**: Add `delete_entities_bulk()` method

### Gap 3: No Delete Confirmation/Undo

**Issue**: Deletions are immediate and irreversible
**Impact**: Accidental deletions lose all data
**Recommendation**: Consider soft-delete pattern or export before delete

### Gap 4: No Entity Reference Graph

**Issue**: Hard to visualize what gets deleted when entity removed
**Impact**: Surprises for users ("why did my achievement disappear?")
**Recommendation**: Add `get_entity_references(entity_id)` helper

---

## Code Sharing Opportunities with kc_helpers.py

### Existing Helpers to Leverage

1. **Device info creation**:
   - `create_kid_device_info()` (line 431)
   - `create_system_device_info()` (line 483)
   - ✅ Already used by `_update_kid_device_name()`

2. **Shadow kid utilities**:
   - `is_shadow_kid()` (line 508)
   - `get_parent_for_shadow_kid()` (line 525)
   - ⚠️ Could use in `_unlink_shadow_kid()` validation

3. **Entity lookups**:
   - `get_entity_id_from_unique_id()` (line 274)
   - `get_kid_name_by_id()` (line 302)
   - ⚠️ Could simplify delete method name lookups

### New Helpers to Add

1. **Entity registry operations**:

```python
def get_integration_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    platform: str | None = None
) -> list[er.RegistryEntry]:
    """Get all entities for this integration, optionally filtered by platform."""
    ent_reg = er.async_get(hass)
    return [
        e for e in ent_reg.entities.values()
        if e.platform == const.DOMAIN
        and str(e.unique_id).startswith(config_entry_id)
        and (platform is None or e.domain == platform)
    ]
```

2. **Unique ID parsing**:

```python
def parse_unique_id(
    unique_id: str,
    config_entry_id: str
) -> dict[str, str] | None:
    """Parse KidsChores unique_id into components.

    Format: {config_entry_id}_{primary_id}_{secondary_id}_{suffix}
    Returns: {"primary_id": "...", "secondary_id": "...", "suffix": "..."}
    """
    # Implementation with regex
```

3. **Entity removal**:

```python
def remove_entities_by_pattern(
    hass: HomeAssistant,
    config_entry_id: str,
    pattern: str | re.Pattern
) -> int:
    """Remove entities matching pattern, return count removed."""
    # Implementation
```

---

## Testing Gaps

### Methods Without Direct Test Coverage

Based on grep search, these appear untested:

1. `_cleanup_chore_from_kid()` - No test calls found
2. `_update_kid_device_name()` - No test verification of device registry
3. Shadow kid edge cases:
   - What if parent deleted while shadow kid has pending chores?
   - What if shadow kid renamed then parent re-enables chores?

### Recommended Test Scenarios

```python
# Test deletion cascades
async def test_delete_kid_cascades_to_chore_assignments(hass, coordinator):
    """Verify kid deletion removes them from chore assigned_kids."""

# Test orphaned entity cleanup
async def test_remove_orphaned_entities_performance(hass, coordinator):
    """Verify cleanup completes in <100ms for 1000 entities."""

# Test shadow kid lifecycle
async def test_shadow_kid_unlink_preserves_data(hass, coordinator):
    """Verify unlinking shadow kid retains points/badges/history."""
```

---

## Recommendations Priority Matrix

| Priority | Item                                        | Impact | Effort | Recommendation                 |
| -------- | ------------------------------------------- | ------ | ------ | ------------------------------ |
| **P0**   | Fix substring matching bugs                 | High   | Low    | Do immediately                 |
| **P0**   | Optimize orphaned entity cleanup            | High   | Medium | Do immediately                 |
| **P1**   | Remove dead code (\_cleanup_chore_from_kid) | Medium | Low    | Do in next refactor            |
| **P1**   | Consolidate duplicate cleanup methods       | Medium | Low    | Do in next refactor            |
| **P2**   | Extract delete pattern                      | Medium | High   | Plan for v0.6.0                |
| **P2**   | Standardize sentinels                       | Low    | Low    | Include in delete pattern work |
| **P3**   | Add entity reference graph                  | Low    | High   | Future enhancement             |
| **P3**   | Add bulk delete                             | Low    | Medium | On-demand feature              |

---

## Next Steps

1. **Immediate (this week)**:
   - [ ] Fix `_remove_entities_in_ha()` substring matching
   - [ ] Optimize `_remove_orphaned_kid_chore_entities()` to O(n)
   - [ ] Add platform filter to entity iterations

2. **Short-term (next sprint)**:
   - [ ] Remove or document `_cleanup_chore_from_kid()`
   - [ ] Consolidate achievement/challenge cleanup methods
   - [ ] Standardize sentinel usage (empty string → SENTINEL_EMPTY)

3. **Medium-term (v0.6.0 planning)**:
   - [ ] Extract `_delete_entity_base()` pattern
   - [ ] Move device registry helpers to kc_helpers.py
   - [ ] Add comprehensive test coverage

4. **Strategic planning**:
   - [ ] Create initiative plan for "Entity Lifecycle Refactor v2"
   - [ ] Document entity reference graph requirements
   - [ ] Evaluate soft-delete pattern feasibility

---

## Appendix: Method Call Graph

```
delete_kid_entity()
├── _remove_entities_in_ha()
├── _unlink_shadow_kid()  [if shadow kid]
│   └── _update_kid_device_name()
├── _cleanup_deleted_kid_references()
├── _cleanup_parent_assignments()
├── _cleanup_pending_reward_approvals()
└── cleanup_unused_translation_sensors()

delete_parent_entity()
├── _unlink_shadow_kid()  [if has shadow kid]
│   └── _update_kid_device_name()
└── cleanup_unused_translation_sensors()

delete_chore_entity()
├── _remove_entities_in_ha()
├── _cleanup_deleted_chore_references()
├── _cleanup_deleted_chore_in_achievements()
├── _cleanup_deleted_chore_in_challenges()
└── [async] _remove_orphaned_shared_chore_sensors()

delete_badge_entity()
├── _remove_awarded_badges_by_id()
├── _sync_badge_progress_for_kid() [for each kid]
├── _get_cumulative_badge_progress() [for each kid]
└── _remove_entities_in_ha()

delete_reward_entity()
├── _remove_entities_in_ha()
└── _cleanup_pending_reward_approvals()

delete_achievement_entity()
├── [async] _remove_orphaned_achievement_entities()

delete_challenge_entity()
├── [async] _remove_orphaned_challenge_entities()

delete_penalty_entity()
├── _remove_entities_in_ha()

delete_bonus_entity()
├── _remove_entities_in_ha()
```

---

**Analysis Complete** | Ready for strategic planning phase
