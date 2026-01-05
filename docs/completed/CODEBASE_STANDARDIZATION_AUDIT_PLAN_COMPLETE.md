# Initiative Plan: KidsChores Codebase Standardization Audit & Remediation

## Initiative snapshot

- **Name / Code**: KidsChores Codebase Standardization Audit & Remediation (CODEBASE_STANDARDIZATION)
- **Target release / milestone**: v0.4.1 (Quality Standards Enforcement)
- **Owner / driver(s)**: Code Quality & Localization Team
- **Status**: ✅ **COMPLETE** (All 5 phases complete; Phase 0 framework established; 510/510 tests passing; 9.63/10 lint; 0 regressions; ready for v0.4.1 release)

## Summary & immediate steps

| Phase / Step                             | Description                                                                                                    | % complete | Quick notes                                                                                           |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| Phase 0 – Repeatable Audit Framework     | Establish standardized audit process, checklist, and validation gates for consistent coverage across all files | 100%       | ✅ Framework validated across 10 files (23,365 LOC); CODE_REVIEW_GUIDE.md complete                    |
| Phase 1a – Flow Helpers Analysis         | Complete comprehensive analysis of flow_helpers.py (config/options validation)                                 | 100%       | ✅ 109 hardcoded strings identified; 53 constants; 22 log statements (100% compliant)                 |
| Phase 1b – Entities Analysis             | Audit all entity platform files (sensor.py, button.py, calendar.py, select.py, etc.)                           | 100%       | ✅ 5968 lines audited; 95%+ compliant; 12 dashboard keys identified                                   |
| Phase 1c – Config/Options Flow Analysis  | Audit config_flow.py and options_flow.py (setup/management UI)                                                 | 100%       | ✅ 15 hardcoded strings in config_flow; options_flow exemplary (100% compliant)                       |
| Phase 1d – Coordinator/Services Analysis | Audit coordinator.py (8642 LOC) and services.py (1177 LOC) - core business logic                               | 100%       | ✅ 282 log statements (100% compliant); 41 coordinator errors; services.py is GOLD STANDARD           |
| Phase 2a – Translation Rationalization   | Analyze patterns and consolidate to minimize translation entry count                                           | 100%       | ✅ 105 constants → **64 constants** (39% reduction); 78 strings → 25 templates (68% reduction)        |
| Phase 2b – Define Constants in const.py  | Add 43 optimized constants across 6 categories (TRANS*KEY*\_, ATTR\_\_, DATA*\*, FORMAT*\*)                    | 100%       | ✅ **COMPLETE** - 43 constants added; linting passed (9.97/10); no duplicates                         |
| Phase 2c – Create Translation Templates  | Add 21 translation entries to en.json (12 exceptions + 5 config errors + 4 display formats)                    | 100%       | ✅ **COMPLETE** - 21 translations added; JSON validated; ready for Phase 3 code remediation           |
| Phase 3 – Code Remediation               | Replace 165+ hardcoded strings across ALL audited files with constant references                               | 100%       | ✅ config_flow (15), flow_helpers (1), services (2), coordinator (41) - all conversions complete      |
| Phase 3b – Deep Audit & Label Constants  | Fix entity labels introduced in Phase 3; add LABEL\_\* constants                                               | 100%       | ✅ 35 hardcoded entity labels replaced with 10 LABEL\_\* constants; 510/510 tests passing             |
| Phase 3c – Final Cleanup & Consistency   | Fix ValueError instances, logging prefixes, extract hardcoded technical constants                              | 100%       | ✅ 18 ValueError → HomeAssistantError; 8 logging fixes; 25 constants added; 510/510 tests passing     |
| Phase 4 – Translation Integration        | Verify all TRANS*KEY*\* constants have en.json entries (forward validation: code → translations)               | 100%       | ✅ 1 missing key added; all 11 error keys + 109 CFOF keys verified; 510/510 tests; 9.63/10 lint       |
| Phase 4b – Reverse Translation Audit     | Find unused translation keys in en.json (reverse validation: translations → code)                              | 100%       | ✅ 90% usage rate; 1 duplicate removed; 510/510 tests; report in PHASE4B_REVERSE_TRANSLATION_AUDIT.md |
| Phase 5 – Testing & Validation           | Run linting, execute full test suite, verify no regressions across all modules                                 | 100%       | ✅ 510/510 tests (24.59s); 9.63/10 lint; 0 regressions; comprehensive metrics compiled                |

1. **Key objective**
   **Comprehensive codebase standardization** across KidsChores integration to:

   - ✅ **Establish repeatable audit framework** – Consistent methodology for identifying hardcoded strings, data constants, logging patterns
   - ✅ **Conform ALL user-facing strings to localization standards** – `CFOP_ERROR_*`, `TRANS_KEY_CFOF_*` patterns across flow_helpers.py, entities, and core modules
   - ✅ **Extract ALL hardcoded data/lookup strings into constants** – Backup metadata keys, entity type keys, format strings, enum values
   - ✅ **Standardize dictionary access patterns** – Use constants instead of hardcoded string keys across all files
   - ✅ **Ensure translation completeness** – Update en.json (master file) with all TRANS*KEY*_ and CFOP*ERROR*_ entries

   **Current compliance: 94.8% (flow_helpers.py only)**; Additional files TBD after framework establishment.

2. **Summary of recent work**

   - **Phase 0**: Framework validated across 10 files (23,365 LOC); CODE_REVIEW_GUIDE.md complete with 6-step audit process ✅
   - **Phase 1a**: flow_helpers.py audit completed (100%) – 109 hardcoded strings, 53 constants needed, 22 log statements (100% compliant) ✅
   - **Phase 1b**: Entity platform files audited (100%) – 5968 lines, 95%+ compliant, 0 hardcoded strings, 12 dashboard keys identified ✅
   - **Phase 1c**: config_flow.py & options_flow.py audited (100%) – 15 hardcoded strings, 40 constants needed, 126 log statements (100% compliant) ✅
   - **Phase 1d**: coordinator.py & services.py audited (100%) – 9819 lines, 282 log statements (100% compliant), 41 hardcoded errors identified ✅
   - **Phase 2a**: Translation rationalization complete ✅ - Reduced 105 constants → **43 constants** (59% reduction) via generic error templates
   - **Phase 2b**: Constants defined in const.py ✅ - Added 43 constants (12 TRANS_KEY_ERROR, 5 TRANS_KEY_CFOF, 3 TRANS_KEY_TIME, 12 ATTR_DASHBOARD, 8 DATA_KEY, 3 FORMAT); linting passed (9.97/10)
   - **Phase 2c**: Translation templates added to en.json ✅ - Added 21 translations (12 exceptions, 5 config.error, 4 display); JSON validated successfully
   - **Test Baseline Established** ✅: 509/510 tests passing (99.8%), 29.17s runtime - documented in BASELINE_TEST_RESULTS_PHASE2.md
   - **Key Finding**: services.py is GOLD STANDARD for error handling (95% translation compliance); coordinator.py needs 41 error strings migrated
   - **Audit reports**: 3 comprehensive JSON reports generated (entity platforms, config/options flows, coordinator/services)

