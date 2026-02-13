# Initiative Plan: Chore UX Improvements

## Initiative snapshot

- **Name / Code**: CHORE_UX_IMPROVEMENTS
- **Target release / milestone**: v0.5.0-beta4 follow-up (post Phase 3 parity)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                        | Description                                                                | % complete | Quick notes                                              |
| ----------------------------------- | -------------------------------------------------------------------------- | ---------- | -------------------------------------------------------- |
| Phase 1 – UX inventory              | Baseline current chore add/edit forms and identify pain points             | 0%         | Long-scroll and mixed concern grouping are key blockers  |
| Phase 2 – Information architecture  | Define section model, field grouping, and canonical ordering               | 0%         | Keep behavior unchanged while improving discoverability  |
| Phase 3 – Field consolidation rules | Reduce redundant fields and define compatibility behavior                  | 0%         | Evaluate custom frequency + interval/unit simplification |
| Phase 4 – Delivery staging          | Implement UX changes in safe increments with translation and test coverage | 0%         | Stage to avoid regressions across config/options flows   |

1. **Key objective** – Improve chore add/edit UX by reducing form overload, introducing clear sectioning, and consolidating scheduling-related fields without breaking existing behavior.
2. **Summary of recent work** – Initiative split from chore-logic stream to prevent UX refactor scope from blocking claim-path fixes.
3. **Next steps (short term)** – Finalize section model and permanent placement for the new lock-claim toggle, then define migration-safe field consolidation sequence.
4. **Risks / blockers** – UX refactor touches shared schema used by both Config Flow and Options Flow; translation and service metadata drift risk is high without staged rollout.
5. **References** –
   - [docs/PLAN_TEMPLATE.md](../PLAN_TEMPLATE.md)
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/in-process/CHORE_LOGIC_PHASE5_WAITING_CLAIM_PATH_IN-PROCESS.md](CHORE_LOGIC_PHASE5_WAITING_CLAIM_PATH_IN-PROCESS.md)
   - [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
   - [custom_components/kidschores/config_flow.py](../../custom_components/kidschores/config_flow.py)
   - [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
   - [custom_components/kidschores/services.yaml](../../custom_components/kidschores/services.yaml)
   - [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep this initiative strictly UX/layout/field-model focused (separate from core FSM behavior changes).
     - Use one shared chore schema source as the primary implementation point.
     - Any field consolidation must preserve backward compatibility for stored data and services.
   - **Completion confirmation**: `[ ]` All follow-up items completed (layout, translations, validation, compatibility notes, tests) before owner approval.

> **Important:** Keep the Summary section current after every major scope or sequencing decision.

## Tracking expectations

- **Summary upkeep**: Update phase percentages and blockers after each design decision or implementation chunk.
- **Detailed tracking**: Keep all granular decisions in phase sections below; keep Summary high-level.

## Detailed phase tracking

### Phase 1 – UX inventory

- **Goal**: Build a factual baseline of current chore add/edit form structure and coupling points.
- **Steps / detailed work items**
  1. - [ ] Document current field order and grouping in the shared schema.
     - Files: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
  2. - [ ] Map Config Flow vs Options Flow usage differences and conditional fields.
     - Files: [custom_components/kidschores/config_flow.py](../../custom_components/kidschores/config_flow.py), [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
  3. - [ ] Capture current service/UI metadata parity gaps (fields exposed in runtime but missing in docs/translations).
     - Files: [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py), [custom_components/kidschores/services.yaml](../../custom_components/kidschores/services.yaml), [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
- **Key issues**
  - Shared schema changes have broad blast radius; baseline must be exact before refactor.

### Phase 2 – Information architecture

- **Goal**: Define a simpler mental model for chore setup with clear sections and ordering.
- **Steps / detailed work items**
  1. - [ ] Propose section model for chore forms (Identity, Schedule & Window, Rules & Automation, Notifications).
  2. - [ ] Define canonical field order within each section and apply consistently to add/edit flows.
  3. - [ ] Decide whether to adopt collapsible sections via data_entry_flow.section in this phase or stage for next pass.
     - If adopted, add section translation blocks in [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
- **Key issues**
  - Section adoption requires schema input-shape handling (nested section payloads).

### Phase 3 – Field consolidation rules

- **Goal**: Reduce form complexity by consolidating or reworking high-friction scheduling fields.
- **Steps / detailed work items**
  1. - [ ] Define final model for claim-window lock control (new toggle) with defaults preserving existing behavior.
  2. - [ ] Evaluate and decide consolidation path for custom frequency inputs (frequency variants vs separate interval/unit fields).
  3. - [ ] Produce compatibility matrix for existing stored chores and service payloads.
- **Key issues**
  - Consolidation can impact engine scheduling assumptions and test fixtures.

### Phase 4 – Delivery staging

- **Goal**: Execute UX improvements in low-risk increments with parity validation.
- **Steps / detailed work items**
  1. - [ ] Ship form reordering and section labels first (no behavior changes).
  2. - [ ] Ship new lock-claim toggle with default OFF and explicit helper text.
  3. - [ ] Ship field consolidation changes only after compatibility safeguards and tests are in place.
  4. - [ ] Validate translations and service metadata parity for each shipment.
- **Key issues**
  - Large one-shot UX changes are likely to regress options flow edit paths.

## Testing & validation

- Tests executed: Not started for this initiative.
- Outstanding tests:
  - Config flow chore creation and validation paths
  - Options flow add/edit chore paths
  - Service metadata parity (services.yaml and translations)
  - Regression checks for schedule behavior after field consolidation

## Notes & follow-up

- This initiative is intentionally separate from CHORE_LOGIC phase work to keep scope and risk manageable.
- Confirmed field decision:
  - Base key constant: CHORE_CLAIM_LOCK_UNTIL_WINDOW
  - Stored chore field: DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW
  - CFOF field: CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW
  - Label: Lock Claim Until Window Opens
  - Helper: If checked, kids cannot claim this chore until the due window begins.
  - Placement rule: place before Auto-Approve Claims in chore forms.
- Follow-up: apply this field consistently in service schema/metadata, flow transforms, and translation keys.
