# Reward Cost Override Feature - Implementation Plan

## Initiative snapshot

- **Name / Code**: Reward Cost Override / COST-OVERRIDE-v0.5.1
- **Target release / milestone**: v0.5.1 (maintenance release)
- **Owner / driver(s)**: Development team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                | Description                                      | % complete | Quick notes                            |
| --------------------------- | ------------------------------------------------ | ---------- | -------------------------------------- |
| Phase 1 – Core Refactor     | Extract reward tracking to unified helper method | 0%         | Updates approve_reward + \_award_badge |
| Phase 2 – Service Extension | Add cost_override to approve_reward service      | 0%         | Parent decides cost at approval time   |
| Phase 3 – Translations      | Update strings.json for service field UI labels  | 0%         | Service field descriptions + examples  |
| Phase 4 – Validation        | Test scenarios + notification verification       | 0%         | Covers override, free, default cases   |
| Phase 5 – Documentation     | Update services.yaml with examples               | 0%         | User-facing service documentation      |

1. **Key objective** – Enable optional cost override in `approve_reward` service to support context-aware reward approvals (weekend/weekday pricing, special occasions, etc.) while maintaining full backward compatibility.

2. **Summary of recent work** – Not started. Analysis completed showing badges already implement free reward grants; this feature unifies approval patterns.

3. **Next steps (short term)**
   - Create `_grant_reward_to_kid()` helper method (Phase 1)
   - Add `cost_override` parameter to coordinator & service (Phase 2)
   - Validate notification messages use actual cost (Phase 3)

4. **Risks / blockers**
   - **Low risk**: Changes are additive (optional parameter)
   - **Dependency**: Must verify notification messages don't hardcode cost values
   - **Testing**: Need scenarios for override=0, override>default, override<default

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage schema (no changes needed)
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Naming conventions for constants
   - [coordinator.py:5605-5850](../../custom_components/kidschores/coordinator.py) - Current `approve_reward()`
   - [coordinator.py:6521-6625](../../custom_components/kidschores/coordinator.py) - Badge reward pattern (reference implementation)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Use `cost_override` parameter name (matches chore pattern: `points_awarded`)
     - Helper method named `_grant_reward_to_kid()` (clear intent)
     - Default behavior unchanged (None = use stored cost)
     - Cost tracking only occurs if cost > 0 (matches badge pattern)
   - **Completion confirmation**:
     - `[ ]` Coordinator refactored with helper method
     - `[ ]` Service schema updated with optional cost field
     - `[ ]` Tests pass (existing + new scenarios)
     - `[ ]` Notifications verified to show actual cost
     - `[ ]` services.yaml documented with examples
     - `[ ]` All follow-up items completed before marking done

---

## Detailed phase tracking

### Phase 1 – Core Refactor (Reward Tracking Extraction)

**Goal**: Extract duplicated reward tracking logic from `approve_reward()` and `_award_badge()` into a unified helper method `_grant_reward_to_kid()` that separates tracking from cost deduction.

**Steps / detailed work items**

1. **Create `_grant_reward_to_kid()` helper method** [Lines ~5580-5600 in coordinator.py]
   - [ ] Add method signature with parameters: `kid_id`, `reward_id`, `cost_deducted`, `notif_id`, `is_pending_claim`
   - [ ] Move reward_entry update logic from approve_reward
   - [ ] Include: TOTAL_APPROVED, LAST_APPROVED, TOTAL_POINTS_SPENT (conditional)
   - [ ] Include: PERIOD_APPROVED, PERIOD_POINTS (conditional on cost > 0)
   - [ ] Include: pending_count decrement (conditional on is_pending_claim)
   - [ ] Include: notification ID removal logic
   - [ ] Include: period data cleanup with retention settings
   - [ ] Add comprehensive docstring explaining unified pattern

2. **Update `approve_reward()` to use helper** [Lines 5605-5850 in coordinator.py]
   - [ ] Keep cost determination logic (lines ~5640-5642)
   - [ ] Keep points deduction logic (lines ~5659-5662, 5740-5741)
   - [ ] Replace reward_entry update blocks (lines ~5665-5727, 5750-5810) with call to `_grant_reward_to_kid()`
   - [ ] Verify lock context maintained around both deduction + tracking
   - [ ] Verify notifications still trigger correctly

