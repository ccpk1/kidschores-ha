# Coordinator CRUD & Entity Management Refactor

## Initiative snapshot

- **Name / Code**: Coordinator CRUD Refactor (CCR-2026-001)
- **Target release / milestone**: v0.6.1 (post parent-chores merge)
- **Owner / driver(s)**: Development Team
- **Status**: Not started (Planning phase)

## Summary & immediate steps

| Phase / Step                | Description                                | % complete | Quick notes                                   |
| --------------------------- | ------------------------------------------ | ---------- | --------------------------------------------- |
| Phase 1 – Foundation        | Extract generic helpers, add validation    | 0%         | ~800 lines → ~200 lines + helper module       |
| Phase 2 – Performance       | Optimize entity registry operations        | 0%         | Target: 80%+ reduction in cleanup overhead    |
| Phase 3 – Organization      | Consolidate cleanup orchestration          | 0%         | 8 cleanup methods → unified orchestrator      |
| Phase 4 – Advanced (Future) | Audit trail, soft-delete, batch operations | 0%         | Deferred to v0.7.0+ unless priority escalates |

1. **Key objective** – Reduce duplication in coordinator.py CRUD/cleanup methods (lines 421-2566) from ~2,145 lines to ~800 lines while improving performance, maintainability, and adding missing validation.

2. **Summary of recent work** – Analysis completed 2026-01-20. Identified 9× duplicated CRUD patterns, 8 separate cleanup methods, entity registry performance bottleneck (measured at .3fs, scales O(n×m)), missing data validation on all `_create_*` methods.

3. **Next steps (short term)** –
   - Create `crud_helpers.py` with generic validation/CRUD functions
   - Add schema validation decorators for incoming entity data
   - Extract common entity registry removal pattern to `kc_helpers.py`

4. **Risks / blockers** –
   - Refactor must maintain 100% backward compatibility with existing storage schema
   - Cannot break options flow workflows during transition
   - Must preserve all existing logging/debug behavior
   - Performance improvements must be validated with large datasets (100+ kids/chores)

5. **References** –
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Storage schema v42+, data model
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Naming conventions, constant usage
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) – Phase 0 audit standards
   - Coordinator analysis: Lines 421-2566 (2,145 lines of CRUD/cleanup code)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Use decorator pattern for schema validation (non-breaking)
     - Keep existing `_create_*`/`_update_*` method signatures (internal APIs)
     - Cache expected entity UIDs on config change events (invalidate on assignment changes)
     - Defer soft-delete/undo to v0.7.0 (requires storage schema change)
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** This plan focuses on code consolidation and performance. Shadow kid deletion complexity was explicitly excluded per user request (unlink/relink is sufficient).

## Tracking expectations

- **Summary upkeep**: Update summary table percentages after each phase milestone. Reference commit SHAs for completed steps.
- **Detailed tracking**: Use phase sections below for granular progress. Do not pollute summary with implementation details.

---

## Detailed phase tracking

### Phase 1 – Foundation (Helpers & Validation)

**Goal**: Extract reusable patterns from duplicated CRUD code and add missing validation layer.

**Steps / detailed work items**:

1. **Create `entity_crud_helper.py` module** (Status: Not started)
   - Location: `custom_components/kidschores/entity_crud_helper.py`
   - Extract generic validation function:
     ```python
     def validate_entity_exists(
         data: dict[str, dict],
         entity_type_key: str,
         entity_id: str,
         label_key: str
     ) -> None:
         """Raise HomeAssistantError if entity not found."""
     ```
   - Extract generic entity creation logger:
     ```python
     def log_entity_operation(
         operation: str,  # "Added" | "Updated" | "Deleted"
         entity_type: str,
         entity_name: str,
         entity_id: str
     ) -> None:
         """Standardized logging for CRUD operations."""
     ```
   - Extract field update helper:
     ```python
     def update_entity_fields(
         entity_info: dict[str, Any],
         update_data: dict[str, Any],
         field_mappings: dict[str, tuple[str, Any]]  # (const_key, default_value)
     ) -> None:
         """Generic field updater with defaults."""
     ```

2. **Add schema validation decorators** (Status: Not started)
   - Create `@validate_entity_schema` decorator in `entity_crud_helper.py`
   - Define schema validators for each entity type:
     - `SCHEMA_KID_CREATE` / `SCHEMA_KID_UPDATE`
     - `SCHEMA_PARENT_CREATE` / `SCHEMA_PARENT_UPDATE`
     - `SCHEMA_CHORE_CREATE` / `SCHEMA_CHORE_UPDATE`
     - `SCHEMA_BADGE_CREATE` / `SCHEMA_BADGE_UPDATE`
     - `SCHEMA_REWARD_CREATE` / `SCHEMA_REWARD_UPDATE`
     - `SCHEMA_PENALTY_CREATE` / `SCHEMA_PENALTY_UPDATE`
     - `SCHEMA_BONUS_CREATE` / `SCHEMA_BONUS_UPDATE`
     - `SCHEMA_ACHIEVEMENT_CREATE` / `SCHEMA_ACHIEVEMENT_UPDATE`
     - `SCHEMA_CHALLENGE_CREATE` / `SCHEMA_CHALLENGE_UPDATE`
   - Apply decorators to all `_create_*` and `_update_*` methods
   - Validation should:
     - Check required fields presence
     - Validate field types (str, int, float, list, dict)
     - Reject unknown fields (strict mode)
     - Log validation failures at WARNING level

3. **Refactor `_create_kid()` as reference implementation** (Status: Not started)
   - File: `coordinator.py`, Line ~971
   - Before (current):
     ```python
     def _create_kid(self, kid_id: str, kid_data: dict[str, Any]):
         self._data[const.DATA_KIDS][kid_id] = {
             const.DATA_KID_NAME: kid_data.get(const.DATA_KID_NAME, const.SENTINEL_EMPTY),
             const.DATA_KID_POINTS: kid_data.get(const.DATA_KID_POINTS, const.DEFAULT_ZERO),
             # ... 20+ more fields
         }
         const.LOGGER.debug("DEBUG: Kid Added - '%s', ID '%s'", ...)
     ```
   - After (using helpers):
     ```python
     @validate_entity_schema(SCHEMA_KID_CREATE)
     def _create_kid(self, kid_id: str, kid_data: dict[str, Any]):
         self._data[const.DATA_KIDS][kid_id] = build_kid_data_structure(kid_data)
         log_entity_operation("Added", const.LABEL_KID, kid_data[const.DATA_KID_NAME], kid_id)
     ```

4. **Migrate remaining entity types to helpers** (Status: Not started)
   - Parents: Lines ~1038-1093 (`_create_parent`, `_update_parent`)
   - Chores: Lines ~1292-1320 (`_create_chore`) - Note: `_update_chore` is complex, keep separate
   - Badges: Lines ~1677-1709 (`_create_badge`, `_update_badge`)
   - Rewards: Lines ~1711-1756 (`_create_reward`, `_update_reward`)
   - Penalties: Lines ~1807-1852 (`_create_penalty`, `_update_penalty`)
   - Bonuses: Lines ~1759-1804 (`_create_bonus`, `_update_bonus`)
   - Achievements: Lines ~1855-1952 (`_create_achievement`, `_update_achievement`)
   - Challenges: Lines ~1955-2081 (`_create_challenge`, `_update_challenge`)

5. **Testing** (Status: Not started)
   - Run full test suite: `pytest tests/ -v`
   - Validate no regressions in existing CRUD workflows
   - Add unit tests for new helpers: `tests/test_entity_crud_helper.py`
   - Test schema validation rejection paths
   - Verify logging output unchanged (grep for "Added", "Updated" patterns)

**Key issues**:

- Risk: Schema validation could break existing options flow if schemas too strict
- Mitigation: Start with warning-only mode, promote to errors after validation
- Chore update logic (`_update_chore`) is complex due to completion criteria conversion - keep separate initially

