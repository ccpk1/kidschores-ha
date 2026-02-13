# Initiative Plan: CHORE_LOGIC Phase 5 — Waiting Claim Path Reinstatement

## Initiative snapshot

- **Name / Code**: CHORE_LOGIC Phase 5 — Waiting Claim Path Reinstatement
- **Target release / milestone**: v0.5.0-beta4 follow-up patch (no schema bump)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                     | Description                                                  | % complete | Quick notes                                               |
| -------------------------------- | ------------------------------------------------------------ | ---------- | --------------------------------------------------------- |
| Phase 1 – Contract alignment     | Reconcile plan intent vs current code and docs               | 0%         | `waiting` state exists but P6 branch is removed in engine |
| Phase 2 – Core logic restoration | Re-enable due-window waiting path using existing fields      | 0%         | No new storage fields; derive from `due_window_offset`    |
| Phase 3 – Flow/service parity    | Keep create/update UX aligned with existing options/services | 0%         | No new form fields required                               |
| Phase 4 – Tests & validation     | Add focused regression tests around waiting/can-claim        | 0%         | Emphasize manager + engine + sensor `Lock_reason` contract |

1. **Key objective** – Reinstate Phase 5 “claim restriction before due window” behavior by using existing `due_window_offset` and current `can_claim` pipeline, returning `waiting` as a calculated lock state.
2. **Summary of recent work** – Audit confirms `CHORE_STATE_WAITING` is defined and translated, but `resolve_kid_chore_state()` currently has `P6 — [REMOVED]` and never emits `waiting`.
3. **Next steps (short term)** – Restore P6 logic in engine, normalize error-key handling for lock reasons, and add regression tests.
4. **Risks / blockers** – Existing tests may assume pre-window chores are plain `pending`; these must be updated intentionally.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md)
   - [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py)
   - [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py)
   - [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
   - [custom_components/kidschores/data_builders.py](../../custom_components/kidschores/data_builders.py)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep D-04 intent: claim restriction is derived from existing `due_window_offset` presence and due-window timing.
     - Do **not** add `claim_restriction_enabled` to storage constants/forms/services; existing `type_defs.py` optional key remains unused legacy typing and should not drive behavior.
     - Use existing pipeline only: `resolve_kid_chore_state()` → `can_claim_chore()` (engine) → `ChoreManager.can_claim_chore()` and `claim_chore()` guards.
     - Do **not** overload unrelated selectors (`approval_reset_type`, `completion_criteria`, `overdue_handling_type`) to encode claim restriction.
   - **Completion confirmation**: `[ ]` All follow-up items completed before requesting owner approval.

## Tracking expectations

- **Summary upkeep**: Update this plan table after each merged implementation/test pass.
- **Detailed tracking**: Keep architectural rationale in this plan; keep code/test details in PR notes.

## Detailed phase tracking

### Phase 1 – Contract alignment

- **Goal**: Remove ambiguity between blueprint intent and present implementation behavior.
- **Steps / detailed work items**
  1. - [ ] Update decision notes in [docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md#L229) to reflect actual implementation gap: `waiting` currently not emitted.
     - File: `docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md`
     - Hint: around current D-04 + Phase 5 sections (~L229, ~L608).
  2. - [ ] Add short architecture note in [docs/ARCHITECTURE.md](../ARCHITECTURE.md) under chore FSM section clarifying `waiting` is derived (not persisted) and gated by due-window math.
     - File: `docs/ARCHITECTURE.md`
     - Hint: chore state resolution / manager-engine boundaries section.
  3. - [ ] Add implementation guardrail note in [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md): avoid introducing dedicated claim-restriction field; use existing due-window field.
     - File: `docs/DEVELOPMENT_STANDARDS.md`
     - Hint: choreography/logic placement and no-duplication rules.
- **Key issues**
  - Existing plan docs imply feature complete while code path is disabled; this mismatch risks future regressions.

### Phase 2 – Core logic restoration

- **Goal**: Re-enable waiting lock in the engine and ensure all claim paths consume it.
- **Steps / detailed work items**
  1. - [ ] Restore P6 waiting branch in [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py#L680).
     - Replace removed placeholder with condition:
       - `due_window_start is not None`
       - `due_date is not None`
       - `now < due_window_start`
       - return `(CHORE_STATE_WAITING, "waiting")`
  2. - [ ] Ensure `can_claim_chore()` lock handling maps lock reasons to valid translation keys/messages.
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - If returning bare `"waiting"`, manager/service exception path must not degrade to generic `already_claimed`.
  3. - [ ] Align manager error propagation in [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py#L615) for lock reasons `waiting|not_my_turn|missed`.
     - Add explicit branch or translation mapping instead of falling through default error.
  4. - [ ] Verify read-path parity in [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py#L2948) and status-context path (~L3156) still uses same engine-derived state for both dashboard and claim validation.
  5. - [ ] Populate chore status sensor `Lock_reason` attribute from resolved lock context so waiting/claim locks are visible without inferring from state alone.
    - Files: `custom_components/kidschores/managers/chore_manager.py` (status context builder) and corresponding chore status sensor entity platform.
    - Rule: expose lock reason token (`waiting`, `not_my_turn`, `missed`, etc.) when locked; set `None` when claim is currently allowed.
- **Key issues**
  - Lock reason strings are state tokens, while exception paths currently prefer translation keys; mismatch can produce wrong user-facing error text.

### Phase 3 – Flow/service parity (no new fields)

- **Goal**: Keep UX/API stable while ensuring claim restriction behavior is controllable via existing fields only.
- **Steps / detailed work items**
  1. - [ ] Confirm [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L717) remains the sole UI path for due-window configuration (`chore_due_window_offset`).
  2. - [ ] Confirm [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L895) transform path maps due-window offset consistently for create/edit.
  3. - [ ] Confirm [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py#L357) `UPDATE_CHORE_SCHEMA` keeps `due_window_offset` mutable and does not introduce claim-restriction flags.
  4. - [ ] Remove/update stale comments indicating immutable criteria in [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py#L259) if still present, to avoid contradictory guidance.
- **Key issues**
  - API docs/comments can drift from behavior and mislead automation users.

### Phase 4 – Tests & validation

- **Goal**: Add focused test coverage proving waiting lock behavior and preventing silent removal in future refactors.
- **Steps / detailed work items**
  1. - [ ] Add engine-level tests in [tests/test_chore_engine.py](../../tests/test_chore_engine.py) for P6 waiting:
     - pre-window returns `(waiting, lock_reason=waiting)`;
     - in-window returns `due` or `pending` depending on due timing.
  2. - [ ] Add manager-level tests in [tests/test_chore_scheduling.py](../../tests/test_chore_scheduling.py#L2200) or a dedicated file to validate `can_claim_chore()` rejects before window and allows once window opens.
  3. - [ ] Add sensor/status contract checks in [tests/test_ui_manager.py](../../tests/test_ui_manager.py) or existing dashboard-helper tests to verify `lock_reason=waiting` and `available_at` when waiting.
  4. - [ ] Add chore status sensor attribute assertions verifying `Lock_reason` mirrors lock context across locked vs claimable states.
    - Target tests: existing chore status sensor tests (or add focused test file if missing coverage).
  5. - [ ] Run quality gates:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/test_chore_engine.py tests/test_chore_scheduling.py -v --tb=line`
     - `python -m pytest tests/ -v --tb=line` (final confidence run)
- **Key issues**
  - Some legacy tests may encode previous “pending-before-window” semantics and need intentional updates.

## Testing & validation

- **Planned tests**: Engine unit tests + manager scheduling behavior + sensor/dashboard helper lock attribute checks.
- **Outstanding tests**: Full suite run required after targeted tests pass.

## Notes & follow-up

- **Architecture recommendation (final)**: Re-implement Phase 5 using existing due-window signal (`due_window_offset`) and current can-claim path; do not overload other selectors and do not add storage fields.
- **Why this fits best**:
  - Preserves established manager/engine separation.
  - Avoids schema churn and migration complexity.
  - Keeps one source of truth for claimability (engine FSM + manager wrappers).
- **Future cleanup (optional, post-fix)**:
  - Remove `claim_restriction_enabled` from `ChoreData` `TypedDict` if confirmed permanently unused to reduce cognitive overhead (separate cleanup PR).