3. **Next steps (short term)**

   - **Phase 1 Research: COMPLETE** ✅ - All main files audited (10 files, 23,365 LOC total)
   - **Phase 2a Rationalization: COMPLETE** ✅ - Optimized to 43 constants + 21 en.json entries (59% reduction from original 105)
   - **Phase 2b Define Constants: COMPLETE** ✅ - 43 constants added to const.py; linting passed; no duplicates
   - **Phase 2c Translation Templates: COMPLETE** ✅ - 21 translations added to en.json; JSON validated
   - **Test Baseline: ESTABLISHED** ✅ - 509 passing tests documented for regression detection
   - **Phase 2: COMPLETE** ✅ - All 43 constants defined, all 21 translations added, validation passing
   - **READY FOR**: Phase 3 - Code Remediation (165+ locations: 109 flow_helpers + 15 config_flow + 41 coordinator)
   - **Estimated Phase 3 effort**: 3-4 hours (HIGH priority files first: flow_helpers, config_flow, coordinator)

4. **Risks / blockers**

   - ~~**Phase 0 framework not yet validated**~~: Framework successfully validated across 10 files (23,365 LOC) ✅
   - ~~**Entity file complexity**~~: All 50+ entity types audited with 95%+ compliance ✅
   - ~~**Translation rationalization scope**~~: Phase 2a complete - 39% reduction achieved (105→64 constants) ✅
   - **None currently blocking Phase 2b**: Ready to proceed with constant definition

5. **References**

   - [Code Review Guide](../CODE_REVIEW_GUIDE.md) – Phase 0 framework checklist (Steps 1-6) - validated across all files ✅
   - [Architecture Documentation](../ARCHITECTURE.md) – Storage-only architecture, entity naming patterns
   - [Testing Agent Instructions](../../tests/TESTING_AGENT_INSTRUCTIONS.md) – Test execution patterns
   - [Copilot Instructions](../../.github/copilot-instructions.md) – Constant naming standards (8 categories), translation patterns
   - [Test Baseline Results](../BASELINE_TEST_RESULTS_PHASE2.md) – Pre-Phase 2 baseline: 509/510 passing (99.8%), 29.17s runtime ✅
   - [Audit Report: Entity Platforms](./AUDIT_REPORT_ENTITY_PLATFORMS.json) – 5968 LOC audit results ✅
   - [Audit Report: Config/Options Flows](./AUDIT_REPORT_CONFIG_OPTIONS_FLOWS.json) – 4262 LOC audit results ✅
   - [Audit Report: Coordinator/Services](./AUDIT_REPORT_COORDINATOR_SERVICES.json) – 9819 LOC audit results ✅

6. **Decisions & completion check**
   - **Decisions captured**:
     - Translation architecture: en.json is master file (no strings.json needed for storage-only integrations) ✅
     - Phase 0 framework: 6-step audit process standardized in CODE_REVIEW_GUIDE.md and validated across 10 files ✅
     - Translation rationalization: Completed as Phase 2a - achieved 39% reduction (105→64 constants) via generic templates ✅
     - Priority order: Phase 1 research complete → NOW: Phase 2b (define constants) → Phase 2c (add translations) → Phase 3 (remediate code) ✅
     - Test baseline: Established 509/510 passing tests (99.8%) for regression detection ✅
     - Gold standard identified: services.py error handling pattern (translation_key with placeholders) to replicate in coordinator.py ✅
   - **Completion criteria**:
     - [ ] Phase 2b: 64 constants defined in const.py with proper organization and documentation
     - [ ] Phase 2c: 21 translation entries added to en.json with JSON validation passing
     - [ ] Phase 3: All 165+ hardcoded strings replaced with constant references across flow_helpers, config_flow, coordinator
     - [ ] Phase 4: Translation integration verified; spot checks completed
     - [ ] Phase 5: All tests passing (≥509/510); linting clean; no regressions vs baseline
   - **Completion confirmation**: `[ ]` All follow-up items completed (Phase 0 framework validated, all audits completed, constants defined, code remediated, translations added, tests passing, documentation updated) before marking initiative done.

---

## Phase 0 – Repeatable Audit Framework

**Goal**: Establish standardized, documented process for auditing any Python file in the KidsChores codebase to ensure consistent identification of user-facing strings, data constants, logging patterns, and translation requirements.

**Status**: 0% (Not started)

**Why this matters**: With 50+ entity files and 30+ module files, we need a systematic approach to ensure nothing is missed. This framework prevents audit fatigue and maintains consistency.

### Framework Checklist (Applied to Each File)

#### Step 1: Logging Audit

- [ ] Search for all `const.LOGGER.*` calls in file
- [ ] Verify each uses lazy logging (not f-strings): `logger.debug("Message: %s", var)` ✓
- [ ] Count by severity: DEBUG, INFO, WARNING, ERROR
- [ ] Document any hardcoded strings in log messages
- [ ] Result: "N log statements reviewed; X% compliant; [list of issues]"

#### Step 2: User-Facing String Identification

- [ ] Identify all user-facing validation error messages (config flow, options flow)
- [ ] Identify all field labels and descriptions (schema builders)
- [ ] Identify all entity names, descriptions used in UI
- [ ] Identify all error messages returned to user
- [ ] Search for hardcoded strings in error dicts: `errors['field'] = 'hardcoded_string'`
- [ ] Result: List of 50+ user-facing strings with line numbers

#### Step 3: Data/Lookup Constant Identification

- [ ] Search for repeated string literals (use `grep` with frequency count)
- [ ] Identify dictionary keys used 2+ times: `dict['key']`, `dict.get('key')`
- [ ] Identify enum-like strings: status values, type names, tag names
- [ ] Identify format strings: date formats, filename patterns, templates
- [ ] Identify magic numbers and delimiters: hardcoded lengths, delimiters
- [ ] Result: Categorized list of 20+ data constants with occurrence counts

#### Step 4: Pattern Analysis

- [ ] Verify error messages follow `CFOP_ERROR_*` → `TRANS_KEY_CFOF_*` pattern
- [ ] Verify field labels use appropriate `CFOF_*` or `LABEL_*` constants
- [ ] Verify data structure access is consistent (dict keys vs. const references)
- [ ] Verify logging compliance (no f-strings, lazy evaluation)
- [ ] Result: "Pattern compliance: X% (Y errors, Z warnings)"

#### Step 5: Translation Key Verification

- [ ] Extract all unique `TRANS_KEY_*` and `CFOP_ERROR_*` constants found in file
- [ ] Cross-reference against en.json → verify English translations exist (master file)
- [ ] Identify missing translation keys (constants defined but no en.json entry)
- [ ] Document gaps for Phase 4 remediation
- [ ] Note: KidsChores uses en.json for all integration translations
- [ ] Result: "Translation coverage: X% (Y missing entries, Z gaps)"

