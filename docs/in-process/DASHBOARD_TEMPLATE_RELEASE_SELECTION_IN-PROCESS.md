# Initiative Plan: Dashboard Template Release Selection

## Initiative snapshot

- **Name / Code**: Dashboard Template Release Selection (DASH-REL-SELECT-01)
- **Target release / milestone**: v0.5.0-beta5 (or next patch after beta4)
- **Owner / driver(s)**: KidsChores Team (Integration + Dashboard coordination)
- **Status**: Not started

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| ------------------------------ | ----------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| Phase 1 – Release policy | Define release-source rules, minimum supported tag, and fallback behavior | 0% | Must handle pre-releases and tag format differences safely |
| Phase 2 – Core resolver | Add GitHub release discovery + tag resolution + template URL construction | 0% | Keep local template fallback intact for reliability |
| Phase 3 – Options flow UX | Show selectable release list, default to newest compatible, allow override | 0% | Preserve create/update/delete clarity from recent UX cleanup |
| Phase 4 – Validation | Add focused tests and failure-mode checks | 0% | No dedicated dashboard generator tests currently cover release selection |

1. **Key objective** – Allow users to select dashboard template releases from the dashboard repo, default to the newest compatible release, and optionally enforce a minimum release floor.
2. **Summary of recent work**
   - Current template fetch path is style-only and points to a single hardcoded source (`main`) via `DASHBOARD_TEMPLATE_URL_PATTERN` in `custom_components/kidschores/const.py` (~line 125).
   - Template resolution entry point is `fetch_dashboard_template()` in `custom_components/kidschores/helpers/dashboard_builder.py` (~lines 70-110), with local fallback already implemented.
   - Dashboard create/update UX already supports explicit action routing in `custom_components/kidschores/options_flow.py` (~lines 3990-4170).
   - Existing translation blocks for dashboard forms are centralized in `custom_components/kidschores/translations/en.json` (~lines 1504-1555).
3. **Next steps (short term)**
   - [ ] Finalize release tag compatibility contract with dashboard repo owner (tag grammar + prerelease handling).
   - [ ] Implement resolver abstraction and wire into template fetch path.
   - [ ] Add release selector fields in create/update dashboard forms.
   - [ ] Add tests for newest-default, pinned selection, and minimum-version rejection.
