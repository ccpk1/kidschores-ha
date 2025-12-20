# KidsChores Coordinator.py - String Literal Constants Inventory

**File**: Supporting document for coordinator.py code standardization  
**Phase**: 2 - String Literal Constants Standardization  
**Date**: December 19, 2025  

## High-Priority Constants (>5 occurrences)

### Dictionary Key Constants
| Current String | Occurrences | Proposed Constant | Usage Context |
|----------------|-------------|-------------------|---------------|
| `"name"` | 47 | `DICT_KEY_NAME` | Entity name lookups, exception placeholders |
| `"entity_type"` | 47 | `DICT_KEY_ENTITY_TYPE` | Exception translation placeholders |
| `"kid"` | 4 | `LABEL_KID` | Exception translation placeholders |
| `"entity"` | 3 | `LABEL_ENTITY` | Exception translation placeholders |

### Date/Time Format Constants
| Current String | Occurrences | Proposed Constant | Usage Context |
|----------------|-------------|-------------------|---------------|
| `"%Y-W%V"` | 8 | `FORMAT_WEEK_ISO` | Week period calculations |
| `"%Y-%m"` | 8 | `FORMAT_MONTH_ISO` | Month period calculations |
| `"%Y"` | 8 | `FORMAT_YEAR` | Year period calculations |

### Period/Frequency Constants
| Current String | Occurrences | Proposed Constant | Usage Context |
|----------------|-------------|-------------------|---------------|
| `"daily"` | 2 | `PERIOD_DAILY` | Period data structures |
| `"weekly"` | 2 | `PERIOD_WEEKLY` | Period data structures |
| `"monthly"` | 2 | `PERIOD_MONTHLY` | Period data structures |
| `"yearly"` | 2 | `PERIOD_YEARLY` | Period data structures |

## Medium-Priority Constants (3-5 occurrences)

### Action/Label Constants
| Current String | Occurrences | Proposed Constant | Usage Context |
|----------------|-------------|-------------------|---------------|
| `"required"` | 2 | `LABEL_REQUIRED` | Exception placeholders |
| `"current"` | 2 | `LABEL_CURRENT` | Exception placeholders |
| `"whitelist"` | 2 | `LABEL_WHITELIST` | Entity cleanup logic |
| `"immediate"` | 2 | `RESET_TYPE_IMMEDIATE` | Badge reset logic |

### String Patterns
| Current String | Occurrences | Proposed Constant | Usage Context |
|----------------|-------------|-------------------|---------------|
| `"{self.config_entry.entry_id}_"` | 4 | `UID_PREFIX_PATTERN` | Entity unique ID construction |
| `"_"` | 4+ | `SEPARATOR_UNDERSCORE` | String concatenation |
| `":"` | 3 | `SEPARATOR_COLON` | Message formatting |

## Repeated Warning/Error Messages (2+ occurrences)

### Parent Assignment Warnings
| Current String | Occurrences | Proposed Constant |
|----------------|-------------|-------------------|
| `"WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent"` | 2 | `WARNING_PARENT_KID_NOT_FOUND` |

### Badge Maintenance Messages
| Current String | Occurrences | Proposed Constant |
|----------------|-------------|-------------------|
| `"DEBUG: Badge Updated - '%s', ID '%s'"` | 2 | `DEBUG_BADGE_UPDATED` |
| `"DEBUG: Badge Maintenance - Reset badge '%s' for kid '%s'. New cycle: %s to %s"` | 2 | `DEBUG_BADGE_MAINTENANCE_RESET` |

### Entity Management Messages
| Current String | Occurrences | Proposed Constant |
|----------------|-------------|-------------------|
| `"ERROR: Reset Rewards - Kid ID '%s' not found."` | 2 | `ERROR_RESET_REWARDS_KID_NOT_FOUND` |
| `"ERROR: Reset Penalties - Kid ID '%s' not found."` | 2 | `ERROR_RESET_PENALTIES_KID_NOT_FOUND` |
| `"ERROR: Reset Bonuses - Kid ID '%s' not found."` | 2 | `ERROR_RESET_BONUSES_KID_NOT_FOUND` |

