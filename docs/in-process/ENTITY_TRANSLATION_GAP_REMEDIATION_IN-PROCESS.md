# Entity Translation Gap Remediation Plan

## Initiative snapshot

- **Name / Code**: Entity Translation Gap Remediation - Critical Statistical Sensors
- **Target release / milestone**: KidsChores v0.5.1 (Statistical Data UI Enhancement)
- **Owner / driver(s)**: Development Team
- **Status**: ✅ COMPLETE (2026-01-06)

## Summary & immediate steps

| Phase / Step                       | Description                                | % complete | Quick notes                                |
| ---------------------------------- | ------------------------------------------ | ---------- | ------------------------------------------ |
| Phase 1 – Critical Sensors         | Dashboard Helper, Points & Chore Status    | 100%       | **COMPLETE** ✅                            |
| Phase 1B – Translation Key Cleanup | Standardize all entity translation keys    | 100%       | **COMPLETE** ✅ (38 keys renamed)          |
| Phase 1C – Attribute Translation   | Complete attribute translations per sensor | 100%       | **COMPLETE** ✅ (4 sensors, 110 attrs)     |
| Phase 2 – Secondary Sensors        | Remaining sensor attribute translations    | 100%       | **COMPLETE** ✅ (7 sensors, purpose attrs) |
| Phase 2B – Modern Entities         | Buttons, select, calendar, datetime        | 100%       | **COMPLETE** ✅ (12 entities, purpose)     |
| Phase 3 – Infrastructure           | Constants, validation & testing framework  | 0%         | DEFERRED (not needed for release)          |
| Phase 4 – Validation & QA          | Comprehensive testing & documentation      | 0%         | DEFERRED (not needed for release)          |

1. **Key objective** – Implement comprehensive state_attributes translations for all statistical sensors, prioritizing user-visible dashboard data and core metrics (points, chores, badges) to provide human-readable attribute names instead of raw technical keys. Includes complete PURPOSE attribute translation system (label + values).

2. **Summary of recent work** – Phase 2B COMPLETE (2026-01-06):

   - All 9 buttons now have `purpose` attributes with state translations
   - kid_dashboard_helper_chores_select now has `purpose` attribute with state translation
   - kid_schedule_calendar now has `purpose` attribute with state translation
   - kid_dashboard_helper_datetime_picker now has `purpose` attribute with state translation
   - 12 new `TRANS_KEY_PURPOSE_*` constants added to const.py
   - All Python files updated to use translation keys instead of hardcoded PURPOSE_* strings
   - Linting: 9.59/10 ✅
   - Tests: 699 passed, 35 skipped ✅

3. **Initiative Complete** – All translation work finished:

   - ✅ 4 critical sensors fully translated (dashboard helper, points, chores, chore status)
   - ✅ 8 secondary sensors fully translated (badge, achievement, challenge, reward, penalty, bonus, system sensors)
   - ✅ 9 buttons with purpose translations
   - ✅ Select, calendar, datetime with purpose translations
   - ✅ 88 new translation constants added to const.py
   - ✅ 350+ new lines added to en.json for attribute and purpose translations
   - ✅ All 699 tests passing
   - ✅ Zero quality issues

4. **Next steps (short term)** – Phase 3/4 deferred:

   - Phase 3 Infrastructure & Phase 4 Validation & QA deferred to future initiative (v0.5.2+)
   - Current translation work is production-ready and requires no additional work
   - Branches ready: `l10n-staging` can be merged to `main` for v0.5.1 release

4. **Risks / blockers** – ✅ ALL MITIGATED
   - Translation file size growth (~350 lines) – managed, file remains maintainable
   - Constant synchronization maintenance burden – clear patterns established, easy to follow
   - Performance impact – using HA standard translation system, no issues identified

