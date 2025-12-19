# Test Plan: Coordinator Refactoring & Coverage Expansion

**Document**: Test strategy for KidsChores coordinator refactoring  
**Created**: December 18, 2025  
**Scope**: Build 127+ test cases to achieve 70%+ coordinator coverage  
**Target Release**: v0.5.0  
**Related Docs**: [COORDINATOR_CODE_REVIEW.md](COORDINATOR_CODE_REVIEW.md), [COORDINATOR_REVIEW_IMPROVEMENTS.md](COORDINATOR_REVIEW_IMPROVEMENTS.md)

---

## Test Plan Overview

### Vision

Transform coordinator from **39% coverage (untested critical paths)** → **70%+ coverage (production-ready)** by implementing:
- **Badge System Tests** (80+ scenarios): 0% → 85% coverage on 2,360 lines
- **Migration Tests** (27 scenarios): 0% → 70% coverage on 760 lines  
- **Integration Tests** (15+ scenarios): Coordinator-wide workflows and edge cases

### Success Criteria

All of the following must pass:
1. ✅ **Coverage Targets**: 70%+ overall, 85%+ badges, 70%+ migrations
2. ✅ **Test Count**: 150+ new tests created and passing
3. ✅ **Critical Issues Validated**: All 7 KC-COORD issues have test coverage
4. ✅ **No Regressions**: Existing 150 tests still pass (356 total passing)
5. ✅ **Code Quality**: Zero linting errors, type hints on all test functions
6. ✅ **Documentation**: Each test has docstring explaining what it validates
7. ✅ **Idempotency**: Migration tests can re-run without side effects
8. ✅ **Performance**: Coordinator update < 100ms under test load

---

## Entry Criteria (Prerequisites)

Before beginning test implementation, complete these:

- [ ] **KC-COORD-002 & KC-COORD-003 fixes merged** (datetime migration, period stats merge)
- [ ] **Phase 4 badge audit complete** (state machines, handlers documented)
- [ ] **Test fixtures available** (conftest.py with kid/chore/badge factories)
- [ ] **Storage layer stable** (schema v41+ migrations tested)
- [ ] **CI/CD pipeline supports 350+ tests** (verify test suite runtime < 15 sec)
- [ ] **Team capacity confirmed** (test engineer(s) assigned)

---

## Test Suite Architecture

### File Structure

```
tests/
├── test_coordinator.py                    (existing, 5 tests, keep intact)
├── test_coordinator_badges.py             (NEW, 80+ badge tests)
├── test_coordinator_migrations.py         (NEW, 27 migration tests)
├── test_coordinator_integration.py        (NEW, 15 integration tests)
├── conftest.py                            (existing, update with new fixtures)
├── fixtures/
│   ├── coordinator_fixtures.py            (NEW, badge/migration factories)
│   ├── scenario_data.yaml                 (NEW, test data scenarios)
│   └── migration_scenarios.yaml           (NEW, KC 3.x legacy data)
└── README_TEST_PLAN.md                    (NEW, this plan in detail)
```

### Test Suite Categorization

| Suite | File | Tests | Coverage | Effort | Priority |
|-------|------|-------|----------|--------|----------|
| **Badge System** | `test_coordinator_badges.py` | 80+ | 0% → 85% (2,360 lines) | 20-24 hrs | 🔴 CRITICAL |
| **Migrations** | `test_coordinator_migrations.py` | 27 | 0% → 70% (760 lines) | 10-12 hrs | �� CRITICAL |
| **Integration** | `test_coordinator_integration.py` | 15 | 39% → 70% overall | 6-8 hrs | 🟡 HIGH |
| **Existing** | `test_coordinator.py` | 5 | Maintain | 0 hrs | ✅ Keep |
| **TOTAL** | — | **127+** | — | **36-44 hrs** | — |

---

## Test Suite 1: Badge System Tests (80+ tests, 20-24 hours)

**File**: `tests/test_coordinator_badges.py`  
**Purpose**: Validate badge award logic, state transitions, recurring resets, and persistence  
**Coverage Target**: 2,360 lines → 85%+ (1,950+ lines)

### Test Scenario Matrix

#### A. Core Badge Workflow (15 tests, 4-5 hours)

