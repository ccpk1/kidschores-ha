# KidsChores Testing Suite

Welcome to the KidsChores Home Assistant integration testing suite! This comprehensive test framework validates the integration's functionality, including dashboard templates, business logic, and user workflows.

## 🌟 The Stårblüm Family

Our tests follow the adventures of the magical **Stårblüm Family**, who use the KidsChores integration to manage their household chores and earn rewards!

### Meet the Family

**Parents**:

- **Môm Astrid Stårblüm** (@Astrid) - The family organizer who approves chores and rewards
- **Dad Leo Stårblüm** (@Leo) - The fun parent who creates bonus opportunities

**Kids**:

- **Zoë Stårblüm** (Age 8, avatar: mdi:star-face) - The responsible oldest, loves earning badges
- **Max! Stårblüm** (Age 6, avatar: mdi:rocket) - The energetic middle child, always claiming chores
- **Lila Stårblüm** (Age 8, avatar: mdi:flower) - The creative twin, motivated by rewards

### Why Special Characters?

All names include special characters (å, ï, ë, ø, @, !) to ensure robust Unicode handling throughout the integration. This validates that the system works for international families with diverse naming conventions.

---

## 📚 Testing Philosophy

Our testing approach follows three key principles:

### 1. **User-Centric Testing**

Tests mirror real-world user workflows:

- Setup integration → Config flow
- Add entities → Options flow
- Interact with system → Services & UI
- View data → Dashboard templates

### 2. **Comprehensive Coverage**

Tests cover all entity types and workflows:

- **Entities**: Parents, kids, chores, badges, bonuses, penalties, rewards
- **Workflows**: Claim, approve, disapprove, reset, redeem, award
- **Features**: Recurring chores, shared chores, badge maintenance, reward approval

### 3. **Scenario-Based Data**

Tests use pre-built scenarios that tell a story:

- **Minimal**: Zoë's first week with simple chores
- **Medium**: Zoë and Max! learning to share chores
- **Full**: Complete family with badges, streaks, and advanced features

---

## 🎯 What We Test

### Config & Setup (8 tests)

- Initial integration setup via UI
- YAML configuration import
- Input validation and error handling
- Duplicate detection

### Coordinator Logic (12 tests)

- Chore lifecycle: claim → approve → reset
- Points calculation: base + bonuses - penalties
- Badge awards and maintenance
- Recurring chore scheduling
- Shared chore coordination

### Options Flow (9 tests)

- Adding entities: kids, chores, badges, etc.
- Editing entity properties
- Deleting entities with dependency checks
- Validation: unique names, point limits, required fields

### Services (5 tests)

- Chore services: `claim_chore`, `approve_chore`, etc.
- Points services: `adjust_points`, `apply_bonus`, `apply_penalty`
- Reward services: `redeem_reward`, `approve_reward`, etc.
- Badge services: `award_badge`, `remove_badge`
- Bulk operations: `reset_all_chores`, `reset_penalties`

### Dashboard Templates (17 tests)

- Jinja2 template rendering without errors
- Entity filtering and grouping
- Translation loading from backend
- State color mapping (green/orange/red/blue)
- Date handling with timezone awareness
- Empty state handling
- Complex multi-kid scenarios

### Workflow Tests (32 tests)

- Kid chore workflow: claim → approve → complete (11 tests)
- Parent penalty/bonus application (11 tests)
- Kid reward redemption: claim → approval (10 tests)

**Total: 78 tests (71 passing, 7 intentionally skipped) ✅**

**Test Success Rate**: 100% of non-skipped tests passing

---

## 🚀 Quick Start

### Run All Tests

```bash
cd /workspaces/kidschores-ha
python -m pytest tests/ -v
```

### Run Specific Category

```bash
# Dashboard tests only
python -m pytest tests/test_dashboard_templates.py -v

# Coordinator tests only
python -m pytest tests/test_coordinator.py -v
```

### Run Single Test

```bash
python -m pytest tests/test_dashboard_templates.py::TestDashboardWelcomeCard::test_welcome_card_renders -v
```

### Run with Coverage

```bash
python -m pytest tests/ --cov=custom_components.kidschores --cov-report=term-missing
```

---

## 📖 Documentation Structure

