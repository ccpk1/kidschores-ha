# Proposed Heading Structure for Chore Configuration Guide

## Current Problems

1. **Section 2** contains 7 major topics all nested as ### headings under "Assignments & Logic"
2. Major configuration topics (Completion Criteria, Approval Reset, Overdue Handling) are buried too deep
3. Inconsistent hierarchy: "Frequency" (in Section 3) gets same treatment as "Completion Criteria" despite being less critical

## Proposed Changes

### Level 1 (#) - Document Title

- `# Chore Configuration Guide`

### Level 2 (##) - Top-Level Sections (Current: Correct)

- `## What You'll Learn`
- `## Understanding the Configuration Form`
- `## Quick Decision Guide`
- **CHANGE: Remove "Section 1-4" structure**, promote major topics to ## level
- `## Assigned Kids`
- `## Completion Criteria` ⭐ **(Most Important Setting)**
- `## Approval Reset Type`
- `## Choosing Your Approval Reset Type`
- `## Pending Claim Action`
- `## Overdue Handling`
- `## Auto-Approve`
- `## Frequency`
- `## Due Date & Time`
- `## Applicable Days`
- `## Show in Calendar`
- `## Notification Settings`
- `## Validation Rules`
- `## Common Configuration Patterns`
- `## Next Steps`

### Level 3 (###) - Sub-Topics Under Major Sections

- Under **Quick Decision Guide**: `### Step 1-4` (procedural steps - correct as-is)
- Under **Completion Criteria**: `### Option 1: Independent`, `### Option 2: Shared (All)`, `### Option 3: Shared (First)`, `### Comparison: Which Mode to Choose?`
- Under **Approval Reset Type**: `### Option 1-4` (the 4 reset types)
- Under **Overdue Handling**: `### Option 1-4` (the 4 overdue types)
- Under **Frequency**: `### None (One-Time)`, `### Daily`, `### Daily Multi`, `### Custom`, etc.
- Under **Validation Rules**: `### Rule 1-6` (individual validation rules)
- Under **Common Configuration Patterns**: `### Scenario 1-5` (example configurations)

### Level 4 (####) - Detail Subsections

- Under frequency options: `#### When to Use`, `#### Configuration`, `#### Behavior`, etc.
- Under approval reset options: `#### How It Works`, `#### Example`, `#### Compatible With`, etc.

## Rationale

1. **Flatter Structure**: Major config topics (Completion Criteria, Approval Reset, Overdue) deserve top-level visibility
2. **Better Navigation**: Users can jump directly to "Overdue Handling" without navigating through "Section 2: Assignments & Logic"
3. **Reference-Friendly**: Document works both as tutorial (Quick Guide → detailed sections) and reference (direct topic access)
4. **Consistent Importance**: Topics are organized by configuration importance, not arbitrary section grouping
5. **Matches Form UI**: Each ## heading roughly corresponds to a form field/section in the actual UI

## Migration Strategy

1. Remove "## Section 1-4" headings
2. Promote all major topics (currently ### under Section headers) to ## level
3. Keep Quick Decision Guide steps as ### (they're procedural, not configuration topics)
4. Keep Validation Rules and Common Patterns as ## (meta-sections)
5. Update all internal links in Quick Decision Guide to match new heading levels

## Before/After Example

**BEFORE:**

```markdown
## Section 2: Assignments & Logic

### Assigned Kids

### Completion Criteria ⭐

#### Option 1: Independent

#### Option 2: Shared (All)

### Approval Reset Type

#### Option 1: At Midnight Once
```

**AFTER:**

```markdown
## Assigned Kids

## Completion Criteria ⭐ **(Most Important Setting)**

### Option 1: Independent (Most Common)

#### How It Works

#### Real-World Examples

### Option 2: Shared (All Kids Must Complete)

### Option 3: Shared (First Completes)

### Comparison: Which Mode to Choose?

## Approval Reset Type

### Option 1: At Midnight Once

### Option 2: At Midnight Multi
```

## Impact on Quick Decision Guide Links

Current links like `[Independent](#option-1-independent-most-common)` will continue to work because we're only changing the parent heading level, not the ### option headings themselves.

Links that need updating:

- None (all Quick Guide links target ### headings which remain unchanged)

## Summary

**Remove**: "Section 1-4" organizational headers
**Promote**: 13 major configuration topics from ### to ##
**Keep**: Option subsections (Independent, Shared, reset types) as ###
**Keep**: Quick Decision Guide steps as ###
**Keep**: Validation Rules and Common Patterns as ##

This creates a **flatter, more navigable structure** that better serves both tutorial and reference use cases.
