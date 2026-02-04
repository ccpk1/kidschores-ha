# Risk Analysis: Zombie Managers & Cache Memory Leaks

**Analysis Date**: 2026-02-04
**Analyzed By**: KidsChores Maintainer
**Context**: Code review findings for potential architectural risks

---

## Risk 4: "Zombie" Managers

### 🔍 Current Implementation Analysis

**Location**: `custom_components/kidschores/__init__.py`, lines 176-182

```python
# Initialize all managers (v0.5.x+)
# Each manager's async_setup() subscribes to relevant events
await coordinator.economy_manager.async_setup()
await coordinator.notification_manager.async_setup()
await coordinator.chore_manager.async_setup()
await coordinator.gamification_manager.async_setup()
await coordinator.statistics_manager.async_setup()
await coordinator.system_manager.async_setup()
```

**Manager Instantiation**: `coordinator.py`, lines 106-141

- All managers instantiated in `__init__()` - **no error handling**
- Instantiation happens BEFORE `async_setup_entry()` runs
- All `async_setup()` calls in `__init__.py` are **NOT wrapped in try/except**

### 📊 Criticality Assessment

**Severity**: ⚠️ **MEDIUM-HIGH**

**Impact if Triggered**:

1. **Silent Point Transaction Failures**: If `EconomyManager.async_setup()` throws, point deposits/withdrawals will fail silently (no listeners registered)
2. **No User Notification**: Integration loads successfully, dashboard shows up, but core features are broken
3. **Difficult to Debug**: No clear error in logs - just "nothing happens" when user claims rewards
4. **Data Consistency Risk**: Partial manager initialization could lead to event mismatches (e.g., chore approved but points never deposited)

**Likelihood**:

- **Low under normal conditions** - managers are well-tested
- **Higher during**:
  - Storage corruption (malformed JSON in `.storage/kidschores_data`)
  - Schema migration failures (e.g., missing required keys)
  - Race conditions on first startup (rare but possible)
  - Custom modifications by advanced users

**Real-World Scenario**:

```python
# User manually edits .storage/kidschores_data with typo
"point_data": {
    "periods": "not_a_dict"  # Should be dict, causes JSON decode or validation error
}

# StatisticsManager.async_setup() reads this malformed data → exception
# Integration loads successfully (no ConfigEntryNotReady)
# BUT: Stats never update, dashboard shows stale data, events silently fail
```

### 🛠️ Difficulty to Resolve

**Effort**: ✅ **LOW** (2-4 hours)

**Implementation Strategy**:

```python
# In __init__.py async_setup_entry(), wrap manager setup
CRITICAL_MANAGERS = [
    ("economy_manager", "Point transactions"),
    ("chore_manager", "Chore workflow"),
    ("reward_manager", "Reward redemptions"),
]

for manager_name, description in CRITICAL_MANAGERS:
    try:
        manager = getattr(coordinator, manager_name)
        await manager.async_setup()
    except Exception as err:
        const.LOGGER.error(
            "CRITICAL: %s failed to initialize (%s): %s",
            description,
            manager_name,
            err,
        )
        raise ConfigEntryNotReady(
            f"Failed to initialize {description} - try reloading integration"
        ) from err

# Non-critical managers can log and continue
for manager_name in ["statistics_manager", "ui_manager", "notification_manager"]:
    try:
        manager = getattr(coordinator, manager_name)
        await manager.async_setup()
    except Exception as err:
        const.LOGGER.warning(
            "Non-critical manager %s failed to initialize: %s",
            manager_name,
            err,
        )
```

**Testing Approach**:

1. Unit test: Mock `ChoreManager.async_setup()` to raise exception
2. Verify: `async_setup_entry()` raises `ConfigEntryNotReady`
3. Integration test: Corrupt storage file, reload, confirm integration refuses to load

**Standards Compliance**:

- ✅ Follows HA guidelines: Use `ConfigEntryNotReady` for temporary failures
- ✅ Aligns with `AGENTS.md`: "Fail fast rather than loading in a broken state"
- ✅ Matches error handling patterns in `DEVELOPMENT_STANDARDS.md` § 4.3

---

## Risk 5: Memory Leak in Translation Cache

### 🔍 Current Implementation Analysis

**Location**: `helpers/translation_helpers.py`, line 30

```python
# Module-level translation cache for performance (v0.5.0+)
# Key format: f"{language}_{translation_type}" where translation_type is "dashboard" or "notification"
# This avoids repeated file I/O when sending notifications to multiple parents with same language
_translation_cache: dict[str, dict[str, Any]] = {}
```

**Cache Usage**:

- **Populated**: Lines 230, 258 (during `get_dashboard_translations()`, `get_notification_translations()`)
- **Read**: Lines 207, 244 (cache hits)
- **Cleared**: Line 288 (`clear_translation_cache()`)

**Unload Behavior**: `__init__.py`, lines 275-292

```python
async def async_unload_entry(hass: HomeAssistant, entry: KidsChoresConfigEntry) -> bool:
    """Unload a config entry."""
    # ... persist, unload platforms ...
    # ❌ NO call to clear_translation_cache()
```

**Statistics Cache** (for comparison):

- `StatisticsManager._stats_cache` (line 94) - **instance-level**
- Dies with coordinator on unload ✅

### 📊 Criticality Assessment

**Severity**: 🟡 **LOW-MEDIUM**

**Impact if Triggered**:

1. **Memory Growth**: Each reload adds 2 cache entries per language (dashboard + notification)
2. **Stale Translations**: If user edits translation files and reloads, old translations persist until HA restarts
3. **Resource Waste**: Typical cache entry ~5-15 KB JSON, 20 reloads × 3 languages × 2 types = 120 KB - 1.8 MB wasted

**Likelihood**:

- **Low for normal users** - most don't reload 20+ times
- **Higher for**:
  - Developers (testing integration repeatedly)
  - Users debugging issues (following support advice to "reload integration")
  - Multi-language setups (cache grows faster with 5+ languages)

**Real-World Scenario**:

```python
# Developer iterates on translation file improvements
# Each reload cycle:
1. Edit translations/es.json (fix typo)
2. Reload integration in HA UI
3. _translation_cache still holds OLD "es_dashboard" entry
4. Dashboard shows old translation (cached)
5. Developer confused, edits file again
6. Cache now has 2 entries for "es_dashboard" (NO - dict overwrites)

# ACTUAL PROBLEM:
# After 50 dev reloads across 3 languages:
# Cache holds: en_dashboard, en_notification, es_dashboard, es_notification, de_dashboard, de_notification
# Expected: 6 entries × ~10 KB = 60 KB
# Reality: Cache persists across reloads, but dict keys are STABLE (same keys reused)
# → Memory leak is MINIMAL (dict keys don't multiply)
```

**CORRECTION**: Upon closer analysis, the memory leak is **nearly non-existent** because:

- Dict keys are deterministic (`f"{lang}_{type}"`)
- Each reload **overwrites** the same keys (not appending)
- Cache size is bounded by: `(# languages) × (2 types) × (avg JSON size)`
- Typical max: 10 languages × 2 × 15 KB = **300 KB total** (not per-reload)

### 🛠️ Difficulty to Resolve

**Effort**: ✅ **TRIVIAL** (15 minutes)

**Implementation Strategy**:

```python
# In __init__.py async_unload_entry()
async def async_unload_entry(hass: HomeAssistant, entry: KidsChoresConfigEntry) -> bool:
    """Unload a config entry."""
    const.LOGGER.info("INFO: Unloading KidsChores entry: %s", entry.entry_id)

    # Force immediate save of any pending changes before unload
    coordinator = entry.runtime_data
    if coordinator:
        coordinator._persist(immediate=True)
        const.LOGGER.debug("Forced immediate persist before unload")

    # Clear module-level translation cache to prevent stale data
    from .helpers.translation_helpers import clear_translation_cache
    clear_translation_cache()
    const.LOGGER.debug("Translation cache cleared on unload")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, const.PLATFORMS)

    if unload_ok:
        await async_unload_services(hass)

    return unload_ok
```

**Testing Approach**:

1. Unit test: Populate cache, call `async_unload_entry()`, verify cache is empty
2. Integration test: Load integration, change language, reload, verify new translations appear

**Standards Compliance**:

- ✅ Matches pattern in `AGENTS.md`: "Ensure async_unload_entry clears module caches"
- ✅ Aligns with HA best practices: Clean up all resources on unload

---

## Comparative Risk Matrix

| Risk                  | Severity    | Likelihood | Impact on Users       | Effort to Fix | Priority |
| --------------------- | ----------- | ---------- | --------------------- | ------------- | -------- |
| **Zombie Managers**   | Medium-High | Low        | 🔴 Core features fail | Low (2-4h)    | **HIGH** |
| **Translation Cache** | Low-Medium  | Low        | 🟡 Stale translations | Trivial (15m) | Medium   |

---

## Recommendations

### Immediate Actions (High Priority)

**1. Add Manager Initialization Error Handling** (Risk 4)

- **Why Now**: Prevents silent feature failures that are hard to debug
- **Effort**: 2-4 hours (including tests)
- **Benefit**: Fail-fast behavior, clear error messages for users
- **Implementation**: Wrap critical managers in try/except, raise `ConfigEntryNotReady`

### Nice-to-Have (Low Priority)

**2. Clear Translation Cache on Unload** (Risk 5)

- **Why Low Priority**: Actual memory impact is minimal (dict keys don't multiply)
- **Effort**: 15 minutes (one import + one function call)
- **Benefit**: Prevents stale translations, completes resource cleanup pattern
- **Implementation**: Add `clear_translation_cache()` call in `async_unload_entry()`

### Optional Enhancement

**3. Add Cache Size Monitoring** (Future-proofing)

```python
# In translation_helpers.py
def get_cache_stats() -> dict[str, int]:
    """Return cache statistics for diagnostics."""
    import sys
    return {
        "entries": len(_translation_cache),
        "size_bytes": sys.getsizeof(_translation_cache),
    }
```

- Include in diagnostics payload to track real-world cache behavior
- Useful for validating leak fix or identifying new leak sources

---

## Conclusion

**Risk 4 (Zombie Managers)**: Should be addressed **before v0.5.0 stable release**. While rare, the impact (silent feature failure) creates poor user experience and difficult support cases.

**Risk 5 (Translation Cache)**: Can be addressed **anytime** as a code quality improvement. The actual memory impact is negligible (cache keys are stable, not multiplicative). Main benefit is completing the "clean resource cleanup" pattern, not preventing a critical leak.

**Overall Assessment**: Neither risk is a showstopper, but Risk 4 should be prioritized for robustness. Both fixes are low-effort and align with existing code standards.