---

### Phase 2 – Performance (Entity Registry Optimization)

**Goal**: Reduce entity registry scan overhead from O(n×m) to O(n) and cache expected entity UIDs.

**Steps / detailed work items**:

1. **Extract common entity registry removal pattern** (Status: Not started)
   - Add to `kc_helpers.py` (after Line ~1630, Device Info section):

     ```python
     async def remove_orphaned_entities_by_pattern(
         hass: HomeAssistant,
         entry_id: str,
         entity_domain: str,  # "sensor" | "button"
         suffix: str | None,
         validation_func: Callable[[str, EntityEntry], bool],
         label: str  # For logging
     ) -> int:
         """Generic orphaned entity removal by UID pattern matching.

         Returns count of removed entities.
         """
     ```

   - Replace 4× duplicated patterns:
     - `_remove_orphaned_shared_chore_sensors()` (Line 439)
     - `_remove_orphaned_achievement_entities()` (Line 536)
     - `_remove_orphaned_challenge_entities()` (Line 563)
     - `_remove_orphaned_kid_chore_entities()` (Line 461) - **Critical bottleneck**

2. **Optimize `_remove_orphaned_kid_chore_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 461-534
   - Current complexity: O(entities × chores × kids)
   - Target: O(entities) with set lookups
   - Before (current):
     ```python
     for entity_entry in list(ent_reg.entities.values()):
         # ... nested chore loop
         for chore_id in self.chores_data:  # ❌ O(n×m)
     ```
   - After (optimized):

     ```python
     # Build valid combinations once: O(kids + chores)
     valid_uids = set()
     for chore_id, chore_info in self.chores_data.items():
         for kid_id in chore_info[const.DATA_CHORE_ASSIGNED_KIDS]:
             # Add all expected UID patterns for this kid+chore
             valid_uids.add(f"{prefix}{kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}")
             valid_uids.add(f"{prefix}{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}")
             # ... etc

     # Scan registry once: O(entities)
     for entity_entry in list(ent_reg.entities.values()):
         if entity_entry.unique_id not in valid_uids:  # O(1) set lookup
             ent_reg.async_remove(entity_entry.entity_id)
     ```

   - Measure: Log before/after performance with `time.perf_counter()`
   - Target: <.1fs for medium setups (was .3fs), linear scaling

3. **Add expected entity UID cache** (Status: Not started)
   - File: `coordinator.py` `__init__` method (after Line ~400)
   - Add coordinator fields:
     ```python
     self._expected_entity_cache: dict[str, set[str]] = {
         "buttons": set(),
         "sensors": set(),
     }
     self._cache_invalidated: bool = True
     ```
   - Create cache rebuilder:
     ```python
     def _rebuild_expected_entities_cache(self) -> None:
         """Build expected entity UIDs once per config change."""
         self._expected_entity_cache["buttons"] = self._build_expected_button_uids()
         self._expected_entity_cache["sensors"] = self._build_expected_sensor_uids()
         self._cache_invalidated = False
         const.LOGGER.debug("PERF: Rebuilt entity UID cache (%d buttons, %d sensors)",
             len(self._expected_entity_cache["buttons"]),
             len(self._expected_entity_cache["sensors"]))
     ```
   - Invalidate cache on:
     - Kid/parent/chore/reward/badge assignment changes
     - Entity creation/deletion via options flow
     - Config entry reload

4. **Refactor `remove_deprecated_button_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 771-853
   - Current: Rebuilds whitelist every call (~100 lines)
   - After: Use cached expected UIDs:

     ```python
     def remove_deprecated_button_entities(self) -> None:
         if self._cache_invalidated:
             self._rebuild_expected_entities_cache()

         allowed_uids = self._expected_entity_cache["buttons"]
         # ... simple diff against registry
     ```

   - Estimated reduction: 100 lines → 20 lines

5. **Refactor `remove_deprecated_sensor_entities()`** (Status: Not started)
   - File: `coordinator.py`, Lines 855-970
   - Current: Rebuilds whitelist every call (~115 lines)
   - After: Use cached expected UIDs (same pattern as buttons)
   - Estimated reduction: 115 lines → 20 lines

6. **Performance validation** (Status: Not started)
   - Create large test scenario: 50 kids, 30 chores, 20 rewards, 10 badges
   - Measure entity registry cleanup time before/after
   - Target metrics:
     - `_remove_orphaned_kid_chore_entities()`: <.1fs (was .3fs)
     - `remove_deprecated_button_entities()`: <.05fs
     - `remove_deprecated_sensor_entities()`: <.05fs
     - Total cleanup overhead: <.2fs (down from ~.5fs+)
   - Add performance regression test to CI

**Key issues**:

- Risk: Cache invalidation logic could miss edge cases
- Mitigation: Add cache validation in debug mode (compare cache vs rebuild)
- Risk: Set operations could have memory overhead with 1000+ entities
- Mitigation: Profile memory usage, consider LRU cache if needed

---

### Phase 3 – Organization (Cleanup Orchestration)

**Goal**: Consolidate 8 separate cleanup methods into unified orchestrator with dependency resolution.

**Steps / detailed work items**:

1. **Create cleanup orchestrator class** (Status: Not started)
   - File: `coordinator.py` (new class before Line ~421)
   - Design:

     ```python
     class EntityCleanupOrchestrator:
         """Manages cleanup operations after entity deletions.

         Ensures cleanup steps execute in correct order with dependency resolution.
         """

         def __init__(self, coordinator: KidsChoresDataCoordinator):
             self.coordinator = coordinator
             self._cleanup_graph = self._build_cleanup_dependency_graph()

         async def cleanup_after_deletion(
             self,
             entity_type: str,
             entity_id: str,
             cascade: bool = True
         ) -> CleanupResult:
             """Execute cleanup steps for deleted entity."""
     ```

2. **Define cleanup dependency graph** (Status: Not started)
   - Map relationships:

     ```
     Kid deletion →
       1. Remove kid entities (buttons, sensors)
       2. Remove kid from chore assignments
       3. Remove kid from achievement assignments
       4. Remove kid from challenge assignments
       5. Remove kid from parent associations
       6. Cleanup pending reward approvals
       7. Cleanup unused translation sensors

     Chore deletion →
       1. Remove chore entities (shared state sensors)
       2. Remove chore from kids' kid_chore_data
       3. Remove chore from achievement selected_chore_id
       4. Remove chore from challenge selected_chore_id
       5. Remove orphaned kid-chore entities

     Parent deletion →
       1. Cascade to shadow kid (if exists)
       2. Cleanup unused translation sensors
     ```

   - Encode as directed acyclic graph (DAG) with topological sort

3. **Migrate existing cleanup methods** (Status: Not started)
   - Wrap existing methods in orchestrator:
     - `_cleanup_chore_from_kid` (Line 617)
     - `_cleanup_pending_reward_approvals` (Line 636)
     - `_cleanup_deleted_kid_references` (Line 649)
     - `_cleanup_deleted_chore_references` (Line 690)
     - `_cleanup_parent_assignments` (Line 702)
     - `_cleanup_deleted_chore_in_achievements` (Line 716)
     - `_cleanup_deleted_chore_in_challenges` (Line 728)
   - Keep methods as internal steps, orchestrator manages invocation order

4. **Update public delete methods** (Status: Not started)
   - Replace manual cleanup sequences:
     - `delete_kid_entity()` (Line 2363): Currently calls 4 cleanup methods
     - `delete_chore_entity()` (Line 2277): Currently calls 3 cleanup methods + async task
     - `delete_parent_entity()` (Line 2222): Currently calls 1 cleanup method
     - `delete_reward_entity()` (Line 2394): Currently calls 1 cleanup method
     - `delete_achievement_entity()` (Line 2505): Currently calls 1 async task
     - `delete_challenge_entity()` (Line 2543): Currently calls 1 async task
   - Replace with single orchestrator call:
     ```python
     async def delete_kid_entity(self, kid_id: str) -> None:
         # ... validation
         del self._data[const.DATA_KIDS][kid_id]
         await self._cleanup_orchestrator.cleanup_after_deletion("kid", kid_id)
         self._persist()
         self.async_update_listeners()
     ```

