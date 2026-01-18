# Chore Logic Audit Initiative - Quick Reference

**Created**: January 18, 2026
**Status**: Planning Complete, Ready for Implementation

---

## 📁 Document Structure

### Main Plan

**[CHORE_LOGIC_AUDIT_IN-PROCESS.md](CHORE_LOGIC_AUDIT_IN-PROCESS.md)**

- 6 phases covering investigation, audit, architecture, remediation, documentation, testing
- Use this for overall progress tracking and phase management

### Supporting Documents

1. **[CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md](CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md)**
   - Detailed analysis of all 6 identified gaps
   - Severity ratings, root causes, potential fixes
   - **Start here** for Gap 6 investigation

2. **[CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md](CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md)**
   - Complete matrix of 480 configuration combinations
   - Decision tree diagrams (Mermaid format)
   - Test coverage tracking
   - **Use this** for understanding all chore logic paths

3. **[CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md](CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md)**
   - Analysis of ChoreHandler class extraction
   - 4 refactor options with pros/cons
   - **Recommendation**: Option C + D (organize + extract utils)
   - Complexity metrics checklist

---

## 🚨 Critical Priority: Gap 6

**Issue**: User's fix for Gap 1 may break SHARED chores with UPON_COMPLETION

**Location**: coordinator.py lines 3583-3606

**Problem**: Fix resets ALL kids to PENDING before SHARED chore's all_approved check runs

**Impact**: SHARED chores may never reschedule (reschedule never triggers)

**Next Steps**:

1. Read [Gap Analysis doc](CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md#gap-6-shared--upon_completion-interaction-)
2. Create test: `tests/test_gap6_shared_upon_completion.py`
3. Test scenario: SHARED chore, 2 kids, upon_completion, sequential approvals
4. If bug confirmed: Apply Option B fix (move user's fix inside INDEPENDENT block)

---

## 📊 Phase Summary

| Phase       | Focus               | Priority    | Blocker?             |
| ----------- | ------------------- | ----------- | -------------------- |
| **Phase 1** | Gap Investigation   | 🚨 CRITICAL | Yes - Gap 6          |
| **Phase 2** | Logic Path Audit    | 🟡 HIGH     | No                   |
| **Phase 3** | Architecture Review | 🟡 MEDIUM   | No                   |
| **Phase 4** | Remediation         | 🔴 HIGH     | Depends on Phase 1   |
| **Phase 5** | Documentation       | 🟢 MEDIUM   | No                   |
| **Phase 6** | Testing             | 🔴 HIGH     | Yes - v0.5.1 release |

---

## 🎯 Quick Actions by Role

### If You're Investigating Gap 6 (URGENT)

1. Open [Gap Analysis](CHORE_LOGIC_AUDIT_SUP_GAP_ANALYSIS.md) and read Gap 6 section
2. Review coordinator.py lines 3583-3606 (user's fix)
3. Review coordinator.py lines 3503-3526 (SHARED logic)
4. Create test file: `tests/test_gap6_shared_upon_completion.py`
5. Run test with Stårblüm Family scenario (2 kids, SHARED chore)
6. Update Gap Analysis doc with results

### If You're Implementing Tests

1. Open [Behavior Matrix](CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md)
2. Check "Needs Testing" section
3. Use existing test scenarios: scenario_minimal, scenario_shared, scenario_full
4. Follow pattern from `tests/test_workflow_*.py`
5. Update matrix with test status (✅ or ❌)

### If You're Considering Refactor

1. Open [Refactor Analysis](CHORE_LOGIC_AUDIT_SUP_REFACTOR_ANALYSIS.md)
2. Read "Recommendations" section (Option C + D recommended)
3. Run complexity metrics: `radon cc coordinator.py -s`
4. Document results in Refactor Analysis doc
5. Make decision based on metrics (not line count alone)

### If You're Documenting

1. Open [Behavior Matrix](CHORE_LOGIC_AUDIT_SUP_BEHAVIOR_MATRIX.md) for decision trees
2. Copy Mermaid diagrams to wiki pages
3. Create user-facing guide from behavior patterns
4. Link supporting docs in ARCHITECTURE.md

---

## 📈 Progress Tracking

### Completed ✅

- Deep analysis of approval/reset/overdue logic
- Identified 6 gaps with severity ratings
- Created comprehensive behavior matrix (480 combinations)
- Documented decision trees and logic flows
- Architecture refactor analysis with 4 options

### In Progress 🔄

- None (waiting to start Phase 1)

### Blocked 🚫

- Phase 4 (Remediation) - Depends on Gap 6 results
- Phase 6 (Testing) - Depends on remediation decisions

---

## 🔗 External References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, storage
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Code patterns
- [AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md) - Test scenarios
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Quality standards

---

## 📝 How to Use This Initiative

### For Implementers (Builder Agent)

1. Start with Phase 1 (Gap 6 investigation) - **CRITICAL PRIORITY**
2. Read supporting docs linked in each phase
3. Update main plan summary table after each phase milestone
4. Move to next phase only after current phase complete

### For Reviewers

1. Check main plan for high-level status
2. Dive into supporting docs for detailed analysis
3. Review Gap Analysis for confirmed vs suspected issues
4. Check Behavior Matrix for test coverage gaps

### For Maintainers

1. Use supporting docs as permanent reference
2. Gap Analysis doc becomes edge case documentation
3. Behavior Matrix becomes testing checklist
4. Refactor Analysis guides future architecture decisions

---

## 🎬 Getting Started

**First step**: Investigate Gap 6 (SHARED + UPON_COMPLETION)

**Command**:

```bash
# Create test file
touch tests/test_gap6_shared_upon_completion.py

# Open for editing
code tests/test_gap6_shared_upon_completion.py
```

**Test scenario to implement**:

```python
async def test_shared_chore_upon_completion_reschedule(
    hass: HomeAssistant,
    coordinator: KidsChoresCoordinator,
) -> None:
    """Test SHARED chore reschedules correctly with upon_completion."""
    # Setup: SHARED chore, 2 kids (Sarah, Emily), upon_completion
    # Step 1: Sarah approves → verify both kids' states
    # Step 2: Emily approves → verify reschedule triggers
    # Expected: Chore resets to PENDING for both kids
    # Bug: If all_approved never True, reschedule never triggers
```

**After test results**: Update Gap Analysis doc with findings

---

## 💡 Key Insights from Analysis

1. **FREQUENCY_NONE is special**: No auto-reschedule (returns None from calculator)
2. **User's fixes work for INDEPENDENT**: Gaps 1 & 2 resolved correctly
3. **SHARED chores vulnerable**: Gap 6 race condition needs investigation
4. **AT*DUE_DATE*\* needs decision**: Auto-reset timer vs manual-only?
5. **Coordinator is large but manageable**: 11,846 lines, but organization helps more than extraction
6. **480 combinations exist**: But only ~50 high-priority tests needed

---

## ✅ Success Criteria

**Before v0.5.1 release**:

- [ ] Gap 6 investigated and resolved (or confirmed safe)
- [ ] Gaps 1 & 2 regression tested
- [ ] Owner decision on Gap 3 (AT*DUE_DATE*\* behavior)

**Before marking initiative complete**:

- [ ] All 6 phases completed
- [ ] Test coverage ≥95% for chore logic
- [ ] Documentation published to wiki
- [ ] Owner approval obtained

---

**Next Action**: Start Phase 1, Step 1 (Gap 6 investigation)

**Estimated Timeline**: 2-4 weeks for complete initiative (varies by findings)
