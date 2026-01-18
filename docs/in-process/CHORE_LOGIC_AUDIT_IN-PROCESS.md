# Chore Logic Comprehensive Audit & Gap Remediation

## Initiative snapshot

- **Name / Code**: Chore Logic Audit & Gap Remediation (CLAG)
- **Target release / milestone**: v0.5.1 (post-parent-chores merge)
- **Owner / driver(s)**: Integration maintainer + Builder agent
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                  | Description                                                     | % complete | Quick notes                                       |
| ----------------------------- | --------------------------------------------------------------- | ---------- | ------------------------------------------------- |
| Phase 1 – Gap Investigation   | Deep-dive Gap 6 (SHARED + UPON_COMPLETION), validate other gaps | 0%         | Critical: User's fix may break SHARED chores      |
| Phase 2 – Logic Path Audit    | Map all chore processing paths, identify missing edge cases     | 0%         | Create comprehensive matrix + flowcharts          |
| Phase 3 – Architecture Review | Analyze refactor to separate ChoreHandler class                 | 0%         | Coordinator at 8987 lines - complexity threshold? |
| Phase 4 – Remediation         | Fix confirmed gaps, add validation, optimize                    | 0%         | Depends on Phase 1-3 findings                     |
| Phase 5 – Documentation       | Update wiki, add diagrams, create behavior matrix               | 0%         | Behavior matrix, decision trees, edge case guide  |
| Phase 6 – Testing             | Comprehensive test coverage for all identified paths            | 0%         | Target 95%+ coverage for chore logic              |

### Key objective

Conduct comprehensive audit of chore approval/reset/overdue logic to:

1. Validate user's recent fixes don't introduce regressions (especially SHARED chores)
2. Identify all edge cases and gaps in current implementation
3. Create complete documentation of all chore processing paths
4. Determine if chore handling should be refactored into separate class
5. Implement fixes for confirmed gaps with full test coverage

### Summary of recent work

- **Gap identification completed** (Jan 18): Deep analysis identified 6 gaps in approval handling
- **User fixes applied** (pre-audit): Two fixes for UPON_COMPLETION + FREQUENCY_NONE bugs
- **Critical finding**: User's fix (coordinator.py lines 3583-3606) may break SHARED + UPON_COMPLETION by resetting all kids to PENDING before all_approved check runs
- **Documentation created**: Decision tree flowchart, 40-row behavior matrix, gap severity ratings

### Next steps (short term)

1. **Immediate**: Investigate Gap 6 (SHARED + UPON_COMPLETION interaction) - HIGH PRIORITY
2. Create test case to validate SHARED chore behavior with user's fix applied
3. Map complete chore processing logic paths across all coordinator methods
4. Build comprehensive configuration matrix (5 approval × 4 overdue × 8 frequency × 3 completion = 480 combinations)
5. Analyze coordinator.py complexity metrics for refactor justification

### Risks / blockers

- **Critical**: Gap 6 may require rollback or modification of user's fix (blocking release)
- **Medium**: Full logic audit may reveal additional gaps requiring extensive testing
- **Low**: Refactor to separate class could introduce regressions if not carefully planned
- **Dependency**: Parent chores feature must be stable before refactor
- **Timeline**: Comprehensive testing may delay v0.5.1 if significant issues found

### References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, storage schema
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Code patterns, naming
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Quality standards
- [AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md) - Test scenarios
- **Supporting docs** (this initiative):
  - [CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md](CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md) - Detailed gap documentation
  - [CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md](CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md) - Complete configuration matrix
  - [CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md](CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md) - Class extraction analysis

### Decisions & completion check

- **Decisions captured**:
  - [ ] Gap 6 confirmed as bug or false positive
  - [ ] User's fix requires modification or is safe as-is
  - [ ] Refactor to ChoreHandler class approved or deferred
  - [ ] Validation enhancements prioritized (warnings vs errors)
  - [ ] Optimization approach selected (single-chore check vs current full scan)
  - [ ] Documentation format finalized (Mermaid diagrams vs tables vs both)
- **Completion confirmation**:
  - [ ] All 6 identified gaps resolved or documented as design decisions
  - [ ] Complete logic path audit conducted with findings documented
  - [ ] All configuration combinations tested (or exempted with justification)
  - [ ] Architecture decision made on ChoreHandler class refactor
  - [ ] Comprehensive documentation added to wiki
  - [ ] Test coverage ≥95% for chore approval/reset/overdue logic
  - [ ] Release blocker status confirmed (v0.5.1 or later)
  - [ ] Owner approval obtained before marking complete

