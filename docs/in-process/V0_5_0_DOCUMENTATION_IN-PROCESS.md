# v0.5.0 Documentation Initiative

## Initiative snapshot

- **Name / Code**: v0.5.0 Documentation - Entity-Type Organization
- **Target release / milestone**: v0.5.0 pre-release
- **Owner / driver(s)**: Documentation team (ad-ha, ccpk1)
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                   | Description                                            | % complete | Quick notes                                                              |
| ------------------------------ | ------------------------------------------------------ | ---------- | ------------------------------------------------------------------------ |
| Phase 1 – Getting Started      | Installation, Quick Start, Backup/Restore              | 100%       | ✅ COMPLETE - All 3 docs finalized (736 lines)                           |
| Phase 2 – Core Entity Guides   | Kids/Parents, Chores, Rewards, Badges, Points          | 100%       | ✅ All unblocked docs complete (6 of 6), only Badges blocked on research |
| Phase 3 – Services & Advanced  | Services reference, Achievements, Bonuses/Penalties    | 0%         | Services can migrate from old wiki                                       |
| Phase 4 – Welcome & Polish     | Home.md, README.md updates, navigation                 | 0%         | Depends on Phase 1-3 structure solidifying                               |
| Phase 5 – Production Migration | Copy to main wiki, add deprecation notices, test links | 0%         | After all phases complete and user-tested                                |

1. **Key objective** – Create comprehensive entity-type organized documentation for v0.5.0 release, stage in `docs/wiki/`, then migrate to production GitHub wiki (currently at `kidschores-ha.wiki/`).
2. **Summary of recent work**
   - ✅ **Phase 1 COMPLETE** (2025-01-15) - All 3 Getting Started documents finalized
     - Installation-and-Setup.md (236 lines) - Minimal setup guide, links to full docs
     - Quick-Start-Guide.md (184 lines) - Rewritten to be minimal, correct entity names
     - Backup-and-Restore-Reference.md (316 lines) - Streamlined, focus on custom KidsChores features
   - ✅ **Phase 2 - 100% COMPLETE** (2025-01-16) - All 6 unblocked docs complete
     - Configuration:-Kids-and-Parents.md (185 lines) - Simplified, maintainable guide
     - Chore-Configuration-Guide.md - Basic chore setup and fields
     - Chore-Advanced-Features.md - Shared chores, multi-approval, streaks
     - Chore-Technical-Reference.md - Complete field reference
     - Configuration:-Rewards.md (118 lines) - Simplified configuration guide with 5 fields, claiming workflow, sensor attributes, undo feature
     - Configuration:-Points-System.md (237 lines) - Points label/icon, manual adjustment buttons, earning/spending, badge multipliers, troubleshooting
   - Multiple refinement cycles based on user feedback
   - Minimal duplication strategy implemented (link to full guides)
   - Custom KidsChores features highlighted (backup system, auto-dashboard)
   - Completed documentation audit (DOCUMENTATION_AUDIT_2025.md)
   - Verified content coverage: shared chores ✅, overdue handling ✅
   - Created MVP outline with entity-type organization strategy
3. **Next steps (short term)**
   - **Phase 2 - Effectively Complete** - 100% of unblocked docs done (6 of 6)
   - **Current**: Badge code research (cumulative vs periodic badges in config_flow.py and en.json)
   - **Blocked**: Badges.md awaits comprehensive badge research completion
4. **Risks / blockers**
   - **BLOCKER**: Badge system code research required before writing Badges.md
     - Must understand config_flow.py badge configuration
     - Must understand coordinator.py badge maintenance logic
     - Must verify dashboard helper badge attributes
   - User testing feedback may require content restructuring
   - External link updates across ecosystem after production migration
