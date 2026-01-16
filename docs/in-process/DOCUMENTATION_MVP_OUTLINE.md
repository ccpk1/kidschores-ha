# Documentation MVP - Pre-Release Requirements

**Purpose**: Minimum documentation needed for v0.5.0 release
**Status**: Planning - based on verified inventory
**Date**: January 2025

---

## Coverage Verification

### ✅ Already Documented (Chore Configuration Guide)

**Shared Chores**: Lines 186-301

- Option 2: Shared (All Kids Must Complete)
- Option 3: Shared (First Completes)
- Complete decision matrix and examples
- Daily Multi compatibility documented

**Overdue Handling**: Lines 602-800+

- Option 1: Clear Late Approvals Immediately (Default)
- Option 2: Clear Overdue at Next Approval Reset
- Option 3: Never Clear Until Chore Resets (Stays Overdue)
- Option 4: Never Overdue
- Complete examples and behavior tables

**Status**: ✅ No additional chore guide needed

---

## MVP Requirements: What We Must Create

### 1. Installation & Quick Start (HIGH PRIORITY)

**Why**: First user experience, migration from old wiki
**Source**: Old wiki Installation-&-Setup.md (39 lines)
**Estimated**: ~150 lines

**Content Needed**:

- ✅ HACS installation (exists in old wiki)
- ✅ Manual installation (exists in old wiki)
- ✅ Configuration wizard walkthrough (exists in old wiki)
- ❌ NEW: v0.5.0 feature highlights (needs creation)
- ❌ NEW: First chore creation walkthrough (needs creation)

**File**: `docs/wiki/Installation-and-Quick-Start.md`

---

### 2. Badges System Guide (HIGH PRIORITY - FULL REWRITE)

**Why**: System overhauled, old wiki outdated
**Source**: Old wiki has 82 lines but system changed significantly
**Estimated**: ~300-400 lines

**Old Content (OUTDATED)**:

- Points multiplier (format changed?)
- "Highest badge earned" calculation (still accurate?)
- Progress tracking explanation (still accurate?)
- Example badge series (Bronze/Silver/Gold, Gamer, Star Collector)

**New Content Needed** (Verify from code):

- ❌ Badge configuration in config flow
- ❌ How badges are earned (points vs chores)
- ❌ Badge maintenance system (new in v0.5.0)
- ❌ Badge progress tracking (entity attributes)
- ❌ Points multiplier effects
- ❌ Badge status and history
- ❌ Parent management (activate/deactivate badges)
- ✅ Keep example badge series (still relevant)

**Sensors to Document**:

- `sensor.kc_{kid}_badges` - Entity documented in Technical Reference
- `sensor.kc_{kid}_badge_status` - Entity documented in Technical Reference
- `sensor.kc_{badge_name}_badge` - Entity documented in Technical Reference

**File**: `docs/wiki/Badges-Guide.md`

**Research Required**:

- Read badge configuration code in config_flow.py
- Verify badge maintenance attributes from coordinator.py
- Understand badge activation/deactivation behavior
- Document badge priority and "highest earned" logic

---

### 3. Services Reference (HIGH PRIORITY)

**Why**: Critical functionality, not in new docs
**Source**: Old wiki has 3 service docs (166 lines total)
**Estimated**: ~250 lines

**Services to Document**:

#### Reset All Data

- ✅ Old wiki has complete doc (51 lines)
- Clears all chore status, streaks, points, history
- Keeps kids, chores, rewards intact
- Use cases: New year reset, cleanup after testing

#### Reset Overdue Chores

- ✅ Old wiki has complete doc (35 lines)
- Reset specific chore for all kids
- Reset all chores for specific kid
- Reset specific chore for specific kid
- Reset all overdue chores
- Note: Only works on recurring chores

#### Set Chore Due Dates

- ✅ Old wiki has complete doc (80 lines)
- Dynamically assign due dates
- Use cases: One-time chores, calendar-based automation
- Interaction with recurrence and chore states
- Due date clearing behavior

**Action**: Migrate content, verify service names match v0.5.0, add YAML examples

**File**: `docs/wiki/Services-Reference.md`

---

### 4. Achievements & Challenges (MEDIUM PRIORITY - KEEP AS IS)

**Why**: Old wiki content is adequate, no major changes
**Source**: Old wiki (149 lines)
**Estimated**: Copy + light editing = ~150-180 lines

**Content from Old Wiki**:

- ✅ Achievement vs Challenge definitions
- ✅ Sensor naming conventions
- ✅ Progress tracking explanation
- ✅ Update logic and completion handling
- ✅ Parent management actions
- ✅ Example achievements (milestones, streaks)
- ✅ Example challenges (time-bound, themed)

**Changes Needed**:

- Minor formatting updates
- Verify sensor entity IDs match current code
- Add reference links to Technical Reference

**File**: `docs/wiki/Achievements-and-Challenges.md`

---

## What We Are NOT Creating (Out of Scope)

### ❌ Bonuses & Penalties Guide

**Why**: Only 27 lines in old wiki, low complexity
**Action**: Keep in old wiki for now, migrate in Phase 2

### ❌ Access Control & Security

**Why**: 70 lines, advanced topic
**Action**: Keep in old wiki for now, migrate in Phase 2

### ❌ Automation Cookbook

**Why**: 661 lines across 6 Tips & Tricks pages
**Action**: Keep in old wiki for now, consolidate in Phase 2

### ❌ Troubleshooting Guide

**Why**: 146 lines, support content
**Action**: Keep in old wiki for now, update in Phase 2

### ❌ FAQ