3. **Update `_award_badge()` to use helper** [Lines 6608-6625 in coordinator.py]
   - [ ] **Replace lines 6610-6619** (manual reward_data updates) with single call:
     ```python
     self._grant_reward_to_kid(
         kid_id=kid_id,
         reward_id=reward_id,
         cost_deducted=None,  # Badges don't deduct cost
         notif_id=None,       # No notifications for badge rewards
         is_pending_claim=False,  # Badges don't resolve pending claims
     )
     ```
   - [ ] Maintain existing logging at line 6621
   - [ ] Remove now-redundant lines:
     - Line 6611: `reward_data = self._get_kid_reward_data(...)`
     - Line 6612-6614: `reward_data[...TOTAL_APPROVED] = ...`
     - Line 6616-6618: `self._increment_reward_period_counter(...)`
   - [ ] Verify badge tests still pass (test_badges.py)

**Key issues**

- Ensure cleanup logic is identical in both paths (retention settings must match)
- Lock context must remain around entire operation in approve_reward
- No behavior changes visible to users (pure refactor)

---

### Phase 2 – Service Extension (Add Cost Override)

**Goal**: Add optional `cost_override` parameter to `approve_reward` service only. Parent decides final cost at approval time, not kid at claim time.

**Steps / detailed work items**

1. **Update coordinator.approve_reward() signature** [Line 5605 in coordinator.py]
   - [ ] Add parameter: `cost_override: float | None = None`
   - [ ] Update docstring with parameter documentation and examples
   - [ ] Add cost determination logic (line ~5642):
     ```python
     if cost_override is not None:
         cost = cost_override
     else:
         cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)
     ```
   - [ ] Pass actual cost used to `_grant_reward_to_kid()` call
   - [ ] Verify existing calls (from services.py, tests) work unchanged

2. **Update services.py schema** [Line 68 in services.py]
   - [ ] Add to `APPROVE_REWARD_SCHEMA`:
     ```python
     vol.Optional(const.FIELD_COST_OVERRIDE): vol.Coerce(float)
     ```

3. **Update services.py handler** [Line ~402 in services.py]
   - [ ] `handle_approve_reward()`: Extract `cost_override` from call.data
   - [ ] Pass to coordinator: `await coordinator.approve_reward(..., cost_override=cost_override)`

4. **Update const.py** [Line ~2133 in const.py]
   - [ ] Add constant: `FIELD_COST_OVERRIDE: Final = "cost_override"`

5. **Update services.yaml** [Lines 114-140 in services.yaml]
   - [ ] Add `cost_override` field to `approve_reward` service (after `reward_name`)
   - [ ] Field structure:
     ```yaml
     cost_override:
       name: "Cost Override"
       description: "Optional cost override. If omitted, uses reward's stored cost. Set to 0 for free grant (like badge rewards). Useful for context-aware pricing."
       example: 10
       required: false
       selector:
         number:
           min: 0
           max: 10000
           mode: box
     ```

**Key issues**

- Must maintain backward compatibility (None = use stored cost)
- Schema validation should allow 0 (free grant)
- Existing service calls without cost_override must work unchanged
- **Rationale**: Parent makes pricing decision at approval, not kid at claim (avoids storing override in pending state)

---

### Phase 3 – Translations (Service UI Labels)

**Goal**: Add translation strings for service field labels and descriptions to support Home Assistant UI service forms.

**Steps / detailed work items**

1. **Update translations/en.json** [Add to services section]
   - [ ] Add service field translations for `cost_override` in `approve_reward`:
     ```json
     {
       "services": {
         "approve_reward": {
           "fields": {
             "cost_override": {
               "name": "Cost override",
               "description": "Optional cost override. If omitted, uses the reward's stored cost. Set to 0 for a free grant (like badge rewards). Useful for context-aware pricing (weekends, special occasions, etc.)."
             }
           }
         }
       }
     }
     ```
   - [ ] Verify JSON syntax is valid
   - [ ] Ensure nested structure matches existing service field translations