**A1. Daily Badge: Points Accumulation → Award**
```python
@pytest.mark.asyncio
async def test_badge_daily_points_accumulation_awards_at_threshold(hass, coordinator, scenario_data):
    """
    Validate: Kid accumulates 50 points in one day → daily badge awarded
    
    Scenario:
    1. Create daily badge (target: points, threshold: 50, recurring: daily)
    2. Kid claims 3 chores (20 pts each = 60 pts total in ONE day)
    3. Coordinator processes badge evaluation
    
    Expected:
    - Badge entry created in badges_earned
    - Notification sent to kid
    - Kid's badge_progress updated with today's date
    """
```

**A2. Daily Badge: Zero Points → No Award**
- Validate: Zero points in a day → badge not awarded

**A3. Daily Badge: Below Threshold → No Award**
- Validate: 45 points in a day (threshold 50) → not awarded

**A4. Daily Badge: Exact Threshold → Award**
- Validate: Exactly 50 points → awarded

**A5. Daily Badge: Reset at Midnight**
- Validate: Daily badge resets progress at midnight

**A6-A15**: Similar patterns for:
- Weekly badge recurring (reset on Monday)
- Monthly badge recurring (reset on 1st)
- Custom interval badge (reset on user-defined day)
- Multiple daily badges (independent counters per badge)
- Mid-cycle badge creation
- Orphan badge cleanup
- Badge with multiple kids (isolation)

#### B. Cumulative Badge State Machine (12 tests, 5-6 hours)

**B1. Cumulative Badge: Bronze Promotion**
- Validate: Cumulative badge Bronze tier awarded at point threshold

**B2. Cumulative Badge: Silver Promotion**
- Validate: Bronze (100 pts) → Silver (300 pts)

**B3. Cumulative Badge: Gold Promotion**
- Validate: Silver (300 pts) → Gold (500 pts)

**B4. Cumulative Badge: Grace Period (No Demotion)**
- Validate: After promotion, grace period prevents demotion for 30 days

**B5. Cumulative Badge: Demotion After Grace Period**
- Validate: After grace period expires, demotion happens if points insufficient

**B6-B12**: Similar patterns for:
- Points regained within grace (stays Silver)
- Multiple demotions (Gold → Silver → Bronze)
- Multiple promotions back (Bronze → Silver → Gold)
- Edge-case: Exactly at threshold boundary
- Grace period customization (15 days, 60 days)
- Points spent (penalty impact on tier)
- Tier advancement history tracking

#### C. Streak Badge (10 tests, 3-4 hours)

**C1. Streak Badge: 10 Consecutive Days Award**
- Validate: Completing 10 chores per day for 10 consecutive days → streak badge awarded

**C2. Streak Badge: Break at Day 9 (No Award)**
- Validate: 8 days complete, day 9 zero chores → streak broken, reset to 0

**C3. Streak Badge: Reset After Award**
- Validate: After streak awarded, counter resets for next streak

**C4-C10**: Similar patterns for:
- Variable streak lengths (5, 20, 30 days)
- Mid-streak customization (change min chores/day)
- Timezone transitions (DST break)
- Leap years (Feb 28→29)
- Multiple kid streaks (independence)
- Partial day completion handling

#### D. Achievement/Challenge-Linked Badges (8 tests, 2-3 hours)

**D1. Achievement Badge: Auto-Award on Milestone**
- Validate: When kid completes achievement, linked badge auto-awarded

**D2. Challenge Badge: Award on Completion**
- Similar to D1, but for challenge completion

**D3-D8**: Similar patterns for:
- Multiple achievements linking same badge
- Challenge with custom completion criteria
- Partial achievement progress tracking
- Achievement history preservation

#### E. Edge Cases & Error Handling (20 tests, 5-6 hours)

**E1. Badge: Multiple Conditions Same Kid (Independence)**
- Validate: Kid with 5 different badge conditions → each evaluated independently

**E2. Badge: Orphan Badge Cleanup**
- Validate: When badge definition deleted, orphan entries cleaned up

**E3. Badge: Persistence Across Coordinator Restart**
- Validate: Badge progress persisted to storage, survives coordinator restart

**E4-E20**: Similar patterns for:
- DST transitions (spring/fall)
- Leap year Feb 28/29 transitions
- Timezone changes (UTC to EST)
- Null/empty badge data handling
- Invalid threshold values (negative, zero, string)
- Concurrent badge updates (race condition simulation)
- Storage corruption recovery
- Badge with no kids assigned
- Very large point values (overflow check)
- Badge config during active cycle (add/remove target)