5. **Add cleanup validation/testing** (Status: Not started)
   - Create `tests/test_cleanup_orchestration.py`
   - Test scenarios:
     - Delete kid with active chores (verify all references removed)
     - Delete chore assigned to multiple kids (verify all kid entities removed)
     - Delete parent with associated kids (verify parent associations cleared)
     - Delete chore selected in achievement/challenge (verify references cleared)
   - Add orchestrator dry-run mode for debugging:
     ```python
     result = await orchestrator.cleanup_after_deletion("kid", kid_id, dry_run=True)
     print(result.planned_steps)  # Shows cleanup steps without executing
     ```

6. **Documentation** (Status: Not started)
   - Update `ARCHITECTURE.md` with cleanup orchestration section
   - Document cleanup dependency graph in docstrings
   - Add troubleshooting guide for orphaned entities

**Key issues**:

- Risk: Orchestrator could introduce new bugs if dependency graph incomplete
- Mitigation: Keep existing cleanup methods, orchestrator just invokes them in correct order
- Risk: Async task cleanup could be missed (achievements, challenges)
- Mitigation: Orchestrator should track async cleanup tasks and ensure completion

---

### Phase 4 – Advanced Features (Deferred to v0.7.0+)

**Goal**: Add audit trail, soft-delete with undo, and batch entity registry operations.

**Rationale**: These features require storage schema changes (audit log structure) and significant testing. Defer unless priority escalates.

**Steps / detailed work items**:

1. **Audit trail for options flow changes** (Status: Deferred)
   - Design: Add `audit_log` section to storage schema v43+
   - Track: who, when, what changed (entity type, entity ID, changed fields)
   - Storage format:
     ```json
     "audit_log": {
       "entries": [
         {
           "timestamp": "2026-01-20T15:30:00Z",
           "user_id": "user.parent1",
           "action": "update",
           "entity_type": "kid",
           "entity_id": "kid-uuid",
           "changes": {
             "name": {"old": "Sarah", "new": "Sarah M."},
             "points": {"old": 100, "new": 150}
           }
         }
       ]
     }
     ```
   - Retention: Configurable via options (default: 90 days)

2. **Soft-delete with undo mechanism** (Status: Deferred)
   - Add `deleted_at` timestamp to entity data
   - Keep deleted entities in storage for grace period (default: 7 days)
   - Add `restore_deleted_entity()` service call
   - UI: Show "Recently Deleted" section in options flow
   - Auto-purge after grace period expires

3. **Batch entity registry operations** (Status: Deferred)
   - Investigate HA core support for batch `async_remove()`
   - If not available, implement custom batching:
     ```python
     async def async_batch_remove_entities(
         ent_reg: EntityRegistry,
         entity_ids: list[str]
     ) -> int:
         """Remove multiple entities in single registry write."""
         # Implementation depends on HA core internals
     ```
   - Target: Reduce registry write overhead by 80%+ for bulk operations

4. **Performance telemetry** (Status: Deferred)
   - Add opt-in performance metrics collection
   - Track: entity registry scan times, cleanup durations, cache hit rates
   - Report: Expose as diagnostic sensor for debugging

**Key issues**:

- Requires storage schema v43+ (breaking change)
- Needs comprehensive migration testing
- UI work for "Recently Deleted" section
- Consider privacy implications of audit trail

---

## Testing & validation

### Phase 1 Testing

- [ ] Unit tests for `entity_crud_helper.py` validators
- [ ] Schema validation rejection tests (malformed data)
- [ ] Full integration test suite (no regressions)
- [ ] Verify logging output unchanged

### Phase 2 Testing

- [ ] Performance benchmarks before/after (50 kids, 30 chores scenario)
- [ ] Entity registry cleanup correctness (no false positives)
- [ ] Cache invalidation edge cases
- [ ] Memory profiling for large datasets

### Phase 3 Testing

- [ ] Cleanup orchestration correctness (all references removed)
- [ ] Dependency graph validation (no circular dependencies)
- [ ] Dry-run mode verification
- [ ] Cascade deletion integration tests

### Phase 4 Testing (Deferred)

- [ ] Audit trail storage/retrieval
- [ ] Soft-delete restore workflows
- [ ] Batch operation performance
- [ ] Migration from v42 → v43 schema

### Quality Gates

- All phases require:
  - `./utils/quick_lint.sh --fix` passing (9.5+/10)
  - `mypy custom_components/kidschores/` zero errors
  - `pytest tests/ -v` 100% pass rate
  - Code coverage maintained at 95%+

---

## Notes & follow-up

### Architecture decisions

1. **Why decorator pattern for validation?**
   - Non-breaking: Can be added incrementally
   - Testable: Validation logic isolated from CRUD logic
   - Flexible: Can switch to warning-only mode during transition

2. **Why cache expected entity UIDs?**
   - Performance: Rebuilding whitelist on every cleanup is O(n×m×k)
   - Cache: One-time cost O(n+m+k), then O(1) lookups
   - Trade-off: ~1-2KB memory for 10× performance improvement

3. **Why orchestrator pattern for cleanup?**
   - Correctness: Ensures cleanup steps execute in dependency order
   - Maintainability: Single place to manage cleanup logic
   - Testability: Can dry-run cleanup without side effects
   - Extensibility: Easy to add new cleanup steps

### Code reduction estimate

| Section                   | Current Lines | After Refactor | Reduction  |
| ------------------------- | ------------- | -------------- | ---------- |
| CRUD methods (Phase 1)    | ~800          | ~200           | -600       |
| Entity registry (Phase 2) | ~500          | ~200           | -300       |
| Cleanup methods (Phase 3) | ~300          | ~150           | -150       |
| **Total**                 | **~1,600**    | **~550**       | **-1,050** |

Plus ~300 lines of new helper code = **Net reduction: ~750 lines (~35% smaller)**

### Performance improvement estimate

| Operation                        | Before    | After      | Improvement |
| -------------------------------- | --------- | ---------- | ----------- |
| Kid-chore entity cleanup         | .3fs      | <.1fs      | 3×          |
| Deprecated button entity removal | ~.05fs    | <.01fs     | 5×          |
| Deprecated sensor entity removal | ~.05fs    | <.01fs     | 5×          |
| **Total cleanup overhead**       | **~.4fs** | **~.12fs** | **3.3×**    |

### Follow-up tasks

1. **Phase 1 completion** → Update [ARCHITECTURE.md](../ARCHITECTURE.md) with validation decorator pattern
2. **Phase 2 completion** → Document entity UID cache behavior in [ARCHITECTURE.md](../ARCHITECTURE.md)
3. **Phase 3 completion** → Add cleanup orchestration diagram to [ARCHITECTURE.md](../ARCHITECTURE.md)
4. **All phases** → Update [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) Phase 0 checklist with new patterns

### Dependencies

- No external package dependencies required
- Compatible with current storage schema v42
- No changes to entity platform files (sensor.py, button.py)
- No changes to config/options flow logic (flow signatures unchanged)

### Risk mitigation

- **Backward compatibility**: Keep existing method signatures, add helpers internally
- **Incremental rollout**: Phase 1 validation in warning-only mode initially
- **Performance validation**: Benchmark before/after with realistic data
- **Rollback plan**: Git revert possible at any phase boundary (no schema changes)

---

## Completion criteria

This initiative is considered complete when:

- [ ] Phase 1 complete: Generic CRUD helpers extracted, validation added
- [ ] Phase 2 complete: Entity registry operations optimized, cache implemented
- [ ] Phase 3 complete: Cleanup orchestrator deployed, all delete methods migrated
- [ ] All tests passing (unit + integration + performance)
- [ ] Documentation updated (ARCHITECTURE.md, CODE_REVIEW_GUIDE.md)
- [ ] Performance benchmarks meet targets (3× improvement in cleanup)
- [ ] Code coverage maintained at 95%+
- [ ] No regressions in options flow workflows
- [ ] Peer review completed (2+ reviewers)

**Phase 4 deferred** to v0.7.0+ unless priority changes.

---

_Plan created: 2026-01-20_
_Last updated: 2026-01-20 (Deep dive added)_
_Status: Planning phase - awaiting approval to begin Phase 1_

---

# 🔬 DEEP DIVE: Implementation Details & Critical Patterns

## Table of Contents

1. [CRUD Method Pattern Analysis](#crud-method-pattern-analysis)
2. [Entity Type Catalog](#entity-type-catalog)
3. [Default Value Patterns](#default-value-patterns)
4. [Validation Requirements](#validation-requirements)
5. [Logging Standards](#logging-standards)
6. [Storage Access Patterns](#storage-access-patterns)
7. [Entity Registry UID Patterns](#entity-registry-uid-patterns)
8. [Overlooked Opportunities](#overlooked-opportunities)
9. [Hidden Traps & Edge Cases](#hidden-traps--edge-cases)
10. [Migration Safety Checklist](#migration-safety-checklist)

---

## 1. CRUD Method Pattern Analysis

### Current Duplication Map

**Pattern A: Simple Create (7 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    self._data[const.DATA_XS][x_id] = {
        const.DATA_X_FIELD1: x_data.get(const.DATA_X_FIELD1, DEFAULT),
        const.DATA_X_FIELD2: x_data.get(const.DATA_X_FIELD2, DEFAULT),
        # ... N more fields
        const.DATA_X_INTERNAL_ID: x_id,  # ⚠️ Always last field
    }
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)
```

**Used by**: Rewards, Bonuses, Penalties, Achievements, Challenges, Parents (partial), Badges (partial)

**Pattern B: Simple Update (9 entity types)**

```python
def _update_X(self, x_id: str, x_data: dict[str, Any]):
    x_info = self._data[const.DATA_XS][x_id]
    x_info[const.DATA_X_FIELD1] = x_data.get(const.DATA_X_FIELD1, x_info[const.DATA_X_FIELD1])
    x_info[const.DATA_X_FIELD2] = x_data.get(const.DATA_X_FIELD2, x_info[const.DATA_X_FIELD2])
    # ... N more fields
    const.LOGGER.debug("DEBUG: X Updated - '%s', ID '%s'", name, x_id)
```

**Used by**: Rewards, Bonuses, Penalties, Achievements, Challenges, Badges (partial), Parents

**Pattern C: Complex Create with Side Effects (2 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    # Pre-processing/validation
    validated_refs = [ref for ref in x_data.get(REFS) if ref in other_data]

    self._data[const.DATA_XS][x_id] = { ... }
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)

    # Post-create side effects
    for kid_id in assigned_kids:
        self.hass.async_create_task(self._notify_kid(...))
```

**Used by**: Chores (notifications), Parents (kid validation)

**Pattern D: Delegated Create (2 entity types)**

```python
def _create_X(self, x_id: str, x_data: dict[str, Any]):
    # Delegates to helper function
    self._data[const.DATA_XS][x_id] = kh.build_default_X_data(x_id, x_data)
    const.LOGGER.debug("DEBUG: X Added - '%s', ID '%s'", name, x_id)
```

**Used by**: Chores (`kh.build_default_chore_data`), Kids (partial - uses `.get()` pattern)

**Pattern E: Update with State Machine (1 entity type)**

```python
def _update_X(self, x_id: str, x_data: dict[str, Any]) -> bool:
    x_info = self._data[const.DATA_XS][x_id]

    # Complex state transitions
    old_state = x_info.get(STATE_FIELD)
    new_state = x_data.get(STATE_FIELD)

    if new_state != old_state:
        self._handle_state_transition(x_id, x_info, old_state, new_state)

    # ... field updates

    return state_changed  # Signals reload needed
```

**Used by**: Chores (completion criteria conversion, assignment changes)

### Complexity Matrix

| Entity Type | Create Lines | Update Lines | Side Effects | State Machine | Helper Delegation  |
| ----------- | ------------ | ------------ | ------------ | ------------- | ------------------ |
| Reward      | ~24          | ~18          | None         | No            | No                 |
| Bonus       | ~24          | ~18          | None         | No            | No                 |
| Penalty     | ~24          | ~18          | None         | No            | No                 |
| Achievement | ~28          | ~25          | None         | No            | No                 |
| Challenge   | ~32          | ~30          | None         | No            | No                 |
| Badge       | ~14          | ~14          | None         | No            | No (direct assign) |
| Kid         | ~45          | ~10          | None         | No            | Partial            |
| Parent      | ~40          | ~55          | Validation   | No            | No                 |
| **Chore**   | **~30**      | **~155**     | **Notify**   | **YES**       | **YES**            |

**Key Insight**: Chores are 3-5× more complex than other entity types. **DO NOT** consolidate chore update logic initially.

---

## 2. Entity Type Catalog

### Entity Field Inventory

#### Kids (22 fields)

```python
{
    const.DATA_KID_NAME: str,
    const.DATA_KID_POINTS: float,
    const.DATA_KID_BADGES_EARNED: dict[str, Any],  # badge_id → earned_data
    const.DATA_KID_HA_USER_ID: str | None,
    const.DATA_KID_INTERNAL_ID: str,  # UUID
    const.DATA_KID_POINTS_MULTIPLIER: float,
    const.DATA_KID_PENALTY_APPLIES: dict[str, int],  # penalty_id → count
    const.DATA_KID_BONUS_APPLIES: dict[str, int],  # bonus_id → count
    const.DATA_KID_REWARD_DATA: dict[str, Any],  # v0.5.0+ reward tracking
    const.DATA_KID_ENABLE_NOTIFICATIONS: bool,
    const.DATA_KID_MOBILE_NOTIFY_SERVICE: str,
    const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: bool,
    const.DATA_KID_OVERDUE_CHORES: list[str],  # chore_ids
    const.DATA_KID_OVERDUE_NOTIFICATIONS: dict[str, str],  # chore_id → timestamp
    const.DATA_KID_CHORE_DATA: dict[str, Any],  # v0.4.0+ timestamp tracking
    # Additional runtime fields (not in _create_kid):
    const.DATA_KID_BADGE_PROGRESS: dict[str, Any],  # badge_id → progress
    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS: dict[str, Any],
    const.DATA_KID_CHORE_STATS: dict[str, Any],  # completion counters
    const.DATA_KID_POINT_STATS: dict[str, Any],  # earned/spent tracking
    const.DATA_KID_IS_SHADOW: bool,  # Shadow kid marker
    const.DATA_KID_LINKED_PARENT_ID: str | None,  # Parent UUID
    const.DATA_KID_DASHBOARD_LANGUAGE: str,  # ISO language code
}
```

#### Parents (12 fields)

```python
{
    const.DATA_PARENT_NAME: str,
    const.DATA_PARENT_HA_USER_ID: str | None,
    const.DATA_PARENT_ASSOCIATED_KIDS: list[str],  # kid UUIDs
    const.DATA_PARENT_ENABLE_NOTIFICATIONS: bool,
    const.DATA_PARENT_MOBILE_NOTIFY_SERVICE: str,
    const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS: bool,
    const.DATA_PARENT_INTERNAL_ID: str,  # UUID
    const.DATA_PARENT_DASHBOARD_LANGUAGE: str,
    const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: bool,  # v0.6.0+
    const.DATA_PARENT_ENABLE_CHORE_WORKFLOW: bool,
    const.DATA_PARENT_ENABLE_GAMIFICATION: bool,
    const.DATA_PARENT_LINKED_SHADOW_KID_ID: str | None,  # Shadow kid UUID
}
```

#### Chores (20+ fields) ⚠️ COMPLEX

```python
{
    const.DATA_CHORE_NAME: str,
    const.DATA_CHORE_STATE: str,  # enabled/disabled/archived
    const.DATA_CHORE_DEFAULT_POINTS: float,
    const.DATA_CHORE_APPROVAL_RESET_TYPE: str,  # daily/weekly/monthly
    const.DATA_CHORE_DESCRIPTION: str,
    const.DATA_CHORE_LABELS: list[str],
    const.DATA_CHORE_ICON: str,
    const.DATA_CHORE_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_CHORE_RECURRING_FREQUENCY: str,  # daily/weekly/custom/etc.
    const.DATA_CHORE_DUE_DATE: str | None,  # ISO datetime
    const.DATA_CHORE_LAST_COMPLETED: str | None,  # ISO datetime
    const.DATA_CHORE_LAST_CLAIMED: str | None,  # ISO datetime
    const.DATA_CHORE_APPLICABLE_DAYS: list[int] | None,  # 0-6 (Mon-Sun)
    const.DATA_CHORE_NOTIFY_ON_CLAIM: bool,
    const.DATA_CHORE_NOTIFY_ON_APPROVAL: bool,
    const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL: bool,
    const.DATA_CHORE_CUSTOM_INTERVAL: int | None,
    const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: str | None,  # days/weeks/months
    const.DATA_CHORE_DAILY_MULTI_TIMES: str | None,  # CSV "08:00,14:00,20:00"
    const.DATA_CHORE_COMPLETION_CRITERIA: str,  # independent/shared
    const.DATA_CHORE_PER_KID_DUE_DATES: dict[str, str | None],  # kid_id → ISO
    const.DATA_CHORE_PER_KID_APPLICABLE_DAYS: dict[str, list[int]],  # PKAD-2026-001
    const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES: dict[str, str],  # PKAD-2026-001
    const.DATA_CHORE_INTERNAL_ID: str,  # UUID
}
```

#### Badges (11 fields)

```python
{
    const.DATA_BADGE_NAME: str,
    const.DATA_BADGE_DESCRIPTION: str,
    const.DATA_BADGE_ICON: str,
    const.DATA_BADGE_TYPE: str,  # cumulative/periodic
    const.DATA_BADGE_TRIGGER: str,  # chore_count/points_earned/streak/etc.
    const.DATA_BADGE_THRESHOLD: int,
    const.DATA_BADGE_PERIOD: str | None,  # daily/weekly/monthly (periodic only)
    const.DATA_BADGE_SELECTED_CHORE_ID: str | None,  # UUID
    const.DATA_BADGE_POINT_REWARD: float,
    const.DATA_BADGE_LABELS: list[str],
    const.DATA_BADGE_INTERNAL_ID: str,  # UUID
}
```

#### Rewards (6 fields)

```python
{
    const.DATA_REWARD_NAME: str,
    const.DATA_REWARD_COST: float,
    const.DATA_REWARD_DESCRIPTION: str,
    const.DATA_REWARD_LABELS: list[str],
    const.DATA_REWARD_ICON: str,
    const.DATA_REWARD_INTERNAL_ID: str,  # UUID
}
```

#### Penalties (6 fields)

```python
{
    const.DATA_PENALTY_NAME: str,
    const.DATA_PENALTY_POINTS: float,  # Negative value
    const.DATA_PENALTY_DESCRIPTION: str,
    const.DATA_PENALTY_LABELS: list[str],
    const.DATA_PENALTY_ICON: str,
    const.DATA_PENALTY_INTERNAL_ID: str,  # UUID
}
```

#### Bonuses (6 fields)

```python
{
    const.DATA_BONUS_NAME: str,
    const.DATA_BONUS_POINTS: float,
    const.DATA_BONUS_DESCRIPTION: str,
    const.DATA_BONUS_LABELS: list[str],
    const.DATA_BONUS_ICON: str,
    const.DATA_BONUS_INTERNAL_ID: str,  # UUID
}
```

#### Achievements (11 fields)

```python
{
    const.DATA_ACHIEVEMENT_NAME: str,
    const.DATA_ACHIEVEMENT_DESCRIPTION: str,
    const.DATA_ACHIEVEMENT_LABELS: list[str],
    const.DATA_ACHIEVEMENT_ICON: str,
    const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_ACHIEVEMENT_TYPE: str,  # streak/completion/points
    const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: str,  # UUID or ""
    const.DATA_ACHIEVEMENT_CRITERIA: str,
    const.DATA_ACHIEVEMENT_TARGET_VALUE: int,
    const.DATA_ACHIEVEMENT_REWARD_POINTS: float,
    const.DATA_ACHIEVEMENT_PROGRESS: dict[str, Any],  # kid_id → progress_data
    const.DATA_ACHIEVEMENT_INTERNAL_ID: str,  # UUID
}
```

#### Challenges (13 fields)

```python
{
    const.DATA_CHALLENGE_NAME: str,
    const.DATA_CHALLENGE_DESCRIPTION: str,
    const.DATA_CHALLENGE_LABELS: list[str],
    const.DATA_CHALLENGE_ICON: str,
    const.DATA_CHALLENGE_ASSIGNED_KIDS: list[str],  # kid UUIDs
    const.DATA_CHALLENGE_TYPE: str,  # daily_min/weekly_min/total
    const.DATA_CHALLENGE_SELECTED_CHORE_ID: str,  # UUID or SENTINEL_EMPTY
    const.DATA_CHALLENGE_CRITERIA: str,
    const.DATA_CHALLENGE_TARGET_VALUE: int,
    const.DATA_CHALLENGE_REWARD_POINTS: float,
    const.DATA_CHALLENGE_START_DATE: str | None,  # ISO date
    const.DATA_CHALLENGE_END_DATE: str | None,  # ISO date
    const.DATA_CHALLENGE_PROGRESS: dict[str, Any],  # kid_id → progress_data
    const.DATA_CHALLENGE_INTERNAL_ID: str,  # UUID
}
```

---

## 3. Default Value Patterns

### Default Constant Mapping

**CRITICAL**: These defaults must match exactly or validation will fail.

```python
# Entity-specific defaults (from const.py)
DEFAULT_ZERO = 0
DEFAULT_REWARD_COST = 10.0
DEFAULT_REWARD_ICON = "mdi:gift"
DEFAULT_BONUS_POINTS = 5.0
DEFAULT_BONUS_ICON = "mdi:star"
DEFAULT_PENALTY_POINTS = 5.0  # Applied as negative
DEFAULT_PENALTY_ICON = "mdi:alert"
DEFAULT_ACHIEVEMENT_TARGET = 5
DEFAULT_ACHIEVEMENT_REWARD_POINTS = 10.0
DEFAULT_CHALLENGE_TARGET = 3
DEFAULT_CHALLENGE_REWARD_POINTS = 5.0
DEFAULT_KID_POINTS_MULTIPLIER = 1.0
DEFAULT_NOTIFY_ON_CLAIM = True
DEFAULT_NOTIFY_ON_APPROVAL = True
DEFAULT_NOTIFY_ON_DISAPPROVAL = True
DEFAULT_APPROVAL_RESET_TYPE = "daily"
DEFAULT_DASHBOARD_LANGUAGE = "en"
DEFAULT_PARENT_ALLOW_CHORE_ASSIGNMENT = False
DEFAULT_PARENT_ENABLE_CHORE_WORKFLOW = True
DEFAULT_PARENT_ENABLE_GAMIFICATION = True

# Sentinel values (not defaults, but markers)
SENTINEL_EMPTY = ""
```

### `.get()` Pattern Analysis

**Pattern 1: Simple default** (most common)

```python
x_data.get(const.DATA_X_FIELD, const.DEFAULT_VALUE)
```

**Pattern 2: Nested fallback** (update methods)

```python
x_data.get(const.DATA_X_FIELD, x_info[const.DATA_X_FIELD])
# Or with double fallback:
x_data.get(const.DATA_X_FIELD, x_info.get(const.DATA_X_FIELD, const.DEFAULT))
```

**Pattern 3: Conditional default** (challenges, achievements)

```python
(
    x_data.get(const.DATA_X_FIELD)
    if x_data.get(const.DATA_X_FIELD) not in [None, {}]
    else None
)
```

**Pattern 4: List/dict defaults**

```python
x_data.get(const.DATA_X_LABELS, x_info.get(const.DATA_X_LABELS, []))
x_data.get(const.DATA_X_PROGRESS, {})
```

**TRAP**: Inconsistent `.get()` usage across entity types. Some use 2-level fallback, some don't.

---

## 4. Validation Requirements

### Current Validation Gaps (Missing in `_create_*` methods)

**❌ No Type Checking**:

```python
# Current: Accepts anything
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    self._data[const.DATA_REWARDS][reward_id] = {
        const.DATA_REWARD_COST: reward_data.get(const.DATA_REWARD_COST, 10.0),  # What if string?
    }
```

**❌ No Required Field Validation**:

```python
# Current: Silently uses SENTINEL_EMPTY if missing
const.DATA_REWARD_NAME: reward_data.get(const.DATA_REWARD_NAME, const.SENTINEL_EMPTY)
# Should: Raise error if name not provided
```

**❌ No Range Validation**:

```python
# Current: Accepts negative costs, zero points, etc.
const.DATA_REWARD_COST: reward_data.get(const.DATA_REWARD_COST, 10.0)
# Should: Validate cost > 0
```

**❌ No Reference Validation**:

```python
# Current: Parents can reference non-existent kids
const.DATA_PARENT_ASSOCIATED_KIDS: parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, [])
# Should: Validate all kid_ids exist in self.kids_data
```

### Required Validation Rules Per Entity

#### Universal Rules (All Entities)

- `internal_id`: Must be valid UUID string
- `name`: Required, non-empty string, max 100 chars
- `description`: Optional string, max 500 chars
- `labels`: Optional list of strings
- `icon`: Optional string, must match `mdi:*` pattern

#### Entity-Specific Rules

**Rewards**:

- `cost`: Required, float > 0

**Penalties**:

- `points`: Required, float (stored as negative)

**Bonuses**:

- `points`: Required, float > 0

**Kids**:

- `points`: float >= 0
- `points_multiplier`: float > 0, <= 10.0
- `ha_user_id`: Optional, must exist in HA users if provided
- `mobile_notify_service`: Optional, must match notify.\* service if provided

**Parents**:

- `associated_kids`: list[str], all UUIDs must exist in kids_data
- `ha_user_id`: Optional, must exist in HA users if provided
- `linked_shadow_kid_id`: If set, must point to valid shadow kid

**Chores** ⚠️ COMPLEX:

- `assigned_kids`: list[str], all UUIDs must exist in kids_data
- `default_points`: float >= 0
- `recurring_frequency`: Must be valid frequency constant
- `completion_criteria`: Must be "independent" or "shared"
- `per_kid_due_dates`: If present, keys must match assigned_kids
- `applicable_days`: list[int], all values 0-6
- `daily_multi_times`: If present, must be valid CSV time format

**Achievements/Challenges**:

- `assigned_kids`: list[str], all UUIDs must exist in kids_data
- `selected_chore_id`: If not empty, must exist in chores_data
- `target_value`: int > 0
- `reward_points`: float >= 0

**Badges**:

- `threshold`: int > 0
- `selected_chore_id`: If not None, must exist in chores_data
- `period`: If badge_type is "periodic", must be set

### Validation Strategy

**Phase 1**: Warning-only mode

```python
@validate_entity_schema(SCHEMA_REWARD_CREATE, mode="warn")
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    # Logs warnings but doesn't block
```

**Phase 2**: After 1 release, promote to errors

```python
@validate_entity_schema(SCHEMA_REWARD_CREATE, mode="error")
def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
    # Raises HomeAssistantError on validation failure
```

---

## 5. Logging Standards

### Current Logging Patterns

**Create methods**:

```python
const.LOGGER.debug(
    "DEBUG: X Added - '%s', ID '%s'",
    self._data[const.DATA_XS][x_id][const.DATA_X_NAME],
    x_id,
)
```

**Update methods**:

```python
const.LOGGER.debug(
    "DEBUG: X Updated - '%s', ID '%s'",
    x_info[const.DATA_X_NAME],
    x_id,
)
```

**Delete methods** (public):

```python
const.LOGGER.info("INFO: Deleted X '%s' (ID: %s)", x_name, x_id)
```

**Shadow kid operations**:

```python
const.LOGGER.info(
    "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
    parent_info.get(const.DATA_PARENT_NAME),
    shadow_kid_id,
    parent_info.get(const.DATA_PARENT_NAME),
    parent_id,
)
```

### Logging Anti-Patterns to Avoid

❌ **Redundant prefixes**:

```python
const.LOGGER.debug("DEBUG: message")  # Log level already shown
```

❌ **F-strings in logs**:

```python
const.LOGGER.debug(f"Value: {var}")  # Use lazy logging
```

✅ **Correct**:

```python
const.LOGGER.debug("Value: %s", var)
```

❌ **Inconsistent naming**:

```python
# Don't mix "Added" / "Created" / "Inserted"
const.LOGGER.debug("Added kid '%s'", ...)
const.LOGGER.debug("Created parent '%s'", ...)  # Pick one term
```

### Logging Consolidation Target

**Extract to helper**:

```python
def log_entity_crud(
    operation: str,  # "created", "updated", "deleted"
    entity_type: str,  # const.LABEL_KID, const.LABEL_CHORE, etc.
    entity_name: str,
    entity_id: str,
    level: str = "debug"  # "debug" or "info"
) -> None:
    """Standardized CRUD operation logging."""
    message = f"{operation.capitalize()} {entity_type} '%s' (ID: %s)"
    logger_func = getattr(const.LOGGER, level)
    logger_func(message, entity_name, entity_id)
```

---

## 6. Storage Access Patterns

### Dict Access Methods

**Pattern 1: Direct assignment** (create)

```python
self._data[const.DATA_KIDS][kid_id] = { ... }
```

**Pattern 2: Update existing** (update)

```python
kid_info = self._data[const.DATA_KIDS][kid_id]
kid_info[const.DATA_KID_NAME] = new_name
```

**Pattern 3: Update with .update()** (badge)

```python
existing = badges.get(badge_id, {})
existing.update(badge_data)  # Merge new fields
badges[badge_id] = existing
```

**Pattern 4: Setdefault** (badge create)

```python
self._data.setdefault(const.DATA_BADGES, {})[badge_id] = badge_data
```

**TRAP**: Inconsistent dict access patterns across entity types. Badge uses `.setdefault()` + `.update()`, others use direct assignment.

### Storage Hierarchy

```
self._data
├── const.DATA_KIDS: dict[str, KidData]
├── const.DATA_PARENTS: dict[str, ParentData]
├── const.DATA_CHORES: dict[str, ChoreData]
├── const.DATA_BADGES: dict[str, BadgeData]
├── const.DATA_REWARDS: dict[str, RewardData]
├── const.DATA_PENALTIES: dict[str, PenaltyData]
├── const.DATA_BONUSES: dict[str, BonusData]
├── const.DATA_ACHIEVEMENTS: dict[str, AchievementData]
├── const.DATA_CHALLENGES: dict[str, ChallengeData]
└── const.DATA_META: dict[str, Any]
```

**CRITICAL**: Always use `const.DATA_*` keys, never hardcoded strings.

---

## 7. Entity Registry UID Patterns

### UID Construction Formulas

**Kid-specific sensors**:

```
{entry_id}_{kid_id}{SENSOR_KC_UID_SUFFIX_*}
```

**Kid-chore sensors**:

```
{entry_id}_{kid_id}_{chore_id}{SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}
```

**Kid-chore buttons**:

```
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_CLAIM}
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_APPROVE}
{entry_id}_{kid_id}_{chore_id}{BUTTON_KC_UID_SUFFIX_DISAPPROVE}
```

**Reward buttons/sensors**:

```
{entry_id}_{BUTTON_REWARD_PREFIX}{kid_id}_{reward_id}
{entry_id}_{kid_id}_{reward_id}{BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}
{entry_id}_{kid_id}_{reward_id}{SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}
```

**Penalty/Bonus buttons**:

```
{entry_id}_{BUTTON_PENALTY_PREFIX}{kid_id}_{penalty_id}
{entry_id}_{BUTTON_BONUS_PREFIX}{kid_id}_{bonus_id}
```

**Points adjust buttons**:

```
{entry_id}_{kid_id}{BUTTON_KC_UID_MIDFIX_ADJUST_POINTS}{delta}
```

**Global sensors**:

```
{entry_id}{SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}
{entry_id}{SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}
```

**Shared chore global state**:

```
{entry_id}_{chore_id}{DATA_GLOBAL_STATE_SUFFIX}
```

**Dashboard helper** (hardcoded):

```
{entry_id}_{kid_id}_ui_dashboard_helper
```

**Badge progress sensors**:

```
{entry_id}_{kid_id}_{badge_id}{SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}
```

**Achievement/Challenge progress sensors**:

```
{entry_id}_{kid_id}_{achievement_id}{SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}
{entry_id}_{kid_id}_{challenge_id}{SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}
```

### UID Cache Structure

**Proposed cache**:

```python
self._expected_entity_cache = {
    "buttons": {
        "chore_claim": set(),  # kid-chore claim buttons
        "chore_approve": set(),  # kid-chore approve buttons
        "chore_disapprove": set(),
        "reward_claim": set(),
        "reward_approve": set(),
        "reward_disapprove": set(),
        "penalty_apply": set(),
        "bonus_apply": set(),
        "points_adjust": set(),
    },
    "sensors": {
        "kid": set(),  # kid-specific sensors (points, badges, etc.)
        "chore_status": set(),  # kid-chore status sensors
        "reward_status": set(),
        "penalty_applies": set(),
        "bonus_applies": set(),
        "badge_progress": set(),
        "achievement_progress": set(),
        "challenge_progress": set(),
        "shared_chore_state": set(),
        "global": set(),  # pending approvals
    },
}
```

---

## 8. Overlooked Opportunities

### 1. **Shadow Kid Workflow Integration**

**Opportunity**: Extend CRUD helpers to handle shadow kid creation/unlinking consistently.

**Current State**: Shadow kid logic scattered:

- `_create_shadow_kid_for_parent()` (Line 1170)
- `_unlink_shadow_kid()` (Line 1270)
- Duplicates kid creation logic with special markers

**Improvement**:

```python
# In entity_crud_helper.py
def create_shadow_kid_from_parent(
    parent_id: str,
    parent_data: dict[str, Any],
    coordinator: KidsChoresDataCoordinator
) -> tuple[str, dict[str, Any]]:
    """Build shadow kid data structure from parent.

    Returns:
        (shadow_kid_id, kid_data) tuple ready for _create_kid()
    """
    shadow_kid_id, kid_data = fh.build_shadow_kid_data(parent_id, parent_data)
    # Add shadow markers
    kid_data[const.DATA_KID_IS_SHADOW] = True
    kid_data[const.DATA_KID_LINKED_PARENT_ID] = parent_id
    return shadow_kid_id, kid_data
```

**Impact**: Reduces shadow kid creation from 30 lines → 5 lines.

### 2. **Notification Side Effects as Decorator**

**Current**: Chore creation sends notifications inline (Line 1375-1389).

**Opportunity**:

```python
@notify_after_create(
    entity_type="chore",
    recipient_field=const.DATA_CHORE_ASSIGNED_KIDS,
    notification_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED
)
def _create_chore(self, chore_id: str, chore_data: dict[str, Any]):
    # Just create, decorator handles notifications
```

**Benefit**: Separates data creation from side effects, easier testing.

### 3. **Field Update Batch Operations**

**Current**: Each update field is individual `.get()` call (18 lines for reward update).

**Opportunity**:

```python
# Define field mappings once
REWARD_UPDATE_FIELDS = {
    const.DATA_REWARD_NAME: (str, None),  # (type, default)
    const.DATA_REWARD_COST: (float, None),
    const.DATA_REWARD_DESCRIPTION: (str, None),
    const.DATA_REWARD_LABELS: (list, None),
    const.DATA_REWARD_ICON: (str, None),
}

# Update in one call
update_entity_fields(reward_info, reward_data, REWARD_UPDATE_FIELDS)
```

**Impact**: 18 lines → 1 line per entity update.

### 4. **Delegated Create Standardization**

**Current**: Only chores delegate to helper (`kh.build_default_chore_data`).

**Opportunity**: Extend pattern to all entity types:

```python
# In entity_crud_helper.py
def build_default_kid_data(kid_id: str, kid_data: dict[str, Any]) -> KidData:
    """Single source of truth for kid data structure."""

def build_default_parent_data(parent_id: str, parent_data: dict[str, Any]) -> ParentData:
    """Single source of truth for parent data structure."""
```

**Benefit**: Coordinator methods become thin wrappers, all logic in testable helpers.

### 5. **Transaction-like Operations**

**Current**: No rollback if operation fails mid-process.

**Opportunity**:

```python
class EntityTransaction:
    """Context manager for transactional entity operations."""

    def __enter__(self):
        self._snapshot = copy.deepcopy(self.coordinator._data)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Rollback on exception
            self.coordinator._data = self._snapshot
```

**Use case**: Complex chore conversion (SHARED ↔ INDEPENDENT) could corrupt data mid-conversion.

### 6. **Entity Reference Graph**

**Current**: Manual reference tracking in cleanup methods.

**Opportunity**: Build dependency graph at startup:

```python
# At coordinator init
self._entity_graph = EntityReferenceGraph(self._data)
# Query dependencies
refs = self._entity_graph.get_references_to("kid", kid_id)
# Returns: [("chore", chore_id), ("achievement", ach_id), ...]
```

**Benefit**: Automated orphan detection, cleanup validation.

---

## 9. Hidden Traps & Edge Cases

### TRAP 1: Badge Update Uses `.update()` Instead of Direct Assignment

**Location**: `_update_badge()` (Line 1694)

**Code**:

```python
existing = badges.get(badge_id, {})
existing.update(badge_data)  # ⚠️ Merges instead of replaces
badges[badge_id] = existing
```

**Other entity types**:

```python
badge_info = self._data[const.DATA_BADGES][badge_id]
badge_info[FIELD] = new_value  # Direct field updates
```

**Risk**: If helper uses direct assignment pattern, badge updates will break.

**Solution**: Helper must support both update strategies:

```python
def update_entity(
    entity_dict: dict,
    entity_id: str,
    update_data: dict,
    update_strategy: str = "fields"  # "fields" or "merge"
):
    if update_strategy == "merge":
        existing = entity_dict.get(entity_id, {})
        existing.update(update_data)
        entity_dict[entity_id] = existing
    else:
        # Field-by-field updates
        entity_info = entity_dict[entity_id]
        for key, value in update_data.items():
            entity_info[key] = value
```

### TRAP 2: Parent Validation Must Check Kid Existence

**Location**: `_create_parent()` / `_update_parent()` (Lines 1108-1119, 1173-1182)

**Code**:

```python
for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
    if kid_id in self.kids_data:
        associated_kids_ids.append(kid_id)
    else:
        const.LOGGER.warning(
            "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
            parent_data.get(const.DATA_PARENT_NAME, parent_id),
            kid_id,
        )
```

**Risk**: Generic helper won't have access to `self.kids_data` for validation.

**Solution**: Pass coordinator reference to validation:

```python
@validate_entity_schema(SCHEMA_PARENT_CREATE, coordinator_ref=True)
def _create_parent(self, parent_id: str, parent_data: dict[str, Any]):
    # Decorator injects self (coordinator) for cross-entity validation
```

### TRAP 3: Chore Update Returns Boolean (Reload Signal)

**Location**: `_update_chore()` (Line 1393)

**Signature**:

```python
def _update_chore(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
    # Returns True if assigned_kids changed (requires reload)
```

**Risk**: Generic update helper signature won't match.

**Solution**: Keep chore update separate, or use optional return:

```python
def update_entity(...) -> dict[str, Any]:
    """Returns metadata about update."""
    return {
        "success": True,
        "reload_needed": False,  # Chores can set True
        "side_effects": [],
    }
```

### TRAP 4: Chore Conversion Logic is Stateful

**Location**: `_convert_independent_to_shared()` / `_convert_shared_to_independent()` (Lines 1575-1740)

**Complexity**:

- Modifies both `chore_info` AND `chore_data` dicts
- Clears per-kid fields when converting to SHARED
- Populates per-kid fields when converting to INDEPENDENT
- Must handle `applicable_days` type conversion (strings → integers)

**Risk**: Cannot consolidate into generic helper without significant refactoring.

**Solution**: **DO NOT consolidate chore update initially**. Phase 1 skips chores.

### TRAP 5: Challenge/Achievement Date Fields Need Null Coalescing

**Location**: `_create_challenge()` (Lines 2000-2009)

**Code**:

```python
const.DATA_CHALLENGE_START_DATE: (
    challenge_data.get(const.DATA_CHALLENGE_START_DATE)
    if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
    else None
),
```

**Reason**: Options flow might send `{}` instead of `None` for empty dates.

**Risk**: Generic helper using simple `.get()` will store `{}` instead of `None`.

**Solution**: Add date field preprocessor:

```python
def normalize_optional_date(value: Any) -> str | None:
    """Convert empty values to None for date fields."""
    return value if value not in [None, {}, ""] else None
```

### TRAP 6: Kid Create Has No Side Effects, But Update Does (Device Registry)

**Location**: `update_kid_entity()` (Line 2353)

**Code**:

```python
# Check if name is changing
old_name = self._data[const.DATA_KIDS][kid_id].get(const.DATA_KID_NAME)
new_name = kid_data.get(const.DATA_KID_NAME)

self._update_kid(kid_id, kid_data)
# ...

# Update device registry if name changed
if new_name and new_name != old_name:
    self._update_kid_device_name(kid_id, new_name)
```

**Risk**: Generic update helper won't trigger device registry update.

**Solution**: Post-update hook system:

```python
@post_update_hook("update_device_name")
def _update_kid(self, kid_id: str, kid_data: dict[str, Any]):
    # Decorator calls hook after update if name changed
```

### TRAP 7: Internal ID Must Always Be Last Field

**Pattern observed** (all create methods):

```python
{
    const.DATA_X_FIELD1: value1,
    const.DATA_X_FIELD2: value2,
    # ... more fields
    const.DATA_X_INTERNAL_ID: x_id,  # ⚠️ Always last
}
```

**Reason**: Likely code review convention for easy visual verification.

**Risk**: Auto-generated dict might put internal_id first alphabetically.

**Solution**: Use OrderedDict or explicit field ordering in helper.

### TRAP 8: Logging Extracts Name from Created Dict vs Updated Dict

**Create**:

```python
const.LOGGER.debug(
    "DEBUG: X Added - '%s', ID '%s'",
    self._data[const.DATA_XS][x_id][const.DATA_X_NAME],  # ⚠️ From storage
    x_id,
)
```

**Update**:

```python
const.LOGGER.debug(
    "DEBUG: X Updated - '%s', ID '%s'",
    x_info[const.DATA_X_NAME],  # ⚠️ From local variable
    x_id,
)
```

**Risk**: Logger helper must know where to get name (storage vs parameter).

**Solution**: Always pass name explicitly:

```python
def log_entity_crud(operation, entity_type, entity_name, entity_id):
    # Caller responsible for extracting name
```

---

## 10. Migration Safety Checklist

### Pre-Implementation Validation

- [ ] **Identify ALL usage of `_create_*` / `_update_*` methods**
  - `grep -r "_create_kid\|_update_kid" custom_components/kidschores/`
  - Validate no external calls outside coordinator/options_flow

- [ ] **Verify ALL entity types have consistent field structures**
  - Run storage validator against test scenarios
  - Check for unexpected nested dicts or type inconsistencies

- [ ] **Document ALL side effects**
  - Chore create → notifications
  - Parent create → kid validation + shadow kid creation
  - Parent update → shadow kid linking/unlinking
  - Kid update → device registry update
  - Chore update → completion criteria conversion
  - Badge update → progress recalculation

- [ ] **Map ALL cleanup method dependencies**
  - Which cleanup methods call other cleanup methods?
  - What's the execution order?
  - Are there circular dependencies?

### Implementation Checkpoints

**After creating `entity_crud_helper.py`**:

- [ ] Module imports without circular dependency
- [ ] All helper functions have type hints
- [ ] All helpers have docstrings
- [ ] Unit tests for each helper (no coordinator needed)

**After migrating first entity (Reward)**:

- [ ] Existing tests pass unchanged
- [ ] Storage structure identical (diff `.storage/kidschores_data`)
- [ ] Logging output identical (compare logs before/after)
- [ ] Options flow works for create/update/delete

**After migrating all simple entities**:

- [ ] Code reduction target met (~600 lines → ~200 lines)
- [ ] No new test failures
- [ ] Performance unchanged (measure entity creation time)
- [ ] Validate with `./utils/quick_lint.sh --fix` (9.5+/10)
- [ ] MyPy zero errors

**After Phase 2 (Performance)**:

- [ ] Benchmark entity registry cleanup (before/after)
- [ ] Measure cache memory usage
- [ ] Verify cache invalidation triggers correctly
- [ ] Test with large dataset (50 kids, 30 chores, 20 rewards)

**After Phase 3 (Orchestration)**:

- [ ] All cleanup paths tested (kid, chore, parent, etc.)
- [ ] Orphan entity verification (none left after deletions)
- [ ] Dry-run mode works correctly
- [ ] Async task cleanup completes

### Rollback Triggers

**Abort migration if**:

- Storage corruption detected in any test scenario
- More than 5% performance regression
- Any test failure that cannot be resolved in 1 hour
- MyPy errors increase above baseline
- Lint score drops below 9.5/10

**Rollback procedure**:

1. `git revert <commit-range>`
2. Verify tests pass on reverted code
3. Document issue in plan as "Blocked" item
4. Analyze root cause before retry

---

## Summary: Critical Success Factors

✅ **DO**:

1. Start with simplest entity (Reward) as reference implementation
2. Keep chore update separate initially (too complex)
3. Use validation decorators with warning-only mode first
4. Measure before/after performance for every optimization
5. Test with multiple storage schema scenarios
6. Preserve ALL existing logging behavior
7. Extract helpers incrementally (one entity type at a time)

❌ **DON'T**:

1. Consolidate chore logic in Phase 1 (defer to Phase 2/3)
2. Change method signatures (break compatibility)
3. Skip validation warnings (silent failures are worse)
4. Optimize without measuring (premature optimization)
5. Batch-migrate all entities at once (too risky)
6. Forget device registry side effects (kid name changes)
7. Ignore edge cases in date handling (null vs {})

🎯 **Key Metrics**:

- Code reduction: ~750 lines (-35%)
- Performance improvement: 3× faster cleanup
- Test coverage: Maintain 95%+
- MyPy errors: Zero
- Lint score: 9.5+/10
- Storage compatibility: 100%

---

_Deep dive completed: 2026-01-20_
_Ready for implementation approval_