### Chore Management Messages
| Current String | Occurrences | Proposed Constant |
|----------------|-------------|-------------------|
| `"WARNING: Claim Chore - Chore '{chore_name}' has already been "` | 2 | `WARNING_CHORE_ALREADY_CLAIMED_PREFIX` |
| `"INFO: Reset Overdue Chores - Rescheduling chore: %s for kid: %s"` | 2 | `INFO_RESET_OVERDUE_CHORE` |

## Implementation Strategy

### Phase 2.1: Dictionary Key Constants
```python
# Add to const.py
DICT_KEY_NAME = "name"
DICT_KEY_ENTITY_TYPE = "entity_type" 
LABEL_KID = "kid"
LABEL_ENTITY = "entity"
LABEL_REQUIRED = "required"
LABEL_CURRENT = "current"

# Replace in coordinator.py (47 + 47 + 4 + 3 + 2 + 2 = 105 replacements)
# Old: exception_dict["name"] = value
# New: exception_dict[const.DICT_KEY_NAME] = value
```

### Phase 2.2: Date/Time Format Constants
```python
# Add to const.py
FORMAT_WEEK_ISO = "%Y-W%V"
FORMAT_MONTH_ISO = "%Y-%m"  
FORMAT_YEAR = "%Y"

# Replace in coordinator.py (8 + 8 + 8 = 24 replacements)
# Old: now_local.strftime("%Y-W%V")
# New: now_local.strftime(const.FORMAT_WEEK_ISO)
```

### Phase 2.3: Period Constants
```python
# Add to const.py (if not already defined)
PERIOD_DAILY = "daily"
PERIOD_WEEKLY = "weekly"
PERIOD_MONTHLY = "monthly" 
PERIOD_YEARLY = "yearly"

# Replace in coordinator.py (2 + 2 + 2 + 2 = 8 replacements)
```

### Phase 2.4: Message Template Constants
```python
# Add to const.py
WARNING_PARENT_KID_NOT_FOUND = "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent"
DEBUG_BADGE_UPDATED = "DEBUG: Badge Updated - '%s', ID '%s'"
DEBUG_BADGE_MAINTENANCE_RESET = "DEBUG: Badge Maintenance - Reset badge '%s' for kid '%s'. New cycle: %s to %s"
ERROR_RESET_REWARDS_KID_NOT_FOUND = "ERROR: Reset Rewards - Kid ID '%s' not found."
ERROR_RESET_PENALTIES_KID_NOT_FOUND = "ERROR: Reset Penalties - Kid ID '%s' not found."
ERROR_RESET_BONUSES_KID_NOT_FOUND = "ERROR: Reset Bonuses - Kid ID '%s' not found."
WARNING_CHORE_ALREADY_CLAIMED_PREFIX = "WARNING: Claim Chore - Chore '{chore_name}' has already been "
INFO_RESET_OVERDUE_CHORE = "INFO: Reset Overdue Chores - Rescheduling chore: %s for kid: %s"

# Replace in coordinator.py (16 message template replacements)
```

## Low-Priority Single-Occurrence Strings

**Estimated Count**: 150+ individual strings requiring review
**Categories**:
- Entity cleanup and validation messages
- Debug statements with unique context
- Error handling for specific scenarios
- Configuration and state management strings

**Approach**: Review during Phase 2.5 cleanup - consolidate where possible, create constants for reusable patterns

## Summary Statistics

| Priority | Constants Needed | Replacements | Effort Estimate |
|----------|------------------|--------------|-----------------|
| High | 12 | 150+ | 30-40 hours |
| Medium | 8 | 30+ | 15-20 hours |
| Messages | 8 | 16 | 10-15 hours |
| Low | 20-30 | 150+ | 10-15 hours |
| **Total** | **48-58** | **350+** | **65-90 hours** |

## Risk Assessment

**High Risk Areas**:
- Dictionary key changes (could break entity lookups)
- Date format changes (could break period calculations)
- Message template changes (could break logging/debugging)

**Mitigation Strategy**:
- Incremental implementation with testing after each sub-phase
- Careful validation of dictionary access patterns
- Preserve logging functionality throughout changes
- Full regression testing after each category