#### F. Performance & Stress Tests (10 tests, 2-3 hours)

**F1. Badge Performance: 50 Kids, 20 Badges Each**
- Validate: Coordinator badge evaluation completes < 100ms under load

**F2-F10**: Similar patterns for:
- 100 kids, 10 badges each
- 1,000 badge progress entries per kid
- Concurrent updates (simulated race)
- Storage I/O during badge evaluation
- Memory usage under large dataset

---

## Test Suite 2: Migration Tests (27 tests, 10-12 hours)

**File**: `tests/test_coordinator_migrations.py`  
**Purpose**: Validate KC 3.x → KC 4.0+ data transformations, idempotency, and data integrity  
**Coverage Target**: 760 lines → 70%+ (530+ lines)

### Test Scenario Matrix

#### A. Datetime Migration (6 tests, 2 hours)

**A1. Migrate DateTime: String to UTC**
- Validate: Legacy string datetime → UTC-aware Python datetime

**A2. Migrate DateTime: Naive to UTC**
- Validate: Naive datetime (no TZ) → UTC-aware

**A3. Migrate DateTime: Already UTC (Passthrough)**
- Validate: UTC datetime unchanged

**A4. Migrate DateTime: Timezone Conversion (EST→UTC)**
- Validate: EST datetime converted to UTC (3-hour offset applied)

**A5. Migrate DateTime: Invalid Format Handling**
- Validate: Malformed datetime string → logged, not migrated

**A6. Migrate DateTime: Nested Fields (All 5 fields)**
- Validate: All 5 kid_chore datetime fields migrated

#### B. Badge Migration (7 tests, 3 hours)

**B1. Migrate Badge: Chore Count → Points Target**
- Validate: Legacy badge (chore_count: 50) → points target

**B2. Migrate Badge: Structure Modernization (Add Missing Fields)**
- Validate: Legacy badge missing new v4.0 fields added with defaults

**B3. Migrate Badge: Award Type Mapping**
- Validate: Legacy award_type enum → new badge type system

**B4. Migrate Badge: Progress Initialization**
- Validate: Legacy badge_earned entries converted to new structure

**B5. Migrate Badge: Orphan ID Cleanup**
- Validate: Badge IDs not matching current badge definitions logged as orphans

**B6-B7**: Similar patterns for:
- Multiple badge transitions per kid
- Badge deletion during migration
- Empty/null badge data

#### C. Kid Chore Data Migration (6 tests, 2-3 hours)

**C1. Migrate Kid Chore Data: Streak Preservation**
- Validate: Legacy streak tracking → new period-based stats

**C2. Migrate Kid Chore Data: Points Preservation**
- Validate: Legacy point counts moved to period_stats

**C3. Migrate Kid Chore Data: Chore-Specific Overrides**
- Validate: Legacy chore point multipliers moved correctly

**C4-C6**: Similar patterns for:
- Last completed date migrations
- Approval history preservation
- Multiple kids independence

#### D. Point Stats Migration (5 tests, 2 hours)

**D1. Migrate Point Stats: Data Merge (Not Loss)**
- Validate: KC-COORD-003 fix → Legacy point stats merged, not skipped

**D2. Migrate Point Stats: Empty Legacy Data**
- Validate: Empty legacy stats (all zeros) → no merge needed

**D3. Migrate Point Stats: Conflict Resolution (Existing Wins)**
- Validate: When both legacy and current have data, current value preserved

**D4-D5**: Similar patterns for:
- Multiple period overlaps
- Partial period migrations

#### E. Migration Idempotency (3 tests, 1-2 hours)

**E1. Migrate Idempotency: Run Twice = Same Result**
- Validate: Running migration twice produces identical result

**E2. Migrate Idempotency: No Duplicate IDs**
- Validate: KC-COORD-004 fix → No random ID collisions on re-run

**E3. Migrate Idempotency: Storage State Consistent**
- Validate: After migration re-run, storage.yaml integrity maintained

---

## Test Suite 3: Integration Tests (15+ tests, 6-8 hours)

**File**: `tests/test_coordinator_integration.py`  
**Purpose**: Validate coordinator workflows combining multiple components  
**Coverage Target**: Overall 39% → 70% (5,000+ additional lines)

### Test Scenario Matrix

