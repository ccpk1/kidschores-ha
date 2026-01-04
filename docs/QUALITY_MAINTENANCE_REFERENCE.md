# Quality Maintenance Reference Guide

**Purpose**: Cross-reference between KidsChores code quality standards and Home Assistant's official AGENTS.md guidance.

**Last Updated**: January 4, 2026
**Integration Version**: 0.5.0
**Quality Level**: Silver (Certified)

---

## 📋 How to Use This Guide

When developing or reviewing code for KidsChores, use this guide to:

1. **Find relevant quality standards** - Locate which standards apply to your work
2. **Reference official guidance** - Get links to Home Assistant's authoritative AGENTS.md
3. **Check implementation status** - Verify KidsChores has already implemented each rule
4. **Review examples** - See code examples from KidsChores codebase

**Key Documents**:

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - KidsChores architecture and quality standards (NEW Section: Quality Standards & Maintenance Guide)
- **[CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md)** - Phase 0 Audit Framework and detailed review checklists
- **[AGENTS.md](../../core/AGENTS.md)** - Home Assistant's official integration quality guidance (authoritative source)
- **[quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml)** - Current rule implementation status

---

## 🎯 Silver Quality Scale Mapping

### AGENTS.md Sections → KidsChores Implementation

| HA Quality Rule            | AGENTS.md Section                   | KidsChores Status | Implementation File             | ARCHITECTURE.md Ref   |
| -------------------------- | ----------------------------------- | ----------------- | ------------------------------- | --------------------- |
| **Configuration Flow**     | Config Flow Patterns                | ✅ Done           | config_flow.py                  | Quality Standards § 1 |
| **Entity Unique IDs**      | Unique IDs                          | ✅ Done           | sensor.py, button.py, select.py | Quality Standards § 2 |
| **Service Actions**        | Service Registration Patterns       | ✅ Done           | services.py                     | Quality Standards § 3 |
| **Entity Unavailability**  | State Handling, Entity Availability | ✅ Done           | All entity classes              | Quality Standards § 4 |
| **Parallel Updates**       | Update Patterns                     | ✅ Done           | sensor.py (line ~40)            | Quality Standards § 5 |
| **Unavailability Logging** | Unavailability Logging              | ✅ Done           | coordinator.py                  | Quality Standards § 6 |

---

## 🔍 Code Quality Standards Mapping

### Type Hints (100% Required)