4. **Risks / blockers**
   - GitHub API availability/rate limits may prevent release list fetch; graceful fallback behavior is mandatory.
   - Release tags may not strictly follow SemVer; parser must support current observed format (`KCD_v0.5.0_beta3`).
   - Integration and dashboard compatibility matrix can drift if minimum-floor rules are not explicit.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md)
   - [custom_components/kidschores/helpers/dashboard_builder.py](../../custom_components/kidschores/helpers/dashboard_builder.py)
   - [custom_components/kidschores/helpers/dashboard_helpers.py](../../custom_components/kidschores/helpers/dashboard_helpers.py)
   - [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
   - [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py)
   - [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Release source should be dashboard repo releases (not integration repo `main` branch) for deterministic template behavior.
     - Default behavior should auto-select newest compatible release to keep UX simple.
     - Users should have an explicit override to pin a release when needed.
     - A minimum compatible release floor should be enforced to prevent known-broken template generations.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

## Option presentation and allow/restrict policy

### User-facing controls (MVP)

| Control | Visible when | Allowed values | Restricted / blocked values | Default | User feedback |
| --- | --- | --- | --- | --- | --- |
| `release_mode` | Always (create + update) | `latest_compatible`, `pin_release` | None | `latest_compatible` | Short description under field |
| `release_tag` | Only when `release_mode = pin_release` | Tags returned by resolver and marked compatible | Any tag below minimum floor, malformed tags, missing assets | Newest compatible tag pre-selected | Inline error if selected tag becomes unavailable |
| `include_prereleases` | Optional advanced toggle (Phase 3) | `true`, `false` | If hidden, user cannot change | `true` during beta cycle | Helper text explains beta-default behavior |
| `minimum_release_override` | Not shown in MVP (operator-only follow-up) | N/A in MVP | All user overrides blocked in MVP | Integration constant | Info text: minimum is enforced automatically |

### Enforcement rules (authoritative)

1. **Always allow** `latest_compatible` mode, even when release API is down.
2. **Allow pinning only** to compatible tags from discovered list; no free-text tag entry in MVP.
3. **Restrict any release below floor** (example floor tied to beta compatibility), with deterministic fallback to newest compatible.
4. **Restrict malformed tags** from selector population (quietly excluded, debug logged).
5. **Restrict hard failure on remote outages**; system must degrade to local bundled templates.

### Compatibility gate algorithm (prevents incompatible picks)

1. Read installed integration version from [custom_components/kidschores/manifest.json](../../custom_components/kidschores/manifest.json) (`version`, currently `0.5.0b4`).
2. Build compatibility metadata for each dashboard release tag from one of these sources:
   - Primary: release metadata manifest (recommended follow-up in dashboard repo), or
   - MVP fallback: integration-side compatibility map constants keyed by tag pattern/range.
3. For each release candidate, evaluate:
   - `min_integration_version <= installed_integration_version`
   - optional `max_integration_version` if provided.
4. Only include passing releases in selector options.
5. If user has pinned a now-incompatible release, block that selection and auto-fallback to newest compatible.

Example policy for your case:
- Dashboard `KCD_v0.5.4` carries `min_integration_version = 0.5.2`.
- If installed integration is `0.5.1`, `KCD_v0.5.4` is excluded from the selector and cannot be chosen.
- If installed integration is `0.5.2+`, it appears and may be selected (or auto-selected if newest compatible).

### Compatibility metadata shape (proposed)

```text
release_tag: KCD_v0.5.4
min_integration_version: 0.5.2
max_integration_version: null
compatibility_note: Requires integration 0.5.2+
```

MVP implementation note:
- Until dashboard release assets expose metadata, enforce compatibility in integration constants as a temporary gate.
- Promote to release-embedded metadata once dashboard repo adopts compatibility manifests.

### UX response matrix

| Scenario | Behavior | Result copy expectation |
| --- | --- | --- |
| API reachable, compatible releases found | Show selector list; default newest compatible | “Using latest compatible release: {tag}” |
| User pins valid compatible release | Use pinned release | “Using pinned release: {tag}” |
| User pins tag that later disappears | Fallback to newest compatible | “Pinned release unavailable; used {fallback_tag}” |
| Only below-floor releases found | Reject remote set; use bundled local | “No compatible remote release found; used bundled template” |
| API timeout/rate-limit/network error | Skip remote selection; use bundled local | “Release service unavailable; used bundled template” |

### Recommended MVP decision

- **Choose hardcoded minimum floor (no user override) for v1**.
- **Reason**: prevents support complexity and avoids exposing users to known-bad combinations.
- **Follow-up**: Add advanced operator override only after telemetry/support confirms need.

### Phase 1 – Release policy and compatibility contract

- **Goal**: Define exactly which dashboard releases are selectable and how compatibility is enforced.
- **Steps / detailed work items**
  1. [ ] Define canonical tag parser contract and accepted formats
     - Files: `custom_components/kidschores/helpers/dashboard_builder.py` (~template fetching section), `custom_components/kidschores/const.py` (~dashboard constants)
     - Support at minimum:
       - `KCD_vX.Y.Z_betaN`
       - `KCD_vX.Y.Z`
     - Reject malformed tags without crashing flow.
  2. [ ] Add minimum compatible dashboard release constant(s)
     - File: `custom_components/kidschores/const.py` (~dashboard constants near lines 100-140)
     - Introduce constants (names TBD by builder) for floor tag and user-facing message key.
  3. [ ] Define prerelease policy (include/exclude toggle)
     - Files: `const.py`, `dashboard_helpers.py` (selector defaults)
     - Default recommendation: include prereleases while integration itself is beta.
  4. [ ] Document compatibility matrix source of truth
     - Files: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, optional short note in `README.md`
     - Clarify “integration version → minimum dashboard release” mapping.
- **Key issues**
  - Tag semantics are project-specific; strict SemVer parsing alone is insufficient.
  - Future naming changes in dashboard repo can break parsing unless guarded by fallback.

### Phase 2 – Release discovery and template resolution engine

- **Goal**: Resolve selected/default release to template URLs with robust fallback behavior.
- **Steps / detailed work items**
  1. [ ] Add release listing helper using GitHub Releases API
     - File: `custom_components/kidschores/helpers/dashboard_builder.py` (~new helper block near fetch functions)
     - Endpoint target: `ccpk1/kidschores-ha-dashboard` releases list.
  2. [ ] Implement release normalization + sort logic
     - File: `dashboard_builder.py`
     - Build deterministic “newest compatible” selection from fetched releases.
  3. [ ] Build release-aware template URL constructor
     - Files: `const.py` (URL patterns), `dashboard_builder.py`
     - Resolve templates from selected tag/ref instead of fixed `main` path.
  4. [ ] Preserve existing fallback chain
     - File: `dashboard_builder.py` (`fetch_dashboard_template`)
     - New order:
       1) Selected/newest compatible release template
       2) Fallback compatible release (if selected missing)
       3) Local bundled template
  5. [ ] Add structured diagnostics logging for release resolution
     - File: `dashboard_builder.py`
     - Log selected tag, fallback reason, and final source used (without sensitive data).
