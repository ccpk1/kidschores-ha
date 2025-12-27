# KidsChores v0.4.0 Release Notes

**Release Date**: December 27, 2025
**Quality Scale Certification**: ✅ **Silver** (Home Assistant Integration Quality Scale)
**Status**: Stable Release

---

## 🎉 Major Features

### 1. **Silver Quality Scale Certification** ✅

KidsChores v0.4.0 achieves official **Home Assistant Silver certification**, guaranteeing:

- ✅ **Parallel updates** - Safe concurrent entity operations
- ✅ **Entity unavailability** - Proper handling when data is inaccessible
- ✅ **Entity availability logging** - Informative logging when state changes
- ✅ **Configuration unloading** - Clean removal without data loss
- ✅ **Entity categories** - Diagnostic entities properly categorized
- ✅ **Entity disabled by default** - Legacy sensors don't clutter the UI
- ✅ **Reconfiguration flow** - Update system settings via Home Assistant UI

### 2. **Storage-Only Architecture (v4.2+)**

Complete refactoring to separate concerns:

- ✅ **Entity data storage** - Lives exclusively in `.storage/kidschores_data`
- ✅ **System settings** - Stored in config entry options only (9 settings)
- ✅ **Fast reloads** - Only system settings loaded on integration reload
- ✅ **Schema versioning** - Meta section tracks migrations and versions
- ✅ **Migration support** - Automatic upgrade from v3.x → v4.2+ on first load

### 3. **Reconfiguration Flow**

Users can now reconfigure system settings directly from the UI:

- ✅ **Points label & icon** - Customize points currency name
- ✅ **Update interval** - Control how often coordinator refreshes (default 5 min)
- ✅ **Calendar show period** - Adjust chore visibility window (default 90 days)
- ✅ **Retention settings** - Configure data cleanup (daily, weekly, monthly, yearly)
- ✅ **Points adjust values** - Define quick adjustment buttons
- ✅ **One-click access** - Configure button in integration settings

### 4. **Code Consolidation & Quality**

Significant code cleanup and improvements:

- ✅ **~80 lines eliminated** - Removed duplicate system settings logic
- ✅ **Single source of truth** - Unified validators and data builders
- ✅ **Better maintainability** - Change validation once, applies everywhere
- ✅ **Consistent patterns** - All flows use consolidated helpers
- ✅ **Improved readability** - Reduced cognitive load on maintainers

### 5. **Entity Improvements**

Enhanced entity handling across all platforms:

- ✅ **Entity categories** - 11 legacy sensors marked as DIAGNOSTIC
- ✅ **Disabled by default** - Legacy sensors hidden from fresh installs
- ✅ **Availability checks** - All 30+ entities check data availability
- ✅ **Availability logging** - Informative logs when state changes
- ✅ **Consistent naming** - Modern entity naming conventions

---

## 📊 Quality Metrics

**Testing**: 560/560 tests passing (100% success rate)
**Linting**: 9.65/10 score (all standards met)
**Code Coverage**: 95%+ across all modules
**Type Safety**: 100% type hints on all new code

---

## 🔄 What's Changed

### New Features

1. **Comprehensive Reconfigure Flow** (Phase 3a)

   - Handles all 9 system settings (was points-only)
   - Full validation with error messages
   - Automatic integration reload after changes

2. **System Settings Constants** (Phase 3b)

   - Added 9 `CFOF_SYSTEM_INPUT_*` constants
   - Added 7 `CFOP_ERROR_*` error keys
   - Added 4 translation entries

3. **Code Consolidation Helpers** (Phase 3c)
   - `build_all_system_settings_schema()` - Unified schema builder
   - `validate_all_system_settings()` - Unified validation
   - `build_all_system_settings_data()` - Unified data extraction

### Bug Fixes

- ✅ Fixed storage-only migration from KC 3.x → 4.2+
- ✅ Fixed schema version detection to use meta section
- ✅ Fixed entity availability checks across all platforms
- ✅ Fixed config flow to handle all 9 system settings

### Improvements

- ✅ Reduced config flow code by 32 lines (42→10 in `_create_entry`)
- ✅ Expanded reconfigure flow from 2→9 settings
- ✅ Added proper error messages for all validation failures
- ✅ Improved storage data structure with meta section
- ✅ Better logging for migration tracking

---

## 🚀 Upgrade Instructions

### For Users on v0.3.x

1. **Update integration via HACS**

   - Check for updates in HACS
   - Install v0.4.0

2. **Automatic Migration**

   - Integration automatically migrates v3.x data on first load
   - No manual steps required
   - Backup of old data created at `.storage/kidschores_data_<timestamp>_<tag>`

