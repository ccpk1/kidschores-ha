# KidsChores Coordinator.py Code Standardization Remediation Plan

## Initiative snapshot

- **Name / Code**: Coordinator.py Code Standardization - Phase 0 Remediation
- **Target release / milestone**: KidsChores v4.3+ (Post-Storage Migration)
- **Owner / driver(s)**: Development Team / AI Agent
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                   | Description                                      | % complete | Quick notes                                    |
| ------------------------------ | ------------------------------------------------ | ---------- | ---------------------------------------------- |
| Phase 1 – Notification Constants | Standardize all hardcoded notification strings | 0%         | 31 notification strings identified for remediation |
| Phase 2 – String Literal Constants | Systematic replacement of 200+ hardcoded literals | 0%         | High-impact strings prioritized first |
| Phase 3 – Exception & Testing | Review exceptions, comprehensive testing        | 0%         | Final validation and compliance verification |

1. **Key objective** – Achieve 95%+ compliance with KidsChores Code Quality Standards by systematically replacing hardcoded strings with const.py-based constants throughout the coordinator.py file (8,987 lines).

2. **Summary of recent work** – Completed Phase 0 Repeatable Audit Framework revealing 19% overall compliance with critical violations in notification standardization (0% compliant), string literals (20% compliant), and user-facing text standards.

3. **Next steps (short term)** – Begin Phase 1 with notification constant definition in const.py, followed by systematic replacement of 18 hardcoded notification titles and 13 hardcoded messages with proper TRANS_KEY_NOTIF_* patterns.

4. **Risks / blockers** – Large file size (8,987 lines) increases regression risk; notification system changes require extensive testing across all entity types; coordination with ongoing storage architecture work needed.

5. **References** – 
   - Audit findings: `docs/in-process/COORDINATOR_CODE_REVIEW.md`
   - Code standards: `docs/CODE_REVIEW_GUIDE.md`
   - Testing approach: `tests/TESTING_AGENT_INSTRUCTIONS.md`

6. **Decisions & completion check**
   - **Decisions captured**: 
     * 3-phase incremental approach approved (minimize regression risk)
     * Notification standardization prioritized first (highest user impact)
     * Full testing required between phases
     * Storage-only architecture constraints acknowledged
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

---

## Detailed phase tracking

### Phase 1 – Notification Constants Standardization

- **Goal**: Replace all 31 hardcoded notification strings with const.py-based constants and proper translation patterns
- **Steps / detailed work items**
  1. **Define notification constants in const.py** (Status: Not started)
     - Add 18 `TRANS_KEY_NOTIF_TITLE_*` constants
     - Add 13 `TRANS_KEY_NOTIF_MESSAGE_*` constants
     - Follow naming convention: `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED = "notification_title_chore_claimed"`
  2. **Update en.json translation entries** (Status: Not started)
     - Add all 31 new translation entries with proper message templates
     - Use placeholder substitution instead of f-strings: `"New chore '{chore_name}' assigned! Due: {due_date}"`
  3. **Replace hardcoded notification calls** (Status: Not started)
     - Update all 24 notification function calls in coordinator.py
     - Convert f-string messages to message_data dictionary pattern
     - Test notification delivery for all scenarios
  4. **Validation and testing** (Status: Not started)
     - Execute `./utils/quick_lint.sh --fix` (must pass)
     - Run `python -m pytest tests/ -v --tb=line` (must pass)
     - Manual testing of notification scenarios
- **Key issues**
  - Notification system integration complexity requires careful testing
  - Message_data dictionary pattern needs consistent implementation
  - Coordination with notification_helper.py may be required

### Phase 2 – String Literal Constants

