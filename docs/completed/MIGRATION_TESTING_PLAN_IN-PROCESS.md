# MIGRATION_TESTING_PLAN

## Initiative snapshot

- **Name / Code**: Migration testing (v3.x → v4.2 storage)
- **Target release / milestone**: KC 4.2 storage-only release
- **Owner / driver(s)**: Migration QA squad
- **Status**: In progress (badge migration failure blocking completion)

## Summary & immediate steps

| Phase / Step                                | Description                                                                                                  | % complete | Quick notes                                                                                                                                |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 1 – Test coverage & sample validation | Build structural validation, preservation checks, datetime/schema assertions across v30/v31/v40beta1 samples | 65%        | Core validation implemented; 19/30 tests passing after entity count fixes; badge migration still failing (list→dict, datetime issues)      |
| Phase 2 – Migration fixes & schema handling | Stabilize coordinator migration (clean install detection, badge data restructuring, schema_version handling) | 35%        | Storage check added to avoid wiping data, meta schema decision postponed; badge migration gap and badge struct mismatch remain the blocker |
| Phase 3 – Regression proofs & documentation | Snapshot tests, regression artifacts, and decision notes (schema design, bug fixes)                          | 15%        | Syrupy snapshots added, root cause analysis documented; plan now ensures badge tests drive future work                                     |

1. **Key objective** – Validate KC 3.x/4.0beta storage migrations by running sample-based tests, capturing structural requirements, and surfacing migration bugs so storage-only release isn’t shipped with data loss.
2. **Summary of recent work** – Fixtures and tests implemented (structural, counts, datetimes, schema); storage clean install bug fixed, coordinator now checks storage before deciding to wipe data, and 19/30 tests now pass. Badge migration still failing due to list→dict conversion and datetime formatting.
3. **Next steps (short term)** – Fix badge migration (list to dict, nested datetime fields), ensure schema metadata handling doesn’t cause pytest to skip migrations, and re-run all samples to reach 100% of desired coverage.
4. **Risks / blockers** – Badge migration failure (KC-COORD-001 style) prevents Phase 1 completion; test framework injecting schema_version into root space still causing detection issues; need to decide whether to move schema_version into `meta` or keep at root while adjusting tests.
5. **References** – Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), legacy migration plan (`docs/archive/MIGRATION_TESTING_PLAN_LEGACY.md`), architecture doc for schema details (`docs/ARCHITECTURE.md`), production JSON sample (`tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`), Data Recovery Backup Plan (shared Phase 5/1.5 entity validation strategy).
6. **Decisions & completion check**
   - **Decisions captured**:
     - Continue with schema_version 42 for testing cycle
     - Add storage entity check before classifying clean installs (✅ done Dec 18)
     - Document badge migration gaps; future schema bump to 43 (meta section) deferred until badge migration resolved
     - Entity validation framework shared between Migration (Phase 1.5/2) and Data Recovery (Phase 5) plans
     - Production JSON sample requires character encoding validation before use in tests
     - Entity creation tests must verify both data structure AND entity registry entries
   - **Completion confirmation**: `[ ]` All follow-up items completed (badge migration validated, entity creation verified, production JSON tested, schema handling stabilized, snapshots updated, release owner approval) before marking initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Test coverage & sample validation

- **Goal**: Validate structural integrity, counts, datetimes, and schema for legacy samples (v3.0, v3.1, v4.0beta1).
- **Steps / detailed work items**
  1. Load migration sample via mocked storage and `MockConfigEntry`, ensuring coordinator reads original schema_version before migrating.
  2. Assert structural requirements for kids, chores, badges, rewards, and parents per sections 1-4 in the legacy plan.
  3. Validate datetimes are UTC-aware ISO strings and `schema_version` equals 42 post-migration.
- **Key issues**
  - Badge migration still outputs legacy `badges` list, blocking tests that expect `badges_earned` dict; tests failing for v30/v31 badge fields/datetime formatting.

### Phase 1.5 – Production JSON sample validation (Dec 18, 2025)

