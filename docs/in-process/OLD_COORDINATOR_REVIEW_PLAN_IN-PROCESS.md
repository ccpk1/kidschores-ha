# COORDINATOR_REVIEW_PLAN

## Initiative snapshot

- **Name / Code**: Coordinator audit & refactor
- **Target release / milestone**: v0.5.0 (with Phase 5/6 impact)
- **Owner / driver(s)**: @triage / coordinator engineering squad
- **Status**: In progress (Phase 5 awaiting test expansion)

## Summary & immediate steps

| Phase / Step                                          | Description                                                                                                          | % complete | Quick notes                                                                                                                                            |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 1 – Automated quality baseline                  | Establish lint/test baseline, capture artifacts, and document drift                                                  | 100%       | Baseline commands (lint/tests) reproducible via commit ef93b6cc...; summary table and Phase 1 artifacts captured in the legacy review                  |
| Phase 2 – Critical issue triage & fix readiness       | Convert badge/migration findings into seven GH issues (KC-COORD-001→007) with severity, effort, owners, and blockers | 60%        | Issues documented plus estimated hours; KC-COORD-001/002/003 prioritized before release                                                                |
| Phase 3 – Test expansion & architecture documentation | Implement 127+ tests (badge, migration, integration) and formalize architecture/ADRs around coordinator workflows    | 10%        | TEST_PLAN_COORDINATOR_REFACTORING_COMPLETE.md defines suites 1-3, success criteria, and the 5-week roadmap; blocked until KC-COORD-002/003 fixes merge |

1. **Key objective** – Turn the 6-phase coordinator review into a living project plan: document baselines, triage issues, execute the 127+ test expansion, and update architecture references before v0.5.0 ships.
2. **Summary of recent work** – Phase 1 artifacts, status table, and critical issues table now exist; the improvements doc expanded to include reproducible commands, decision tracking, new test plan, and execution roadmap.
3. **Next steps (short term)** – Assign owners to KC-COORD-002/003, apply fixes + tests, and start badge/migration test skeletons as outlined in `docs/completed/TEST_PLAN_COORDINATOR_REFACTORING_COMPLETE.md`.
4. **Risks / blockers** – KC-COORD-002/003 must merge before the test suite can cover the new scenarios; badge telemetry/performance fixes (KC-COORD-006/007) still depend on final spec.
5. **References** – Agent testing instructions (`tests/TESTING_AGENT_INSTRUCTIONS.md`), architecture overview (`docs/ARCHITECTURE.md`), legacy audit source (`docs/archive/COORDINATOR_CODE_REVIEW_LEGACY.md`), and the test plan (`docs/completed/TEST_PLAN_COORDINATOR_REFACTORING_COMPLETE.md`).
6. **Decisions & completion check**
   - **Decisions captured**: Keep Phase 1+2 results as the audit baseline; create KC-COORD issues (001-007) with severity and effort; anchor Phase 5 tests to the badge/migration/integration suites; record architecture documentation deliverables for Phase 6 before completion.
   - **Completion confirmation**: `[ ]` All follow-up items completed (critical fixes merged, test plan executed, architecture notes updated, release owner approval) before requesting sign-off to move to completed.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Automated quality baseline

- **Goal**: Capture coordinator lint/test baseline and ensure reproducibility for future reviewers.
- **Steps / detailed work items**
  1. Run `./utils/quick_lint.sh --fix` and `python -m pytest tests/ -q --tb=no` on commit `ef93b6cc1ef4d44415cf432c3d63f5cac9427c96` and record logs in Phase 1 artifacts.
  2. Document lint score (9.40/10) and coordinator coverage (39%) plus the implementation commands in the legacy review artifact section.
  3. Capture phase closure criteria (baseline metrics, artifact links) and mark Phase 1 complete in the status table.
- **Key issues**
  - None; closure criteria satisfied (lint/test baseline documented, artifacts reproducible).

### Phase 2 – Critical issue triage & fix readiness

- **Goal**: Convert Phase 3-4 findings into 7 executable KC-COORD issues so we can assign owners and verify fixes prior to Phase 5 testing.
- **Steps / detailed work items**
  1. Track KC-COORD-001 through KC-COORD-007 with severity, estimated effort, priority (RED for v0.5.0 blockers, green for later), and placeholders for PR/owner.
  2. Document root cause/code snippets and proposed fixes for each issue so engineers can implement them deterministically (e.g., badge coverage, incomplete migration, period stats merge, orphan IDs, migration order, badge maintenance perf, handler duplication).
  3. Surface the dependencies for KC-COORD-002/003 (datetime & period stats migrations) that gate the Phase 5 test suite; log blockers in the summary table.
- **Key issues**
  - KC-COORD-001: Zero badge test coverage; plan 80+ badge system tests (Suite 1).
  - KC-COORD-002: Datetime migrations missing conversions; fix ensures str/datetime inputs become UTC-aware.
  - KC-COORD-003: Period stats migration skipping filled periods; fix merges legacy data without dropping history.
  - KC-COORD-004/005/006/007: Orphan IDs, migration order, badge maintenance perf, handler duplication (lower priority but part of same effort wave).

### Phase 3 – Test expansion & architecture documentation

- **Goal**: Implement 127+ tests (badge, migration, integration) and formalize architecture coverage (flow diagrams, ADRs) before closing the initiative.
- **Steps / detailed work items**
  1. Follow `docs/completed/TEST_PLAN_COORDINATOR_REFACTORING_COMPLETE.md`—Suite 1 (80+ badge tests), Suite 2 (27 migration tests), Suite 3 (15+ integration tests plus TAGGED stress tests); track progress per suite and update percentages in this plan.
  2. Align each KC-COORD issue with specific test coverage (e.g., KC-COORD-001 via Suite 1 test set, KC-COORD-004 via Suite 2-B5/2-E2) so completion criteria are measurable.
  3. Draft Phase 6 deliverables: architecture diagrams (badge lifecycle, chore lifecycle, recurring resets), updated `ARCHITECTURE.md` sections, and ADRs documenting decisions captured here (migration ordering, badge handling refactors).
- **Key issues**
  - Blocked by KC-COORD-002/003 until fixes merge so tests operate on clean data; note dependency in status table and issue entries.
  - Track performance/stress scenarios (Suite 1-F) for KC-COORD-006 to ensure daily badge maintenance short-circuits when idle.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed: Baseline lint + pytest commands from Phase 1 (referenced by command list and commit `ef93b6cc1ef4d44415cf432c3d63f5cac9427c96`).
- Outstanding tests: 80+ badge scenarios, 27 migration scenarios, 15+ integration/stress scenarios defined in `TEST_PLAN_COORDINATOR_REFACTORING_COMPLETE.md`; additional coverage for KC-COORD-004/005/007 once code fixes land.
- Links to failing logs or CI runs: None yet; capture per-suite logs when Phase 5 tests are added.

## Notes & follow-up

- Additional context: Legacy documents now archived (`docs/archive/COORDINATOR_CODE_REVIEW_LEGACY.md`, `docs/archive/COORDINATOR_REVIEW_IMPROVEMENTS_LEGACY.md`); this plan consolidates the actionable content.
- Follow-up tasks: Update `ARCHITECTURE.md` with chore + badge workflows after Phase 6; place ADRs for migration order and badge handler refactor; ensure owner sign-off includes final coverage numbers and architecture updates before marking `[ ]` completion checkbox.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS`. Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