#### Step 6: Audit Documentation

- [ ] Create summary: Total strings identified, breakdown by category
- [ ] Create priority breakdown: HIGH (>5 occurrences), MEDIUM (2-4), LOW (1)
- [ ] Create actionable remediation list: File name, line numbers, suggested constant names
- [ ] Estimate LOC changes required (constants to add, code locations to update)
- [ ] Result: JSON or table format audit report for tracking

### Output Format (Standardized Audit Report)

```json
{
  "file": "path/to/file.py",
  "audit_date": "2025-12-19",
  "loc_total": 1234,
  "sections": {
    "logging": {
      "total_statements": 22,
      "debug": 17,
      "info": 2,
      "warning": 3,
      "error": 0,
      "compliance_percent": 100,
      "issues": []
    },
    "user_facing_strings": {
      "total": 32,
      "error_messages": 10,
      "field_labels": 15,
      "descriptions": 8,
      "hardcoded": 6,
      "compliance_percent": 81
    },
    "data_constants": {
      "total": 47,
      "dict_keys": 12,
      "entity_keys": 9,
      "enum_values": 15,
      "format_strings": 9,
      "magic_strings": 3,
      "high_priority": 21,
      "medium_priority": 21,
      "low_priority": 5
    },
    "translation_keys": {
      "found": 28,
      "in_strings_json": 26,
      "in_en_json": 24,
      "missing_en_json": 4,
      "coverage_percent": 86
    }
  },
  "summary": "109 total hardcoded strings; 94.8% user-facing compliance; 53+ constants needed",
  "next_phase": "Constant definition and code remediation"
}
```

### Validation Gate: Audit Completeness Checklist

- [ ] All file sections read (start line, end line documented)
- [ ] Logging audit completed and verified
- [ ] User-facing strings 100% identified
- [ ] Data constants categorized by priority
- [ ] Translation keys cross-referenced with en.json (master file)
- [ ] Audit report generated and reviewed
- [ ] Estimated LOC changes calculated
- [ ] Sign-off: Audit deemed complete before Phase 1 remediation

---

## Phase 1a – Flow Helpers Analysis (COMPLETED)

**Goal**: Complete comprehensive analysis of `flow_helpers.py` (config/options validation).

**Status**: ✅ **100% Complete**

**Findings Summary**:

- **Total hardcoded strings**: 109 (62 user-facing + 47 data)
- **Logging compliance**: 100% (22 statements, all correct lazy logging)
- **User-facing compliance**: 94.8% (73/77 strings using constants)
- **Data constants needed**: 47 items (dictionary keys, entity types, format strings)
- **Translation coverage**: 5 missing entries in en.json (master file)

**Deliverables**:

- ✅ Audit report: Complete
- ✅ Constant list: 53 constants identified (6 translation/error + 47 data)
- ✅ Code remediation plan: 70+ locations mapped
- ✅ Translation gaps: 5 missing en.json entries

---

## Phase 1b – Entities Analysis

**Goal**: Audit all entity platform files to identify user-facing strings, data constants, and logging patterns.

**Status**: ✅ **100% Complete**

**Files audited** (Entity platforms):

- [x] `sensor.py` (3374 lines) – 17 extra*state_attributes methods; 195 ATTR* usages; 0 hardcoded strings; dashboard helper has 12 JSON keys
- [x] `button.py` (1396 lines) – 9 extra_state_attributes; 36 logging statements; 100% compliant
- [x] `calendar.py` (747 lines) – 1 extra_state_attributes; minimal, perfect implementation
- [x] `select.py` (328 lines) – 1 extra_state_attributes; 100% compliant
- [x] `datetime.py` (123 lines) – 1 extra_state_attributes; 100% compliant
- [x] `image.py` – N/A (file does not exist)

**Audit steps**:

1. Apply Phase 0 framework to each entity file
2. Document user-facing strings (entity names, attributes, state values)
3. Identify data constants (entity identifiers, state mapping, device info)
4. Verify logging patterns (debug, info, warning calls)
5. Cross-reference translation keys with en.json (master file)
6. Create consolidated audit report for all entities

**Actual findings**:

- **sensor.py**: 0 hardcoded strings; 12 dashboard JSON attribute keys; 0 logging; 17 extra_state_attributes methods
- **button.py**: 0 hardcoded strings; 36 logging statements (100% compliant); 9 extra_state_attributes
- **calendar.py**: 0 hardcoded strings; 1 logging statement; 1 extra_state_attributes (minimal, perfect)
- **select.py**: 0 hardcoded strings; 0 logging; 1 extra_state_attributes (perfect)
- **datetime.py**: 0 hardcoded strings; 0 logging; 1 extra_state_attributes (perfect)
- **Total**: 0 hardcoded user-facing strings; 12 dashboard attribute keys; 37 logging statements; 29 extra_state_attributes methods; **95%+ compliance**

**Acceptance criteria**: ✅ **ALL COMPLETE**

- [x] All entity files audited using Phase 0 framework (5 files, 5968 lines)
- [x] Audit report generated (see `AUDIT_REPORT_ENTITY_PLATFORMS.json`)
- [x] Priority assessment: Entity files are **LOW priority** for remediation (95%+ compliant)
- [x] Translation gaps: 0 missing translations (100% coverage)
- [x] Ready for Phase 2 - but entity files should be DEFERRED

**Key Finding**: Entity platform files are **already 95%+ compliant**. Only finding: Dashboard helper sensor uses 12 hardcoded JSON keys for API structure (intentional design for frontend consumption). **Recommendation**: Focus Phase 2 on flow_helpers.py and config_flow.py (HIGH priority).

---

## Phase 1c – Config/Options Flow Analysis

**Goal**: Audit config_flow.py and options_flow.py to identify user-facing strings, data constants, and logging patterns in configuration flows.

**Status**: ✅ **100% Complete**

**Files audited** (Configuration flows):

- [x] `config_flow.py` (~1400 lines) – 15 hardcoded strings identified; 32 log statements verified; 6 missing translations
- [x] `options_flow.py` (~2900 lines) – 0 hardcoded strings; 94 log statements verified; 100% translation coverage; **exemplary architecture**

**Why these files matter**:

- **Highest user interaction**: Config/options flows are the primary UI for integration setup and management
- **Translation-critical**: All error messages, field labels, and descriptions must be localized
- **Data structure access**: Heavy use of dictionary keys for entity data (internal_id, name, points, etc.)
- **Validation patterns**: Error handling patterns must follow CFOP*ERROR*_ → TRANS*KEY_CFOF*_ conventions

**Audit approach**:

1. Apply Phase 0 framework (6-step process) to each file
2. Document all user-facing validation errors and field labels
3. Identify repeated dictionary access patterns (entity data, backup metadata)
4. Verify logging compliance (lazy logging, appropriate severity levels)
5. Cross-reference translation keys with en.json
6. Create consolidated audit report with HIGH/MEDIUM/LOW priority items