5. **References**
   - [DOCUMENTATION_AUDIT_2025.md](DOCUMENTATION_AUDIT_2025.md) - Full inventory and gap analysis
   - [DOCUMENTATION_MVP_OUTLINE.md](DOCUMENTATION_MVP_OUTLINE.md) - Detailed content planning
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture reference
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Naming conventions
   - **Current production wiki**: `kidschores-ha.wiki/` (22 files, 1,806 lines) - cloned GitHub wiki
   - **Staging area**: `docs/wiki/` (5 files currently, 2,957 lines)
6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Entity-type organization (mirrors user experience)
     - ✅ Two-guide installation strategy (basic fresh start + technical backup/restore reference)
     - ✅ Staging approach (build in `docs/wiki/`, test/validate, then migrate to `kidschores-ha.wiki/` production)
     - ✅ Keep old wiki content with deprecation notices (version history, gradual migration)
     - ✅ Kids and Parents combined in single guide (tightly coupled workflows)
     - ✅ Shared chores kept in Chores.md (can extract later if needed)
   - **Completion confirmation**: `[ ]` All follow-up items completed (all phases 100%, README updated, main wiki migrated, old wiki notices added, all links tested) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after completing each document or major milestone. Reference commits/PRs where applicable.
- **Detailed tracking**: Use phase sections below for granular task tracking, code research notes, and migration checklists.

---

## Detailed phase tracking

### Phase 1 – Getting Started (Installation & Onboarding)

**Goal**: Provide clear onboarding path for new v0.5.0 users with both basic and technical installation guidance. All content created in `docs/wiki/` staging area.

**Steps / detailed work items**:

1. [x] **Installation-and-Setup.md** (236 lines, 6 hours) ✅ COMPLETE

   - ✅ HACS installation steps with screenshots preserved
   - ✅ Manual installation steps included
   - ✅ Configuration wizard walkthrough (minimal setup approach)
   - ✅ v0.5.0 feature highlights with Data Recovery dialog
   - ✅ Prerequisites section (HA 2024.1.0+, HACS)
   - ✅ Verification steps (simple integration check)
   - ✅ Next steps section with guide links
   - ✅ Emphasis on Points-only initial setup
   - **Status**: ✅ COMPLETE (2025-01-24, refined 2025-01-15)
   - **Dependencies**: None
   - **File**: `docs/wiki/Installation-and-Setup.md`

2. [x] **Quick-Start-Guide.md** (184 lines, 4 hours) ✅ COMPLETE

   - ✅ First kid creation walkthrough (Sarah example, name-only required)
   - ✅ First parent assignment (Mom with multi-parent note)
   - ✅ First chore creation (Make Bed daily, minimal required fields)
   - ✅ Complete claim-approve workflow with correct entity names
   - ✅ Status sensor verification for each step
   - ✅ Dashboard section emphasizes creative freedom → auto-dashboard option
   - ✅ Understanding the Workflow explanation with formatting
   - ✅ Links to full guides for details (minimal duplication)
   - **Status**: ✅ COMPLETE (2025-01-24, major rewrite 2025-01-15)
   - **Note**: Reduced from 346 → 184 lines for maintainability
   - **Dependencies**: None
   - **File**: `docs/wiki/Quick-Start-Guide.md`

3. [x] **Backup-and-Restore-Reference.md** (316 lines, 6 hours) ✅ COMPLETE
   - ✅ Overview of `/config/.storage/kidschores_data` file
   - ✅ Automatic Protection section (HA backups + custom automatic backups)
   - ✅ Custom backup system with triggers table (reset, pre-migration, recovery, manual)
   - ✅ Backup Retention configuration (General Options UI path)
   - ✅ Manual Backup Operations (create, delete, restore via dropdown)
   - ✅ Diagnostics as Backup method (portable backup strategy)
   - ✅ Three restore methods documented (General Options, Paste JSON, Data Recovery)
   - ✅ Backup file naming explanation with examples
   - ✅ Troubleshooting section
   - ✅ Best Practices (KidsChores-specific, defers to HA for general)
   - ✅ Why This Matters section (historical context)
   - **Status**: ✅ COMPLETE (2025-01-24, streamlined 2025-01-15)
   - **Note**: Reduced from 516 → 316 lines, focused on custom KidsChores features
   - **File**: `docs/wiki/Backup-and-Restore-Reference.md`
   - **Dependencies**: None