Our testing documentation is organized into focused guides:

### 1. [README.md](README.md) (This File)

**High-level overview**: Testing philosophy, family introduction, quick start

**Target Audience**: New contributors, code reviewers, stakeholders

**Contents**:

- Stårblüm Family introduction
- Testing philosophy
- What we test (summary)
- Quick start commands
- Documentation map

### 2. [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md)

**Comprehensive technical guide**: All test types, patterns, and best practices

**Target Audience**: Developers writing or modifying tests

**Contents**:

- Test structure and organization
- **Data loading methods** (options flow vs direct coordinator)
- Running tests (all options)
- Test categories (8 types with examples)
- **Dashboard template testing** (complete section)
- Test fixtures and scenarios
- Testing patterns (6 common patterns)
- Debugging tests
- Best practices

**Key Sections**:

- **Data Loading Methods**: Critical distinction between options flow (UI simulation) and direct coordinator loading (business logic)
- **Dashboard Template Testing**: Complete guide to Jinja2 template validation
- **Critical Patterns**: Platform reload, direct entity access, notification mocks, authorization

### 3. [TESTING_AGENT_INSTRUCTIONS.md](TESTING_AGENT_INSTRUCTIONS.md)

**AI agent guidance**: Step-by-step workflows and troubleshooting

**Target Audience**: AI agents, automated test generators

**Contents**:

- Quick reference commands
- Test processing workflow (4 steps)
- Critical patterns (6 essential patterns)
- Troubleshooting guide (common issues + solutions)
- Code quality standards (no lint errors/warnings)
- Lessons learned (10 key insights)
- Common errors and solutions
- Best practices checklist

**Key Sections**:

- **Test Processing Workflow**: Step-by-step guide for determining test type and data loading method
- **Troubleshooting Guide**: Solutions to common test failures
- **Lessons Learned**: 10 key insights from building the test suite (platform reload, service dispatcher, authorization, etc.)
- **Code Quality Standards**: Linting, naming, type hints, docstrings

### 4. [TEST_SCENARIOS.md](TEST_SCENARIOS.md)

**Test data scenarios**: Stårblüm Family storyline details

**Target Audience**: Test data authors, scenario designers

**Contents**:

- Stårblüm Family backstory
- Scenario descriptions (minimal, medium, full)
- Entity lists for each scenario
- Usage guide: loading YAML, using in tests
- When to use each scenario

---

## 🧪 Test Scenarios

We provide three pre-built test scenarios with the Stårblüm Family:

### Minimal Scenario

**File**: `testdata_scenario_minimal.yaml`

**Purpose**: Entry-level testing, basic workflows

**Contents**:

- 1 parent (Môm Astrid)
- 1 kid (Zoë)
- 2 chores (Feed the cåts, Pick up Lëgo!)
- 1 badge (Brønze Står)
- 1 bonus (Stär Sprïnkle Bonus)
- 1 penalty (Førget Chöre)
- 1 reward (Ice Créam!)

**Best For**: Config flow tests, basic service tests, simple coordinator logic

### Medium Scenario

**File**: `testdata_scenario_medium.yaml`

**Purpose**: Multi-kid coordination, shared chores

**Contents**:

- 2 parents (Môm Astrid, Dad Leo)
- 2 kids (Zoë, Max!)
- 4 chores (1 shared: Clëan Living Room)
- 2 badges (Brønze Står, Dåily Dëlight)
- 2 bonuses
- 2 penalties
- 2 rewards

**Best For**: Shared chore tests, multi-kid filtering, parent approval tests

### Full Scenario

**File**: `testdata_scenario_full.yaml`

**Purpose**: Complete feature set validation

**Contents**:

- 2 parents (Môm Astrid, Dad Leo)
- 3 kids (Zoë, Max!, Lila)
- 7 chores (3 recurring, 1 shared)
- 5 badges (3 cumulative with maintenance, 1 periodic, 1 daily)
- 2 bonuses
- 3 penalties
- 5 rewards
- Detailed progress tracking (streaks, badge progress, reward claims)

**Best For**: Badge maintenance tests, recurring chore tests, comprehensive dashboard tests

See [TEST_SCENARIOS.md](TEST_SCENARIOS.md) for full details.

---