**Actual findings**:

- **config_flow.py**: 15 hardcoded UI strings (data recovery menu options); 28 data constants (storage keys, error keys); 32 logging statements (100% compliant); 6 missing translation keys
- **options_flow.py**: 0 hardcoded strings (delegates to flow_helpers); 12 data constants (minimal, mostly using const); 94 logging statements (100% compliant); 0 missing translations
- **Total**: 15 user-facing strings; 40 data constants; 126 logging statements; 6 missing translations; 40 code locations to update

**Acceptance criteria**: ✅ **ALL COMPLETE**

- [x] Both files audited using Phase 0 framework (6-step process applied)
- [x] Audit reports generated in JSON format (see `AUDIT_REPORT_CONFIG_OPTIONS_FLOWS.json`)
- [x] Translation gaps identified: 6 missing keys in en.json for config_flow data recovery
- [x] Priority breakdown completed: 10 HIGH, 13 MEDIUM, 5 LOW priority items
- [x] Ready for Phase 2 constant definition

**Key Finding**: options_flow.py is architecturally excellent - delegates ALL validation to flow_helpers, resulting in 100% compliance with zero hardcoded strings.

---

## Phase 1d – Additional Files Analysis

**Goal**: Audit coordinator.py, services.py, and other core modules to identify standardization requirements.

**Status**: ✅ **100% Complete**

**Files audited** (Core modules):

- [x] `coordinator.py` (8642 lines) – 196 logging statements (100% compliant); 41 hardcoded error strings; 1992 DATA\_ usages
- [x] `services.py` (1177 lines) – 86 logging statements (100% compliant); **95% translation compliance** (GOLD STANDARD)
- [ ] `notification_*.py` – Deferred (notification methods in coordinator use proper patterns)
- [ ] Other utility modules – Deferred

**Actual findings**:

- **coordinator.py**: 41 hardcoded `HomeAssistantError` f-string messages (need translation_key pattern)
- **services.py**: ✅ **EXEMPLARY** - 95%+ translation compliance, uses `translation_key` pattern correctly
- **Logging**: Both files 100% compliant with lazy logging patterns
- **Data constants**: coordinator.py uses 1992 const.DATA\_\* references (perfect compliance)

**Key Discovery**: services.py is the **GOLD STANDARD** for error handling - uses `HomeAssistantError(translation_domain=const.DOMAIN, translation_key=const.TRANS_KEY_ERROR_*, translation_placeholders={...})` pattern. coordinator.py needs to adopt this pattern.

**Acceptance criteria**: ✅ **ALL COMPLETE**

- [x] coordinator.py and services.py audited using Phase 0 framework
- [x] Audit report generated (see `AUDIT_REPORT_COORDINATOR_SERVICES.json`)
- [x] Priority assessment: coordinator.py = **HIGH priority** (41 error strings); services.py = **LOW priority** (exemplary)
- [x] Translation gaps: 12 new TRANS*KEY_ERROR*\* constants needed for coordinator.py
- [x] Ready for Phase 2 - Define new constants

**Estimated remediation effort**: 12 new constants + 41 string replacements in coordinator.py = ~4-6 hours

---

## Phase 2 – Constant Definition & Translation Templates

**Goal**: Define 64 optimized constants in `const.py` and create 21 translation templates in `en.json` using rationalized patterns from Phase 1 analysis.

**Status**: 0% (Not started; Ready to begin - all Phase 1 audits complete)

**Phase 2 Overview**: After translation rationalization analysis, reduced scope from 105 constants → **64 constants** (39% reduction) by using generic error templates and consolidating patterns.

---

### Phase 2a: Translation Rationalization (✅ Complete)

**Status**: ✅ **100% Complete**

**Key Findings**:

1. **Generic Error Templates**: 41 coordinator.py errors → 12 reusable templates (71% reduction)
   - Pattern: `HomeAssistantError(translation_domain=DOMAIN, translation_key="entity_not_found", translation_placeholders={"entity_type": "kid", "entity_name": name})`
2. **Time Formatting**: 15+ format strings → 3 templates with pluralization (80% reduction)
3. **Dashboard JSON Keys**: 12 constants INCLUDED (no breaking change - constant values = current strings)
4. **Existing Patterns**: flow_helpers.py CFOF pattern already 95% compliant (only 6 missing keys)

**Deliverable**: ✅ Rationalization analysis complete (see conversation history)

---

### Phase 2b: Define Constants in const.py

**Status**: 0% (Not started)

**Deliverables** (Sequential checklist):

- [ ] **Step 1**: Read current const.py structure (lines 1-100) to identify insertion points
- [ ] **Step 2a**: Add 12 generic error translation keys (TRANS*KEY_ERROR*\*)
- [ ] **Step 2b**: Add 6 missing config flow translation keys (TRANS*KEY_CFOF*\*)
- [ ] **Step 2c**: Add 3 time format translation keys (TRANS*KEY_TIME*\*)
- [ ] **Step 3**: Add 12 dashboard attribute keys (ATTR*DASHBOARD*\*)
- [ ] **Step 4**: Add 19 data structure keys (DATA*KEY*_, BACKUP*KEY*_, FORMAT\_\*)
- [ ] **Step 5**: Add 12 additional flow helper constants (BACKUP*TAG*_, TIME*UNIT*_, etc.)
- [ ] **Step 6**: Verify alphabetical ordering within each category
- [ ] **Step 7**: Run linting check on const.py
- [ ] **Step 8**: Verify no duplicate constant values or naming conflicts

**TOTAL: 64 new constants**

**Constant Categories** (with counts):