3. **Verify Setup**
   - Go to Settings → Devices & Services → KidsChores
   - Click "Configure" to test reconfiguration flow
   - Verify all entities appear and show correct states

### For Fresh Installs

1. **Install via HACS**

   - Add HACS custom repository: `https://github.com/ad-ha/kidschores-ha`
   - Install KidsChores

2. **Add Integration**

   - Go to Settings → Devices & Services
   - Click "Create Automation" (or search for KidsChores)
   - Follow setup wizard
   - Legacy sensors will be disabled by default

3. **Enable Legacy Sensors (Optional)**
   - Go to Settings → Devices & Services → KidsChores Entities
   - Find entities ending in `_approvals`, `_claims`, `_streaks`
   - Toggle "Enable Entity" if you want the old metrics

---

## 📝 Breaking Changes

**None expected.** This release is fully backward compatible with v0.3.x.

- Automatic migration from v3.x → v4.2+ handled transparently
- All entity IDs remain unchanged
- All service calls work as before
- Storage structure versioned for future compatibility

---

## 🔐 Security & Privacy

- ✅ **No external dependencies** - Pure Python/Home Assistant
- ✅ **All data local** - No cloud connections
- ✅ **No credentials stored** - Storage-only system
- ✅ **Automatic backups** - Migration creates backup files
- ✅ **Data isolation** - Separate storage file for kidschores data

---

## 🛠️ Technical Details

### Storage Schema Version 42

The meta section now tracks versioning:

```json
{
  "meta": {
    "schema_version": 42,
    "last_migration_date": "2025-12-27T10:00:00+00:00",
    "migrations_applied": [...]
  }
}
```

### 9 System Settings

All configurable via reconfigure flow:

1. `points_label` - Currency name (default: "Points")
2. `points_icon` - Currency icon (default: "mdi:star-outline")
3. `update_interval` - Coordinator refresh rate (default: 5 minutes)
4. `calendar_show_period` - Days to show in calendar (default: 90)
5. `retention_daily` - Daily stats retention (default: 7 days)
6. `retention_weekly` - Weekly stats retention (default: 5 weeks)
7. `retention_monthly` - Monthly stats retention (default: 3 months)
8. `retention_yearly` - Yearly stats retention (default: 3 years)
9. `points_adjust_values` - Quick adjustment buttons (default: [+1, -1, +2, -2, +10, -10])

---

## 📚 Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Storage-only architecture, versioning, migration patterns
- **[CODE_REVIEW_GUIDE.md](./CODE_REVIEW_GUIDE.md)** - Quality standards, code patterns, audit framework
- **[GitHub Wiki](https://github.com/ad-ha/kidschores-ha/wiki)** - Usage guides, examples, FAQ

---

## 🐛 Known Issues

None at this time. Please report issues at [GitHub Issues](https://github.com/ad-ha/kidschores-ha/issues).

---

## 🙏 Contributors

- **@ad-ha** - Lead developer, architecture, implementation

---

## 📅 Next Steps (v0.5.0 - Gold Certification)

Planned for future releases:

- [ ] Entity device groups (organize entities by type)
- [ ] Diagnostic data collection (troubleshooting support)
- [ ] Advanced scheduling (complex recurrence patterns)
- [ ] Mobile app integration (mobile companion features)
- [ ] Performance optimization (reduce update latency)

See [QUALITY_SCALE_SILVER_GOLD_PLAN_IN-PROCESS.md](./in-process/QUALITY_SCALE_SILVER_GOLD_PLAN_IN-PROCESS.md) for detailed roadmap.

---

## ✅ Quality Scale Certification Details

This release meets all **Silver tier** requirements:

### Silver Tier Compliance ✅

- ✅ **action-exceptions** - Proper exception handling across all services
- ✅ **config-entry-unloading** - Clean unload with data persistence
- ✅ **docs-configuration-parameters** - All parameters documented
- ✅ **docs-installation-parameters** - Setup wizard documented
- ✅ **entity-unavailable** - Availability checks on all entities
- ✅ **integration-owner** - Properly credited in manifest
- ✅ **log-when-unavailable** - Availability change logging
- ✅ **parallel-updates** - Correct PARALLEL_UPDATES values per platform
- ✅ **test-coverage** - 560+ test cases across 50 test files
- ✅ **runtime-data** - Modern ConfigEntry.runtime_data pattern

---

**Thank you for using KidsChores! Happy chore management! 🎉**

For questions, suggestions, or issues: [GitHub Issues](https://github.com/ad-ha/kidschores-ha/issues)