**Key issues**: None currently

---

### Phase 2 – Core Entity Guides

**Goal**: Document all core entity types users interact with: Kids, Parents, Chores, Rewards, Badges, Points.

**Steps / detailed work items**:

1. [ ] **Kids-and-Parents.md** (~300 lines, 8 hours)

   - Overview (why combined, roles and permissions)
   - Creating Kids section (Options Flow, configuration options, entity creation)
   - Creating Parents section (Options Flow, parent assignment)
   - Parent Approvals (workflow, notifications, multi-parent support v0.5.0)
   - Kid Entities Created (list with links to Technical Reference)
   - Managing Kids and Parents (edit, remove, reassign)
   - **Status**: Not started
   - **Dependencies**: None

2. [ ] **Chores.md** (~800 lines, 10 hours)

   - Extract and restructure from Chore-Configuration-Guide.md (1,256 lines)
   - Chore Entity Overview
   - Creating Chores (Options Flow, basic settings)
   - Completion Criteria (Independent, Shared All, Shared First, decision matrix)
   - Scheduling (no recurrence, daily, weekly, monthly, custom, daily multi-times)
   - Due Dates and Overdue Handling (4 modes with examples)
   - Approval Requirements (required vs auto-approve)
   - Per-Kid Customization (applicable days, points, hide, required)
   - Chore Entities Created (buttons, sensors)
   - Managing Chores (edit, remove, bulk operations)
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: docs/wiki/Chore-Configuration-Guide.md

3. [x] **Rewards.md** (118 lines, 6 hours) ✅ COMPLETE

   - ✅ Reward System Overview (universal claiming, simple workflow)
   - ✅ Creating Rewards (Options Flow, 5 configuration fields)
   - ✅ Reward Configuration Fields table (name, cost, description, labels, icon)
   - ✅ Claiming Workflow (claim → approve/disapprove, points processed at approval)
   - ✅ Undo Feature (kids can use disapprove button to cancel claims)
   - ✅ Entities Created (4 per kid per reward: sensor + 3 buttons)
   - ✅ Reward Sensor Attributes (comprehensive claim history, statistics, approval rates)
   - ✅ Managing Rewards (edit, delete with warnings)
   - ✅ Notifications (kid and parent notifications)
   - ✅ Troubleshooting (4 common issues)
   - ✅ Related Documentation links
   - **Status**: ✅ COMPLETE (2025-01-16, simplified to maintainable style)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Rewards.md`

4. [x] **Points-System.md** (237 lines, 6 hours) ✅ COMPLETE

   - ✅ Points Configuration (label & icon fields, manual adjustment buttons)
   - ✅ Earning Points (chores with badge multipliers, bonuses, manual adjustments)
   - ✅ Spending Points (rewards at approval time, penalties immediate)
   - ✅ Points Tracking (primary sensor attributes, optional extra sensors)
   - ✅ Manual Adjustment Buttons (6 button entities, default values, customization)
   - ✅ Badge Multipliers (what applies: chores/bonuses; what doesn't: rewards/penalties/manual)
   - ✅ Points System Flow (earning cycle, spending cycle, balance updates)
   - ✅ Troubleshooting (5 issues including statistics warnings after label changes)
   - ✅ Related Documentation links
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Points-System.md`

