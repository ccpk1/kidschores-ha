# KC_HELPERS_CODE_REVIEW_PLAN

## Initiative snapshot

- **Name / Code**: KC_HELPERS general cleanup
- **Target release / milestone**: v0.5.0 / Phase 4.5 cleanup
- **Owner / driver(s)**: Platform engineering (coordinator team)
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                    | Description                                                                                             | % complete | Quick notes                                                                            |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------- |
| Phase 1 – Stabilize helpers     | Close critical gaps (docstrings, loop detection, production logging) before the next refactor milestone | 35%        | Critical issues documented, autologged tests passing but docstrings/type hints pending |
| Phase 2 – DRY and performance   | Refactor duplicated lookups, consolidate constants, and modernize friendly label handling               | 15%        | Entity lookup plan drafted, magic-number constants scoped, async label access designed |
| Phase 3 – Tests & documentation | Expand missing tests and reorganize sections/ordering for maintainability                               | 5%         | Test candidates listed, documentation reorganization section drafted                   |

1. **Key objective** – Turn the kc_helpers.py audit into an actionable cleanup plan that preserves the existing 160 passing datetime tests while removing duplication, improving documentation, and covering uncovered edge cases.
2. **Summary of recent work** – Logged 12 action items with priority; baseline tests confirmed for datetime helpers across five timezones and loop detection edge cases identified; template copy placed in `docs/in-process/` per policy.
3. **Next steps (short term)** – Add docstrings/type hints in the most-exposed helpers, remove the dead `DEBUG` flags and move logging to lazy statements, and draft the new async-friendly label helper.
4. **Risks / blockers** – Need consensus on changing `get_friendly_label` signature to async (impacts callers); ensure `MAX_DATE_CALCULATION_ITERATIONS` constant change is reflected everywhere.
5. **References** – Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), architecture overview (`docs/ARCHITECTURE.md`), and kc_helpers code review baseline (`docs/archive/KC_HELPERS_CODE_REVIEW_LEGACY.md`).
6. **Decisions & completion check**
   - **Decisions captured**: Keep documented decision to maintain helper coverage before refactor; adopt the generic entity lookup plus convenience wrappers; treat label registry as async-only.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Stabilize helpers

- **Goal**: Address the critical issues flagged in the original code review so the core helpers remain trustworthy during the Phase 4 calendar refactor.
- **Steps / detailed work items**
  1. Add missing docstrings and precise type hints to the public helpers listed (docstring gap for 11 functions, especially ID lookups and parse helpers, plus explicit `HomeAssistant` typing).
  2. Remove every `DEBUG = False` block, keep only lazy `const.LOGGER.debug` statements for high-value locations, and ensure log messages use Home Assistant standards (no manual prefixes).
  3. Fix loop detection logic (PERIOD_MONTH_END and similar) by guaranteeing each iteration strictly advances (test coverage addition + `MAX_DATE_CALCULATION_ITERATIONS` constant in `const.py`).
- **Key issues**
  - Document any decisions that expand loop detection increments beyond 1 hour (e.g., day-based step for end-of-period cases).
  - Track whether the JSON logging cleanup requires release-note mention (should not surface to end users).

### Phase 2 – DRY and performance

- **Goal**: Transform duplicated helpers into reusable constructs while minimizing cost for frequent label lookups.
- **Steps / detailed work items**
  1. Replace the eight `get_*_id_by_name` helpers with a generic `get_entity_id_by_name` plus thin wrappers; update existing callers and keep logging for invalid entity types.
  2. Centralize magic constants (`MAX_DATE_CALCULATION_ITERATIONS`, retention defaults) in `const.py` and reduce sprinkling of raw numbers/comments.
  3. Convert `get_friendly_label` into an `async` helper, guard with try/except, and ensure any new async call sites are updated or use helper plus caching.
  4. Reorganize kc_helpers sections with visible separators (authorization, lookup, datetime, progress, dashboard) so future readers quickly find logic.
- **Key issues**
  - Ensure new generic lookup function logs errors once per invalid input rather than raising, and document the decision for convenience wrappers.
  - Identify callers of `get_friendly_label` that may now run inside sync contexts and plan transitional wrappers if necessary.

### Phase 3 – Tests & documentation

- **Goal**: Cover all the missing scenarios noted (loop detection edge cases, authorization, lookup, progress, dashboard translations) and tidy the documentation.
- **Steps / detailed work items**
  1. Write new pytest files covering loop detection (month/year end + large deltas), authorization helpers (global action, kid-level permissions), and duplicate name lookups.
  2. Add tests for `get_today_chore_completion_progress`/`get_today_chore_and_point_progress` plus translation helpers (`get_available_dashboard_languages`, `load_dashboard_translation`).
  3. Document the reorganized sections in the helper file, highlight new constants, and update any architecture notes referencing kc_helpers (per Decision #1 in summary).
- **Key issues**
  - Decide whether additional fixtures are needed to simulate label registry errors for the new async label helper.
  - Align new tests with existing baseline of 160 timezone tests to avoid regressions.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed: 160 existing datetime-focused tests across 5 global timezones (baseline noted in legacy review).
- Outstanding tests: Edge cases in loop detection (PERIOD_MONTH_END/YEAR_END with `require_future`), authorization helpers, entity lookup duplicates, progress calculators, dashboard translation helpers.
- Links to failing logs or CI runs: TBD (no failing runs yet; list any as soon as open). Provide future PR IDs when tests land.

## Notes & follow-up

- Additional context: Estimated LOC reduction ~94 (DEBUG removal, DRY lookup, cleanup); maintainers noted the helper suite is already high quality (good type hints, lazy logging) so cleanup focus is low risk.
- Follow-up tasks: Update architecture docs to mention `get_entity_id_by_name` and new async label helper; confirm that agents use this plan and not the legacy review document.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` (already done) with the suffix `_IN-PROCESS`. Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
