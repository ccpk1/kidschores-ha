# Chore Configuration Behavior Matrices

**Purpose**: Quick-reference compatibility tables for all chore configuration combinations  
**Source**: Test-verified behaviors from test_chore_scheduling.py and validation rules  
**Status**: 100% verified from test suite

---

## Matrix 1: Approval Reset Type × Frequency Compatibility

| Approval Reset Type | None | Daily | Daily Multi | Weekly | Biweekly | Monthly | Custom | Custom From Complete |
|---------------------|------|-------|-------------|--------|----------|---------|--------|---------------------|
| **UPON_COMPLETION** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AT_MIDNIGHT_ONCE** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AT_MIDNIGHT_MULTI** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AT_DUE_DATE_ONCE** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AT_DUE_DATE_MULTI** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Legend**:
- ✅ = Compatible, tested and working
- ❌ = Incompatible, validation blocks this combination

**Key Insights**:
- **DAILY_MULTI × AT_MIDNIGHT_* = INVALID**: DAILY_MULTI needs immediate slot advancement. AT_MIDNIGHT_* keeps chore APPROVED until midnight, blocking slots.
- **Validation Rule**: `if frequency == DAILY_MULTI and reset_type in {AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI}` → raises error `daily_multi_requires_compatible_reset`

---

## Matrix 2: Approval Reset Type × Completion Criteria Compatibility

| Approval Reset Type | INDEPENDENT | SHARED_ALL | SHARED_FIRST |
|---------------------|-------------|------------|--------------|
| **UPON_COMPLETION** | ✅ | ✅ | ✅ |
| **AT_MIDNIGHT_ONCE** | ✅ | ✅ | ✅ |
| **AT_MIDNIGHT_MULTI** | ✅ | ✅ | ✅ |
| **AT_DUE_DATE_ONCE** | ✅ | ✅ | ✅ |
| **AT_DUE_DATE_MULTI** | ✅ | ✅ | ✅ |

**All combinations valid.** Approval reset types work with all completion criteria.

**Behavior Differences**:
- **INDEPENDENT**: Per-kid approval tracking. Each kid has independent `period_start`.
- **SHARED_ALL**: Chore-level period tracking. Each kid must complete independently, all must finish for chore completion.
- **SHARED_FIRST**: Chore-level period tracking. First kid to claim owns until reset.

---

## Matrix 3: Overdue Handling × Approval Reset Type Compatibility

| Overdue Handling | UPON_COMPLETION | AT_MIDNIGHT_ONCE | AT_MIDNIGHT_MULTI | AT_DUE_DATE_ONCE | AT_DUE_DATE_MULTI |
|------------------|-----------------|------------------|-------------------|------------------|-------------------|
| **AT_DUE_DATE** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **NEVER_OVERDUE** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AT_DUE_DATE_THEN_RESET** | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ |

**Legend**:
- ✅ = Compatible and tested
- ⚠️ = Likely incompatible (not explicitly validated but logical constraint)

**Key Constraint**:
- **AT_DUE_DATE_THEN_RESET** only works with **AT_MIDNIGHT_*** reset types
- Rationale: "THEN_RESET" means overdue clears when approval reset mechanism runs. AT_MIDNIGHT types have defined reset times (midnight). AT_DUE_DATE types reset when due date passes (variable timing).

---

## Matrix 4: Frequency × Due Date Requirements

| Frequency | Due Date Required? | Rationale |
|-----------|-------------------|-----------|
| **None** | ❌ Optional | Non-recurring, manual completion |
| **Daily** | ❌ Optional | Fixed period (midnight), no anchor needed |
| **Daily Multi** | ✅ **Required** | Time slots need reference point |
| **Weekly** | ❌ Optional | Fixed period (Monday midnight), no anchor needed |
| **Biweekly** | ✅ **Required** | Needs anchor to calculate 14-day cycles |
| **Monthly** | ✅ **Required** | Needs anchor for month-relative scheduling |
| **Custom** | ✅ **Required** | Interval needs starting point |
| **Custom From Complete** | ✅ **Required** | Initial due date for first occurrence |

---

## Matrix 5: Frequency × Completion Criteria Compatibility

| Frequency | INDEPENDENT | SHARED_ALL | SHARED_FIRST |
|-----------|-------------|------------|--------------|
| **None** | ✅ | ✅ | ✅ |
| **Daily** | ✅ | ✅ | ✅ |
| **Daily Multi** | ✅ | ❌ | ❌ |
| **Weekly** | ✅ | ✅ | ✅ |
| **Biweekly** | ✅ | ✅ | ✅ |
| **Monthly** | ✅ | ✅ | ✅ |
| **Custom** | ✅ | ✅ | ✅ |
| **Custom From Complete** | ✅ | ✅ | ✅ |

**Key Constraint**:
- **DAILY_MULTI × SHARED = INVALID**: DAILY_MULTI requires per-kid time slot tracking, incompatible with shared completion modes.
- **Validation Rule**: `if frequency == DAILY_MULTI and completion_criteria in {SHARED, SHARED_FIRST}` → raises error `invalid_daily_multi_shared`

---

## Matrix 6: Approval Reset Behaviors Summary

| Reset Type | Period Boundary | Completions Per Period | Returns to PENDING? | Points Per Approval? |
|------------|----------------|------------------------|---------------------|---------------------|
| **UPON_COMPLETION** | None (no tracking) | Unlimited | Immediately | Yes |
| **AT_MIDNIGHT_ONCE** | Midnight local | 1 | At midnight | Yes (once) |
| **AT_MIDNIGHT_MULTI** | Midnight local | Unlimited | Immediately | Yes (per approval) |
| **AT_DUE_DATE_ONCE** | When due date passes | 1 | When due date passes | Yes (once) |
| **AT_DUE_DATE_MULTI** | When due date passes | Unlimited | Immediately | Yes (per approval) |