**Why**: 64 lines, evolving content
**Action**: Keep in old wiki for now, update in Phase 2

### ❌ Dashboard Guide

**Why**: Separate repository (kidschores-ha-dashboard), documented there
**Action**: Link to dashboard repo, don't duplicate

---

## MVP File Structure

```
docs/wiki/
├── README.md (exists - update with links)
├── Installation-and-Quick-Start.md (CREATE - Phase 1)
├── Chore-Configuration-Guide.md (✅ EXISTS - 1,256 lines)
├── Chore-Advanced-Features.md (✅ EXISTS - 346 lines)
├── Chore-Technical-Reference.md (✅ EXISTS - 427 lines)
├── Badges-Guide.md (CREATE - Phase 1)
├── Achievements-and-Challenges.md (MIGRATE - Phase 1)
├── Services-Reference.md (CREATE - Phase 1)
└── Technical-Reference:-Entities-&-States.md (✅ EXISTS - 799 lines)
```

**Total New Content**: ~800-900 lines across 4 documents
**Total After MVP**: ~4,600 lines

---

## Success Criteria

### Pre-Release Requirements (v0.5.0)

✅ **Installation covered**: Users can install and configure
✅ **Core features documented**: Chores, badges, achievements covered
✅ **Services documented**: All 3 services have reference docs
✅ **Entities documented**: Technical reference complete (done)
✅ **No broken promises**: Don't claim features are documented if they're not

### Quality Standards

- All content verified against actual code (no assumptions)
- Every service/feature has YAML example
- Every entity reference includes attribute list
- All links work (no 404s)
- Examples use consistent kid names (Sarah, Alex pattern from tests)

### Out of Scope (Phase 2)

- Advanced automation examples
- Troubleshooting deep dives
- FAQ expansion
- Bonuses/penalties guide
- Access control patterns

---

## Phase 1 Task Breakdown

### Task 1: Installation & Quick Start (~2 hours)

1. Copy HACS/manual installation from old wiki
2. Create configuration wizard walkthrough with screenshots
3. Add v0.5.0 feature highlights section
4. Create "first chore" tutorial with step-by-step
5. Test all links

### Task 2: Badges Guide (~4 hours)

**REQUIRES CODE RESEARCH**:

1. Read config_flow.py badge configuration code
2. Verify badge maintenance attributes from coordinator.py
3. Document badge earning logic (points vs chores)
4. Document badge activation/deactivation
5. Document badge progress and status tracking
6. Copy example badge series from old wiki
7. Add entity attribute tables (link to Technical Reference)
8. Create badge configuration YAML examples

### Task 3: Services Reference (~2 hours)

1. Copy Reset All Data from old wiki
2. Copy Reset Overdue Chores from old wiki
3. Copy Set Chore Due Dates from old wiki
4. Verify service names match v0.5.0 code
5. Add YAML examples for each service
6. Test each service with example YAML
7. Add use case examples

### Task 4: Achievements & Challenges (~1 hour)

1. Copy content from old wiki
2. Light formatting updates
3. Verify sensor entity naming
4. Add reference links to Technical Reference
5. Keep all examples as-is (still relevant)

**Total Estimated Time**: ~9 hours

---

## Dependencies & Blockers

### Badges Guide Dependencies

**BLOCKER**: Must research badge code before writing

- Where is badge configuration in config_flow.py?
- What are badge maintenance attributes?
- How does badge activation/deactivation work?
- What is "highest badge earned" logic?

**Resolution**: Read code sections:

- `custom_components/kidschores/config_flow.py` - Badge configuration
- `custom_components/kidschores/coordinator.py` - Badge logic
- `custom_components/kidschores/sensor.py` - Badge sensors (already documented)

### No Other Blockers

- Installation: Source material exists
- Services: Source material exists
- Achievements: Source material adequate

---

## Post-MVP Migration Plan (Phase 2)

**After v0.5.0 release**, migrate remaining old wiki content:

1. **Automation Cookbook** (~800 lines)

   - Consolidate 6 Tips & Tricks pages
   - Organize by use case
   - Add v0.5.0 automation patterns

2. **Bonuses & Penalties** (~50 lines)

   - Migrate and expand old wiki content

3. **Access Control** (~100 lines)

   - Migrate security best practices

4. **Troubleshooting** (~200 lines)

   - Update for v0.5.0
   - Add common issues

5. **FAQ** (~100 lines)
   - Migrate and update

**Phase 2 Estimated**: ~1,250 lines additional

---

## Old Wiki Deprecation Strategy

**After Phase 1 Complete**:

1. Add banner to every old wiki page:

   ```
   > ⚠️ **NOTICE**: This documentation is being migrated to the new wiki.
   > See [New Documentation](link) for updated content.
   ```

2. Add specific redirects:

   - Installation → New Quick Start
   - Badges → New Badges Guide
   - Services → New Services Reference
   - Achievements → New Achievements Guide

3. Keep old wiki read-only as fallback

**After Phase 2 Complete**:

- Archive entire old wiki
- Redirect all traffic to new docs

---

## Navigation Updates (After MVP)

Add to `docs/wiki/README.md`:

**Getting Started**

- Installation & Quick Start
- Configuration Guide
- Advanced Features

**Features**

- Badges System
- Achievements & Challenges
- Services & Automation

**Reference**

- Technical Reference: Entities & States
- Chore Technical Reference
- Services Reference

**Support** (Phase 2)

- Troubleshooting
- FAQ

---

**Document Status**: READY FOR REVIEW
**Next Action**: Validate priorities and start Phase 1 implementation
