# KidsChores v0.5.0 Release Notes

**Release Date**: January 2026
**Quality Scale Certification**: ✅ **Silver** (Home Assistant Integration Quality Scale)
**Storage Schema**: 42 (Meta Section Architecture)
**Status**: Stable Release

---

## 🎉 Highlights

KidsChores v0.5.0 is a **stability and quality focused release** that builds on v0.4.0's foundation with significant improvements to code quality, testing infrastructure, and documentation.

### 🎯 Key Improvements

- **699 Tests Passing** – Expanded test coverage from 560 to 699 tests (25% increase)
- **Enhanced Stability** – Storage Schema 42 with meta section architecture
- **Multilingual Dashboard Support** – Dashboard templates now support 10+ languages
- **Improved Documentation** – Comprehensive developer and architecture documentation
- **Code Quality** – Maintained 9.64/10 linting score with zero critical errors

---

## 🚀 What's New

### 1. Enhanced Testing Infrastructure

Significant expansion of test coverage:

- ✅ **25% more tests** – From 560 tests to 699 tests passing
- ✅ **Badge system tests** – Comprehensive badge assignment and migration validation
- ✅ **Auto-approve tests** – Full feature coverage for automatic approval
- ✅ **Approval reset tests** – All 5 reset timing modes tested
- ✅ **Overdue handling tests** – Complete overdue scenario coverage
- ✅ **Migration tests** – Schema migration path validation

### 2. Reward System Modernization

Complete modernization of reward handling:

- ✅ **Period-based tracking** – Aligned with `chore_data` and `point_data` patterns
- ✅ **Date-keyed counters** – Historical tracking with retention cleanup
- ✅ **Multi-claim support** – Pending count increment pattern
- ✅ **No midnight reset** – Claims persist until resolved
- ✅ **Per-reward statistics** – Detailed stats as sensor attributes

### 3. Chore Enhancement Features

Five major chore features completed:

- ✅ **Show on Calendar** – Optional chore visibility control
- ✅ **Auto Approve** – Automatic approval of claimed chores
- ✅ **Completion Criteria** – INDEPENDENT and SHARED_FIRST modes
- ✅ **Approval Reset Timing** – 5 configurable reset modes
- ✅ **Overdue Handling** – 3 handling types + 3 pending claim actions

### 4. Dashboard Translation Support

Multilingual dashboard templates:

- ✅ **10+ languages** – Dashboard translations for international users
- ✅ **Consistent UI** – Translation keys across all dashboard elements
- ✅ **Easy localization** – JSON-based translation files

### 5. Documentation Updates

Comprehensive documentation refresh:

- ✅ **ARCHITECTURE.md** – Updated for v0.5.0 with Storage Schema 42 details
- ✅ **CODE_REVIEW_GUIDE.md** – Current quality standards and Phase 0 audit framework
- ✅ **QUALITY_MAINTENANCE_REFERENCE.md** – Ongoing quality guidance
- ✅ **README.md** – v0.5.0 highlights and contributor credits

---

## 📊 Quality Metrics

| Metric            | Value   | Target | Status       |
| ----------------- | ------- | ------ | ------------ |
| **Tests Passing** | 699/699 | 95%+   | ✅ 100%      |
| **Linting Score** | 9.64/10 | ≥9.5   | ✅ Pass      |
| **Type Coverage** | 100%    | 100%   | ✅ Pass      |
| **Quality Level** | Silver  | Silver | ✅ Certified |

---

## 🔄 Technical Changes

### Storage Schema 42

No changes required from v0.4.0. The meta section architecture introduced in v0.4.0 remains stable:

- **Schema version**: Stored in `meta.schema_version` (not top-level)
- **Migration tracking**: `meta.migrations_applied` list
- **Test framework safe**: Protected from test framework interference

### Code Quality Improvements

- ✅ **Legacy constant cleanup** – Removed deprecated constants
- ✅ **Attribute improvements** – Added `purpose` attribute to entities
- ✅ **Notification error handling** – Improved notification reliability
- ✅ **Flow improvements** – Enhanced config/options flow handling

### Dependencies

- No new dependencies required
- Compatible with Home Assistant 2024.1.0+
- Python 3.11+ required

---

## 📚 Migration Notes

### From v0.4.x

**No migration required** – v0.5.0 is fully backward compatible with v0.4.x installations.

### From v0.3.x or Earlier

Automatic migration occurs on first load:

1. Integration detects schema version < 42
2. Runs automatic migration sequence
3. Entity data migrates from config entry to storage
4. Meta section created with version tracking
5. No user action required

---

## 🐛 Bug Fixes

- ✅ Fixed shared chore handling for SHARED_FIRST completion criteria
- ✅ Fixed due date handling for migrated chores
- ✅ Fixed chores sensor translation for Spanish
- ✅ Fixed various linting issues and code quality warnings

---

## 👥 Contributors

This release includes contributions from:

- **@ad-ha** – Project creator and lead developer
- **@ccpk1** – Core contributor and co-maintainer

Special thanks to all users who reported issues and provided feedback!

---

## 🔗 Links

- [GitHub Repository](https://github.com/ad-ha/kidschores-ha)
- [Issue Tracker](https://github.com/ad-ha/kidschores-ha/issues)
- [Wiki & Documentation](https://github.com/ad-ha/kidschores-ha/wiki)
- [HACS Integration](https://hacs.xyz/)

---

## 📋 Full Changelog

### Features

- feat(entities): add purpose attribute and improve notification error handling
- feat(chores): Phase 5 - Overdue Handling implementation
- feat(chores): Phases 1-4 - Calendar visibility, Auto Approve, Completion Criteria, Reset Timing

### Improvements

- refactor: modernize reward system and clean up legacy constants
- refactor: legacy constant cleanup, various fixes
- refactor: attribute improvements and cleanup
- refactor: flow improvements and translation work

### Bug Fixes

- fix: shared chore handling and due date handling for migrated chores
- fix: chores sensor translation updates
- fix: notification error handling improvements
- fix: various linting issues

### Documentation

- docs: updated ARCHITECTURE.md for v0.5.0
- docs: updated CODE_REVIEW_GUIDE.md with current standards
- docs: updated README.md with v0.5.0 highlights
- docs: added QUALITY_MAINTENANCE_REFERENCE.md

### Testing

- test: expanded test coverage to 699 tests
- test: badge assignment and migration baseline tests
- test: auto-approve feature tests
- test: approval reset timing tests
- test: overdue handling tests

### Translations

- i18n: dashboard translations for 10+ languages
- i18n: badge translations updates
- i18n: Spanish translation improvements

---

**Document Version**: 1.0
**Last Updated**: January 4, 2026
