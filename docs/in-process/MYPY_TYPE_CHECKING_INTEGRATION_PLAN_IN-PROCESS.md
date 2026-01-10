# MyPy Type Checking Integration Plan

## Initiative snapshot

- **Name / Code**: MyPy Type Checking Integration
- **Target release / milestone**: v0.6.0 (post-parent-chores feature)
- **Owner / driver(s)**: TBD
- **Status**: Not started

## Summary & immediate steps

| Phase / Step              | Description                                  | % complete | Quick notes                               |
| ------------------------- | -------------------------------------------- | ---------- | ----------------------------------------- |
| Phase 1 – Fix Type Issues | Resolve 188 existing type errors in codebase | 0%         | 188 errors across 12 files identified     |
| Phase 2 – Integration     | Add mypy to quick_lint.sh validation         | 0%         | Script changes prepared, awaiting Phase 1 |
| Phase 3 – Strictness      | Optionally increase type checking strictness | 0%         | Deferred until Phase 2 stable             |

1. **Key objective** – Integrate MyPy type checking into the CI/CD pipeline to prevent type regressions and catch bugs earlier. MyPy is already configured in `pyproject.toml` but not enforced during linting.

2. **Summary of recent work** (as of January 10, 2026):

   - Discovered MyPy configuration exists in `pyproject.toml` (lines 212-235)
   - Updated `pyrightconfig.json` to exclude tests from IDE type checking (matches pyproject.toml intent)
   - Attempted to add mypy to `quick_lint.sh`, discovered 188 pre-existing type errors
   - Reverted quick_lint.sh changes to avoid blocking current development
   - Fixed 8 type issues in `tests/test_parent_shadow_kid.py` as proof-of-concept

3. **Next steps (short term)**:

   - Phase 1: Fix type issues in button.py (~80 errors) - list type declarations
   - Phase 1: Fix type issues in sensor.py (~90 errors) - list types + missing annotations
   - Phase 1: Fix remaining issues in config_flow.py and options_flow.py (~18 errors)

4. **Risks / blockers**:

   - **Effort estimate**: 2-4 hours to fix all 188 type issues
   - **Priority**: Medium - improves code quality but not blocking feature development
   - **Scope creep risk**: May uncover additional issues once strict checking enabled
   - **Testing burden**: Must verify all 927+ tests still pass after type fixes

5. **References**:

   - Configuration: `pyproject.toml` (lines 212-235 - mypy config)
   - Configuration: `pyrightconfig.json` (Pylance/IDE settings)
   - Test command: `mypy custom_components/kidschores`
   - Full error output: See Phase 1 detailed section below

6. **Decisions & completion check**
   - **Decisions captured**:
     - Tests excluded from type checking (intentional - pyproject.toml line 235)
     - Basic strictness mode preferred over strict mode (balances safety vs. practicality)
     - MyPy added to quick_lint.sh (not separate script) for consistent CI/CD
   - **Completion confirmation**: `[ ]` All follow-up items completed:
     - `[ ]` All 188 type errors resolved
     - `[ ]` MyPy integrated into quick_lint.sh
     - `[ ]` Full test suite passes (927+ tests)
     - `[ ]` Documentation updated (if needed)

> **Important:** This initiative was deferred on January 10, 2026 to avoid blocking parent-chores feature development. It should be prioritized after v0.5.0 release.

## Tracking expectations

- **Summary upkeep**: Update percentages after each file is type-clean. Update "Next steps" after completing each phase.
- **Detailed tracking**: Log specific file completions, issue counts, and any new type issues discovered in phase sections below.

## Detailed phase tracking

### Phase 1 – Fix Type Issues

- **Goal**: Resolve all 188 existing type errors to establish clean baseline for mypy integration.

- **Steps / detailed work items**:

  1. `[ ]` Fix button.py (~80 errors) - List type declarations

     - **Issue**: Lists declared as `list[KidChoreClaimButton]` but append different button types
     - **Fix**: Change to `list[ButtonEntity]` or use union types
     - **Lines affected**: 94, 108, 135, 150, 167, 196, 224, 289

  2. `[ ]` Fix sensor.py (~90 errors) - List types + missing annotations

     - **Issue 1**: Lists declared as `list[SystemChoresPendingApprovalSensor]` but append different sensor types
     - **Fix**: Change to `list[Entity]` or `list[SensorEntity]`
     - **Lines affected**: 107, 125, 131, 136, 139, 142, 145, 150, 156, 163, 170, 178, 193, 206, 226, 244, 264, 277, 297, 315, 337, 349, 359, 372, 384
     - **Issue 2**: Missing type annotations for dict variables
     - **Fix**: Add explicit type hints
     - **Lines affected**: 1092 (badge_entity_ids), 2672 (\_ui_translations), 3547 (chores_by_label)
     - **Issue 3**: Lambda sort key type mismatch (line 3533)
     - **Fix**: Add explicit return type or use key function with proper typing

  3. `[ ]` Fix options_flow.py (8 errors)

     - Line 2069: Add `errors: dict[str, str] = {}` annotation
     - Line 2136: Fix argument type in build_challenges_data() call
     - Lines 2972, 3033: Fix assignment type mismatches

  4. `[ ]` Fix config_flow.py (5 errors)

     - Lines 719, 1115, 1195: Add `errors: dict[str, str] = {}` annotations
     - Line 1409: Add `entry_data: dict[str, Any] = {}` annotation
     - Line 1424: Remove unused type: ignore comment

  5. `[ ]` Run full test suite after each file fix

     - Command: `python -m pytest tests/ -v --tb=line`
     - Expected: 927+ tests pass

  6. `[ ]` Verify mypy reports zero errors
     - Command: `mypy custom_components/kidschores`
     - Expected: "Success: no issues found in 20 source files"