2. **Run translation development script**
   - [ ] Execute: `python -m script.translations develop --all`
   - [ ] Verify en.json compiles without errors
   - [ ] Check that new strings appear in compiled translations

3. **Verify UI rendering** [Manual test in Home Assistant UI]
   - [ ] Open Developer Tools → Services
   - [ ] Select `kidschores.approve_reward`
   - [ ] Verify "Cost override" field appears with description
   - [ ] Test field accepts numeric input (0, 5, 100)

**Key issues**

- Translation strings required for service UI forms to display properly
- Must follow Home Assistant service translation structure: `services.{service_name}.fields.{field_name}.{name/description}`
- Missing translations won't break functionality but will show field name as "cost_override" instead of "Cost override"

---

### Phase 4 – Validation & Testing

**Goal**: Validate all scenarios work correctly, especially badge integration and notification messages showing actual cost deducted.

**Steps / detailed work items**

1. **Unit tests for `_grant_reward_to_kid()`** [New file or test_coordinator.py]
   - [ ] Test with cost_deducted=10: verify TOTAL_POINTS_SPENT increments
   - [ ] Test with cost_deducted=0: verify no POINTS_SPENT tracking
   - [ ] Test with cost_deducted=None: verify no POINTS_SPENT tracking
   - [ ] Test is_pending_claim=True: verify pending_count decrements
   - [ ] Test is_pending_claim=False: verify pending_count unchanged
   - [ ] Test notif_id removal from list

2. **Integration tests for cost_override** [test_workflow_rewards.py or similar]
   - [ ] Test approve_reward with cost_override=0 (free grant, no points deducted)
   - [ ] Test approve_reward with cost_override=5 (deduct 5 when stored cost=10)
   - [ ] Test approve_reward with cost_override=15 (deduct 15 when stored cost=10)
   - [ ] Test approve_reward with cost_override=None (default: deduct stored cost)
   - [ ] Test approve_reward with insufficient points for override (should raise error)
   - [ ] Verify kid points balance correct in all scenarios

3. **Service tests** [test_services.py]
   - [ ] Test service call with `cost_override: 0` parameter
   - [ ] Test service call with `cost_override: 8` parameter
   - [ ] Test service call without cost_override parameter (backward compat)
   - [ ] Verify schema validation accepts floats

4. **Notification verification** [Manual or test_notifications.py]
   - [ ] Check notification message doesn't hardcode cost from reward_info
   - [ ] Verify notification uses actual deducted cost (from tracking or params)
   - [ ] Review `TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED` usage in coordinator
   - [ ] If notification shows cost, ensure it uses `cost` variable (post-override)
   - [ ] Current notification (line ~5820): only shows reward_name, no cost mentioned ✅

5. **Badge award verification - CRITICAL** [test_badges.py]
   - [ ] **Verify refactored `_award_badge()` calls `_grant_reward_to_kid()` correctly**
   - [ ] Test badge with reward grants: confirm rewards appear in kid's reward_data
   - [ ] Verify `cost_deducted=None` prevents TOTAL_POINTS_SPENT tracking
   - [ ] Verify PERIOD_APPROVED increments
   - [ ] Verify PERIOD_POINTS does NOT increment (no cost tracking)
   - [ ] Test periodic badge awards with multiple rewards
   - [ ] Test cumulative badge awards with rewards
   - [ ] Confirm no points deducted from kid's balance when badge grants reward
   - [ ] **Integration test**: Award badge → verify reward tracking → verify no cost

**Key issues**

- Notification messages at line 5820-5829 don't include cost in message_data ✅ (no changes needed)
- Must test edge case: override cost > kid's current points (should fail)
- Must verify badge tests still pass after refactor

6. **Workflow integration test** [test_services.py]
   - [ ] Test full flow: kid redeems → parent approves with cost_override
   - [ ] Verify redeem uses stored cost for validation (no override needed)
   - [ ] Verify approve respects cost_override (independent decision)
   - [ ] Confirm override doesn't affect pending claim state