## 🎓 Learning Path

New to the test suite? Follow this learning path:

### Step 1: Read the Overview (You're Here!)

- Understand testing philosophy
- Meet the Stårblüm Family
- Learn what we test

### Step 2: Run Tests

```bash
python -m pytest tests/ -v
```

Watch all 46 tests pass, understand test categories

### Step 3: Study One Test File

Start with `test_dashboard_templates.py` (simplest):

- Read test structure
- Understand fixtures (`dashboard_entities`)
- See template rendering pattern

### Step 4: Read Technical Guide

Open [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md):

- **CRITICAL**: Read "Data Loading Methods" section first!
- Understand options flow vs direct coordinator loading
- Study dashboard template testing
- Learn test patterns and fixtures

### Step 5: Write Your First Test

Modify an existing test or add new one:

```python
async def test_my_feature(hass, scenario_minimal):
    """Test my new feature."""
    config_entry, name_to_id_map = scenario_minimal
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Get entity IDs from map
    kid_id = name_to_id_map["kid:Zoë"]

    # Execute action
    # Verify result
```

### Step 6: Deep Dive

- Explore coordinator tests for complex logic
- Study workflow tests for entity interaction patterns
- Review dashboard tests for template techniques

### Step 7: AI Agent Development (Optional)

If developing tests with AI assistance, read [TESTING_AGENT_INSTRUCTIONS.md](TESTING_AGENT_INSTRUCTIONS.md):

- Test processing workflow (4-step decision tree)
- Critical patterns (platform reload, direct entity access, notification mocking)
- Troubleshooting guide (6 common issues with solutions)
- Code quality standards (no linting errors/warnings)
- **Lessons Learned** (10 key insights from building test suite)

---

## 🔍 Key Testing Concepts

### Data Loading Methods (CRITICAL)

**Two methods for loading test data - use the right one!**

#### Options Flow (UI Simulation)

**When**: Testing user interactions, input validation, UI workflows

**Example**: `test_options_flow.py`, `test_config_flow.py`

```python
# Add kid via options flow
result = await hass.config_entries.options.async_init(config_entry.entry_id)
result = await hass.config_entries.options.async_configure(
    result["flow_id"], user_input={"next_step": "add_kid"}
)
result = await hass.config_entries.options.async_configure(
    result["flow_id"], user_input={"name": "Zoë Stårblüm", "age": 8}
)
```

#### Direct Coordinator Loading (Business Logic)

**When**: Testing workflows, state transitions, business logic

**Example**: `test_workflow_*.py`, `test_coordinator.py`, `test_services.py`

```python
# Load scenario data directly into coordinator
async def test_workflow(hass, scenario_minimal):
    config_entry, name_to_id_map = scenario_minimal
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Entities already loaded from YAML scenario
    kid_id = name_to_id_map["kid:Zoë"]
    chore_id = name_to_id_map["chore:Feed the cåts"]
```

**Critical**: After direct loading, entity platforms must be reloaded (done automatically by `scenario_minimal` fixture).

See [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md) "Data Loading Methods" for complete comparison.

### Dashboard Templates

Dashboard templates use Jinja2 to render kid-specific cards. Tests validate:

- Template syntax (no errors)
- Entity filtering (correct kid's data)
- Translation loading (from backend helper sensor)
- State colors (green/orange/red/blue)
- Empty state handling (graceful fallbacks)

See [TESTING_TECHNICAL_GUIDE.md](TESTING_TECHNICAL_GUIDE.md) "Dashboard Template Testing" for complete guide.

---

## 🛠️ Common Commands

### Development

```bash
# Run tests with auto-rerun on changes
python -m pytest tests/ -v --looponfail

# Run specific test pattern
python -m pytest tests/ -k "dashboard" -v

# Stop on first failure
python -m pytest tests/ -x

# Show print statements
python -m pytest tests/ -v -s
```

### Debugging

```bash
# Run with debug logging
python -m pytest tests/ -v --log-cli-level=DEBUG

# Run single test with full output
python -m pytest tests/test_coordinator.py::test_claim_chore -vv --tb=short

# Show test duration
python -m pytest tests/ -v --durations=10
```

### Coverage

```bash
# Generate HTML coverage report
python -m pytest tests/ --cov=custom_components.kidschores --cov-report=html

# Open report
open htmlcov/index.html
```

---

## 🤝 Contributing Tests

### Before Adding Tests

1. **Check existing tests** - Avoid duplicates
2. **Use options flow** - Enter data realistically
3. **Follow naming conventions** - `test_<feature>_<action>_<expected_result>`
4. **Use scenarios** - Load from YAML when possible

### Test Structure

```python
async def test_feature_name(hass, config_entry):
    """Test description: what this test validates."""
    # Arrange: Set up data via options flow
    # Act: Execute service or call coordinator method
    # Assert: Verify expected state changes
```

### Running Your Tests

```bash
# Run your new test
python -m pytest tests/test_your_file.py::test_your_function -v

# Run all tests to ensure no regressions
python -m pytest tests/ -v
```

### Documentation

If your test introduces new patterns:

1. Update [TESTING_INSTRUCTIONS.md](TESTING_INSTRUCTIONS.md) with pattern
2. Add example to relevant section
3. Update test count in this README

---

## 📊 Test Coverage

Current coverage: **~95%** of integration code

**Well-Covered**:

- ✅ Config flow (100%)
- ✅ Options flow (98%)
- ✅ Coordinator logic (96%)
- ✅ Dashboard templates (100% syntax validation)
- ✅ Services (94%)

**Areas for Improvement**:

- ⚠️ Notification action handlers (edge cases)
- ⚠️ Storage migration (version upgrades)
- ⚠️ Error recovery (network failures)

---

## 🐛 Debugging Tests

### Test Fails

1. **Read the traceback** - Error location + message
2. **Check assumptions** - Did options flow complete?
3. **Print coordinator state** - `print(json.dumps(coordinator.data, indent=2))`
4. **Enable debug logging** - See fixture in conftest.py
5. **Run in isolation** - `-k "test_name"` to avoid test pollution

### Dashboard Template Fails

1. **Check entity_id** - Does dashboard helper sensor exist?
2. **Check attributes** - Is data populated in sensor?
3. **Test snippet in HA UI** - Developer Tools → Templates
4. **Print template output** - Add debug prints in test

See [TESTING_INSTRUCTIONS.md](TESTING_INSTRUCTIONS.md) "Debugging Tests" section for more techniques.

---

## 📅 Version History

- **v1.0.0** (Dec 2024): Initial test suite with 46 tests
  - Config flow tests (8)
  - Coordinator tests (12)
  - Options flow tests (9)
  - Service tests (5)
  - Dashboard template tests (17)
  - Stårblüm Family scenarios (3)
  - Comprehensive documentation

---

## 📚 Additional Resources

- **Integration README**: `../README.md` - Integration overview and features
- **Code**: `../custom_components/kidschores/` - Integration source code
- **Documentation**: `../README.md` - User-facing documentation

**External Links**:

- [pytest Documentation](https://docs.pytest.org/) - Official pytest docs
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing) - HA testing guidelines
- [Jinja2 Templates](https://jinja.palletsprojects.com/) - Template syntax reference

---

## ❓ FAQ

**Q: Why "Stårblüm Family"?**
A: Special characters ensure robust Unicode handling. The magical theme makes tests fun!

**Q: Do I need to use options flow?**
A: Yes! It's critical for realistic tests that mirror user workflows.

**Q: Can I skip dashboard tests?**
A: No - dashboard tests catch template syntax errors before runtime.

**Q: How do I add a new scenario?**
A: Copy `testdata_scenario_minimal.yaml`, modify, document in `TEST_SCENARIOS.md`.

**Q: Tests are slow - how to speed up?**
A: Use minimal scenario, run specific test file, use `-x` flag to stop on first failure.

**Q: Test passes locally but fails in CI?**
A: Check timezone handling (use UTC), async contexts, file paths.

---

**Happy Testing! 🎉**

The Stårblüm Family thanks you for keeping the KidsChores integration bug-free and reliable!

```sh
python -m pytest tests/test_services.py -k test_service_apply_bonus_and_penalty
```

## More Information

- See the main repository README for integration details.
- For Home Assistant test best practices, see the [Home Assistant developer docs](https://developers.home-assistant.io/docs/development_testing/).