- **Goal**: Systematically replace 200+ hardcoded string literals with appropriate const.py constants
- **Steps / detailed work items**
  1. **High-priority constants definition** (Status: Not started)
     - Add `DICT_KEY_NAME`, `DICT_KEY_ENTITY_TYPE` constants (47 occurrences each)
     - Add date format constants: `FORMAT_WEEK_ISO`, `FORMAT_MONTH_ISO`, `FORMAT_YEAR` (8 occurrences each)
     - Add period constants: `PERIOD_DAILY`, `PERIOD_WEEKLY`, `PERIOD_MONTHLY`, `PERIOD_YEARLY`
  2. **Medium-priority constants definition** (Status: Not started)
     - Add `LABEL_KID`, `LABEL_ENTITY`, `LABEL_REQUIRED`, `LABEL_CURRENT` constants
     - Add status/state constants for repeated strings
  3. **Systematic replacement implementation** (Status: Not started)
     - Replace high-priority strings first (highest impact)
     - Use multi_replace_string_in_file for efficient bulk changes
     - Maintain functionality through incremental testing
  4. **Low-priority cleanup** (Status: Not started)
     - Address remaining single-occurrence strings
     - Consolidate similar patterns where possible
- **Key issues**
  - Large number of replacements increases regression risk
  - Dictionary key patterns need consistent implementation
  - Date/time format standardization critical for functionality

### Phase 3 – Exception Review & Comprehensive Testing

- **Goal**: Final review of exception messages, cleanup, and comprehensive testing to achieve 95%+ compliance
- **Steps / detailed work items**
  1. **Exception message standardization** (Status: Not started)
     - Review all 59 HomeAssistantError instances
     - Ensure proper translation_key usage patterns
     - Verify translation_placeholder consistency
  2. **Pattern consistency validation** (Status: Not started)
     - Audit all const.py usage patterns
     - Ensure no hardcoded strings remain in user-facing contexts
     - Validate translation key coverage in en.json
  3. **Comprehensive testing suite** (Status: Not started)
     - Full regression testing with storage-only architecture
     - Integration testing across all entity types
     - Notification system end-to-end validation
     - Performance impact assessment (8,987 line file changes)
  4. **Documentation and cleanup** (Status: Not started)
     - Update CODE_REVIEW_GUIDE.md with lessons learned
     - Document new constant patterns for future development
     - Archive working documents to docs/completed/
- **Key issues**
  - Testing complexity due to coordinator.py centrality
  - Storage-only architecture integration requirements
  - Performance validation needed for large-scale changes

---

## Testing & validation

- **Tests executed**: None (Phase 0 audit complete)
- **Outstanding tests**: 
  - All phases require `./utils/quick_lint.sh --fix` passing
  - All phases require `python -m pytest tests/ -v --tb=line` passing
  - Phase 1: Notification delivery testing
  - Phase 2: Entity functionality regression testing
  - Phase 3: Full integration testing
- **Links to failing logs or CI runs**: N/A - not yet executed

## Notes & follow-up

- **Architecture considerations**: Storage-only architecture (v4.2+) constraints acknowledged; no config entry data modifications
- **Performance impact**: Large file size requires incremental approach to minimize regression risk
- **Integration requirements**: Coordination with notification_helper.py and const.py updates
- **Future implications**: Establishes pattern for remaining entity files standardization
- **Follow-up tasks**: 
  * Create notification constant inventory (Phase 1)
  * Develop string literal replacement automation scripts (Phase 2)
  * Design comprehensive testing matrix for coordinator changes (Phase 3)

---

## Resource Requirements

**Estimated Development Hours**: 120-160 hours total
- Phase 1: 40-50 hours (notification constants)  
- Phase 2: 60-80 hours (string literal constants)
- Phase 3: 20-30 hours (exception review + testing)

**Critical Success Factors**:
1. Maintain functionality throughout incremental changes
2. Achieve 95%+ code quality compliance  
3. Pass all linting and testing requirements between phases
4. Minimal performance impact on coordinator operations

**Risk Mitigation**:
- Incremental approach with testing between phases
- Automated validation via quick_lint.sh and pytest
- Focus on high-impact changes first
- Rollback capability for each phase