---

### Phase 5 – Documentation & Polish

**Goal**: Document the feature for users and ensure all strings/docs are updated.

**Steps / detailed work items**

1. **services.yaml documentation** [Lines 88-162 in services.yaml]
   - [ ] Add clear description for `cost_o114-140 in services.yaml]
   - [ ] Add clear description for `cost_override` field in `approve_reward`
   - [ ] Provide usage examples

     # Use stored reward cost (default behavior)

     service: kidschores.approve_reward
     data:
     parent_name: "Mom"
     kid_name: "Alice"
     reward_name: "Screen Time"

     # Custom cost (weekend discount)

     service: kidschores.approve_reward
     data:
     parent_name: "Mom"
     kid_name: "Alice"
     reward_name: "Screen Time"
     cost_override: 5 # Deduct 5 instead of stored cost

     # Free grant (special occasion)

     service: kidschores.approve_reward
     data:
     parent_name: "Mom"
     kid_name: "Alice"
     reward_name: "Screen Time"
     cost_override: 0 # No cost, like badge rewards

     ```

     ```

2. **Translation verification** [translations/en.json]
   - [ ] **Service field translations added** (completed in Phase 3) ✅
   - [ ] Verify existing notification keys still work:
     - `TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED`
     - `TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED`
   - [ ] Confirm notification messages don't hardcode cost values
   - [ ] **Notification translations unchanged** (messages don't expose cost) ✅

3. **README.md updates** [If service section exists]
   - [ ] Document `cost_override` parameter in services section
   - [ ] Provide automation example (weekend/weekday pricing)
   - [ ] Explain use case: context-aware rewards

4. **Inline code documentation**
   - [ ] Ensure `_grant_reward_to_kid()` docstring is comprehensive
   - [ ] Update `approve_reward()` docstring with cost_override examples
   - [ ] Add comments in `_award_badge()` explaining helper method integration
   - [ ] Add comments explaining unified pattern at helper method
   - [ ] Note in `redeem_reward()` docstring: "Cost override only available at approval time"

**Key issues**

- No new translation keys needed (cost is numeric, not user-facing string)
- Services.yaml examples should be practical and clear
- Inline docs should reference badge pattern for context

---

## Testing & validation

### Manual test scenarios

1. **Scenario: Weekend discount automation**

   ```yaml
   alias: "Weekend Reward Discount"
   trigger:
     - platform: time
       at: "17:00:00"
   condition:
     - condition: time
       weekday: [fri, sat, sun]
   action:
     - service: kidschores.approve_reward
       data:
         parent_name: "Mom"
         kid_name: "Alice"
         reward_name: "Extra Screen Time"
         cost_override: 5 # Weekend price (normal: 10)
   ```

   - **Expected**: Deducts 5 points, not 10
   - **Verify**: Kid points balance, reward tracking counters

2. **Scenario: Birthday free grant**

   ```yaml
   service: kidschores.approve_reward
   data:
     parent_name: "Mom"
     kid_name: "Bob"
     reward_name: "Special Treat"
     cost_override: 0 # Birthday special
   ```

   - **Expected**: Grants reward, deducts 0 points
   - **Verify**: Kid points unchanged, reward approved counter increments

3. **Scenario: Backward compatibility (no override)**
   ```yaml
   service: kidschores.approve_reward
   data:
     parent_name: "Dad"
     kid_name: "Charlie"
     reward_name: "Game Time"
     # No cost_override specified
   ```

   - **Expected**: Uses stored reward cost (e.g., 15 points)
   - **Verify**: Behavior unchanged from current version

### Automated test commands

```bash
# Run all reward tests
pytest tests/test_workflow_rewards.py -v

# Run service tests
pytest tests/test_services.py::test_approve_reward_service -v

# Run badge tests (verify refactor didn't break)
pytest tests/test_badges.py -v

# Full test suite
pytest tests/ -v --tb=line

# Type checking
mypy custom_components/kidschores/coordinator.py