---

## Tracking expectations

- **Summary upkeep**: Builder agent or maintainer updates Summary section after each phase completion, Gap 6 investigation results, or blocker changes
- **Detailed tracking**: Use phase sections below for granular progress - keep Summary high-level only

---

## Detailed phase tracking

### Phase 1 – Gap Investigation

**Goal**: Validate all 6 identified gaps, prioritize by severity, determine if user's fixes introduce regressions

**Steps / detailed work items**:

1. **Gap 6 - SHARED + UPON_COMPLETION interaction** (CRITICAL - 🚨)
   - [ ] Trace code flow: approve_chore() lines 3583-3606 (user's fix) → lines 3503-3526 (SHARED check)
   - [ ] Identify race condition: Do all kids reset to PENDING before all_approved check?
   - [ ] Test scenario: SHARED chore, 2 kids, upon_completion, approve kid 1 → does kid 2 auto-reset?
   - [ ] File: `tests/test_gap6_shared_upon_completion.py` (create new test file)
   - [ ] Validate: `pytest tests/test_gap6_shared_upon_completion.py -v`
   - [ ] Decision: Fix required? Rollback user's fix? Modify logic for SHARED vs INDEPENDENT?
   - **Blocker**: Must resolve before v0.5.1 release if confirmed bug

2. **Gap 1 & 2 - User's fixes validation** (RESOLVED but verify)
   - [ ] Verify UPON_COMPLETION + FREQUENCY_NONE immediately resets to PENDING
   - [ ] Verify overdue check runs after immediate reset
   - [ ] Verify midnight reset skips FREQUENCY*NONE (unless AT_MIDNIGHT*\*)
   - [ ] Test: Use existing `test_workflow_*.py` scenarios
   - [ ] Confirm: No regressions in INDEPENDENT chore behavior

3. **Gap 3 - AT*DUE_DATE*\* + FREQUENCY_NONE behavior** (DESIGN QUESTION - ⚠️)
   - [ ] Document current behavior: Manual reset only (no auto-trigger)
   - [ ] Search codebase: `grep -r "AT_DUE_DATE" custom_components/kidschores/`
   - [ ] Identify: Does \_reset_daily_chore_statuses() or any timer trigger these?
   - [ ] Decision: Is this intended behavior or missing feature?
   - [ ] Option A: Add timer-based check for AT_DUE_DATE_ONCE/MULTI reaching due date
   - [ ] Option B: Document as "manual reset only" with UI warning
   - [ ] Owner decision required

4. **Gap 4 - Validation warnings missing** (LOW PRIORITY - 📝)
   - [ ] List unsupported combinations: AT*DUE_DATE*\* + FREQUENCY_NONE, etc.
   - [ ] Review flow_helpers.py lines 1217-1232 (existing validation)
   - [ ] Add info/warning messages for surprising behaviors
   - [ ] Update config flow to show warnings (not errors - allow but inform)
   - [ ] File: `custom_components/kidschores/flow_helpers.py`

5. **Gap 5 - Optimization: Full overdue scan** (OPTIMIZATION - 🔧)
   - [ ] Profile performance: How expensive is \_check_overdue_chores() full scan?
   - [ ] Measure: Add timing logs in approve_chore() before/after overdue check
   - [ ] Analyze: 10 kids × 20 chores = 200 chore checks vs 1 chore check
   - [ ] Decision: Create \_check_overdue_for_single_chore(chore_id) method?
   - [ ] Trade-off: Code complexity vs performance gain (likely minimal for <100 chores)
   - [ ] Defer to v0.6.0 unless profiling shows significant impact

**Key issues**:

- Gap 6 is **release blocker** if confirmed - must investigate immediately
- Gap 3 requires **owner decision** on intended behavior (auto-reset vs manual)
- User's fixes (Gap 1 & 2) may conflict with SHARED chores (Gap 6)
- Test scenarios must cover SHARED + UPON_COMPLETION + FREQUENCY_NONE edge case

---

### Phase 2 – Logic Path Audit

**Goal**: Map all chore processing paths, identify missing edge cases, create comprehensive configuration matrix

**Steps / detailed work items**:

1. **Audit all approval-related methods**
   - [ ] Map method call chains: approve*chore() → \_reschedule*_ → *check_overdue*_
   - [ ] File: `custom_components/kidschores/coordinator.py` lines 3138-3598 (approve_chore)
   - [ ] File: Lines 10023-10232 (\_reschedule_chore_next_due_date + per_kid variant)
   - [ ] File: Lines 9099-9195 (\_check_overdue_chores)
   - [ ] File: Lines 8945-9024 (\_check_overdue_for_chore)
   - [ ] Tool: Create flowchart showing all method calls and decision points

2. **Audit reset mechanisms**
   - [ ] Midnight reset: \_reset_daily_chore_statuses() lines 9488-9530
   - [ ] Due date reset: \_reschedule_chore_next_due_date() lines 10062-10089
   - [ ] Manual reset: Via config flow or button entity (trace from button.py)
   - [ ] Identify: Which reset types trigger which methods?
   - [ ] Map: approval_reset_type constants to reset trigger points

3. **Audit overdue mechanisms**
   - [ ] Scheduled check: \_check_overdue_chores() called from where? (grep for usage)
   - [ ] Approval-triggered: Lines 3583-3606 in approve_chore() (user's fix)
   - [ ] Reschedule-triggered: Check if _reschedule_\* methods call overdue check
   - [ ] Identify: overdue_handling_type impact on each path
   - [ ] Map: Which configurations skip overdue checks vs apply immediately

4. **Create comprehensive configuration matrix**
   - [ ] Dimensions: 5 approval_reset × 4 overdue_handling × 8 frequency × 3 completion_criteria = 480 combinations
   - [ ] Filter invalid: Use flow_helpers.py validation rules to exclude impossible combinations
   - [ ] Categorize: Group into logical behavior classes (e.g., "auto-reschedule", "manual-only", "hybrid")
   - [ ] Test coverage: Identify which combinations have test coverage (grep test files)
   - [ ] Output: Supporting doc `CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md`

5. **Identify logic gaps**
   - [ ] Edge case: SHARED chore, partial approval, upon_completion reset
   - [ ] Edge case: FREQUENCY_NONE with recurring chore patterns (custom_from_complete?)
   - [ ] Edge case: Overdue cleared at midnight vs cleared immediately on late approval
   - [ ] Edge case: Multi-claim chores (daily_multi) with approval resets
   - [ ] Edge case: Parent-assigned chores with kid approval workflow
   - [ ] Document: All edge cases in supporting doc with severity rating

6. **Analyze FREQUENCY_NONE special handling**
   - [ ] Method: \_calculate_next_due_date_from_info() lines 9909-9912 (returns None)
   - [ ] Impact: No auto-reschedule possible for non-recurring chores
   - [ ] Trace: How does each reset type handle None return from calculator?
   - [ ] Validate: All approval_reset_type options work correctly with FREQUENCY_NONE
   - [ ] Test: Create test matrix for 5 reset types × FREQUENCY_NONE

**Key issues**:

- 480 total combinations - need systematic approach to test/validate all
- SHARED chores add complexity (multi-kid coordination)
- Parent-assigned chores may interact unexpectedly with approval workflows
- Missing edge case testing could cause future bugs

---

### Phase 3 – Architecture Review

**Goal**: Analyze if chore handling should be refactored into separate ChoreHandler class

**Steps / detailed work items**:

1. **Measure coordinator.py complexity**
   - [ ] Line count: Currently 8987 lines (use `wc -l coordinator.py`)
   - [ ] Chore-specific lines: Count lines in approve_chore, reschedule, reset, overdue methods
   - [ ] Tool: Run `radon cc custom_components/kidschores/coordinator.py` (cyclomatic complexity)
   - [ ] Tool: Run `radon mi custom_components/kidschores/coordinator.py` (maintainability index)
   - [ ] Threshold: Home Assistant typically recommends <1000 lines per file

2. **Identify chore-specific methods**
   - [ ] Grep: Search for "chore" in method names: `grep "def.*chore" coordinator.py`
   - [ ] Count: How many methods are chore-specific vs other entities?
   - [ ] Categories: Approval, reset, overdue, reschedule, validation, history
   - [ ] Lines: Sum total lines for all chore-specific methods
   - [ ] Estimate: If extracted, would ChoreHandler be 2000+ lines? (separate class justified)

3. **Analyze dependencies**
   - [ ] Data access: Does chore logic access storage directly? Via coordinator methods?
   - [ ] Entity updates: Calls to \_async_update_entity(), \_async_mark_entities_for_update()
   - [ ] State management: Kid data access, points calculations, achievement tracking
   - [ ] Identify: How many coordinator methods would ChoreHandler need to call?
   - [ ] Risk: High coupling = difficult refactor, low value

4. **Pros/Cons analysis**
   - [ ] **Pros**: Reduced coordinator size, better separation of concerns, easier testing
   - [ ] **Pros**: Clearer API for chore operations, easier to understand chore lifecycle
   - [ ] **Cons**: Complexity of extraction, potential for regressions, test maintenance
   - [ ] **Cons**: May need frequent coordinator access (tight coupling remains)
   - [ ] **Cons**: Home Assistant coordinator pattern expects all logic in one class

5. **Alternative approaches**
   - [ ] Option A: Extract to ChoreHandler class (full refactor)
   - [ ] Option B: Extract only approval/reset/overdue logic (partial refactor)
   - [ ] Option C: Keep in coordinator but reorganize methods into logical groups
   - [ ] Option D: Add comprehensive comments/docstrings without structural change
   - [ ] Recommendation: Document in supporting doc with pros/cons for each option

6. **Home Assistant patterns review**
   - [ ] Research: How do other large HA integrations handle complex logic?
   - [ ] Example: ESPHome, Zigbee, Z-Wave coordinators (line counts, structure)
   - [ ] Best practice: Does HA recommend splitting coordinator when it exceeds threshold?
   - [ ] Document: HA patterns vs custom class extraction (which is more maintainable?)

**Key issues**:

- Refactor carries significant regression risk
- Must not break existing storage/entity patterns
- Home Assistant upgrade compatibility concerns
- Value of refactor vs risk must be clearly justified

**Output**: Supporting doc `CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md` with recommendation

---

### Phase 4 – Remediation

**Goal**: Implement fixes for all confirmed gaps, add validation, apply optimizations

**Steps / detailed work items**:

1. **Fix Gap 6 (if confirmed as bug)**
   - [ ] Approach A: Check completion_criteria before resetting to PENDING
   - [ ] Approach B: Only reset approving kid to PENDING, leave others until all_approved
   - [ ] Approach C: Move user's fix inside INDEPENDENT block only (lines 3491-3502)
   - [ ] File: `custom_components/kidschores/coordinator.py` lines 3583-3606
   - [ ] Test: Validate SHARED + UPON_COMPLETION works correctly
   - [ ] Verify: INDEPENDENT + UPON_COMPLETION still works (no regression)

2. **Implement Gap 3 resolution (per owner decision)**
   - [ ] **If auto-reset approved**: Add timer-based check for AT*DUE_DATE*\* reaching due date
   - [ ] Method: Create \_check_due_date_resets() called from async_update_chore_states()
   - [ ] Logic: Check all chores with AT*DUE_DATE*\* approval reset, reset if past due date
   - [ ] **If manual-only**: Add validation warning in flow_helpers.py
   - [ ] Message: "This combination requires manual approval reset after due date"
   - [ ] File: `custom_components/kidschores/flow_helpers.py` (add to validation checks)

3. **Add validation warnings (Gap 4)**
   - [ ] File: `custom_components/kidschores/flow_helpers.py`
   - [ ] Add info message for AT*DUE_DATE*\* + FREQUENCY_NONE: "Manual reset required"
   - [ ] Add info message for SHARED + UPON_COMPLETION: "All kids reset together"
   - [ ] Add to config flow UI: Display warnings in build_chore_schema()
   - [ ] Translation keys: Add TRANS*KEY_CFOF_WARNING*\* constants to const.py
   - [ ] Update: `custom_components/kidschores/translations/en.json`

4. **Optimize overdue check (Gap 5) - if profiling justifies**
   - [ ] Create: \_check_overdue_for_single_chore_by_id(chore_id) method
   - [ ] File: `custom_components/kidschores/coordinator.py` (add near line 9195)
   - [ ] Logic: Extract single-chore check from \_check_overdue_chores() loop
   - [ ] Replace: Call new method from approve_chore() line ~3605 instead of full scan
   - [ ] Test: Verify overdue detection still works correctly
   - [ ] Measure: Compare performance before/after (expect minimal gain for <100 chores)

5. **Update storage schema (if any data changes)**
   - [ ] Review: Do any fixes require new fields or data structure changes?
   - [ ] If yes: Increment SCHEMA_VERSION in const.py
   - [ ] If yes: Add migration method \_migrate_to_v{VERSION}() in coordinator.py
   - [ ] If yes: Test migration with scenario data (minimal, shared, full)

6. **Add translation keys**
   - [ ] File: `custom_components/kidschores/const.py`
   - [ ] Add: TRANS_KEY_CFOF_WARNING_AT_DUE_DATE_FREQUENCY_NONE
   - [ ] Add: TRANS_KEY_CFOF_WARNING_SHARED_UPON_COMPLETION
   - [ ] Add: TRANS_KEY_NOTIF_MESSAGE_CHORE_AUTO_RESET (if auto-reset implemented)
   - [ ] File: `custom_components/kidschores/translations/en.json`
   - [ ] Add corresponding translation strings with clear user-facing messages

**Key issues**:

- Gap 6 fix must not break INDEPENDENT chores
- Validation warnings must be informative, not annoying
- Schema changes require careful migration testing
- All fixes must maintain backward compatibility

---

### Phase 5 – Documentation

**Goal**: Create comprehensive documentation of all chore processing paths and behaviors

**Steps / detailed work items**:

1. **Create complete behavior matrix**
   - [ ] File: `docs/in-process/CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md`
   - [ ] Format: Markdown table with 480 rows (or grouped categories)
   - [ ] Columns: frequency, approval_reset, overdue_handling, completion_criteria, behavior description
   - [ ] Mark: Tested combinations (✅), Untested (⚠️), Invalid (❌)
   - [ ] Include: Expected behavior for each combination (reset timing, overdue handling)

2. **Create decision tree diagrams**
   - [ ] Use Mermaid syntax for flowcharts (HA wiki supports Mermaid)
   - [ ] Diagram 1: Approval flow (claim → approve → reschedule → reset → overdue)
   - [ ] Diagram 2: Reset triggers (midnight, due date, upon completion, manual)
   - [ ] Diagram 3: Overdue checking (at due date, never, clear at reset, clear immediate)
   - [ ] Diagram 4: SHARED chore coordination (multi-kid approval logic)
   - [ ] Include in supporting doc: `CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md`

3. **Document edge cases**
   - [ ] Create table: Edge case, Configuration, Expected behavior, Test coverage
   - [ ] Include all 6 identified gaps with resolution status
   - [ ] Include newly discovered gaps from Phase 2 audit
   - [ ] Severity rating: 🚨 Critical, ⚠️ Medium, 📝 Low, 🔧 Optimization
   - [ ] File: `docs/in-process/CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md`

4. **Update architecture documentation**
   - [ ] File: `docs/ARCHITECTURE.md`
   - [ ] Section: Add "Chore Processing Lifecycle" with flowchart
   - [ ] Section: Add "Approval Reset Types" with behavior descriptions
   - [ ] Section: Add "Overdue Handling Types" with timing explanations
   - [ ] Section: Add "Known Edge Cases" with links to gap analysis doc

5. **Update wiki pages**
   - [ ] Wiki page: "Technical-Chore-Detail.md" (create if doesn't exist)
   - [ ] Content: Link to behavior matrix and decision trees
   - [ ] Content: FAQ for common configuration questions
   - [ ] Example: "Why doesn't my chore auto-reset at due date?"
   - [ ] Example: "What happens when SHARED chore has partial approvals?"

6. **Create user-facing guide**
   - [ ] Wiki page: "Configuration-Guide-Chores.md"
   - [ ] Section: "Choosing the right approval reset type"
   - [ ] Section: "Understanding overdue handling options"
   - [ ] Section: "Common configuration patterns and recommendations"
   - [ ] Include: Decision helper (flowchart or questionnaire format)

**Key issues**:

- Documentation must stay synchronized with code changes
- Mermaid diagrams need to be maintainable (not overly complex)
- User-facing guide should be accessible to non-technical users

---

### Phase 6 – Testing

**Goal**: Achieve 95%+ test coverage for all chore approval/reset/overdue logic paths

**Steps / detailed work items**:

1. **Gap 6 - SHARED + UPON_COMPLETION tests**
   - [ ] File: `tests/test_gap6_shared_upon_completion.py` (create)
   - [ ] Test 1: SHARED chore, 2 kids, upon_completion, approve kid 1 → kid 2 should NOT auto-reset
   - [ ] Test 2: SHARED chore, 2 kids, upon_completion, approve both → chore should reschedule
   - [ ] Test 3: SHARED chore, 3 kids, upon_completion, approve 2 of 3 → verify partial state
   - [ ] Use: scenario_shared (Stårblüm Family - Bathroom, Kitchen chores)
   - [ ] Validate: all_approved check still triggers after user's fix applied

2. **FREQUENCY_NONE tests for all approval_reset_type**
   - [ ] File: `tests/test_frequency_none_approval_resets.py` (create)
   - [ ] Test matrix: 5 approval_reset_type × FREQUENCY_NONE (5 test cases)
   - [ ] Test 1: AT_MIDNIGHT_ONCE + FREQUENCY_NONE → resets at midnight
   - [ ] Test 2: AT_MIDNIGHT_MULTI + FREQUENCY_NONE → resets at midnight (multi-claim)
   - [ ] Test 3: AT_DUE_DATE_ONCE + FREQUENCY_NONE → manual reset only (or auto if implemented)
   - [ ] Test 4: AT_DUE_DATE_MULTI + FREQUENCY_NONE → manual reset only (or auto if implemented)
   - [ ] Test 5: UPON_COMPLETION + FREQUENCY_NONE → immediate reset after approval
   - [ ] Validate: Midnight reset skips FREQUENCY*NONE (except AT_MIDNIGHT*\*)

3. **Overdue handling tests**
   - [ ] File: `tests/test_overdue_handling_comprehensive.py` (create)
   - [ ] Test matrix: 4 overdue_handling_type × 2 (on-time vs late) = 8 test cases
   - [ ] Test: AT_DUE_DATE → becomes overdue after due date
   - [ ] Test: NEVER_OVERDUE → never becomes overdue even if past due
   - [ ] Test: CLEAR_AT_APPROVAL_RESET → overdue cleared when chore resets
   - [ ] Test: CLEAR_IMMEDIATE_ON_LATE → overdue cleared immediately when approved late
   - [ ] Validate: User's fix (lines 3583-3606) correctly triggers overdue check

4. **Edge case tests**
   - [ ] File: `tests/test_chore_edge_cases.py` (create)
   - [ ] Test: SHARED_FIRST completion with upon_completion reset
   - [ ] Test: Parent-assigned chore with kid approval workflow
   - [ ] Test: Multi-claim (daily_multi) with approval resets
   - [ ] Test: Recurring chore (custom_from_complete) with FREQUENCY_NONE (should fail validation)
   - [ ] Test: Due date in past + upon_completion → immediate overdue after approval

5. **Regression tests for user's fixes**
   - [ ] File: `tests/test_regression_upon_completion_fix.py` (create)
   - [ ] Test: Verify Gap 1 fix (immediate PENDING reset) works for INDEPENDENT
   - [ ] Test: Verify Gap 1 fix doesn't break SHARED coordination
   - [ ] Test: Verify Gap 2 fix (midnight skip) doesn't affect AT*MIDNIGHT*\* chores
   - [ ] Test: Verify original bug reproduced (upon_completion stayed APPROVED until midnight)
   - [ ] Test: Verify bug is fixed (upon_completion immediately resets to PENDING)

6. **Coverage analysis**
   - [ ] Run: `pytest tests/ --cov=custom_components/kidschores/coordinator --cov-report=term-missing`
   - [ ] Target: ≥95% coverage for coordinator.py lines 3138-3598 (approve_chore)
   - [ ] Target: ≥95% coverage for lines 9488-9530 (\_reset_daily_chore_statuses)
   - [ ] Target: ≥95% coverage for lines 10023-10232 (reschedule methods)
   - [ ] Identify: Uncovered lines and determine if test gaps or unreachable code
   - [ ] Document: Coverage report in phase completion notes

7. **Integration tests with dashboard**
   - [ ] Test: Dashboard helper sensor correctly displays chore state after approval
   - [ ] Test: Button press → service call → approve_chore() → state update → helper refresh
   - [ ] Test: Verify translations show correct state (PENDING, APPROVED, OVERDUE)
   - [ ] Coordinate: With dashboard repo testing (kidschores-ha-dashboard)

**Key issues**:

- Test scenarios must use Stårblüm Family data for consistency
- Service-based tests preferred over direct coordinator API calls
- Must test both positive (expected behavior) and negative (error handling) cases
- Dashboard integration tests may require coordination with dashboard repo

---

## Testing & validation

### Phase 1 validation

- Run: `pytest tests/test_gap6_shared_upon_completion.py -v`
- Expected: SHARED chore reschedule still triggers after user's fix (or bug confirmed)
- Run: `./utils/quick_lint.sh --fix` (must pass 9.5+/10)
- Run: `mypy custom_components/kidschores/` (zero errors)

### Phase 2 validation

- Review: Complete behavior matrix covers all valid combinations
- Review: Decision tree diagrams are accurate and complete
- Validate: Audit findings match actual code behavior (no assumptions)

### Phase 3 validation

- Metrics: Complexity scores (cyclomatic, maintainability) documented
- Analysis: Refactor recommendation with clear pros/cons and risk assessment
- Review: Owner approves or rejects refactor approach

### Phase 4 validation

- Run: All test files from Phase 6 (must pass 100%)
- Run: Full test suite to ensure no regressions: `pytest tests/ -v`
- Run: Quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`

### Phase 5 validation

- Review: Documentation clear and accurate
- Review: Diagrams render correctly in wiki (Mermaid syntax valid)
- Review: User guide addresses common questions

### Phase 6 validation

- Run: `pytest tests/ -v --tb=line` (all tests pass)
- Coverage: ≥95% for chore-specific coordinator methods
- Integration: Dashboard tests pass (coordinate with dashboard repo)

---

## Notes & follow-up

### Architecture considerations

**Coordinator complexity**: At 8987 lines, coordinator.py exceeds typical HA integration size. However, splitting into separate class may not reduce complexity if tight coupling remains. Phase 3 analysis will provide data-driven recommendation.

**Storage schema stability**: Any schema changes must include migration logic. Current schema (v42+) is stable - avoid changes unless absolutely necessary for bug fixes.

**Parent chores integration**: Phase 4 remediation must consider how parent-assigned chores interact with approval workflows (new in v0.5.0).

### Implementation priorities

1. **Critical**: Gap 6 investigation (release blocker if confirmed)
2. **High**: Complete logic path audit (may reveal additional gaps)
3. **Medium**: Validation warnings for edge cases (UX improvement)
4. **Low**: Optimization (single-chore overdue check)
5. **Defer**: Refactor to separate class (unless strongly justified by Phase 3)

### Testing approach

- Use existing test scenarios: scenario_minimal, scenario_shared, scenario_full (Stårblüm Family)
- Prefer service-based tests: Dashboard helper → button press → validate state
- Direct coordinator API tests: Only for internal logic not exposed to entities
- Import test helpers from `tests.helpers`, NOT from `const.py`

### Documentation strategy

- **Internal**: Behavior matrix and decision trees in supporting docs (technical detail)
- **Wiki**: User-facing guide with common patterns and FAQs (accessible language)
- **Architecture.md**: Integration-level overview with links to detailed docs

### Future considerations

- **v0.6.0**: Potential refactor if Phase 3 strongly recommends
- **v0.6.0**: Additional chore types or approval workflows may require revisiting logic paths
- **Monitoring**: Track user reports for edge cases not covered in audit

### Follow-up tasks (post-initiative)

- [ ] Move completed plan to `docs/completed/CHORE_LOGIC_AUDIT_COMPLETE.md`
- [ ] Close related GitHub issues (if any)
- [ ] Announce in release notes: "Comprehensive chore logic audit completed"
- [ ] Update `RELEASE_CHECKLIST.md` if new validation rules added
- [ ] Consider blog post or wiki announcement highlighting improved stability

---

**Note**: This initiative is comprehensive and may span multiple sprints. Prioritize Phase 1 (Gap 6 investigation) as potential release blocker for v0.5.1. Phases 2-3 can run in parallel. Phase 4-6 depend on findings from earlier phases.

**Status tracking**: Update summary table percentages after each phase milestone. Move to `docs/completed/` only after ALL phases complete and owner approval obtained.