**HA Guidance**: [AGENTS.md § Python Requirements - Strict Typing](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ All functions have complete type hints (args + return)
- ✅ Properties include return type hints
- ✅ Use Python 3.10+ syntax (`str | None` not `Optional[str]`)
- ✅ Use modern dict syntax (`dict[str, Any]` not `Dict[str, Any]`)

**Example**:

```python
async def async_claim_chore(
    self,
    kid_id: str,
    chore_id: str,
) -> tuple[bool, str]:
    """Claim a chore for a kid."""
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Type Hints](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Lazy Logging (100% Required)

**HA Guidance**: [AGENTS.md § Logging](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ 100% compliance - zero f-strings in logging
- ✅ Always use `%s`, `%d` placeholders (lazy evaluation)
- ✅ Never evaluate in log calls (performance critical)

**Correct Pattern**:

```python
_LOGGER.debug("Processing chore for kid: %s", kid_name)
_LOGGER.info("Points adjusted for kid: %s to %s", kid_name, new_points)
```

**Wrong Pattern** (Never use):

```python
_LOGGER.debug(f"Processing {kid_name}")  # ❌ f-string evaluated even if log skipped
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Lazy Logging](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Constants for User-Facing Strings (100% Required)

**HA Guidance**: [AGENTS.md § Code Quality Standards](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ All user-facing strings stored in `const.py`
- ✅ Constants follow strict naming patterns:
  - `DATA_*` - Storage data keys
  - `CONF_*` - Configuration entry keys
  - `TRANS_KEY_*` - Translation keys
  - `CFOF_*` - Config flow input fields
  - `CFOP_ERROR_*` - Config flow error keys
  - etc. (see const.py for complete patterns)
- ✅ No hardcoded strings in error messages, labels, or notifications

**Correct Pattern**:

```python
# In const.py
TRANS_KEY_ERROR_KID_NOT_FOUND = "error_kid_not_found"

# In code
raise HomeAssistantError(
    translation_domain=const.DOMAIN,
    translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND,
    translation_placeholders={"kid_name": kid_name},
)
```

**Wrong Pattern** (Never use):

```python
raise HomeAssistantError(f"Kid {kid_name} not found")  # ❌ Hardcoded, not translatable
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Constants](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Exception Handling (Specific Exceptions Required)

**HA Guidance**: [AGENTS.md § Error Handling](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ Use most specific exception type available:
  - `ServiceValidationError` for user input errors
  - `HomeAssistantError` with translation_key for runtime errors
  - `UpdateFailed` for coordinator errors
  - `ConfigEntryAuthFailed` for auth issues
- ✅ Never use bare `except Exception:`
- ✅ Always chain exceptions with `from err`

**Correct Pattern**:

```python
try:
    data = await client.fetch_data()
except ApiConnectionError as err:
    raise HomeAssistantError("Connection failed") from err
except ApiAuthError as err:
    raise ConfigEntryAuthFailed("Auth expired") from err
```

**Wrong Pattern** (Never use):

```python
try:
    value = await sensor.read_value()
except Exception:  # ❌ Too broad
    _LOGGER.error("Failed")
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Exception Handling](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Docstrings (Required for All Public Functions)

**HA Guidance**: [AGENTS.md § Documentation Standards](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ All public methods have docstrings
- ✅ Module docstrings describe purpose and entity types
- ✅ Class docstrings explain when entities update
- ✅ Clear, descriptive language

**Example**:

```python
"""Platform for KidsChores sensor entities.

Provides 26 sensor types across 3 scopes:
- Kid Scope: Per-kid sensors (points, chores completed, badges)
- Parent Scope: Parent-specific sensors (N/A for sensors)
- System Scope: Global aggregation sensors (pending approvals)
"""

class KidPointsSensor(CoordinatorEntity, SensorEntity):
    """Sensor tracking a kid's current point balance.

    Updates whenever points change via:
    - Chore approvals (adds default_points)
    - Reward redemptions (subtracts cost)
    - Bonus applications (adds bonus_points)
    - Penalty applications (subtracts penalty_points)
    """
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Docstrings](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

## 🧪 Testing Standards Mapping

### Test Coverage (95%+ Required)

**HA Guidance**: [AGENTS.md § Testing Requirements](../../core/AGENTS.md)

**KidsChores Status**:

- ✅ 560/560 tests passing (100% baseline)
- ✅ 10 intentionally skipped (not counted)
- ✅ 95%+ code coverage across all modules
- ✅ All test categories covered:
  - Config flow tests (test_config_flow.py)
  - Options flow tests (test*options_flow*\*.py)
  - Coordinator tests (test_coordinator.py)
  - Service tests (test_services.py)
  - Workflow tests (test*workflow*\*.py)

**Test Validation Command**:

```bash
./utils/quick_lint.sh --fix    # Must pass with 9.5+/10
python -m pytest tests/ -v     # Must pass 560/560
```

**Reference**: [ARCHITECTURE.md § Testing Requirements](ARCHITECTURE.md#testing-requirements-95-coverage-required)

---

### Linting Standards (9.5+/10 Required)

**HA Guidance**: [AGENTS.md § Code Quality Standards](../../core/AGENTS.md)

**KidsChores Status**:

- ✅ Current score: 9.64/10
- ✅ Zero critical errors (Severity 4+)
- ✅ All files pass validation

**Linting Command**:

```bash
./utils/quick_lint.sh --fix
```

**Output Example**:

```
Your code has been rated at 9.64/10
All 50 files meet quality standards
✅ Ready to commit!
```

**Reference**: [ARCHITECTURE.md § Code Review Checklist - Testing Checks](ARCHITECTURE.md#code-review-checklist-before-committing)

---

## 📚 Section-by-Section Reference

### Configuration Flow

**HA Source**: [AGENTS.md § Configuration Flow](../../core/AGENTS.md)
**KidsChores**: [config_flow.py](../custom_components/kidschores/config_flow.py)
**Standards in ARCHITECTURE.md**: [Quality Standards § 1 - Configuration Flow](ARCHITECTURE.md#1-configuration-flow-)

**Key Points**:

- ✅ Multi-step dynamic flow
- ✅ User input validation
- ✅ Translation keys for errors
- ✅ Duplicate detection via unique IDs
- ✅ Storage separation (data vs options)

---

### Entity Development

**HA Source**: [AGENTS.md § Entity Development](../../core/AGENTS.md)
**KidsChores**: [sensor.py](../custom_components/kidschores/sensor.py), [button.py](../custom_components/kidschores/button.py)
**Standards in ARCHITECTURE.md**: [Entity Class Naming Standards](ARCHITECTURE.md#entity-class-naming-standards)

**Key Points**:

- ✅ Every entity has unique ID
- ✅ Has entity name enabled
- ✅ Device info properly set
- ✅ Translation keys for names
- ✅ State handling with None for unknown

---

### Services & Actions

**HA Source**: [AGENTS.md § Service Actions](../../core/AGENTS.md)
**KidsChores**: [services.py](../custom_components/kidschores/services.py)
**Standards in ARCHITECTURE.md**: [Quality Standards § 3 - Service Actions](ARCHITECTURE.md#3-service-actions-with-validation-)

**Key Points**:

- ✅ 17 services with validation
- ✅ ServiceValidationError for input
- ✅ HomeAssistantError with translation_key for runtime
- ✅ Config entry existence checks
- ✅ Proper exception chaining

---

### Coordinator Pattern

**HA Source**: [AGENTS.md § Data Update Coordinator](../../core/AGENTS.md)
**KidsChores**: [coordinator.py](../custom_components/kidschores/coordinator.py)
**Standards in ARCHITECTURE.md**: [Data Separation & Storage Architecture](ARCHITECTURE.md#data-separation)

**Key Pattern**:

```python
class KidsChoresDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        super().__init__(
            hass,
            logger=const.LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # ✅ Always pass config_entry
        )
```

---

## 🔗 Quick Links to Quality References

**Official HA Guidance**:

- [AGENTS.md](../../core/AGENTS.md) - Authoritative source for all quality standards

**KidsChores Documentation**:

- [ARCHITECTURE.md](ARCHITECTURE.md) - Complete architecture + quality standards (NEW)
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) - Phase 0 audit framework + review checklists
- [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) - Rule implementation status

**Implementation Files**:

- [const.py](../custom_components/kidschores/const.py) - All constants (2325+ lines)
- [config_flow.py](../custom_components/kidschores/config_flow.py) - Configuration flow
- [services.py](../custom_components/kidschores/services.py) - Service definitions
- [coordinator.py](../custom_components/kidschores/coordinator.py) - Core business logic

**Test References**:

- [tests/](../tests/) - 560+ tests covering all functionality
- [TESTING_AGENT_INSTRUCTIONS.md](../tests/TESTING_AGENT_INSTRUCTIONS.md) - Testing guidance

---

## ✅ Quality Checklist for Developers

Before submitting code, verify all items:

### Pre-Commit Checklist

- [ ] Read [ARCHITECTURE.md § Quality Standards & Maintenance Guide](ARCHITECTURE.md#quality-standards--maintenance-guide)
- [ ] Run `./utils/quick_lint.sh --fix` (must pass 9.5+/10)
- [ ] Run `python -m pytest tests/ -v --tb=line` (must pass)
- [ ] No f-strings in logging (lazy logging only)
- [ ] All user-facing strings in const.py (no hardcoded strings)
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] All exceptions are specific (no bare Exception)

### Code Review Checklist

- [ ] Exception handling uses proper types (ServiceValidationError, HomeAssistantError)
- [ ] Entity unique IDs follow pattern: `entry_id_{scope_id}{SUFFIX}`
- [ ] All entities implement `available` property
- [ ] Services have proper validation and error handling
- [ ] Translation keys reference entries in en.json
- [ ] Config flow validation uses CFOF*\* and CFOP_ERROR*\* constants

### Before Marking "Ready for Review"

- [ ] All linting passes (`./utils/quick_lint.sh --fix`)
- [ ] All tests pass (`python -m pytest tests/ -v`)
- [ ] Coverage maintained at 95%+
- [ ] No regressions in existing tests
- [ ] Commit message documents what changed and why

---

## 🎯 Relationship to Certification Levels

### Bronze (N/A - KidsChores targets Silver+)

Not applicable (KidsChores went directly to Silver)

### Silver ✅ (Certified)

**All requirements implemented and verified**:

- ✅ Configuration Flow
- ✅ Entity Unique IDs
- ✅ Service Actions with Validation
- ✅ Entity Unavailability Handling
- ✅ Parallel Updates
- ✅ Logging When Unavailable

### Gold (In Progress)

**Planned phases**:

- Phase 5A: Device Registry Integration (3-4h)
- Phase 6: Repair Framework (4-6h)
- Phase 7: Documentation Expansion (5-7h)

See [GOLD_CERTIFICATION_ROADMAP.md](in-process/GOLD_CERTIFICATION_ROADMAP.md) for details.

---

## 📝 Document Maintenance

This guide is maintained alongside the ARCHITECTURE.md document. When updating:

1. **Update both documents** if quality standards change
2. **Keep links current** (especially to AGENTS.md sections)
3. **Add examples from code** when illustrating standards
4. **Mark completion date** when new standards are implemented

**Last Updated**: January 4, 2026
**Maintained By**: KidsChores Development Team