- **Goal**: Validate real production data sample and integrate with data recovery testing flows.
- **Steps / detailed work items**
  1. **Character encoding validation**: Inspect `config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json` for:
     - Special characters: Zoë (U+00EB), cåts (U+00E5), plänts (U+00E4), wåter (U+00E5)
     - Verify UTF-8 encoding throughout file
     - Check for any corrupted or missing characters (user reported potential issues)
  2. **Data structure validation**: Verify production sample contains:
     - 3 kids: Zoë (5e85ea08-...), Max! (cd764ae3-...), Lila (ece7b504-...)
     - 7 chores: Feed the cåts, Wåter the plänts, + 5 others
     - 1 badge: (339e83cf-...)
     - 5 rewards, 2 parents, 3 penalties, 2 bonuses
     - Schema version 42 with meta section
  3. **Integration with Data Recovery Phase 5**: Create shared test suite that validates both migration and entity creation:
     - Test paste JSON flow with production sample (extract `data` section)
     - Test restore from backup with production sample (use full wrapped format)
     - Verify entity counts match: ~150+ sensors, ~50+ buttons, 3 calendars, 3 selects
     - Validate entity naming: `sensor.kc_zoe_points`, `button.kc_zoe_feed_the_cats_claim`, etc.
  4. **Comprehensive entity validation framework**: Build shared helpers for entity verification:
     - `count_entities_by_platform(hass, domain, platform)` - count sensor/button/calendar/select entities
     - `verify_kid_entities(hass, kid_name, expected_chores)` - verify all entities for one kid
     - `verify_entity_states(hass, entity_id, expected_state)` - check entity state values
- **Test patterns to create**:
  - `test_production_json_paste_creates_entities` - paste JSON + verify entity creation
  - `test_production_json_restore_creates_entities` - restore backup + verify entity creation
  - `test_production_json_migration_v42_to_v42` - load as storage + verify no changes needed
  - `test_production_json_character_encoding` - verify special characters preserved
- **Key issues**
  - Production JSON may have character encoding corruption (requires validation before testing)
  - Entity creation tests overlap with Data Recovery Phase 5 (coordinate to avoid duplication)
  - Need to establish entity count baselines for 3-kid setup (current tests use minimal 1-kid samples)

### Phase 2 – Migration fixes & entity validation

- **Goal**: Remedy identified migration failures (badges, schema detection, coordinator data wipes), stabilize schema metadata handling, and validate entity creation post-migration.
- **Steps / detailed work items**
  1. Prevent clean install detection from wiping existing storage by checking both config and storage data before rewriting schema_version (✅ done Dec 18, confirmed in tests).
  2. Decide on schema metadata placement: keep top-level 42 for now but document future plan to move to `meta` (v43) once badge migration passes.
  3. Update coordinator to read schema_version from actual data (consider meta when moving to v43) and restructure migrations to convert badge list→dict with multiplier/datetime.
  4. **Entity creation validation** (integrated with Data Recovery Phase 5):
     - After migration completes, verify entity registry entries created
     - Validate entity counts match kid/chore/badge/reward data
     - Check entity unique IDs use internal_id format
     - Verify entity naming follows `{type}.kc_{kid_slug}_{entity_purpose}` pattern
  5. **Test migration + entity creation together**: Use patterns from Phase 1.5 to validate both data structure AND entity creation:
     - Load v30 sample → migrate to v42 → verify entities created
     - Load v31 sample → migrate to v42 → verify entities created
     - Load v40beta1 sample → migrate to v42 → verify entities created
     - Load production sample → no migration needed → verify entities created
- **Key issues**
  - Migration tests still fail due to badge struct mismatch and datetime formatting; metadata decision pending but should not block immediate fixes.
  - Entity validation framework must be shared with Data Recovery plan to avoid code duplication.

### Phase 3 – Regression proofs & documentation