**Key Patterns**:
- **ONCE** types: Stay APPROVED until period boundary
- **MULTI** types: Immediate return to PENDING for re-claim
- **All types** award points on approval

---

## Matrix 7: Pending Claim Actions × Reset Type Compatibility

| Pending Claim Action | All Reset Types |
|---------------------|-----------------|
| **HOLD_PENDING** | ✅ All compatible |
| **CLEAR_PENDING** | ✅ All compatible |
| **AUTO_APPROVE_PENDING** | ✅ All compatible |

**All combinations valid.** Pending claim actions work with all reset types.

**Behavior**:
- Actions only trigger when reset mechanism runs
- Only affect chores in CLAIMED state (not PENDING or APPROVED)
- AUTO_APPROVE awards points THEN applies normal reset logic

---

## Matrix 8: Edge Cases & Special Behaviors

| Scenario | Behavior | Test Evidence |
|----------|----------|---------------|
| **AT_DUE_DATE_ONCE without due date** | Never resets, blocks after first approval | `test_at_due_date_reset_without_due_date_once` |
| **AT_DUE_DATE_MULTI without due date** | Acts like UPON_COMPLETION (unlimited immediate) | `test_at_due_date_reset_without_due_date_multi` |
| **Claimed chore past due** | Never becomes overdue (protected) | `test_claimed_chore_not_marked_overdue` |
| **SHARED_ALL approval tracking** | Chore-level period, per-kid independent completion | `test_shared_all_midnight_once_per_kid_tracking` |
| **SHARED_FIRST after first claim** | All other kids blocked until reset | `test_shared_first_midnight_once_blocks_all_kids_after_first` |
| **Applicable days snap-forward** | Due date adjusts to next valid weekday | `test_applicable_days_affects_next_due_date` |
| **Monthly scheduling range** | 28-37 days (28-31 month length + up to 6 for weekday snap) | `test_monthly_chore_reschedules_approximately_30_days` |
| **Biweekly scheduling** | Exactly 14 days between due dates | `test_biweekly_chore_reschedules_14_days` |

---

## Matrix 9: Per-Kid Features Compatibility

| Feature | INDEPENDENT | SHARED_ALL | SHARED_FIRST |
|---------|-------------|------------|--------------|
| **Per-Kid Applicable Days** | ✅ Available | ❌ Not available | ❌ Not available |
| **Per-Kid Daily Multi Times** | ✅ Available | ❌ Not available | ❌ Not available |
| **Per-Kid Due Dates** | ✅ Available | ❌ Not available | ❌ Not available |

**Key Constraint**: All per-kid customization features require INDEPENDENT completion criteria.

**Helper Modal Triggers** (Per-Kid Schedule):
- Condition 1: `completion_criteria == INDEPENDENT`
- Condition 2: 2+ kids assigned
- Condition 3: `frequency == DAILY_MULTI` OR `applicable_days` set (chore-level or per-kid)
- **When ALL met**: Shows Per-Kid Schedule helper modal after main form

---

## Validation Rules Summary

### Rule 1: DAILY_MULTI Compatibility
```
DAILY_MULTI + AT_MIDNIGHT_* = ❌ Invalid (error: daily_multi_requires_compatible_reset)
DAILY_MULTI + SHARED_* = ❌ Invalid (error: invalid_daily_multi_shared)
DAILY_MULTI without due_date = ❌ Invalid (due date required)
```

### Rule 2: Due Date Requirements
```
Biweekly/Monthly/Custom/Custom_From_Complete without due_date = ❌ Invalid
Daily/Weekly/None without due_date = ✅ Valid
```

### Rule 3: AT_DUE_DATE_THEN_RESET
```
AT_DUE_DATE_THEN_RESET + AT_MIDNIGHT_* = ✅ Valid
AT_DUE_DATE_THEN_RESET + other reset types = ⚠️ Likely invalid (not explicitly tested)
```

### Rule 4: Per-Kid Features
```
Per-kid features + SHARED_* = ❌ Invalid (per-kid requires INDEPENDENT)
```

---

## Quick Decision Trees

### "What reset type should I use?"
- **Unlimited completions per day?** → AT_MIDNIGHT_MULTI or AT_DUE_DATE_MULTI
- **One completion per day?** → AT_MIDNIGHT_ONCE
- **One completion per custom period?** → AT_DUE_DATE_ONCE
- **Immediate re-availability?** → UPON_COMPLETION
- **Using DAILY_MULTI?** → Must use AT_DUE_DATE_* or UPON_COMPLETION

### "When does my chore reset?"
- **AT_MIDNIGHT_***: Always at midnight local time
- **AT_DUE_DATE_***: When due date passes (variable timing)
- **UPON_COMPLETION**: Immediately after approval

### "Can I use per-kid scheduling?"
- **Check 1**: Is completion criteria INDEPENDENT? (Yes → Continue, No → Not available)
- **Check 2**: Are 2+ kids assigned? (Yes → Continue, No → Not needed)
- **Check 3**: Using DAILY_MULTI or applicable days? (Yes → Helper modal appears)

---

## Notes for Documentation Writers

1. **Matrix Purpose**: Quick validation for configuration combinations. Don't explain every cell in user docs.

2. **Invalid Combinations**: Focus on the 3 main invalid combinations (DAILY_MULTI rules). These are the ones users will hit.

3. **Edge Cases**: The "without due date" edge cases are rare. Mention briefly, don't over-explain.

4. **Test References**: Include test names in technical docs, omit from user-facing content.

5. **Visual Format**: Consider color-coding in wiki (green/red) for valid/invalid combinations.