- **Key issues**
  - Rate limits for anonymous GitHub API calls; include timeout and “best effort” behavior.
  - Must not block dashboard generation when remote API is unavailable.

### Phase 3 – Options flow UX for release selection

- **Goal**: Expose release controls without reintroducing dashboard-flow complexity.
- **Steps / detailed work items**
  1. [ ] Add selector fields for template release strategy
     - File: `custom_components/kidschores/helpers/dashboard_helpers.py` (schema builders around lines 190-260)
     - Proposed controls:
       - `release_mode`: `latest_compatible` (default) / `pin_release`
       - `release_tag`: selectable when pinned mode chosen
  2. [ ] Add optional minimum release field policy
     - Files: `dashboard_helpers.py`, `options_flow.py`
     - Two allowed implementations (pick one in build):
       - **A (recommended)** hardcoded minimum in integration constants, surfaced as read-only info text.
       - **B** advanced override field for operators (validated, hidden behind advanced mode).
  3. [ ] Wire create/update steps to pass release selection through confirmation/execute path
     - File: `custom_components/kidschores/options_flow.py` (~lines 3990-4170 and confirm step)
     - Ensure update flow preserves existing non-selected views as currently implemented.
  4. [ ] Add translation keys and copy for new fields/errors
     - Files: `custom_components/kidschores/const.py` (~translation keys block), `custom_components/kidschores/translations/en.json` (~dashboard sections and selector options)
  5. [ ] Add clear user-facing fallback messaging
     - File: `options_flow.py` result step and/or errors
     - Example behavior: “Selected release unavailable; used newest compatible release X” or “Used bundled template fallback”.
- **Key issues**
  - Release list fetch can be slow; avoid introducing latency that makes options flow feel stalled.
  - Must keep current create/update/delete intent model simple.

### Phase 4 – Testing and release-readiness validation

- **Goal**: Prevent regressions and guarantee safe fallback behavior under failure modes.
- **Steps / detailed work items**
  1. [ ] Add resolver unit tests
     - File: `tests/test_dashboard_template_release_resolution.py` (new)
     - Cases:
       - Newest compatible selection from mixed tags
       - Pinning exact tag
       - Floor rejection for too-old tags
       - Malformed tag ignore behavior
  2. [ ] Add options flow tests for release fields and defaults
     - File: `tests/test_options_flow_dashboard_release_selection.py` (new)
     - Cases:
       - Default `latest_compatible`
       - Pinned flow with selected release
       - Release fetch failure fallback messaging
  3. [ ] Add integration-level fetch fallback tests
     - File: `tests/test_dashboard_builder_release_fetch.py` (new)
     - Cases:
       - API timeout → local fallback
       - Selected tag missing template file → fallback release/local path
  4. [ ] Validate translation completeness for new keys
     - File: `custom_components/kidschores/translations/en.json`
     - Ensure no orphan keys and correct selector mapping.
  5. [ ] Execute standard quality gates (builder execution)
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Existing environment may still show unrelated mypy parse blocker in `core`; isolate dashboard tests first.
  - GitHub API interactions should be mocked to keep tests deterministic.

## Testing & validation

- Tests executed: Planning-only task (no code implementation).
- Outstanding tests (not run and why): All implementation tests pending builder execution after code changes.
- Links to failing logs or CI runs if relevant: N/A for planning-only deliverable.

## Notes & follow-up

- **Recommended product behavior (MVP)**:
  - Default to `latest_compatible` release.
  - Expose optional `pin_release` selector for advanced users.
  - Enforce one integration-defined minimum release floor.
  - Keep local templates as final safety net.
- **No storage schema migration expected** for MVP if release preference remains flow-scoped or stored in existing options fields.
- If long-term persistence per-dashboard is desired, create a follow-up initiative for persistent release pinning metadata.

### Worst-case recovery guarantee

- If remote release resolution fails, dashboard generation must still work from bundled templates shipped inside the integration package (`custom_components/kidschores/templates/`).
- If a user reinstalls/redownloads the integration, those bundled templates are restored to the versions included with that integration build.
- Operational caveat: existing already-generated Lovelace dashboards are stored configs; they are not automatically rewritten on reinstall.
- Recovery action for operators: rerun Dashboard Create/Update flow after reinstall to regenerate views from restored bundled templates.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