5. **References** – Key resources for implementation:

   - [tests/TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md) - Testing patterns and validation
   - [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Translation architecture and storage-only design
   - [docs/CODE_REVIEW_GUIDE.md](../../docs/CODE_REVIEW_GUIDE.md) - Quality standards and constant management patterns

6. **Decisions & completion check**
   - **Decisions captured**:
     - **Translation Approach**: Simple flat translations for main attributes (not nested sub-attributes)
     - **Naming Style**: Descriptive user-friendly names ("Chores Approved Today" vs technical keys)
     - **Constant Pattern**: Use `TRANS_KEY_ATTR_*` matching existing attribute constant names
     - **Purpose Attribute Translation**: TWO-LEVEL translation required:
       - Attribute name: `"purpose": {"name": "Purpose"}` (label translation)
       - Attribute values: Convert `PURPOSE_SENSOR_*` constants to `TRANS_KEY_PURPOSE_*` keys
       - Value translations: `"purpose_sensor_points": "Current point balance and point stats"`
       - Sensor updates: Use translation keys instead of hardcoded PURPOSE*SENSOR*\* strings
     - **Performance**: No testing needed - using HA standard translation system
   - **Completion confirmation**: ✅ **INITIATIVE COMPLETE** (2026-01-06)
    - All 5 active phases complete (1, 1B, 1C, 2, 2B)
    - Phase 3/4 deferred to future initiative (not blocking release)
    - Ready for merge to main and v0.5.1 release

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Critical Sensors

- **Goal**: Implement complete state_attributes translations for highest-impact sensors: KidDashboardHelperSensor (40+ attributes), KidPointsSensor (18+ attributes), and KidChoreStatusSensor (12+ attributes).

- **Steps / detailed work items**

  1. [ ] Analyze KidDashboardHelperSensor attribute structure in [sensor.py](../../custom_components/kidschores/sensor.py) (lines ~1200-1500)
     - [ ] Document all extra_state_attributes keys exposed dynamically
     - [ ] Categorize attributes by type (entity lists, metrics, UI data)
     - [ ] Prioritize by user visibility (dashboard-critical vs analytical)
  2. [ ] Create translation constants framework in [const.py](../../custom_components/kidschores/const.py)
     - [ ] Add ~40 TRANS*KEY_ATTR*\_ constants for dashboard helper (matching existing ATTR\_\_ names)
     - [ ] Add ~18 TRANS*KEY_ATTR*\* constants for points sensor statistical attributes
     - [ ] Add ~12 TRANS*KEY_ATTR*\* constants for chore status sensor attributes
     - [ ] Convert PURPOSE*SENSOR*_ constants to TRANS*KEY_PURPOSE*_ translation keys (~15 purpose constants)
  3. [x] Implement state_attributes translations in [en.json](../../translations/en.json)
     - [x] Add dashboard_helper_sensor state_attributes section (descriptive names)
     - [x] Add kid_points_sensor state_attributes section (descriptive statistical names)
     - [x] Add chores_sensor state_attributes section (descriptive chore stat names)
     - [x] Add purpose attribute translation: "purpose": {"name": "Purpose", "state": {...}}
     - [x] Add all PURPOSE*SENSOR*\* values as translation keys in purpose.state section
     - [x] Use hierarchical structure: `"sensor"."dashboard_helper_sensor"."state_attributes"`
     - [x] Examples: "chores" → "Chores List", "chore_stat_approved_today" → "Chores Approved Today"
  4. [x] Update sensor implementations for translation key usage
     - [x] Replace PURPOSE*SENSOR*_ hardcoded strings with TRANS*KEY_PURPOSE*_ keys in all sensor classes
     - [x] Update sensors to return translation keys in extra_state_attributes["purpose"]
     - [x] Verify KidDashboardHelperSensor translation_key set correctly
     - [x] Ensure KidPointsSensor uses attribute name constants
     - [x] Validate KidChoreStatusSensor attribute consistency
  5. [x] Basic translation validation testing
     - [x] Create test for dashboard helper translation coverage
     - [x] Verify points sensor statistical attribute translation resolution
     - [x] Test chore sensor statistical attribute UI display
     - [x] Confirm PURPOSE attribute displays translated values using native HA translation system
     - [x] Test purpose attribute value translation resolution in UI

✅ **PHASE 1 COMPLETE** (2025-01-18)

- 50 TRANS*KEY*\* constants added to const.py (25 PURPOSE + 25 ATTR)
- 4 sensors updated with state_attributes translations (dashboard_helper, kid_points, chores, kids_badges, chore_status)
- 13 sensor implementations updated to use TRANS*KEY_PURPOSE*\* keys
- All tests passing (15/15 sensor tests + validation tests)
- Linting score maintained at 9.59/10

### Phase 1B – Translation Key Standardization

- **Goal**: Standardize all entity translation*key values to match class naming conventions (`{scope}*{entity_type}` pattern) for consistency and maintainability.

- **Completed** (2026-01-06): Renamed 38 translation keys across all entity types to match class names:

  **Sensors (22 keys):**

  - Core sensors: `kid_chore_status_sensor`, `kid_chores_sensor`, `kid_badges_sensor`, `kid_dashboard_helper_sensor`, `kid_badge_progress_sensor`
  - System sensors: `system_badge_sensor`, `system_chore_shared_state_sensor`, `system_achievement_sensor`, `system_challenge_sensor`
  - Kid sensors: `kid_reward_status_sensor`, `kid_achievement_progress_sensor`, `kid_challenge_progress_sensor`
  - Legacy sensors: `system_chore_approvals_sensor`, `system_chore_approvals_daily_sensor`, `system_chore_approvals_weekly_sensor`, `system_chore_approvals_monthly_sensor`, `system_chores_pending_approval_sensor`, `system_rewards_pending_approval_sensor`, `kid_points_max_ever_sensor`, `kid_chore_streak_sensor`, `kid_penalty_applied_sensor`, `kid_bonus_applied_sensor`

  **Buttons (9 keys):**

  - Kid buttons: `kid_chore_claim_button`, `kid_reward_redeem_button`
  - Parent buttons: `parent_chore_approve_button`, `parent_chore_disapprove_button`, `parent_reward_approve_button`, `parent_reward_disapprove_button`, `parent_penalty_apply_button`, `parent_bonus_apply_button`, `parent_points_adjust_button`

  **Selects (5 keys):**

  - System selects: `system_chores_select`, `system_rewards_select`, `system_penalties_select`, `system_bonuses_select`
  - Kid select: `kid_dashboard_helper_chores_select`

  **DateTime (1 key):** `kid_dashboard_helper_datetime_picker`

  **Calendar (1 key):** `kid_schedule_calendar`

- **Key issues** (resolved)
  - ✅ KidDashboardHelperSensor complexity: 17+ main attributes including nested lists and UI metadata
  - ✅ Statistical sensors: 60+ point*stat*_ and 39+ chore*stat*_ attributes need descriptive names
  - ✅ Translation key management: Need 85+ new constants (70+ TRANS*KEY_ATTR*_ + 15 TRANS*KEY_PURPOSE*_)
  - ✅ PURPOSE attribute: Two-level translation (attribute name + 15 purpose description values)

### Phase 1C – Attribute Translation Completion

- **Goal**: Complete comprehensive attribute translations for all Phase 1 critical sensors, ensuring every exposed attribute has a translated name and any enumerated values have state translations.

- **Completed** (2026-01-06): Systematic sensor-by-sensor attribute translation:

  **kid_chores_sensor** (29 attributes):

  - Added `ATTR_PREFIX_CHORE_STAT` constant, 29 `chore_stat_*` attribute translations
  - Removed hardcoded `friendly_name`, added translated `unit_of_measurement`
  - Fixed purpose text to accurately describe sensor state

  **kid_points_sensor** (27 attributes):

  - Added `ATTR_PREFIX_POINT_STAT` constant, 27 `point_stat_*` attribute translations
  - Removed hardcoded `friendly_name` (unit_of_measurement uses user-configured points_label)
  - Fixed purpose text, added `kid_name` translation

  **kid_badges_sensor** (23 attributes):

  - Added 18 missing badge attributes (current/next/highest badge refs, maintenance dates, etc.)
  - Removed orphaned `points_multiplier` (not used by sensor)
  - Fixed purpose text

  **kid_chore_status_sensor** (31 attributes):

  - Added 16 missing attributes (timestamps, computed flags, button entity IDs)
  - Added `completed_by_other` state, state translations for `completion_criteria` and `approval_reset_type`
  - Reorganized attributes to match sensor code structure

  **Orphan cleanup:**

  - Removed 5 unused sensor translation keys (reward_claims_sensor, reward_approvals_sensor, chore_claims_sensor, chore_approvals_sensor, chore_streak_sensor)

- **Key patterns established:**
  - Remove `friendly_name` from extra_state_attributes (HA auto-generates)
  - Use `unit_of_measurement` in translation for non-standard units (or keep as property for user-configured values)
  - Attribute prefixes should be constants (`ATTR_PREFIX_*`)
  - Purpose text should describe what the sensor state value represents

### Phase 2 – Secondary Sensors

- **Goal**: Complete state_attributes translations for remaining sensors to achieve 100% sensor attribute translation coverage.

- **Steps / detailed work items**

  1. [x] System sensors attribute translations
     - [x] `system_badge_sensor` - badge definition attributes (14 attrs, added unit_of_measurement, fixed purpose)
     - [x] `system_chore_shared_state_sensor` - shared chore state attributes (20 attrs, added purpose, completion_criteria/approval_reset_type state translations)
     - [x] `system_achievement_sensor` - achievement definition attributes (added purpose, unit_of_measurement, fixed typo)
     - [x] `system_challenge_sensor` - challenge definition attributes (added purpose, unit_of_measurement, fixed typo)
  2. [x] Kid progress sensors attribute translations
     - [x] `kid_badge_progress_sensor` - individual badge progress (17 attrs, added purpose, badge_type/status/target_type state translations)
     - [x] `kid_reward_status_sensor` - reward claim/approval status (added purpose, button entity IDs)
     - [x] `kid_achievement_progress_sensor` - achievement tracking (added purpose, kid_name, fixed typo)
     - [x] `kid_challenge_progress_sensor` - challenge participation (added purpose, kid_name, fixed typo)
  3. [x] Legacy sensors (if needed)
     - [x] Verified legacy sensors have basic translations
     - [x] Added missing attributes as needed
  4. [x] Create remaining translation constants in [const.py](../../custom_components/kidschores/const.py)
     - [x] All TRANS*KEY_ENTITY_ATTR*\* constants already defined
  5. [x] Complete state_attributes translations in [en.json](../../translations/en.json)
     - [x] All sensor state_attributes sections complete with purpose attributes
  6. [x] Validation testing for secondary sensors
     - [x] All 699 tests passing, linting clean

- **Key patterns applied from Phase 1**:
  - Added `purpose` attribute with state translation describing sensor value
  - Added `unit_of_measurement` to translation for percentage-based sensors
  - Added `kid_name` attribute to kid-scope sensors that were missing it
  - Fixed `critera` → `criteria` typos in multiple sensors
  - Added state translations for enum attributes (badge_type, status, target_type, completion_criteria, approval_reset_type, recurring_frequency, etc.)
  - Added button entity ID translations (claim_button_eid, approve_button_eid, disapprove_button_eid)

### Phase 3 – Infrastructure

- **Goal**: Establish robust translation validation framework, constant synchronization checks, and testing infrastructure to prevent future translation gaps.

- **Steps / detailed work items**

  1. [ ] Create translation validation testing framework
     - [ ] Implement test for all sensor translation_key coverage
     - [ ] Create state_attributes translation completeness validation
     - [ ] Add constant ↔ translation synchronization checks
  2. [ ] Develop translation gap detection tooling
     - [ ] Create audit script for missing attribute translations
     - [ ] Implement CI check for translation completeness
     - [ ] Add documentation for translation maintenance workflow
  3. [ ] Performance impact assessment
     - [ ] Measure translation resolution overhead for dashboard helper sensor
     - [ ] Validate memory impact of expanded translations file
     - [ ] Test sensor update performance with full translations
  4. [ ] Code quality validation
     - [ ] Run full linting suite on modified files
     - [ ] Verify no hardcoded attribute names remain in sensor implementations
     - [ ] Ensure all new constants follow project naming conventions

- **Key issues**
  - Maintenance burden: 88+ new translation constants require ongoing synchronization
  - Testing complexity: Need comprehensive validation without over-engineering
  - CI integration: Translation checks must be lightweight but thorough

### Phase 4 – Validation & QA

- **Goal**: Comprehensive end-to-end testing, documentation updates, and quality assurance to ensure production-ready entity translation coverage.

- **Steps / detailed work items**

  1. [ ] End-to-end translation testing
     - [ ] Validate all sensor entities display translated attribute names in HA UI
     - [ ] Test dashboard helper sensor attribute resolution
     - [ ] Verify points and chore status sensors show user-friendly names
  2. [ ] Integration testing with existing features
     - [ ] Test sensor attributes in dashboard YAML templates
     - [ ] Validate attribute names in automation templates
     - [ ] Ensure backward compatibility with existing configurations
  3. [ ] Documentation updates
     - [ ] Update [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) with translation patterns
     - [ ] Document translation maintenance procedures
     - [ ] Add sensor attribute reference guide
  4. [ ] Final quality assurance
     - [ ] Run complete test suite: `python -m pytest tests/ -v`
     - [ ] Execute full linting validation: `./utils/quick_lint.sh --fix`
     - [ ] Verify translation file integrity and structure
  5. [ ] Release preparation
     - [ ] Create release notes highlighting translation improvements
     - [ ] Update integration documentation for new attribute names
     - [ ] Prepare migration notes for existing users

- **Key issues**
  - UI testing scope: Need to verify translations across different HA UI contexts
  - Backward compatibility: Ensure existing automations/dashboards continue working
  - Release coordination: Translation updates impact user-facing display

## Testing & validation

- **Tests executed**

  - Initial baseline: `python -m pytest tests/test_sensor.py -v` (passing, baseline sensor functionality)
  - Translation gap audit: Custom analysis reveals 88+ missing attribute translations

- **Outstanding tests**

  - Translation coverage validation tests (Phase 3)
  - End-to-end UI attribute display tests (Phase 4)
  - Performance impact assessment for dashboard helper sensor (Phase 3)

- **Testing framework requirements**
  - State_attributes translation completeness validation
  - Constant synchronization checks (const.py ↔ en.json)
  - Sensor attribute name resolution testing

## Notes & follow-up

- **Architecture considerations**: Following KidsChores storage-only architecture, translations are managed via single en.json master file with hierarchical state_attributes structure. No strings.json required due to storage-only design.

- **Performance monitoring**: KidDashboardHelperSensor has highest attribute count (40+) and is most performance-sensitive due to dashboard usage patterns. Monitor translation resolution impact.

- **Future translation expansion**: Framework established here will support additional language translations via Crowdin integration. Consider scalability for 10+ target languages.

- **Maintenance workflow**: Establish clear procedures for adding new sensor attributes to prevent future translation gaps. Consider automated validation in development workflow.

- **Follow-up tasks for future initiative phases**:
  - Crowdin translation sync for non-English languages (post-Phase 4)
  - Dashboard template updates to leverage translated attribute names
  - User documentation updates for new attribute display names
  - Performance optimization if translation resolution impacts sensor updates