- **Key issues**:
  - **Performance**: Large codebase may slow mypy checks (~5-10 seconds added to quick_lint)
  - **Maintainability**: Need to educate contributors on type hints and mypy errors
  - **False positives**: May encounter edge cases where type: ignore is legitimately needed

### Phase 2 – Integration

- **Goal**: Add mypy to quick_lint.sh so type checking is enforced for all commits.

- **Steps / detailed work items**:

  1. `[ ]` Update utils/quick_lint.sh (--fix mode)

     - Add after ruff format:
       ```bash
       echo ""
       echo "🔍 Running mypy type checking..."
       mypy custom_components/kidschores
       mypy_exit=$?
       ```
     - Update exit condition: `if [ $ruff_check_exit -eq 0 ] && [ $ruff_format_exit -eq 0 ] && [ $mypy_exit -eq 0 ]; then`

  2. `[ ]` Update utils/quick_lint.sh (read-only mode)

     - Add same mypy check before final status
     - Update exit condition to include mypy_exit

  3. `[ ]` Test quick_lint integration

     - Command: `./utils/quick_lint.sh --fix`
     - Expected: "✅ All checks passed!"
     - Command: `./utils/quick_lint.sh` (read-only)
     - Expected: "✅ All checks passed! Ready to commit."

  4. `[ ]` Document in README or CONTRIBUTING
     - Note that mypy is now part of CI/CD
     - Explain how to fix type errors
     - Link to mypy documentation

- **Key issues**:
  - **Developer experience**: Some developers may not be familiar with type hints
  - **CI/CD impact**: Adds ~5-10 seconds to lint time
  - **Regression risk**: New code must be type-safe from day 1

### Phase 3 – Strictness (Optional)

- **Goal**: Optionally increase type checking strictness for better type safety.

- **Steps / detailed work items**:

  1. `[ ]` Evaluate current error rate with basic mode

     - Monitor for 2-4 weeks after Phase 2 complete
     - Count new type errors introduced

  2. `[ ]` Consider enabling stricter settings in pyproject.toml:

     - `strict_optional = true` (currently false)
     - `warn_return_any = true` (currently false)
     - `disallow_untyped_defs = true` (for new code only)

  3. `[ ]` Pilot stricter settings on new modules

     - Test on newly created files only
     - Assess developer feedback

  4. `[ ]` Document decision to enable/skip strictness
     - Record rationale in this plan
     - Update STANDARDS.md if strictness enabled

- **Key issues**:
  - **Diminishing returns**: Basic mode may be sufficient
  - **Developer friction**: Strict mode can be frustrating
  - **Legacy code burden**: May require extensive refactoring

## Testing & validation

- **Tests executed**:

  - `mypy custom_components/kidschores` - 188 errors found (baseline established)
  - `./utils/quick_lint.sh --fix` - Passes (ruff only, mypy excluded)
  - `python -m pytest tests/test_parent_shadow_kid.py -v` - 17 tests pass (type-safe tests confirmed)

- **Outstanding tests**:

  - Full mypy validation after Phase 1 fixes
  - Integration testing of quick_lint.sh with mypy
  - Performance testing (measure lint time increase)

- **Links to failing logs**:
  - Initial mypy run (January 10, 2026): See terminal output in Phase 1 section above

## Notes & follow-up

### Configuration Details

**Current MyPy Configuration** (pyproject.toml lines 212-231):

```toml
[tool.mypy]
python_version = "3.13"
show_error_codes = true
follow_imports = "normal"
local_partial_types = true
strict_equality = true
warn_incomplete_stub = true
warn_redundant_casts = true
warn_unused_configs = true
warn_unused_ignores = true
enable_error_code = "ignore-without-code"
disable_error_code = "annotation-unchecked"
check_untyped_defs = true
strict_optional = false  # Temporarily disabled
warn_return_any = false  # Temporarily disabled

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # Tests excluded from strict typing
```

**Pyright Configuration** (pyrightconfig.json):

```json
{
  "extraPaths": ["/workspaces/core"],
  "exclude": ["**/node_modules", "**/__pycache__", ".git", "tests"],
  "reportMissingImports": "warning",
  "pythonVersion": "3.13"
}
```

### Error Breakdown by File

**January 10, 2026 baseline** (188 total errors):

- button.py: ~80 errors (42%)
- sensor.py: ~90 errors (48%)
- options_flow.py: 8 errors (4%)
- config_flow.py: 5 errors (3%)
- Other files: 5 errors (3%)

### Architecture Considerations

- **Type-safe helpers**: Consider adding type stubs for kc_helpers.py functions
- **Generic types**: May need to use TypeVar for flexible function signatures
- **Protocol types**: Consider using Protocol for duck typing where appropriate

### Follow-up Tasks

- After Phase 2: Monitor type error introduction rate for 1 month
- After Phase 2: Survey contributors about mypy experience
- Future: Consider adding mypy to pre-commit hooks
- Future: Evaluate mypy plugins (e.g., for pytest, Home Assistant)

### Related Work

- **Completed**: pyrightconfig.json updated to exclude tests (January 10, 2026)
- **Completed**: Fixed type issues in test_parent_shadow_kid.py (8 assertions added)
- **Blocked by**: Parent-chores feature completion (priority)

### References

- MyPy documentation: https://mypy.readthedocs.io/
- Home Assistant type checking: Core AGENTS.md (uses mypy internally)
- Type hints PEP: PEP 484, PEP 526, PEP 544 (Protocols)