#### A. Chore Lifecycle (6 tests, 2-3 hours)

**A1. Chore Lifecycle: Claim → Approve → Badge Award**
- End-to-end: Kid claims chore → parent approves → points awarded → badge conditions checked

**A2. Chore Lifecycle: Disapprove**
- Validate: Disapproved chore → no points, no badge progress

**A3-A6**: Similar patterns for:
- Recurring chore auto-reset
- Streak counter reset on overdue
- Multiple parent approvals (shared chore)
- Penalty application on disapproval

#### B. Badge + Points Interaction (5 tests, 2-3 hours)

**B1. Badge Award Triggers Bonus Points**
- Validate: Badge award includes bonus points configured

**B2-B5**: Similar patterns for:
- Tier promotion bonus
- Multiple badge awards same day (bonus stacking)
- Penalty deduction before badge check
- Points spent (penalty) prevents badge demotion

#### C. Recurring Schedules (3 tests, 1-2 hours)

**C1. Daily Reset: Midnight Trigger**
- Validate: All daily resets (chores, badges, stats) trigger at midnight

**C2-C3**: Similar patterns for:
- Weekly reset (Monday)
- Monthly reset (1st of month)

#### D. Error Recovery & Edge Cases (5 tests, 1-2 hours)

**D1. Corrupt Storage Recovery**
- Validate: Missing/malformed kid data → logged, coordinator recovers

**D2-D5**: Similar patterns for:
- Concurrent updates (race condition handling)
- Timezone transition (DST)
- Very large datasets (50+ kids, 100+ chores)
- Network failure simulation

---

## Critical Issues Validation Tests (15 tests, across all suites)

Each Critical Issue (KC-COORD-001 through KC-COORD-007) must have dedicated test coverage:

### KC-COORD-001: Badge Test Coverage
- **Covered By**: All 80+ badge tests in Suite 1
- **Acceptance**: ≥ 1,950 lines covered (85% of 2,360)

### KC-COORD-002: Datetime Migration Complete
- **Test**: `test_migrate_datetime_all_nested_fields_in_kid_chore()` (Suite 2-A6)
- **Validates**: All 5 datetime fields migrated correctly

### KC-COORD-003: Period Stats No Data Loss
- **Test**: `test_migrate_point_stats_merge_not_loss()` (Suite 2-D1)
- **Validates**: Legacy stats merged, not skipped

### KC-COORD-004: Orphan ID Prevention
- **Tests**: 
  - `test_migrate_badge_orphan_id_detection_and_log()` (Suite 2-B5)
  - `test_migrate_idempotent_no_duplicate_ids_generated()` (Suite 2-E2)
- **Validates**: No random IDs, deterministic hash used

### KC-COORD-005: Migration Execution Order
- **Test**: `test_migrate_datetime_all_nested_fields_in_kid_chore()` (Suite 2-A6)
- **Validates**: Nested datetimes converted correctly

### KC-COORD-006: Badge Performance
- **Tests**: `test_badge_performance_*` (Suite 1-F)
- **Validates**: < 100ms coordinator update under load

### KC-COORD-007: Handler Code Duplication
- **Tests**: 
  - `test_badge_daily_reset_at_midnight()` (Suite 1-B5)
  - `test_badge_streak_consecutive_days_awards()` (Suite 1-C1)
- **Validates**: Both handlers work correctly after refactoring

---

## Test Data & Fixtures

### Fixture Strategy

**`conftest.py` additions**:

```python
@pytest.fixture
async def coordinator_with_kids_and_chores(hass, mock_config_entry):
    """Coordinator with 3 kids, 6 chores pre-configured"""
    # Setup returns coordinator + test data dict
    
@pytest.fixture
def legacy_data():
    """KC 3.x format storage (old badge structure, old datetime format)"""
    # YAML fixture with 10 kids, 5 chores, 3 badges in legacy format
    
@pytest.fixture
def scenario_data():
    """Pre-configured test scenarios (daily badge, streak badge, cumulative badge)"""
    # Dictionary with badge configs, kids, test expectations
```

### Test Data Factories

**`fixtures/coordinator_fixtures.py`** (new):