# Linting
./utils/quick_lint.sh --fix
```

### Outstanding validation items

- [ ] Verify dashboard buttons work with refactored coordinator
- [ ] Test multi-parent scenario (concurrent approvals with override)
- [ ] Confirm notification service calls use correct cost value
- [ ] Edge case: override=999999 when kid has 10 points (should fail gracefully)

---

## Notes & follow-up

### Architectural considerations

- **Pattern alignment**: This feature unifies `approve_reward()` with the existing badge reward pattern, reducing code duplication by ~130 lines
- **Backward compatibility**: All existing service calls, automations, and dashboard buttons continue to work without modification
- **Future extensibility**: The `_grant_reward_to_kid()` helper could be extended to support:
  - Temporary reward grants (expire after time period)
  - Conditional rewards (automatically approve if criteria met)
  - Bulk reward operations

### Performance impact

- **Negligible**: Adds one conditional check (`if cost_override is not None`)
- **Positive**: Reduces code duplication (single reward tracking path)
- **Lock safety**: Maintains existing asyncio.Lock pattern for race condition prevention

### User experience improvements

- **Automation flexibility**: Users can build context-aware reward systems (time-based, event-based pricing)
- **Simplified workarounds**: Eliminates need for duplicate reward entries ("Weekday Screen Time", "Weekend Screen Time")
- **Feature parity**: Matches `approve_chore` which already has `points_awarded` override

### Dependencies & blockers

- **None identified**: Feature is self-contained within coordinator and services
- **No schema changes**: Uses existing storage structure
- **No migration needed**: Backward compatible, optional parameter

### Follow-up tasks (future phases)

1. Consider adding `cost_override` to `redeem_reward()` for completeness (kid-initiated claims)
2. Evaluate dashboard UI support for cost override (dropdown or input field)
3. Monitor user feedback on cost override usage patterns
4. Consider extending to bonuses/penalties if requested

### Code quality metrics

- **Expected LOC change**: +80 (helper method) -130 (deduplication) = -50 net reduction
- **Test coverage target**: Maintain >95% coverage
- **Complexity**: Reduces cyclomatic complexity in `approve_reward()` by extracting tracking logic

---

## Implementation checklist (high-level)

- [ ] **Phase 1**: Refactor reward tracking
  - [ ] Create `_grant_reward_to_kid()` helper (lines ~5580-5600)
  - [ ] Update `approve_reward()` to use helper (refactor lines 5665-5810)
  - [ ] **Update `_award_badge()` to use helper** (refactor lines 6610-6619) ← CRITICAL
  - [ ] Verify all existing tests pass

- [ ] **Phase 2**: Add cost override to approve service
  - [ ] Add `cost_override` parameter to `coordinator.approve_reward()`
  - [ ] Update `APPROVE_REWARD_SCHEMA` in services.py
  - [ ] Update `handle_approve_reward()` handler
  - [ ] Add `FIELD_COST_OVERRIDE` constant to const.py

- [ ] **Phase 3**: Service UI translations
  - [ ] Add field translations to translations/en.json
  - [ ] Run `python -m script.translations develop --all`
  - [ ] Verify UI renders correctly in Developer Tools → Services

- [ ] **Phase 4**: Testing
  - [ ] Write unit tests for `_grant_reward_to_kid()` helper
  - [ ] Write integration tests for cost_override scenarios
  - [ ] **Test badge reward integration** (verify refactored code works) ← CRITICAL
  - [ ] Test full workflow (redeem → approve with override)
  - [ ] Verify notification messages
  - [ ] Run full test suite

- [ ] **Phase 5**: Documentation
  - [ ] Update services.yaml with cost_override fields
  - [ ] Add usage examples to services.yaml
  - [ ] Update inline documentation in coordinator
  - [ ] Consider README updates with automation examples

- [ ] **Final validation**
  - [ ] Code review (lint, mypy, tests pass)
  - [ ] Manual testing with various scenarios
  - [ ] Backward compatibility verification
  - [ ] Performance check (no regression)

---

**Status**: Ready for implementation. All analysis complete, no blockers identified. Feature is additive and maintains full backward compatibility.
