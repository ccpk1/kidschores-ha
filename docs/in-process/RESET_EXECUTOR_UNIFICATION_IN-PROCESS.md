## Initiative snapshot

- **Name / Code**: Reset executor unification (`RESET-UNIFY-2026`)
- **Target release / milestone**: `v0.5.0-beta4` hardening window (pre-merge refactor)
- **Owner / driver(s)**: KidsChores integration maintainers (Builder lane)
- **Status**: Not started

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Policy extraction | Extract reset decision policy into shared helpers | 0% | No behavior change |
| Phase 2 – Executor extraction | Build unified reset action executor | 0% | No trigger rewiring yet |
| Phase 3 – Approval lane migration | Route approve-time reset through executor | 0% | Preserve immediate reset semantics |
| Phase 4 – Timer lane migration | Route periodic boundary resets through executor | 0% | Preserve scan batching + boundary rules |
| Phase 5 – Cleanup + parity hardening | Remove duplicates and lock parity tests | 0% | Ensure no drift between lanes |

1. **Key objective** – Keep dual triggers (approval vs timer boundary) but converge effects into a single reset execution path in `chore_manager.py`.
2. **Summary of recent work**
   - Mapped approval reset path in `approve_chore/_approve_chore_locked` and timer reset path in `_process_approval_reset_entries`.
   - Identified common effect primitives already present: `_transition_chore_state`, `_reschedule_chore_due`, and persist/update flow.
3. **Next steps (short term)**
   - Define reset context + decision enums.
   - Extract pure policy function with exhaustive test table.
   - Add no-behavior-change scaffolding behind existing call sites.
4. **Risks / blockers**
   - Trigger-specific behaviors (pending-claim boundary actions, missed/rotation midnight semantics) can be lost if flattened too early.
   - Reschedule timing can alter display state (`pending` vs `due`) and create false regressions if parity assertions are not explicit.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep dual trigger lanes; unify only policy/execution core.
     - Timer-only semantics remain policy inputs (not duplicated side-effect code).
     - Parity tests must compare lane outcomes for identical contexts.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each phase lands.
- **Detailed tracking**: Keep implementation specifics in phase sections; summary remains high level.

## Detailed phase tracking

### Phase 1 – Policy extraction

- **Goal**: Extract shared reset decision policy from approval and timer paths into pure helper(s), with no behavior changes.
- **Steps / detailed work items**
  - [ ] Create `ResetTrigger` and `ResetDecision` primitives (enum-like constants or typed literals).
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Line hints: around approval logic (`~929-1025`) and timer category selection (`~1884-2065`)
  - [ ] Add `build_reset_context(...)` data carrier (TypedDict/dataclass) that captures only policy inputs.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Include: trigger source, completion criteria, current state, pending claim flags, overdue handling, approval reset type, pending claim action, due-date relation.
  - [ ] Add `decide_reset_action(context)` pure function returning one of:
    - `hold`, `reset_only`, `reset_and_reschedule`, `auto_approve_pending`
    - File: `custom_components/kidschores/managers/chore_manager.py`
  - [ ] Replace inline decision branches in `_approve_chore_locked` and `_process_approval_reset_entries` with calls to policy function while preserving existing side effects in-place.
    - Files: `custom_components/kidschores/managers/chore_manager.py`
    - Line hints: approval block `~929-1025`; timer processing `~1884-2065`
  - [ ] Add table-driven policy tests for all approval reset / overdue handling / pending action combinations.
    - File: `tests/test_chore_scheduling.py` (or new focused policy test module)
- **Key issues**
  - Must preserve exact allowed/invalid combinations currently enforced by flow validation.
  - Avoid hidden behavior changes in SHARED_FIRST / rotation modes.

### Phase 2 – Executor extraction

- **Goal**: Build a single side-effect executor that applies decisions consistently.
- **Steps / detailed work items**
  - [ ] Add `apply_reset_action(context, decision)` that centrally performs:
    - state transition to pending,
    - ownership clearing,
    - approval period reset behavior,
    - optional reschedule.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Reuse primitives: `_transition_chore_state` (`~3450+`), `_reschedule_chore_due` (`~4492+`)
  - [ ] Add `finalize_reset(context)` for persist/update/emit ordering.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Ensure compliance with `Persist → Emit` standards.
  - [ ] Keep old code paths active but call executor for a subset (feature-flag or controlled branch) to verify parity.
  - [ ] Add focused tests ensuring executor leaves raw invariants intact (approved cleared, pending count behavior, overdue cleared where expected).
    - File: `tests/test_approval_reset_overdue_interaction.py`
