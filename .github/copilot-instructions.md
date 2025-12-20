# KidsChores Home Assistant Integration - AI Developer Guide

## 📚 Critical Documentation (Read as Needed)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (Storage-only model, data separation, translation architecture)
- **Quality Standards**: [docs/CODE_REVIEW_GUIDE.md](docs/CODE_REVIEW_GUIDE.md) (Audit framework, logging, constants)
- **Testing**: [tests/TESTING_AGENT_INSTRUCTIONS.md](tests/TESTING_AGENT_INSTRUCTIONS.md) (Patterns, execution)

## 🛑 Mandatory Definition of Done
**Work is NOT complete until BOTH commands pass:**
1. **Linting**: `./utils/quick_lint.sh --fix` (Zero tolerance for errors)
2. **Testing**: `python -m pytest tests/ -v --tb=line` (All tests must pass)

## 🏗️ Architectural Non-Negotiables
1. **Storage-Only (v4.2+)**: All entity data lives in `.storage/kidschores_data`. Config entry contains **only** system settings.
2. **Identity**: ALWAYS use `internal_id` (UUID) for logic/lookups. NEVER use entity names.
3. **Datetime**: Store ONLY UTC-aware ISO strings. Use `kc_helpers.parse_datetime_to_utc()`.
4. **Helpers**: 
   - `kc_helpers.py`: Shared logic, entity lookups, authorization.
   - `flow_helpers.py`: Config/Options flow schemas and validation.

## 💎 Code Quality Standards (Enforced)
- **Constants**: NO hardcoded strings. Use `const.py` patterns (`DATA_*`, `CONF_*`, `TRANS_KEY_*`).
- **Translations**: 
  - **Integration**: Use `translations/en.json` keys for exceptions/config flow.
  - **Dashboard**: Custom system via `translations/dashboard/*.json` (OUT OF SCOPE for standard HA translations).
- **Logging**: Lazy logging ONLY: `LOGGER.debug("Val: %s", var)`. NO f-strings in logs.
- **Typing**: 100% type hints required (args + return).

## 🧪 Testing Strategy
- **Mocking**: Always mock notifications: `patch.object(coordinator, "_notify_kid", new=AsyncMock())`.
- **Suppressions**: Use module-level pylint suppressions for test files (e.g., `protected-access`).
- **Data**: Use `tests/testdata_storyline_*.yaml` for consistent scenarios.