5. [ ] **Badges.md** (~400 lines, 12 hours) ⚠️ **BLOCKED**

   - **BLOCKER**: Code research required before writing
   - Badge System Overview (what changed in v0.5.0)
   - Creating Badges (config_flow.py - RESEARCH NEEDED)
   - How Badges Are Earned (points vs chores logic)
   - Badge Effects (points multiplier)
   - Badge Maintenance (coordinator.py - RESEARCH NEEDED)
   - Badge Progress Tracking (dashboard helper attributes)
   - Badge Entities Created (3 sensor types)
   - Badge Examples (keep from old wiki: Bronze/Silver/Gold, Gamer, Star Collector)
   - Managing Badges (activate/deactivate, remove)
   - **Status**: Blocked on research
   - **Dependencies**: Badge code research task (see Key Issues)
   - **Files to research**:
     - `custom_components/kidschores/config_flow.py` - Badge configuration
     - `custom_components/kidschores/coordinator.py` - Badge logic and maintenance
     - `custom_components/kidschores/sensor.py` - Badge sensors (already documented in Technical Reference)

6. [ ] **Points-System.md** (~200 lines, 4 hours)
   - Points System Overview
   - Configuring Points (label, icon, system settings)
   - Earning Points (chores, badge multipliers, bonuses)
   - Spending Points (rewards)
   - Losing Points (penalties, reward claims)
   - Points Tracking (sensor.kc\_{kid}\_points, history)
   - **Status**: Not started
   - **Dependencies**: None

**Key issues**:

- **Badge Code Research Task** (BLOCKER for Badges.md):
  - Investigate config_flow.py badge creation flow
  - Document badge configuration parameters
  - Understand badge maintenance system in coordinator.py
  - Verify dashboard helper badge attributes
  - Understand activation/deactivation logic
  - Document "highest badge earned" calculation
  - Estimated: 4 hours research + documentation

---

### Phase 3 – Services & Advanced Features

**Goal**: Document service actions and advanced features (achievements, bonuses, penalties).

**Steps / detailed work items**:

1. [ ] **Services-Reference.md** (~300 lines, 6 hours)

   - Overview (what services available, when to use)
   - **kidschores.reset_all_data**:
     - Purpose and use cases
     - What gets reset vs what stays
     - YAML example
     - Warning about data loss
   - **kidschores.reset_overdue_chores**:
     - Purpose and use cases
     - Parameters (chore_id, chore_name, kid_name)
     - 4 use case examples with YAML
     - Note: Only works on recurring chores
   - **kidschores.set_chore_due_dates**:
     - Purpose and use cases
     - Parameters
     - 3 scenarios (one-time, calendar-based, dynamic updates)
     - Interaction with recurrence and states
     - YAML examples
   - Service Integration (automations, scripts, dashboards)
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: Old wiki Service-\*.md (3 files, 166 lines)

2. [ ] **Achievements-and-Challenges.md** (~180 lines, 4 hours)

   - Migrate from old wiki (149 lines)
   - Achievement vs Challenge definitions
   - Sensor naming conventions
   - Progress tracking explanation
   - Update logic and completion handling
   - Parent management actions
   - Example achievements (milestones, streaks - keep from old wiki)
   - Example challenges (time-bound, themed - keep from old wiki)
   - Minor formatting updates
   - Verify sensor entity IDs match current code
   - Add reference links to Technical Reference
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: Old wiki Challenges-&-Achievements (149 lines)

3. [ ] **Bonuses-and-Penalties.md** (~100 lines, 3 hours)
   - Migrate from old wiki (27 lines) + expansion
   - Overview (point adjustments outside chores)
   - Creating bonuses (Options Flow)
   - Creating penalties (Options Flow)
   - Applying to kids
   - Tracking applied bonuses/penalties
   - Use cases and examples
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: Old wiki Bonuses-&-Penalties (27 lines)

**Key issues**: None currently

---

### Phase 4 – Welcome & Polish

**Goal**: Create welcome page, update README, establish navigation structure.

**Steps / detailed work items**:

1. [ ] **Home.md** (Wiki Landing Page) (~200 lines, 4 hours)

   - What is KidsChores section (2-3 paragraphs from README)
   - What This Wiki Covers (Getting Started, Core Features, Advanced, Automation, Technical, Support)
   - Quick Links section (Installation, Quick Start, Chores, Services, Technical Reference)
   - New in v0.5.0 section (parent approvals, overdue handling, badge maintenance, dashboard helper, notifications, custom schedules)
   - Need Help section (Troubleshooting, FAQ, Community, GitHub Issues)
   - Contributors section
   - **Status**: Not started
   - **Dependencies**: Phase 1-3 structure solidified

2. [ ] **README.md Update** (~3 hours)

   - Update version badge to v0.5.0
   - Add "New in v0.5.0" callout box:
     - Parent Approvals (multi-parent support)
     - Overdue Handling (4 modes)
     - Badge Maintenance
     - Dashboard Helper improvements
     - Notification modernization
     - Custom scheduling enhancements
   - Update Quick Installation link (line ~50)
   - Update Multi-User Management section (add multi-parent bullet)
   - Update Chore Management section (overdue modes, applicable days)
   - Update Badge System section (badge maintenance mention)
   - Update Detailed Statistics section (dashboard helper)
   - Update all wiki links (old wiki → docs/wiki/ or GitHub wiki)
   - Update bottom references
   - **Status**: Not started
   - **Dependencies**: Phase 1-3 complete (links need destinations)
   - **File**: /workspaces/kidschores-ha/README.md

3. [ ] **docs/wiki/README.md Update** (Navigation Index) (~1 hour)

   - Create/update directory-style navigation
   - Structure:
     - Getting Started section
     - Core Entities section
     - Advanced Features section
     - Automation and Services section
     - Technical Reference section
     - Support section (Phase 2)
   - Link to all documents created in Phases 1-3
   - **Status**: Not started
   - **Dependencies**: Phase 1-3 complete

4. [ ] **Dashboard-Integration.md** (~100 lines, 2 hours)
   - Dashboard overview
   - Link to kidschores-ha-dashboard repository
   - Dashboard helper sensor explanation
   - Integration with entities
   - Installation instructions (link to dashboard repo)
   - **Status**: Not started
   - **Dependencies**: None

**Key issues**: None currently

---

### Phase 5 – Production Migration

**Goal**: Migrate completed docs from `docs/wiki/` staging area to production GitHub wiki (`kidschores-ha.wiki/`), add deprecation notices to old wiki content.

**Steps / detailed work items**:

1. [ ] **Clone and Prepare Wiki Repository**

   ```bash
   git clone https://github.com/ad-ha/kidschores-ha.wiki.git
   cd kidschores-ha.wiki
   git checkout -b v0.5.0-docs
   ```

   - **Status**: Not started
   - **Dependencies**: Phase 1-4 complete

2. [ ] **Copy Content to Wiki Repo**

   - Copy all files from `docs/wiki/` to wiki repo
   - Preserve directory structure (if using folders)
   - Update internal links (docs/wiki/ paths → relative wiki paths)
   - **Status**: Not started

3. [ ] **Add Deprecation Notices to Old Wiki Pages** (in `kidschores-ha.wiki/`)

   - Template:
     ```markdown
     > ⚠️ **DEPRECATED**: This page is outdated for v0.5.0+
     >
     > **For v0.5.0 documentation**, see:
     >
     > - [New Installation Guide](Installation-and-Setup.md)
     > - [New Chores Documentation](Chores.md)
     > - [Full Documentation Index](Home.md)
     >
     > This page remains for **v0.4.x reference only**.
     ```
   - Add to each page in `kidschores-ha.wiki/`
   - List of pages to update:
     - Installation-&-Setup.md → Installation-and-Setup.md
     - Badges:-Overview-&-Examples.md → Badges.md
     - Bonuses-&-Penalties:-Overview-&-Examples.md → Bonuses-and-Penalties.md
     - Challenges-&-Achievements:-Overview-&-Functionality.md → Achievements-and-Challenges.md
     - Service:-Reset-All-Data.md → Services-Reference.md
     - Service:-Reset-Overdue-Chores.md → Services-Reference.md
     - Service:-Set-Chore-Due-Dates.md → Services-Reference.md
     - Chore-Status-and-Recurrence-Handling.md → Chores.md
     - Sensors-&-Buttons.md → Technical-Reference:-Entities-&-States.md
   - **Status**: Not started