- **Key issues**
  - Do not duplicate persistence inside nested call paths.
  - Ensure no double reschedule calls occur in mixed branches.

### Phase 3 – Approval lane migration

- **Goal**: Route approve-time immediate reset path to the unified executor.
- **Steps / detailed work items**
  - [ ] Migrate UPON_COMPLETION + immediate_on_late branches in `_approve_chore_locked` to context+decision+executor flow.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Line hints: `~929-1025`
  - [ ] Preserve completion-criteria distinctions:
    - INDEPENDENT single-kid reset/reschedule,
    - SHARED/SHARED_FIRST all-kids-gated reset.
  - [ ] Ensure non-recurring guard behavior remains exact (clearing past due date where applicable).
  - [ ] Add lane parity tests for same config driven via approval trigger.
    - File: `tests/test_workflow_chores.py`
- **Key issues**
  - Shared chore approval period reset timing must remain unchanged.
  - Notification/economy signals must remain in current sequence.

### Phase 4 – Timer lane migration

- **Goal**: Route periodic boundary processing to same executor while preserving batch efficiency.
- **Steps / detailed work items**
  - [ ] Migrate `_process_approval_reset_entries` to build per-entry contexts and call shared decision/executor.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Line hints: `~1884-2065`
  - [ ] Keep scanner batching (`process_time_checks`) and category partitioning untouched.
    - File: `custom_components/kidschores/managers/chore_manager.py`
    - Line hints: `~1435-1755`
  - [ ] Preserve timer-only semantics as context flags:
    - pending-claim boundary actions,
    - missed lock clear at midnight,
    - rotation advance on boundary.
  - [ ] Add paired-lane parity tests where one test uses approval trigger and paired test uses periodic/midnight trigger with equivalent context.
    - Files: `tests/test_workflow_chores.py`, `tests/test_chore_scheduling.py`
- **Key issues**
  - Avoid accidental per-kid vs chore-level reset cross-talk.
  - Guard against doubled events from batched processing.

### Phase 5 – Cleanup + parity hardening

- **Goal**: Remove duplicate legacy branches and lock down invariants against drift.
- **Steps / detailed work items**
  - [ ] Remove obsolete inline reset branches now superseded by unified executor.
    - File: `custom_components/kidschores/managers/chore_manager.py`
  - [ ] Add/expand parity assertions for sensor and dashboard helper outcomes.
    - Files: `tests/test_workflow_chores.py`, `tests/test_approval_reset_overdue_interaction.py`
  - [ ] Add regression checks for rotation and boundary interactions.
    - File: `tests/test_rotation_fsm_states.py`
  - [ ] Run quality gates and collect before/after evidence.
    - Commands:
      - `./utils/quick_lint.sh --fix`
      - `mypy custom_components/kidschores/`
      - `python -m pytest tests/test_workflow_chores.py -q --tb=line`
      - `python -m pytest tests/test_chore_scheduling.py -q --tb=line`
      - `python -m pytest tests/test_approval_reset_overdue_interaction.py -q --tb=line`
- **Key issues**
  - Must not regress event payload contracts.
  - Must not alter performance profile of periodic scan.

## Testing & validation

- **Baseline before refactor**
  - `tests/test_workflow_chores.py`
  - `tests/test_chore_scheduling.py`
  - `tests/test_approval_reset_overdue_interaction.py`
  - `tests/test_rotation_fsm_states.py`
- **Phase gates**
  - Phase 1-2: policy/executor unit + targeted workflow smoke
  - Phase 3-4: lane parity suite + affected file suites
  - Phase 5: full chore-focused regression set
- **Outstanding tests**
  - Add explicit parity matrix tests for same context across both triggers (new tests required).

## Notes & follow-up

- **Function signatures (proposed)**
  - `build_reset_context(*, trigger: str, kid_id: str, chore_id: str, chore_info: ChoreData, kid_chore_data: dict[str, Any], now_utc: datetime, derived_state: str | None = None) -> ResetContext`
  - `decide_reset_action(context: ResetContext) -> ResetDecision`
  - `apply_reset_action(context: ResetContext, decision: ResetDecision) -> ResetResult`
  - `finalize_reset(context: ResetContext, result: ResetResult) -> None`

- **Minimal Phase 1 skeleton (no behavior changes)**
  1. Introduce `ResetContext` + `ResetDecision` definitions.
  2. Implement `decide_reset_action(context)` by moving existing conditional branches verbatim.
  3. Keep current side-effect code in place; replace only condition evaluation with returned decision.
  4. Add parity tests proving no pre/post behavior change for sampled scenarios.

- **Handoff note**
  - This plan is implementation-ready for a builder and intentionally avoids production refactor in planning phase.