1. **TRANS*KEY_ERROR*\*** (Generic error templates): 12 constants

   - `TRANS_KEY_ERROR_ENTITY_NOT_FOUND` (covers Kid/Chore/Reward/Badge/Penalty/Bonus not found)
   - `TRANS_KEY_ERROR_ENTITY_NOT_ASSIGNED` (chore not assigned to kid)
   - `TRANS_KEY_ERROR_INSUFFICIENT_POINTS` (not enough points)
   - `TRANS_KEY_ERROR_ALREADY_CLAIMED` (chore already claimed)
   - `TRANS_KEY_ERROR_ENTITY_MISMATCH` (penalty/bonus doesn't apply to kid)
   - `TRANS_KEY_ERROR_MISSING_DUE_DATE` (chore missing due date)
   - `TRANS_KEY_ERROR_NO_RECURRING_FREQ` (chore has no recurring frequency)
   - `TRANS_KEY_ERROR_NO_DUE_DATE_SET` (chore due date not set)
   - `TRANS_KEY_ERROR_KID_NAME_NOT_FOUND` (kid name lookup failed)
   - `TRANS_KEY_ERROR_INVALID_DATE_FORMAT` (date parsing error)
   - `TRANS_KEY_ERROR_MISSING_REQUIRED_FIELD` (validation error)
   - `TRANS_KEY_ERROR_INVALID_SELECTION` (invalid user choice)

2. **TRANS*KEY_CFOF*\*** (Config flow validation): 6 constants

   - `TRANS_KEY_CFOF_INVALID_SELECTION` (invalid menu choice)
   - `TRANS_KEY_CFOF_EMPTY_JSON` (empty JSON paste)
   - `TRANS_KEY_CFOF_INVALID_STRUCTURE` (malformed JSON structure)
   - `TRANS_KEY_CFOF_INVALID_JSON` (JSON parse error)
   - `TRANS_KEY_CFOF_INVALID_FORMAT_LIST_EXPECTED` (list validation error)
   - `TRANS_KEY_CFOF_END_DATE_BEFORE_START` (date range validation)

3. **TRANS*KEY_TIME*\*** (Time formatting): 3 constants

   - `TRANS_KEY_TIME_AGO_MINUTES` (e.g., "5 minutes ago")
   - `TRANS_KEY_TIME_AGO_HOURS` (e.g., "2 hours ago")
   - `TRANS_KEY_TIME_AGO_DAYS` (e.g., "3 days ago")

4. **ATTR*DASHBOARD*\*** (Dashboard sensor attributes): 12 constants

   - `ATTR_DASHBOARD_CHORES = "chores"`
   - `ATTR_DASHBOARD_REWARDS = "rewards"`
   - `ATTR_DASHBOARD_BONUSES = "bonuses"`
   - `ATTR_DASHBOARD_PENALTIES = "penalties"`
   - `ATTR_DASHBOARD_ACHIEVEMENTS = "achievements"`
   - `ATTR_DASHBOARD_CHALLENGES = "challenges"`
   - `ATTR_DASHBOARD_BADGES = "badges"`
   - `ATTR_DASHBOARD_UI_TRANSLATIONS = "ui_translations"`
   - `ATTR_DASHBOARD_COMPLETED_CHORES = "completed_chores"`
   - `ATTR_DASHBOARD_REDEEMED_REWARDS = "redeemed_rewards"`
   - `ATTR_DASHBOARD_TOTAL_BADGES = "total_badges"`
   - `ATTR_DASHBOARD_BADGE_MAINTENANCE = "badge_maintenance"`

5. **DATA*KEY*\*** (Data structure keys): 8 constants

   - `DATA_KEY_BACKUP_METADATA` (backup file metadata key)
   - `DATA_KEY_BACKUP_TIMESTAMP` (backup timestamp key)
   - `DATA_KEY_BACKUP_VERSION` (backup version key)
   - `DATA_KEY_BACKUP_TAG` (backup tag key)
   - `DATA_KEY_BACKUP_REASON` (backup reason key)
   - `DATA_KEY_LIST_DATA` (list validation key)
   - `DATA_KEY_VALIDATION_ERROR` (validation error context)
   - `DATA_KEY_ERROR_FIELD` (field name in error)

6. **FORMAT\_\*** (Format strings): 3 constants

   - `FORMAT_BACKUP_FILENAME` (backup filename template)
   - `FORMAT_DATETIME_ISO` (ISO datetime format)
   - `FORMAT_BACKUP_AGE` (backup age display template)

7. **BACKUP*TAG*\***, **TIME*UNIT*\***, etc. (Domain-specific): 8 constants
   - `BACKUP_TAG_RECOVERY = "recovery"`
   - `BACKUP_TAG_REMOVAL = "removal"`
   - `BACKUP_TAG_MANUAL = "manual"`
   - `BACKUP_TAG_PRE_MIGRATION = "pre-migration"`
   - `TIME_UNIT_MINUTES = "minutes"`
   - `TIME_UNIT_HOURS = "hours"`
   - `TIME_UNIT_DAYS = "days"`
   - `TIME_UNIT_WEEKS = "weeks"`

**Organization Strategy in const.py**:

1. Find existing TRANS*KEY_ERROR*\* section → add new error keys alphabetically
2. Find existing TRANS*KEY_CFOF*\* section → add new CFOF keys alphabetically
3. Create new TRANS*KEY_TIME*_ section (after TRANS*KEY_NOTIF*_)
4. Find existing ATTR*\* section → add ATTR_DASHBOARD*\* alphabetically
5. Find existing DATA*\* section → add DATA_KEY*\* alphabetically
6. Find existing FORMAT*\* constants → add new FORMAT*\* alphabetically
7. Create BACKUP*TAG*\* section (group with backup-related constants)
8. Create TIME*UNIT*\* section (group with time-related constants)

**Verification Steps**:

- [ ] No duplicate constant names
- [ ] No duplicate constant values (where uniqueness matters)
- [ ] All constants follow naming conventions from copilot-instructions.md
- [ ] Alphabetical ordering within each category
- [ ] Docstrings explain usage and scope
- [ ] Linting passes: `./utils/quick_lint.sh --fix custom_components/kidschores/const.py`

---

### Phase 2c: Create Translation Templates in en.json

**Status**: 0% (Not started; depends on Phase 2b completion)

**Deliverables** (Sequential checklist):

- [ ] **Step 1**: Read current en.json structure to identify sections
- [ ] **Step 2**: Backup current en.json (safety measure)
- [ ] **Step 3a**: Add 12 generic error templates to "exceptions" section
- [ ] **Step 3b**: Add 6 config flow error messages to "config.error" section
- [ ] **Step 3c**: Add 3 time format templates to new "time" section
- [ ] **Step 4**: Validate JSON syntax
- [ ] **Step 5**: Verify all TRANS*KEY*\* constants have corresponding en.json entries
- [ ] **Step 6**: Test translation lookup in coordinator (spot check 3-5 error paths)

**TOTAL: 21 new en.json entries**

**Translation Templates by Section**:

**A. Exceptions Section** (12 generic error templates):

```json
{
  "exceptions": {
    "entity_not_found": {
      "message": "{entity_type} '{entity_name}' not found"
    },
    "entity_not_assigned": {
      "message": "{entity_type} '{entity_name}' is not assigned to {target_type} '{target_name}'"
    },
    "insufficient_points": {
      "message": "'{kid_name}' does not have enough points ({cost} needed, {available} available)"
    },
    "already_claimed": {
      "message": "Chore '{chore_name}' has already been claimed today. Multiple claims not allowed."
    },
    "entity_mismatch": {
      "message": "{entity_type} '{entity_name}' does not apply to {target_type} '{target_name}'"
    },
    "missing_due_date": {
      "message": "Missing due date in chore '{chore_name}': {error}"
    },
    "no_recurring_frequency": {
      "message": "Chore '{chore_name}' does not have a recurring frequency"
    },
    "no_due_date_set": {
      "message": "Chore '{chore_name}' does not have a due date set"
    },
    "kid_name_not_found": {
      "message": "Kid name '{kid_name}' not found"
    },
    "invalid_date_format": {
      "message": "Invalid date format: {date_string}"
    },
    "missing_required_field": {
      "message": "Missing required field: {field_name}"
    },
    "invalid_selection": {
      "message": "Invalid selection: {selection}"
    }
  }
}
```

**B. Config.Error Section** (6 config flow errors):

```json
{
  "config": {
    "error": {
      "invalid_selection": "Invalid selection. Please choose a valid option.",
      "empty_json": "No JSON data provided. Please paste valid JSON data.",
      "invalid_structure": "Invalid JSON structure. Missing required fields: {fields}",
      "invalid_json": "Failed to parse JSON data: {error}",
      "invalid_format_list_expected": "Invalid format: expected a list, got {type}",
      "end_date_before_start": "End date cannot be before start date"
    }
  }
}
```

**C. Time Section** (3 time format templates - NEW SECTION):

```json
{
  "time": {
    "ago_minutes": "{count} minute{plural} ago",
    "ago_hours": "{count} hour{plural} ago",
    "ago_days": "{count} day{plural} ago"
  }
}
```

**Translation Placeholder Patterns**:

- `{entity_type}`: "kid", "chore", "reward", "badge", "penalty", "bonus"
- `{entity_name}`: The actual name of the entity
- `{target_type}`: Secondary entity type (e.g., "kid" in "penalty doesn't apply to kid")
- `{target_name}`: Secondary entity name
- `{kid_name}`, `{chore_name}`, `{reward_name}`: Specific entity names
- `{cost}`, `{available}`: Point values (numbers)
- `{count}`: Numeric count for time/pluralization
- `{plural}`: "s" or "" for pluralization
- `{error}`, `{fields}`: Error details (strings)

**Validation Strategy**:

1. Use `python -m json.tool custom_components/kidschores/translations/en.json` to verify syntax
2. Verify all TRANS*KEY_ERROR*\* → "exceptions" mapping
3. Verify all TRANS*KEY_CFOF*\* → "config.error" mapping
4. Verify all TRANS*KEY_TIME*\* → "time" mapping
5. Check no duplicate keys within each section

---

### Phase 2 Acceptance Criteria

**Completion Checklist**:

- [ ] All 64 constants defined in const.py (Phase 2b complete)
- [ ] All 21 translation entries added to en.json (Phase 2c complete)
- [ ] Linting passes on both files
- [ ] JSON syntax valid in en.json
- [ ] All TRANS*KEY*\* constants have corresponding translations
- [ ] No duplicate constant names or values
- [ ] Documentation updated with new constant categories
- [ ] Ready to proceed to Phase 3 (code remediation)

**Files Modified**:

- `custom_components/kidschores/const.py` (+64 constants, ~200 lines)
- `custom_components/kidschores/translations/en.json` (+21 entries, ~100 lines)

**Estimated Effort**: 2-3 hours

- Phase 2b (constants): 1-1.5 hours
- Phase 2c (translations): 1-1.5 hours

---

### Phase 2 Dependencies

**Depends on**:

- ✅ Phase 1a complete (flow_helpers.py audit)
- ✅ Phase 1b complete (entity platform audits)
- ✅ Phase 1c complete (config/options flow audits)
- ✅ Phase 1d complete (coordinator/services audits)
- ✅ Translation rationalization analysis complete

**Blocks**:

- Phase 3 (code remediation - needs constants defined)
- Phase 4 (translation integration - needs en.json templates)

---

## Phase 3 – Code Remediation

**Goal**: Replace 100+ hardcoded strings across ALL audited files with constant references.

**Status**: 0% (Not started; Depends on Phase 2 completion)

**Scope**:

- flow_helpers.py: 70+ locations
- Entity files: 30-50+ locations
- Additional files: TBD
- **TOTAL: 100+ code locations**

**Process**:

1. Priority-based remediation: HIGH (>5 occurrences) first, then MEDIUM, then LOW
2. File-by-file updates with linting verification after each file
3. Regression testing between major file updates
4. Final comprehensive linting and testing

**High-priority targets**:

- Backup metadata dict keys (21 instances) → Use BACKUP*KEY*\* constants
- Entity type validation (9 instances) → Use ENTITY*KEY*\* constants
- Error message keys (6+ instances) → Use CFOP*ERROR*\* constants
- Format strings (9+ instances) → Use FORMAT\_\* constants

---

## Phase 4 – Translation Integration (Forward Validation)

**Goal**: Verify ALL TRANS*KEY*\* constants have corresponding **en.json** entries (code → translations).

**Status**: ✅ **100% Complete** (Completed during Phase 3c extension)

**Translation Architecture**: KidsChores uses **dual translation systems**

**1. Integration Translations (Standard HA):**

- Location: `custom_components/kidschores/translations/en.json`
- Provides English text for all `TRANS_KEY_*` and `CFOP_ERROR_*` constants
- All entity translations use `translation_key` → en.json lookup
- strings.json is used for Home Assistant platform development only, not integrations
- **Scope**: Config flow, exceptions, entity names, service descriptions

**2. Dashboard Translations (Custom System - OUT OF SCOPE):**

- Location: `custom_components/kidschores/translations_dashboard/` with files named `{language_code}_dashboard.json` (e.g., `en_dashboard.json`, `es_dashboard.json`)
- **File naming**: Uses constant `DASHBOARD_TRANSLATIONS_SUFFIX = "_dashboard"` to construct filenames
- **Important**: These are **NOT part of Home Assistant's integration translation system**
- **Purpose**: Custom dashboard helper sensor translations exposed via `ui_translations` attribute
- **Access**: Frontend dashboard YAML reads from sensor attributes, not HA translation system
- **Why Custom**: Enables per-kid language selection and optimized dashboard rendering
- **Not Audited**: Dashboard translations are separate system; this audit focuses on HA integration translations only

**Completed Work**:

1. ✅ Created automated script to extract all TRANS*KEY*\* constants from const.py
2. ✅ Cross-referenced with en.json exceptions and config sections
3. ✅ Identified 2 missing keys:
   - `error_msg_no_entry_found`: Added to en.json exceptions section
   - `single_instance_allowed`: Already existed in config.abort section
4. ✅ Validated JSON syntax in en.json (valid)
5. ✅ Verified no duplicate keys or conflicting entries
6. ✅ Full test suite validation: 510/510 tests passing
7. ✅ Linting validation: 9.63/10 maintained

**Coverage Results**:

- [x] All TRANS*KEY_ERROR*\* constants (11 total): ✅ 100% coverage in en.json
- [x] All TRANS*KEY_CFOF*\* constants (109 total): 47 error messages in en.json, 62 are UI labels (pre-existing, out of scope)
- [x] JSON syntax valid in en.json
- [x] No duplicate or conflicting keys
- [x] Translation coverage: 100% for Phase 3/3b/3c scope
- [x] strings.json not modified (platform development only, not used for integrations)

**Documentation**: Forward translation validation complete. All code references verified to have en.json translations.

---

## Phase 4b – Reverse Translation Audit (Translation → Code Validation)

**Goal**: Find **unused translation keys** in en.json that are no longer referenced in code (translations → code).

**Status**: ✅ **100% Complete** (Completed during extended Phase 4 work)

**Purpose**: After verifying all code has translations (Phase 4 forward), validate that all translations have code references:

- Find orphaned/legacy translation keys in en.json not used anywhere in codebase
- Reduce translation bloat (fewer strings = easier maintenance for future languages)
- Establish clean baseline by removing truly unused keys
- Document intentionally-reserved keys for future use

**Approach**:

1. **Extract all keys** from en.json structure (exceptions, config.error, config.abort, entity.\*, etc.)
2. **For each key**, search entire codebase:
   - Check if key exists as TRANS*KEY*\* constant in const.py
   - Search all \*.py files for direct string references
   - Check YAML dashboards for external references
3. **Categorize findings**:
   - **Actively used**: Has code references (keep)
   - **Reserved for future**: Documented as template/future use (keep with comment)
   - **Legacy/deprecated**: From old architecture, no longer needed (consider removing)
   - **Truly orphaned**: No references, no documented purpose (remove)
4. **Document decisions**: Why certain "unused" keys should be kept
5. **Update en.json**: Remove true orphans after validation

**Expected Findings**:

- Legacy keys from pre-v4.2 architecture (before storage-only refactor)
- Renamed keys where old name still exists
- Test-only translation strings
- Reserved templates (10+ identified in Phase 4 as "62 CFOF UI labels")

**Automated Script Template**:

```bash
# Extract all exception keys from en.json
for key in $(jq -r '.exceptions | keys[]' custom_components/kidschores/translations/en.json); do
  # Check const.py for constant definition
  if ! grep -r "TRANS_KEY.*\"$key\"" custom_components/kidschores/const.py > /dev/null; then
    # Check all .py files for direct usage
    if ! grep -r "\"$key\"" custom_components/kidschores/*.py > /dev/null; then
      echo "Potentially unused: exceptions.$key"
    fi
  fi
done
```

**Completed Work**:

1. ✅ Created automated Python script to audit all en.json sections
2. ✅ Script audited 303 translation paths across 4 major sections
3. ✅ Found 2 potentially unused keys out of 20 total (90% active usage)
4. ✅ Manual review categorized findings:
   - `entity_not_found`: Confirmed duplicate of active `not_found` key (REMOVED)
   - `error_insufficient_points`: Potential legacy key, kept for further investigation
5. ✅ Removed 1 orphaned key from en.json (5% reduction in exceptions section)
6. ✅ Full test suite validation: 510/510 passing after cleanup
7. ✅ Linting validation: 9.63/10 maintained
8. ✅ JSON syntax validation: Confirmed valid after removal

**Coverage Results**:

- [x] Automated reverse audit script created and executed
- [x] Report generated: `/docs/completed/PHASE4B_REVERSE_TRANSLATION_AUDIT.md`
- [x] All "unused" keys categorized with recommendations (remove/keep/investigate)
- [x] Keep decisions documented with rationale (see audit report)
- [x] en.json updated to remove true orphans (1 duplicate key removed)
- [x] Full test suite validation: 510/510 passing after cleanup ✅
- [x] Linting validation: 9.63/10 maintained ✅

**Key Findings**:

- **Total sections audited**: 303 (exceptions, config, entity, selector)
- **Translation usage rate**: 90% actively used (18/20 keys)
- **Orphaned keys found**: 1 (`entity_not_found` - duplicate)
- **Keys removed**: 1 (5% reduction in exceptions section)
- **Keys requiring further investigation**: 1 (`error_insufficient_points`)

**Acceptance criteria**:

- [x] All en.json sections audited (exceptions, config, entity, display)
- [x] Each "unused" key has recommendation (remove/keep/reserved)
- [x] Removal candidates listed with specific rationale
- [x] "Keep" decisions have documented reason
- [x] Test suite passes after any en.json changes (510/510 ✅)
- [x] Documentation updated with audit results (PHASE4B_REVERSE_TRANSLATION_AUDIT.md)

**Benefits Achieved**:

- Reduced translation burden when adding new languages
- Faster JSON parsing (smaller file size)
- Cleaner, more understandable translation structure
- Establishes quality baseline for ongoing maintenance

---

## Phase 5 – Testing & Validation

**Goal**: Comprehensive testing and validation across all audited files and modules.

**Status**: ✅ **100% Complete** (All validation criteria met)

**Testing strategy executed**:

1. **Linting**: `./utils/quick_lint.sh --fix` (comprehensive check)
2. **Entity tests**: Entity creation, state updates, attributes
3. **Service tests**: Service handler validation
4. **Full test suite**: All 510 tests passing (100% success rate)
5. **Translation validation**: Forward (Phase 4) and reverse (Phase 4b) audits complete
6. **Metrics compilation**: Comprehensive project statistics gathered

**Validation Results**:

✅ **Linting** (`./utils/quick_lint.sh --fix`):

- Pylint score: **9.63/10** (maintained throughout project)
- Files checked: 41 (all integration and test files)
- Trailing whitespace: 0 issues
- Lines >100 chars: 280 (acceptable per testing instructions)
- Critical errors: **0**
- Status: **ALL CHECKS PASSED - READY TO COMMIT**

✅ **Test Suite** (`pytest tests/ -v --tb=line`):

- Platform: Linux
- Python: 3.13.11
- Pytest: 9.0.0
- **Tests passing: 510/510 (100%)**
- Tests skipped: 10 (intentional)
- Runtime: **24.59s** (baseline: 29.17s, **16% faster**)
- Total scenarios: 520
- **Zero regressions** vs baseline

✅ **Translation Validation**:

- **Phase 4 Forward** (Code→Translations): 100% coverage for error messages
  - 11 TRANS_KEY_ERROR constants: all in en.json
  - 109 TRANS_KEY_CFOF constants: all config flow errors in en.json
  - Missing keys added: 1 (`error_msg_no_entry_found`)
- **Phase 4b Reverse** (Translations→Code): 90% active usage
  - 303 translation paths audited
  - 20 keys in en.json exceptions section
  - Orphaned keys removed: 1 (`entity_not_found` duplicate)

✅ **Final Metrics** (Comprehensive):

- **Files audited**: 10 (20,531 LOC)
- **Constants added**: 78 total (43 core + 10 labels + 25 technical)
- **Strings converted**: 94 hardcoded → constants
- **Error handling improvements**: 31 fixes (18 ValueError, 8 logging, 5 labels)
- **Zero regressions**: All tests passing, lint score maintained

**Acceptance criteria**:

- [x] `./utils/quick_lint.sh --fix` passes with zero errors ✅
- [x] `python -m pytest tests/ -v --tb=line` shows 510 tests passing ✅
- [x] Zero new warnings or regressions ✅
- [x] All translation keys present in en.json ✅
- [x] Comprehensive metrics compiled ✅
- [x] Documentation updated with final results ✅

---

## Notes & follow-up

### Architecture considerations

1. **Audit framework repeatability**: Any developer should be able to apply Phase 0 checklist to new files and produce consistent audit reports
2. **Translation architecture**: KidsChores uses **en.json as master** for all translations; no strings.json updates needed (storage-only, no config flow UI)
3. **Constant naming consistency**: Naming patterns must be enforced across 100+ new constants

### Dependencies

- No external dependencies
- Home Assistant API: No changes required
- Build system: No changes required

### Decisions captured

1. ✅ **Repeatable audit framework**: Phase 0 establishes reusable methodology
2. ✅ **Translation architecture**: en.json (master file) is sole translation source; no strings.json needed
3. ✅ **Priority-based remediation**: HIGH→MEDIUM→LOW ensures critical items first
4. ✅ **Phased approach**: Each phase depends on previous completion (validation gates)

### Completion confirmation

- [x] Phase 0 framework documented and validated
- [x] Phase 1a (flow_helpers.py) complete and verified
- [x] Phase 1b (entities) complete and verified
- [x] Phase 1c (additional files) complete and verified
- [x] Phase 2 (constant definition) complete and verified
- [x] Phase 3 (code remediation) complete and verified
- [x] Phase 3b (entity label remediation) complete and verified
- [x] Phase 3c (ValueError, logging, technical constants) complete and verified
- [x] Phase 4 (translation integration - forward validation) complete and verified
- [x] Phase 4b (reverse translation audit) complete and verified
- [x] Phase 5 (testing & validation) complete and verified
- [ ] Plan document updated to \_COMPLETE and moved to docs/completed/

---

## Master Audit Summary

### Current Status (Snapshot)

| Phase     | File(s)                                                                                   | Strings  | Constants      | Compliance              | Status           |
| --------- | ----------------------------------------------------------------------------------------- | -------- | -------------- | ----------------------- | ---------------- |
| 1a        | flow_helpers.py                                                                           | 109      | 53 needed      | 94.8%                   | ✅ 100%          |
| 1c        | config_flow.py                                                                            | 15       | 40 needed      | 0% (UI), 100% (logging) | ✅ 100%          |
| 1c        | options_flow.py                                                                           | 0        | 12 needed      | 100%                    | ✅ 100%          |
| 1b        | sensor.py (3374), button.py (1396), calendar.py (747), select.py (328), datetime.py (123) | 0        | 12 (dashboard) | 95%+                    | ✅ 100%          |
| 1d        | coordinator.py, services.py, ...                                                          | TBD      | TBD            | TBD                     | 0%               |
| **TOTAL** | **5+ files**                                                                              | **124+** | **105+**       | **Varies**              | **Phase 1: 60%** |

### High-Impact Items (Priority Order)

1. **Phase 0 Framework** – Establish repeatable audit methodology (PREREQUISITE)
2. **flow_helpers.py constants** – 53 constants; 70+ code locations
3. **Entity files constants** – 30-50 constants; 30-50+ code locations
4. **Translation completeness** – Ensure en.json (master file) has all entries
5. **Translation rationalization** – Create templates, consolidate patterns, reduce maintenance
6. **Comprehensive testing** – Verify all modules after remediation

### Risk Assessment

| Risk                               | Impact | Mitigation                                     |
| ---------------------------------- | ------ | ---------------------------------------------- |
| Audit gaps (missing strings)       | HIGH   | Phase 0 framework with validation gates        |
| Translation gaps (missing en.json) | MEDIUM | Automated cross-reference check in Phase 4     |
| Regression bugs                    | MEDIUM | Phase 5 comprehensive testing (150+ tests)     |
| Naming inconsistency               | MEDIUM | Constant naming guidelines documented          |
| Large scope (100+ changes)         | HIGH   | Phased approach with validation between phases |

---

## Testing & validation

### Test Suites to Execute

- **Full test suite**: `python -m pytest tests/ -v --tb=line` (~150 tests, ~7 seconds)
- **Quick lint check**: `./utils/quick_lint.sh --fix` (~22 seconds, comprehensive)
- **Individual file validation**: `python utils/lint_check.py --integration` (per-file checks)

### Validation Gates (Per Phase)

- **Phase 0**: Framework applied to first entity file; audit report generated and validated
- **Phase 2**: All constants added to const.py; no duplicate names; pylint passes
- **Phase 3**: Each file updated; quick_lint.sh passes; no import errors
- **Phase 4**: All translation keys in en.json; no "err-\*" fallback strings in dashboard
- **Phase 5**: Full test suite passes (150/150); quick_lint passes; no regressions

### Tests Executed (As of December 19, 2025)

- ✅ Phase 1a audit completed (manual review)
- ✅ CODE_REVIEW_GUIDE.md updated with Phase 0 framework
- ❌ Phase 0 framework not yet validated on actual file
- ❌ No code changes committed yet (Phase 2+ pending)

### Outstanding Tests

- Phase 0 framework validation (first entity file application)
- Full lint check after constant additions
- Full test suite after code remediation
- Translation completeness verification

---

## Notes & follow-up

### Architecture Considerations

- **Storage-only architecture**: KidsChores uses `.storage/kidschores_data` exclusively; config entry contains only 9 system settings
- **Translation pattern**: en.json is master file for all integration translations (no strings.json needed per HA storage-only pattern)
- **Dashboard helper integration**: Translation keys exposed via `sensor.kc_<kid>_ui_dashboard_helper` attributes for frontend consumption
- **Entity naming**: All entities follow `<type>.kc_<kid_slug>_<purpose>` pattern with exact matching required

### Constant Naming Standards (8 Categories)

1. **DATA\_\*** – Storage/runtime data keys (singular entity name)
2. **CFOF\_\*** – Config/options flow input field names (plural entity, generic field)
3. **CFOP*ERROR*\*** – Config/options flow error keys (exact match to input field)
4. **TRANS*KEY_CFOF*\*** – Translation keys for config/options flows
5. **CONFIG*FLOW_STEP*\*** – Config flow step identifiers
6. **OPTIONS*FLOW*\*** – Options flow menu/action identifiers
7. **DEFAULT\_\*** – Default values for config/options
8. **LABEL\_\*** – UI label constants

### Follow-up Tasks

- **Phase 0 validation**: Apply framework to sensor.py (first entity file) to validate checklist completeness
- **Automation consideration**: Explore automated constant extraction tools to reduce manual audit burden for large files
- **Translation template library**: Document reusable translation patterns discovered during Phase 4b rationalization
- **Dashboard testing**: Verify dashboard helper sensor attributes after translation additions
- **Documentation updates**: Update ARCHITECTURE.md with translation architecture details after Phase 4 completion

### Dependencies

- **Upstream**: None (independent initiative)
- **Downstream**: Dashboard translation integration depends on Phase 4 completion (en.json updates)
- **Parallel work**: Can proceed alongside feature development; requires coordination on const.py merge conflicts
