# KidsChores Documentation - Staging Area

This directory contains the v0.5.0 documentation in staging, organized for migration to the GitHub wiki.

---

## Documentation Structure

### 🚀 Getting Started (4 documents)

New user onboarding and installation:

- **[Getting-Started:-Installation.md](Getting-Started:-Installation.md)** (236 lines) - HACS/manual installation, configuration wizard
- **[Getting-Started:-Quick-Start.md](Getting-Started:-Quick-Start.md)** (184 lines) - First kid, chore, and approval workflow
- **[Getting-Started:-Scenarios.md](Getting-Started:-Scenarios.md)** (150 lines) - Creative family setup ideas (Gaming, Classic, Theme-based)
- **[Getting-Started:-Backup-Restore.md](Getting-Started:-Backup-Restore.md)** (316 lines) - Custom backup system, restore methods

### ⚙️ Configuration (8 documents)

Core entity setup guides:

- **[Configuration:-Kids-Parents.md](Configuration:-Kids-Parents.md)** (185 lines) - Create profiles, assign parents
- **[Configuration:-Chores.md](Configuration:-Chores.md)** (1,259 lines) - Chore configuration fields and patterns
- **[Configuration:-Chores-Advanced.md](Configuration:-Chores-Advanced.md)** (347 lines) - Per-kid customization, custom scheduling
- **[Configuration:-Rewards.md](Configuration:-Rewards.md)** (118 lines) - Reward setup and claiming workflow
- **[Configuration:-Points.md](Configuration:-Points.md)** (237 lines) - Points customization and manual adjustments
- **[Configuration:-Badges-Cumulative.md](Configuration:-Badges-Cumulative.md)** (411 lines) - Progressive achievement badges
- **[Configuration:-Badges-Periodic.md](Configuration:-Badges-Periodic.md)** (653 lines) - Daily/weekly maintenance badges

### 🔧 Services & Automation (4 documents)

Integration with Home Assistant:

- **[Services:-Reference.md](Services:-Reference.md)** (600 lines) - Complete service documentation (15+ services)
- **[Examples:-NFC-Tags.md](Examples:-NFC-Tags.md)** (520 lines) - Physical chore cards
- **[Examples:-Calendar-Scheduling.md](Examples:-Calendar-Scheduling.md)** (660 lines) - Calendar integration
- **[Examples:-Overdue-Penalties.md](Examples:-Overdue-Penalties.md)** (500 lines) - Automated penalties

### 📖 Advanced Topics (5+ documents)

Power user features:

- **[Advanced:-Badges-Overview.md](Advanced:-Badges-Overview.md)** - Badge psychology and design overview
- **[Advanced:-Badges-Cumulative.md](Advanced:-Badges-Cumulative.md)** - Advanced cumulative badge mechanics
- **[Advanced:-Badges-Periodic.md](Advanced:-Badges-Periodic.md)** - Advanced periodic badge mechanics
- **[Advanced:-Dashboard.md](Advanced:-Dashboard.md)** (100 lines) - Dashboard helper and auto-populating UI
- Access Control, Bonuses/Penalties, Challenges/Achievements (to be migrated from old wiki)

### 🆘 Support (2+ documents)

Troubleshooting and help:

- FAQ (to be migrated from old wiki)
- Troubleshooting Guide (to be migrated from old wiki)

### 📚 Technical Reference (5 documents)

Developer documentation:

- **[Technical:-Chores.md](Technical:-Chores.md)** (437 lines) - Entity reference, state mapping, Jinja templates
- **[Technical:-Badge-Entities.md](Technical:-Badge-Entities.md)** - Badge sensor technical details
- **[Technical:-Configuration.md](Technical:-Configuration.md)** - Config/Options flow deep dive
- **[Technical:-Entities-States.md](Technical:-Entities-States.md)** - Complete entity documentation
- **[Technical:-Services-Legacy.md](Technical:-Services-Legacy.md)** - Technical service documentation

---

## Research & Working Documents (Not Migrated)

These files remain in staging for internal reference:

- **RESEARCH_CUMULATIVE_BADGES.md** (449 lines) - Badge research
- **RESEARCH_PERIODIC_BADGES.md** (574 lines) - Badge research
- **RESEARCH_POINTS.md** - Points system research
- **RESEARCH_REWARDS.md** - Rewards system research
- **CORRECTIONS_CHORE_TECHNICAL_REFERENCE.md** - Tracking corrections
- **PROPOSED_HEADING_STRUCTURE.md** - Structure proposals

---

## Migration Status

**Phase 1-3**: ✅ Complete (~8,000 lines)

- All Getting Started, Configuration, and Services documentation complete
- Code-validated against v0.5.0
- Service documentation accuracy updates applied

**Phase 4**: ✅ Complete

- All files renamed with consistent category prefixes
- All internal links updated and verified
- File naming scheme supports alphabetical sorting by category
- Navigation paths fully functional (Getting Started → Configuration → Examples → Advanced → Technical)

**Phase 5**: ⏳ Pending

- Production migration to GitHub wiki
- Legacy wiki deprecation notice
- Link verification

---

## Document Counts

**Production Ready**: ~27 documents (~10,000 lines)
**Research/Internal**: ~6 documents (~2,000 lines)
**Total Staging**: ~33 files

---

## Navigation

For user-facing documentation structure, see **[Home.md](Home.md)** (wiki landing page).

For internal tracking, see **[../in-process/V0_5_0_DOCUMENTATION_IN-PROCESS.md](../in-process/V0_5_0_DOCUMENTATION_IN-PROCESS.md)**.
