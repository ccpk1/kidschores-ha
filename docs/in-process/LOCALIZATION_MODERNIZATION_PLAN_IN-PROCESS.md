# LOCALIZATION_MODERNIZATION_PLAN

## Initiative snapshot

- **Name / Code**: Localization & translation modernization
- **Target release / milestone**: Ha 2025 translation guidelines adoption
- **Owner / driver(s)**: UI/translation squad
- **Status**: In progress (Tasks 1-7 underway)

## Summary & immediate steps

| Phase / Step                         | Description                                                                                                      | % complete | Quick notes                                                                                                     |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Critical TRANSLATION fixes | Convert manual f-strings/backups to proper translation keys, fix calendar labels, remove friendly_name overrides | 45%        | Key constants corrected, fallback helper drafted; need to remove ATTR_FRIENDLY_NAME and translate button deltas |
| Phase 2 – UI polish                  | Audit buttons, attribute text, and config flow messaging for translation readiness                               | 10%        | Delta label fixes pending, open decisions on hardcoded attribute labels and device grouping strategy            |
| Phase 3 – Testing & validation       | Update tests for new entity naming/validation and document migration/release notes                               | 5%         | Tests planned for empty name handling, translation entries verification, and release note updates               |

1. **Key objective** – Modernize KidsChores translation usage by eliminating literal f-string patterns, leveraging `_attr_translation_key`, and ensuring all UI strings follow HA 2024/2025 practices.
2. **Summary of recent work** – Confirmed decisions for entity/attribute naming, identified necessary fixes (TRANS_KEY constant, manual friendly names), and outlined fallback helper to keep clean defaults.
3. **Next steps (short term)** – Apply Task 1 critical fixes (remove manual names, adjust translation constant, enforce defensive logging) and continue Task 2 (button label fix, attribute translation decisions).
4. **Risks / blockers** – Need clarity on device grouping strategy and whether to translate hardcoded English attr values now versus later; changes may require release-note communication due to entity name adjustments.
5. **References** – Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), translation plan (`docs/archive/LOCALIZATION_MODERNIZATION_PLAN_LEGACY.md`), translation strategy in architecture doc if needed (`docs/ARCHITECTURE.md`).
6. **Decisions & completion check**
   - **Decisions captured**: Maintain modern HA translation pattern (has_entity_name + translation_key), keep friendly_name auto-managed, treat manual friendly text as fixable; KT tasks prioritized as 2A critical then 2B polish/2C tests.
   - **Completion confirmation**: `[ ]` All follow-up items completed (translation fixes applied, decision dependencies resolved, tests updated, release notes written) before owner approval to mark done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Critical translation fixes

- **Goal**: Eliminate problematic f-strings and fallback helpers that inhibit translation, ensuring each entity follows HA pattern.
- **Steps / detailed work items**
  1. Update `TRANS_KEY_CALENDAR_NAME` constant and remove manual name constructions in calendar/select entities.
  2. Remove `ATTR_FRIENDLY_NAME` overrides (BadgeSensor) and add defensive logging helpers for missing names.
  3. Remove literal fallback strings, replace with helper `get_entity_fallback_name` that provides clean defaults without referencing translation keys.
- **Key issues**
  - Document removal of manual friendly_name to avoid translation regressions.

### Phase 2 – UI polish

- **Goal**: Adjust remaining UI strings (button delta labels, attribute values) and resolve outstanding translation decisions.
- **Steps / detailed work items**
  1. Fix button delta labels to use translation keys instead of concatenated English text.
  2. Decide whether to translate hardcoded attribute values now or defer; update plan once decision locked.
  3. Address open question on device grouping strategy (impact on translation contexts).
- **Key issues**
  - Need decision on attribute translations (Points/Multiplier text) because it may require new translation entries.

### Phase 3 – Testing & validation

- **Goal**: Cover translation changes with tests and document migration/release impacts.
- **Steps / detailed work items**
  1. Add tests ensuring entity name changes do not break flows (e.g., empty name validation tests).
  2. Update translations/en.json entries for new keys and confirm placeholders exist.
  3. Draft migration guide/release notes describing entity name behaviour and translation improvements.
- **Key issues**
  - Tests must ensure defensive logging helper does not leak after translation keys change.

## Testing & validation

- Tests executed: None yet; existing tests need updates per Phase 3 instructions.
- Outstanding tests: Negative name validation tests, translation entry existence checks, and translation fallback behavior.
- Links to failing logs or CI runs: N/A.

## Notes & follow-up

- Additional context: Translation modernization supports upcoming dashboard overhaul; prior doc archived as reference (`docs/archive/LOCALIZATION_MODERNIZATION_PLAN_LEGACY.md`).
- Follow-up tasks: Add translation entries to `translations/en.json`, update release notes about entity name changes, and ensure template instructions mention translation tasks when copying plan.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS`. Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
