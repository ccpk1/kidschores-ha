# KidsChores Coordinator.py Code Standardization Remediation Plan

## Initiative snapshot

- **Name / Code**: Coordinator.py Code Standardization - Phase 0 Remediation
- **Target release / milestone**: KidsChores v4.3+ (Post-Storage Migration)
- **Owner / driver(s)**: Development Team / AI Agent
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                     | Description                                    | % complete | Quick notes                                                       |
| -------------------------------- | ---------------------------------------------- | ---------- | ----------------------------------------------------------------- |
| Phase 1 – Notification Constants | Standardize all hardcoded notification strings | 100%       | ✅ Complete - All 31 strings replaced with translation system     |
| Phase 2 – Translation System     | Implement HA-standard async_get_translations   | 100%       | ✅ Complete - Both wrapper methods implemented, test mode working |
| Phase 3 – Exception & Testing    | Review exceptions, comprehensive testing       | 0%         | Pending - Final validation needed                                 |

1. **Key objective** – Achieve 95%+ compliance with KidsChores Code Quality Standards by systematically replacing hardcoded strings with const.py-based constants throughout the coordinator.py file (8,987 lines).

2. **Summary of recent work** – Completed Phase 1 (notification constants in const.py and en.json) and Phase 2 (translation system implementation using Home Assistant's async_get_translations API). All 31 notification strings now use proper translation system. Discovered and restored ATTR_CLAIMED_ON and ATTR_REDEEMED_ON constants that were incorrectly removed as "dead code".

3. **Next steps (short term)** – Complete Phase 3 final validation: comprehensive testing suite, exception message standardization, pattern consistency validation, and documentation updates. Archive working documents to docs/completed/ upon successful completion.

4. **Risks / blockers** – None currently. Phases 1 and 2 completed successfully with all tests passing. Phase 3 requires comprehensive testing suite development and final exception message standardization.

5. **References** –

   - Audit findings: `docs/in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md`
   - Code standards: `docs/CODE_REVIEW_GUIDE.md`
   - Testing approach: `tests/TESTING_AGENT_INSTRUCTIONS.md`

6. **Decisions & completion check**
   - **Decisions captured**:
     - 3-phase incremental approach approved (minimize regression risk)
     - Notification standardization prioritized first (highest user impact)
     - Full testing required between phases
     - Storage-only architecture constraints acknowledged
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

---

## ✅ Tracking Expectations

**AI Agents working on this plan MUST track their work:**

- Use checkboxes `- [ ]` for incomplete items, `- [x]` for completed items
- Update task status IMMEDIATELY after completing each item
- Add brief completion notes inline: `- [x] Task description (✓ completed, notes here)`
- Add new tasks discovered during work using `- [ ] NEW: Task description`
- If blocked, mark as: `- [ ] ⚠️ BLOCKED: Task description (reason)`
- Keep summary table and percentages up-to-date with latest progress

---

## Detailed phase tracking

### Phase 1 – Notification Constants Standardization

- **Goal**: Replace all 31 hardcoded notification strings with const.py-based constants and proper translation patterns
- **Status**: ✅ COMPLETE
- **Steps / detailed work items**
  1. **Define notification constants in const.py** (Status: ✅ Complete)
     - [x] Add 15 `TRANS_KEY_NOTIF_TITLE_*` constants (✓ lines 1266-1281)
     - [x] Add 16 `TRANS_KEY_NOTIF_MESSAGE_*` constants (✓ lines 1281-1299)
     - [x] Follow naming convention: `TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED = "notification_title_chore_claimed"`
  2. **Update en.json translation entries** (Status: ✅ Complete)
     - [x] Add all 31 new translation entries with proper message templates (✓ line 2398+)
     - [x] Use placeholder substitution: `"New chore '{chore_name}' assigned! Due: {due_date}"`
  3. **Restore missing constants** (Status: ✅ Complete)
     - [x] ATTR_CLAIMED_ON restored (const.py line 1353) - was incorrectly removed as "dead code"
     - [x] ATTR_REDEEMED_ON restored (const.py line 1403) - required by sensor_legacy.py
  4. **Validation and testing** (Status: ✅ Complete)
     - [x] Execute `./utils/quick_lint.sh --fix` (9.64/10 - passed)
     - [x] Run workflow tests (19 tests passing)
     - [x] Verified legacy sensors working correctly
- **Key achievements**
  - All notification constants defined and documented
  - Translation entries added to en.json
  - Discovered and corrected "dead code" misidentification

### Phase 2 – Translation System Implementation

- **Goal**: Implement Home Assistant standard translation system for all notifications
- **Status**: ✅ COMPLETE
- **Steps / detailed work items**
  1. **Add import and test mode detection** (Status: ✅ Complete)
     - [x] Add `import sys` (coordinator.py line 15)
     - [x] Add `from homeassistant.helpers.translation import async_get_translations` (line 27)
     - [x] Add test mode detection in `__init__` (lines 61-68): `self._test_mode = "pytest" in sys.modules`
  2. **Create translation wrapper methods** (Status: ✅ Complete)
     - [x] Implement `_notify_kid_translated()` method (lines 8867-8918)
     - [x] Implement `_notify_parents_translated()` method (lines 8975-9028)
     - [x] Use `async_get_translations()` with proper language support
     - [x] Implement flattened key format: `component.kidschores.notifications.{type}.title`
  3. **Transform all notification calls** (Status: ✅ Complete)
     - [x] Replace all 17 regular notification calls with translated wrappers
     - [x] Replace 2 reminder notification calls with translated wrappers
     - [x] Update reminder delay logic with test mode (line 9052): 5s vs 1800s
  4. **Validation and testing** (Status: ✅ Complete)
     - [x] Execute `./utils/quick_lint.sh --fix` (9.64/10 - passed)
     - [x] Verify no hardcoded notification strings remain
     - [x] Confirm translation loading works correctly
     - [x] All workflow tests passing
- **Key achievements**
  - Using Home Assistant standard API (not custom storage_manager method)
  - Dynamic language support via `self.hass.config.language`
  - Built-in caching through HA translation system
  - Test mode auto-detection for faster test execution

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
  - Create notification constant inventory (Phase 1)
  - Develop string literal replacement automation scripts (Phase 2)
  - Design comprehensive testing matrix for coordinator changes (Phase 3)

---

## 📝 Additional Notes

**Estimated Development Effort**: 120-160 hours total across all phases

- Phase 1: 40-50 hours (notification constants)
- Phase 2: 60-80 hours (string literal constants)
- Phase 3: 20-30 hours (exception review + testing)

**Critical Success Factors**:

1. Maintain functionality throughout incremental changes
2. Achieve 95%+ code quality compliance
3. Pass all linting and testing requirements between phases
4. Minimal performance impact on coordinator operations

**Risk Mitigation Strategies**:

- Incremental approach with testing between phases
- Automated validation via quick_lint.sh and pytest
- Focus on high-impact changes first
- Rollback capability for each phase

**Supporting Documents**: All detailed audit findings and constant inventories have been moved to:

- `docs/in-process/coordinator-remediation-supporting/`

---

**Created from PLAN_TEMPLATE.md** - This plan follows KidsChores documentation standards for initiative tracking.
