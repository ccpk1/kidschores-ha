# KidsChores HA Integration - Agent Guide

**Version**: v0.5.0+ (Platinum Quality, Storage-Only Architecture)

**Platinum Quality** = 100% type hints + docstrings on all public methods + 95%+ test coverage + strict typing.

## 📚 Documentation Hierarchy

Read **only** what you need for your task:

- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - Data model, storage, versioning
- **[DEVELOPMENT_STANDARDS.md](../docs/DEVELOPMENT_STANDARDS.md)** - How to code (constants, logging, types, translations)
- **[QUALITY_REFERENCE.md](../docs/QUALITY_REFERENCE.md)** - Details on platinum quality requirements
- **[CODE_REVIEW_GUIDE.md](../docs/CODE_REVIEW_GUIDE.md)** - Phase 0 audit framework for reviewing code
- **[AGENT_TESTING_USAGE_GUIDE.md](../tests/AGENT_TESTING_USAGE_GUIDE.md)** - Test validation & debugging

## 🛑 Definition of Done (Non-Negotiable)

**Nothing is complete until ALL THREE pass**:

```bash
./utils/quick_lint.sh --fix    # Must pass (9.5+/10)
mypy custom_components/kidschores/  # Zero errors required
python -m pytest tests/ -v --tb=line  # All tests pass
```

**Error Recovery**: If `mypy` fails more than twice on the same error, STOP and ask for clarification. Do NOT suppress with `# type: ignore`.

## ⚡ Core Principles (Follow These First)

### 1. No Hardcoded Strings

**ALL** user-facing text → `const.py` constants → `translations/en.json`

- Exceptions: `translation_domain=const.DOMAIN, translation_key=const.TRANS_KEY_*`
- Notifications: `TRANS_KEY_NOTIF_TITLE_*` / `TRANS_KEY_NOTIF_MESSAGE_*`
- Config flow errors: `CFOP_ERROR_*` → `TRANS_KEY_CFOF_*`

### 2. Identity = UUID Only

Use `internal_id` (UUID) for logic. **NEVER** use entity names for lookups.

### 3. Storage-Only Model

Entity data → `.storage/kidschores_data` (schema v42+)
Config entry → **9 system settings only** (points theme, intervals, retention)

**Details**: See [ARCHITECTURE.md § Data Architecture](../docs/ARCHITECTURE.md#data-architecture) for storage structure, system settings breakdown, and reload performance comparisons.

### 4. Type Hints Mandatory

100% coverage enforced by MyPy in CI/CD. Modern syntax: `str | None` not `Optional[str]`

**Type System Strategy** (See [ARCHITECTURE.md § Type System Architecture](../docs/ARCHITECTURE.md#type-system-architecture)):
- **TypedDict**: Static structures with fixed keys (entity definitions, config objects)
- **dict[str, Any]**: Dynamic structures accessed with variable keys (runtime-built data)
- **Goal**: Achieve zero mypy errors without type suppressions by matching types to actual code patterns

### 5. Lazy Logging Only

```python
const.LOGGER.debug("Value: %s", var)  # ✅ Correct
const.LOGGER.debug(f"Value: {var}")   # ❌ NEVER f-strings in logs
```

## 🎯 Fast Implementation Strategy

### Before Writing Code

1. Check if helper exists: `kc_helpers.py` (lookups), `flow_helpers.py` (validation)
2. Find constant: `grep TRANS_KEY custom_components/kidschores/const.py`
3. Use test scenario: `scenario_medium` (most common), `scenario_full` (complex)

### While Writing Code

- Copy patterns from existing files (don't invent new patterns)
- **Consolidate duplicates**: If code appears 2+ times, extract to helper function
- **Verify coordinator methods**: When editing `coordinator.py`, search file FIRST to verify method exists. Never assume methods exist by name.
- Use `conftest.py` helpers: `get_kid_by_name()`, `construct_entity_id()`
- Mock notifications: `patch.object(coordinator, "_notify_kid", new=AsyncMock())`

### After Writing Code

Run quality gates (**in this order**):

1. `./utils/quick_lint.sh --fix` (catches most issues fast)
2. `mypy custom_components/kidschores/` (type errors)
3. `python -m pytest tests/ -v` (validates behavior)

## 🚫 Common Mistakes (Avoid These)

❌ Hardcoded strings → ✅ Use `const.TRANS_KEY_*`
❌ `Optional[str]` → ✅ Use `str | None`
❌ F-strings in logs → ✅ Use lazy logging `%s`
❌ Entity names for lookups → ✅ Use `internal_id`
❌ Touching `config_entry.data` → ✅ Use `.storage/kidschores_data`
❌ Direct storage writes → ✅ Use `coordinator._persist()`

## 📦 Quick Reference

**Key Files**:

- `const.py` (2565 lines) - All constants
- `coordinator.py` (8987 lines) - Business logic
- `kc_helpers.py` - Shared utilities
- `translations/en.json` - Master translation file

**Constant Naming Patterns** (See [DEVELOPMENT_STANDARDS.md § 3. Constant Naming Standards](../docs/DEVELOPMENT_STANDARDS.md#3-constant-naming-standards)):
- `DATA_*` = Storage keys (singular entity names)
- `CFOF_*` = Config/Options flow input fields (plural with `_INPUT_`)
- `CONF_*` = System settings in config_entry.options (9 settings only)
- `TRANS_KEY_*` = Translation identifiers
- `ATTR_*` = Entity state attributes
- `SERVICE_*` / `SERVICE_FIELD_*` = Service actions and parameters

**DateTime Functions** (See [DEVELOPMENT_STANDARDS.md § 4. DateTime & Scheduling Standards](../docs/DEVELOPMENT_STANDARDS.md#4-datetime--scheduling-standards)):
- ALWAYS use `dt_*` helpers from `kc_helpers.py` (never raw `datetime` module)
- Examples: `dt_now_iso()`, `dt_parse()`, `dt_add_interval()`, `dt_next_schedule()`

**Common Test Scenarios** (run after making changes):

```bash
pytest tests/test_workflow_*.py -v  # Entity state validation
pytest tests/test_config_flow.py -v  # UI flow changes
pytest tests/ -x  # Stop on first failure (debugging)
```

**Datetime**: Always UTC-aware ISO strings. Use `kc_helpers.dt_to_utc()`

---

**Agent Tip**: When stuck, run `./utils/quick_lint.sh --fix` first. It catches 80% of issues instantly.
