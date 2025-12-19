# LEGACY_CLEANUP_PLAN

## Initiative snapshot

- **Name / Code**: Legacy code cleanup tracking
- **Target release / milestone**: KC 5.0 (safe removal once <1% legacy users)
- **Owner / driver(s)**: Migration/maintenance squad
- **Status**: In progress (dependent on adoption metrics)

## Summary & immediate steps

| Phase / Step                         | Description                                                                                | % complete | Quick notes                                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Storage simplification     | Remove redundant migration keys and rely solely on `schema_version` v42 tracking           | 100%       | Schema v42 removes `migration_performed`/`migration_key_version`; coordinator auto-cleans during first refresh |
| Phase 2 – Legacy initializer removal | Delete the 174-line config_entry initialization helpers once schema v42 users verified     | 40%        | Methods targeted for KC 5.0 removal; need telemetry confirming zero schema <42 active users                    |
| Phase 3 – Constants and keys cleanup | Retire legacy constants (legacy kid data keys, migration markers) after mappings validated | 30%        | Constants documented; timeline suits KC 5.0 for safe deletion once cleanup logic confirmed                     |

1. **Key objective** – Retire KC 3.x and KC 4.0 migration artifacts safely by v5.0 once adoption metrics show legacy schemas nearly extinct, keeping storage lean and logic simpler.
2. **Summary of recent work** – Schema v42 now relies solely on `schema_version`, redundant migration flags auto-removed during coordinator refresh, and documentation outlines the legacy initializer methods slated for removal.
3. **Next steps (short term)** – Monitor usage telemetry (schema version distribution), confirm helper removals produce no errors, and prepare cleanup PRs for legacy constants and initializer methods.
4. **Risks / blockers** – Must wait until adoption drops below 1% before removals; cleanup must not run while older schema users still active.
5. **References** – Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), architecture overview (`docs/ARCHITECTURE.md`), and legacy cleanup audit (`docs/archive/LEGACY_CLEANUP_LEGACY.md`).
6. **Decisions & completion check**
   - **Decisions captured**: Keep cleanup tied to KC 5.0, ensure `schema_version` telemetry is <1% before removing legacy helpers, preserve legacy constants only until cleanup logic runs.
   - **Completion confirmation**: `[ ]` All follow-up items completed (telemetry confirming migration, code removed, documentation updated) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Storage simplification

- **Goal**: Remove redundant migration flags and rely only on `schema_version` v42 for automatic upgrades.
- **Steps / detailed work items**
  1. Delete `migration_performed` and `migration_key_version` keys during coordinator first refresh for schema v41 users.
  2. Update coordinator logic to check `DATA_SCHEMA_VERSION` against `SCHEMA_VERSION_STORAGE_ONLY` (42) before migrations.
  3. Verify storage_manager no longer references the deprecated keys elsewhere.
- **Key issues**
  - None; cleanup already applied in KC 4.x beta and documented for transparency.

### Phase 2 – Legacy initializer removal

- **Goal**: Remove the 174-line `_initialize_*` helper suite once schema adoption is safe.
- **Steps / detailed work items**
  1. Confirm telemetry shows >=99% of users on schema ≥42.
  2. Remove `_initialize_data_from_config` and associated `_initialize_kids/parents/.../sync_entities` methods from `coordinator.py`.
  3. Update documentation and tests to reflect storage-only loading path (no config_entry sync).
- **Key issues**
  - Blocked until adoption metric condition satisfied (per target release note in Architecture doc).

### Phase 3 – Constants and keys cleanup

- **Goal**: Delete legacy `const.py` keys (e.g., `DATA_KID_BADGES_LEGACY`) once cleanup logic runs.
- **Steps / detailed work items**
  1. Confirm no runtime usage of deprecated constants remains (search across repo/tests).
  2. Remove constants once all consumers updated to new keys (e.g., `DATA_KID_BADGES_EARNED`).
  3. Update documentation table to reflect deleted constants and their removal versions.
- **Key issues**
  - Ensure release notes mention removal date to alert automation authors.

## Testing & validation

- Tests executed: Legacy cleanup relies on existing regression suite; no new tests required yet.
- Outstanding tests: Validate storage initialization works after removals once target adoption achieved.
- Links to failing logs or CI runs: N/A.

## Notes & follow-up

- Additional context: Legacy logic remains only until adoption metrics allow; ensures smooth migration to KC 5.0.
- Follow-up tasks: Update Architecture doc when deprecations occur, notify release manager before final removal, cross-reference release note in new plan.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS`. Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