- **Goal**: Snapshot regression tests, code quality review, document design decisions, and ensure migration artifacts are auditable before marking the plan complete.
- **Steps / detailed work items**
  1. Capture syrupy snapshots for representative kid structures so future changes don't regress migration schema.
  2. **Code quality review**: Validate proper use of constants, translation keys, error handling across coordinator migration code:
     - Review coordinator.py migration methods for proper const.DATA\_\* usage
     - Verify schema_version handling uses proper constants
     - Check datetime migration uses kc_helpers.parse_datetime_to_utc() consistently
     - Validate error handling and logging patterns
     - Run linting checks: `./utils/quick_lint.sh --fix`
  3. Document design decisions (schema_version placement, storage wipe bug fix) in plan and architecture documentation.
  4. Re-run full migration suite (30 tests) once Phase 2 fixes land and record pass/fail counts for release reporting.
- **Key issues**
  - Snapshot updates should accompany any intentional schema change; ensure plan records when snapshots refreshed.

## Testing & validation

- Tests executed:
  - Phase 1: 19/30 migration tests passing (coverage across v30, v31, v40beta1) after clean install fix
  - Structural validation, entity counts, datetime format checks implemented
  - Storage wipe bug confirmed fixed (coordinator checks storage before clearing)
- Outstanding tests:
  - Phase 1: 11 badge-related failures (list→dict, datetime, snapshots)
  - Phase 1.5: Production JSON tests (not yet created - 4 tests planned)
  - Phase 2: Entity creation validation tests (not yet created - integration with Data Recovery Phase 5)
  - Phase 2: Migration + entity verification tests (not yet created - 3 tests for v30/v31/v40beta1)
- Production sample details:
  - File: `tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`
  - Contains: 3 kids, 7 chores, 1 badge, 5 rewards, 2 parents, 3 penalties, 2 bonuses
  - Schema version: 42 (current production format)
  - Special characters: Zoë, cåts, plänts, wåter (requires UTF-8 validation)
- Links to failing logs or CI runs: Document logs from `tests/test_migration_samples_validation.py` runs showing badge failures (store under project board when available).

## Notes & follow-up

- Additional context: Investigated pytest framework injecting schema_version into root; plan postpones schema bump to v43 while focusing on badge migration; once badges pass, revisit meta-section restructure.
- Follow-up tasks: Update architecture doc to reflect storage fix, include decision note about schema metadata in release notes, and add manual migrator documentation referencing snapshots.
- **Phase coordination with Data Recovery Plan**:
  - Phase 1.5 (Migration) aligns with Phase 5 (Data Recovery) for entity validation
  - Shared entity validation framework under `tests/conftest.py` or new `tests/entity_validation_helpers.py`
  - Production JSON sample (`config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`) used by both plans
  - Testing sequence: Character validation → Data structure validation → Entity creation verification
  - Expected entity counts for production sample: ~150+ sensors, ~50+ buttons, 3 calendars, 3 selects

## References & decisions

- **References**: Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), legacy migration plan (`docs/archive/MIGRATION_TESTING_PLAN_LEGACY.md`), architecture doc for schema details (`docs/ARCHITECTURE.md`), production JSON sample (`tests/migration_samples/config_entry-kidschores-01KCSXA0MYEFTDFVGF42CDR23F.json`), Data Recovery Backup Plan (shared Phase 5/1.5 entity validation strategy).
- **Decisions captured**:
  - Continue with schema_version 42 for testing cycle
  - Add storage entity check before classifying clean installs (✅ done Dec 18)
  - Document badge migration gaps; future schema bump to 43 (meta section) deferred until badge migration resolved
  - Entity validation framework shared between Migration (Phase 1.5/2) and Data Recovery (Phase 5) plans
  - Production JSON sample requires character encoding validation before use in tests
  - Entity creation tests must verify both data structure AND entity registry entries
- **Completion confirmation**: `[ ]` All follow-up items completed (badge migration validated, entity creation verified, production JSON tested, schema handling stabilized, snapshots updated, release owner approval) before marking initiative done.
  - [ ] New/updated constants that influence translations (e.g., DATA*\* storage keys, TRANS_KEY*\*, error strings) are documented in `docs/LOCALIZATION_MODERNIZATION_PLAN_IN-PROCESS.md` and wired into `strings.json`/translation workflow so the migration tests exercise translation-ready constants without hardcoding names.
  - [ ] Constants referenced by badge/entity migrations include translation keys in `strings.json` and have been run through `python -m script.translations develop --all` to expose missing entries before migration release.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS`. Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