4. [ ] **Create Version Archive**

   - Create `archive/v0.4/` folder in wiki
   - Move old wiki pages to archive (optional, can keep in main folder with notices)
   - Add "Documentation Version: v0.5.0" to new page headers
   - **Status**: Not started

5. [ ] **Update Navigation**

   - Update `_Sidebar.md` with new structure
   - Create breadcrumb navigation in each page (if desired)
   - **Status**: Not started

6. [ ] **Test All Links**

   - Internal links (between wiki pages)
   - External references (GitHub repo, issues, community)
   - README links
   - Old wiki deprecation links
   - **Status**: Not started

7. [ ] **Merge and Publish**

   ```bash
   git add .
   git commit -m "docs: v0.5.0 documentation migration"
   git push origin v0.5.0-docs
   # Merge to main after review
   ```

   - **Status**: Not started

8. [ ] **Update External Links**
   - Community forum posts
   - HACS listing
   - Any other ecosystem references
   - **Status**: Not started

**Key issues**: None currently

---

## Testing & validation

**Pre-Migration Testing** (during Phase 1-4):

- [ ] All internal links work within `docs/wiki/`
- [ ] All code examples are accurate (YAML service calls)
- [ ] All entity references match actual code (verified from source)
- [ ] Screenshots are current (if used)
- [ ] User testing feedback incorporated

**Post-Migration Testing** (Phase 5):

- [ ] All wiki pages render correctly on GitHub
- [ ] Internal wiki links work (relative paths)
- [ ] Deprecation notices display correctly
- [ ] Old wiki pages link to new pages correctly
- [ ] README links point to new wiki
- [ ] External references updated

**Outstanding Tests**:

- User feedback on entity-type organization (will gather during Phase 1-4)
- Accessibility review (screen reader compatibility)

---

## Notes & follow-up

**Architectural Decisions**:

- **Entity-type organization**: Mirrors how users experience KidsChores through entity interactions. Users configure kids, assign chores, view sensors, press buttons - documentation should follow this flow.
- **Wiki Structure**:
  - **Current production wiki**: `kidschores-ha.wiki/` (cloned from GitHub wiki, 22 files, v0.4.x content)
  - **Staging area**: `docs/wiki/` (new v0.5.0 content, validate before production)
  - **Rationale**: Staging in `docs/wiki/` allows validation before public exposure, easier iteration, safer migration without disrupting current wiki.
- **Two-guide installation strategy**: Keeps new users focused on fresh start, advanced users get technical backup/restore details separately.
- **Combined Kids-and-Parents guide**: These entities are tightly coupled (parent assignment, approval workflows), documenting together reduces cross-references.

**Phase 2 Content** (Deferred Post-Release):

- Automation Cookbook (~400 lines) - Consolidate Tips & Tricks
- Automation Examples folder - Migrate 6 Tips & Tricks pages (661 lines)
- Troubleshooting Guide (~200 lines) - Update for v0.5.0
- FAQ (~100 lines) - Migrate and expand
- Access Control Guide (~100 lines) - Security best practices

**Follow-up Tasks**:

- After v0.5.0 release: Gather user feedback on documentation structure
- Consider extracting Shared-Chores-Advanced.md if Chores.md becomes unwieldy
- Evaluate need for Entity-Attributes-Deep-Dive.md (may be redundant with Technical Reference)
- Translation coordination (if multilingual wiki planned)

**Badge Code Research Notes** (To be filled during research):

- _Configuration flow badge creation: [findings]_
- _Badge maintenance system: [findings]_
- _Dashboard helper attributes: [findings]_
- _Activation/deactivation behavior: [findings]_

---

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
