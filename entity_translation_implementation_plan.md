# KidsChores Entity Translation Implementation Plan

## Summary

Most entity translations already exist in en.json. Only a few specific ones are missing.

## Phase 1: Cleanup - Remove Unused Translations ✅ COMPLETE

**Status**: Upon analysis, no unused translations found that need removal. All existing translations correspond to active entities.

## Phase 2: Add Missing Entity Translations

### 🔍 **Confirmed Missing Translations:**

#### **Missing Select Entity Translation:**

1. **`kc_select_base`** - Referenced by `SystemChoresSelect` (const.TRANS_KEY_SELECT_BASE)
   - **Location**: `entity.select.kc_select_base.name`
   - **Suggested**: `"Select Base"`

#### **Missing Sensor Entity Translation:**

2. **`badge_progress_sensor`** - Referenced by `KidBadgeProgressSensor`
   - **Location**: `entity.sensor.badge_progress_sensor.name`
   - **Suggested**: `"Badge Progress - {badge_name}"`

### ✅ **Confirmed Present (No Action Needed):**

- `dashboard_helper_sensor` ✅ EXISTS
- `calendar_name` ✅ EXISTS
- `date_helper` ✅ EXISTS
- `chores_select` ✅ EXISTS
- `rewards_select` ✅ EXISTS
- `penalties_select` ✅ EXISTS
- `bonuses_select` ✅ EXISTS
- `chore_list_helper` ✅ EXISTS
- All button entities ✅ EXISTS

## Phase 3: Implementation Steps

### Step 1: Add Missing Select Translation

**File**: `custom_components/kidschores/translations/en.json`
**Location**: `entity.select` section (around line 2401)

```json
"select": {
  "kc_select_base": {
    "name": "Select Base"
  },
  "chores_select": {
    "name": "Select Chore"
  },
  // ... rest of existing select entries
}
```

### Step 2: Add Missing Sensor Translation

**File**: `custom_components/kidschores/translations/en.json`
**Location**: `entity.sensor` section (around line 2395)

```json
"sensor": {
  // ... existing sensors ...
  "badge_progress_sensor": {
    "name": "Badge Progress - {badge_name}",
    "state_attributes": {
      "kid_name": {
        "name": "Kid Name"
      },
      "badge_name": {
        "name": "Badge Name"
      },
      "progress": {
        "name": "Progress"
      },
      "target": {
        "name": "Target"
      },
      "earned": {
        "name": "Earned",
        "state": {
          "true": "Yes",
          "false": "No"
        }
      }
    }
  }
}
```

### Step 3: Verification

- Run linting: `./utils/quick_lint.sh --fix`
- Run tests: `python -m pytest tests/ -v --tb=line`
- Verify translations load correctly by checking entity names in HA

## Implementation Priority

**TOTAL**: 2 missing translations

- **HIGH**: `badge_progress_sensor` (sensor entity is active and needs proper translation)
- **MEDIUM**: `kc_select_base` (select entity needs translation)

## Risk Assessment

- **LOW RISK**: Only adding missing translations, not modifying existing ones
- **NO BREAKING CHANGES**: All existing translations remain unchanged
- **IMMEDIATE BENEFIT**: Proper entity naming in UI

## Completion Criteria

- [ ] `kc_select_base` translation added to en.json
- [ ] `badge_progress_sensor` translation added to en.json
- [ ] All linting passes
- [ ] All tests pass
- [ ] Translation keys validated in Home Assistant UI