```python
class KidFactory:
    """Generate test kid with configurable properties"""
    @staticmethod
    def create(name="TestKid", points=0, badges=None):
        return {
            "internal_id": uuid4(),
            "name": name,
            "all_time_points": points,
            "badges_earned": badges or [],
            ...
        }

class ChoreFactory:
    """Generate test chore with configurable properties"""
    @staticmethod
    def create(name="TestChore", points=20, recurring=False):
        return {...}

class BadgeFactory:
    """Generate test badge with configurable properties"""
    @staticmethod
    def create(badge_type="daily", target="points", threshold=50):
        return {...}
```

---

## Test Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2, 4-6 hours)

1. **Create test files & fixtures** (2 hours)
2. **Implement Badge Suite A tests** (4 hours)
3. **Run: pytest tests/test_coordinator_badges.py -v** (baseline)

### Phase 2: Badge Coverage (Weeks 2-3, 12-14 hours)

4. **Implement Badge Suite B-F tests** (12-14 hours)
5. **Verify badge coverage**: `pytest --cov=coordinator.py tests/test_coordinator_badges.py`

### Phase 3: Migration Coverage (Weeks 3-4, 10-12 hours)

6. **Implement Migration Suite A-E tests** (10-12 hours)
7. **Verify migration coverage**: `pytest --cov=coordinator.py tests/test_coordinator_migrations.py`

### Phase 4: Integration & Final (Weeks 4-5, 6-8 hours)

8. **Implement Integration Suite tests** (6-8 hours)
9. **Final verification** (1-2 hours)

### Phase 5: Code Review & Release (Week 5, 2-3 hours)

10. **Code review**: Review with 1+ team member
11. **Merge to main**: After review approval

---

## Success Criteria (Acceptance)

### Coverage Metrics

- [ ] **Overall Coordinator**: 70%+ (6,014+ lines of 8,591 covered)
- [ ] **Badge System**: 85%+ (1,950+ lines of 2,360 covered)
- [ ] **Migration Functions**: 70%+ (530+ lines of 760 covered)
- [ ] **test_coordinator.py**: Existing 5 tests still pass (100%)

### Test Count & Quality

- [ ] **Badge Tests**: 80+ created, 100% passing
- [ ] **Migration Tests**: 27 created, 100% passing
- [ ] **Integration Tests**: 15+ created, 100% passing
- [ ] **Total**: 127+ new tests, 150+ tests overall
- [ ] **Linting**: Zero critical errors, `pylint tests/` score ≥ 9.0/10
- [ ] **Type Hints**: 100% of test functions have type hints (params + return)
- [ ] **Docstrings**: 100% of tests have docstring explaining scenario

### Critical Issues Validation

- [ ] **KC-COORD-001** (Badge Coverage): Covered by 80+ tests
- [ ] **KC-COORD-002** (Datetime): Specific test validating fix
- [ ] **KC-COORD-003** (Period Stats): Specific test validating merge
- [ ] **KC-COORD-004** (Orphan IDs): Specific test validating deterministic IDs
- [ ] **KC-COORD-005** (Migration Order): Specific test validating nested datetimes
- [ ] **KC-COORD-006** (Performance): Performance tests passing < 100ms
- [ ] **KC-COORD-007** (Handlers): Both handlers tested independently

### Performance & Regression

- [ ] **Coordinator Update**: < 100ms under test load (50 kids, 20 badges each)
- [ ] **Test Execution Time**: Full suite < 15 seconds
- [ ] **No Regressions**: All 150 existing tests still pass
- [ ] **CI/CD Green**: All linting, type checking, tests pass in pipeline

---

## Dependencies & Blockers

### Must Complete Before Testing

- [ ] KC-COORD-002 (datetime migration fix) - needed for A6 tests
- [ ] KC-COORD-003 (period stats merge) - needed for D1 tests
- [ ] Phase 4 badge audit closure - needed to understand state machines
- [ ] Storage schema v41+ stable - needed for migration tests

### Test Execution Prerequisites

- [ ] pytest 9.0.0+ installed
- [ ] pytest-asyncio plugin available
- [ ] pytest-cov plugin for coverage reporting
- [ ] 350+ concurrent test support in CI/CD (currently 150)
- [ ] Test execution time budget: 15-20 seconds (monitor during implementation)

---

## Next Steps

1. **Create test file stubs** in tests/ directory
2. **Implement factory fixtures** in conftest.py
3. **Begin Phase 1 implementation** (Badge Suite A tests)
4. **Establish baseline coverage** after first 10 tests pass
5. **Track progress** against 127-test target

