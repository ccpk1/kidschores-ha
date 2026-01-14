# Per-Kid Applicable Days + Multi-Times Feature - Quick Reference

**Status**: ✅ Planning Complete - Ready for Implementation
**Code**: PKAD-2026-001
**Timeline**: 14-16 hours (Option B - Full Feature)
**Release**: v0.5.0

---

## Your Problem → Our Solution

**Your Challenge**:

```
10 chores × 3 kids with different schedules/times = 30 chore entries
Example:
  - Wash up AM (Kid A): Mon/Thu @ 08:00|17:00
  - Wash up AM (Kid B): Tue/Fri @ 06:00|12:00|18:00
  - Wash up AM (Kid C): Wed/Sat @ 09:00|16:00
  = 3 entries for ONE chore
```

**Our Solution**:

```
1 chore with per-kid settings:
  Wash up (INDEPENDENT + DAILY_MULTI)
  ├─ Kid A: Mon/Thu @ 08:00|17:00
  ├─ Kid B: Tue/Fri @ 06:00|12:00|18:00
  └─ Kid C: Wed/Sat @ 09:00|16:00
  = 1 entry for ALL kids
```

**Result**: 30 chores → 10 chores 🎉

---

## What's Approved

✅ **Data Model**:

- INDEPENDENT chores: **per-kid days + times** (chore-level fields = null)
- No fallback to chore-level (single source of truth)
- Clear on save (prevents accidents)

✅ **Templating Feature** (UX convenience):

- User enters days + times in main form → helper form pre-fills
- "Apply to all kids" button → copies both days and times to all kids
- Users can still customize each kid individually

✅ **Selected Scope**: Option B - Per-kid applicable days + per-kid multi-times (14-16 hrs)

---

## Architecture Decisions

| Decision                 | What                                                                                          | Why                               |
| ------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------- |
| **Storage**              | `per_kid_applicable_days: {kid_id: [0,3], ...}` + `per_kid_daily_multi_times: {kid_id: "08:00 | 17:00", ...}`                     | Mirrors `per_kid_due_dates` (proven pattern) |
| **Chore-level**          | Cleared to `null` for INDEPENDENT (both days + times)                                         | No ambiguity, no wrong fallback   |
| **Templating**           | User enters both days + times in main form → helper pre-fills                                 | Faster editing, UX improvement    |
| **Due Date Computation** | Auto-computed from applicable days + times                                                    | Coordinator handles it            |
| **Schema**               | No increment (stays v43)                                                                      | Minimal risk, backward compatible |

---

## Three-Phase Implementation

### Phase 1: Setup (1-2 hours)

- Constants, validation, translations
- No schema changes

### Phase 2: UI & Flow (3-4 hours)

- Extended helper form (days + times for DAILY_MULTI)
- Templating feature ("Apply to all" button for both)
- Main form accepts template values (days + times)

### Phase 3: Coordinator (2-3 hours)

- Clear chore-level fields for INDEPENDENT (days + times)
- Auto-compute per-kid due dates from days + times
- Single source of truth enforcement

### Phase 4: Integration (1-2 hours)

- Calendar updates (per-kid day + time lookup)
- Dashboard helper (shows assigned days + times)
- Entity attributes (optional)

### Phase 5: Testing (2-3 hours)

- Test scenarios, edge cases, migration
- Multi-times + days validation
- > 95% coverage

---

## Documents

📋 **Main Plan**: [FEATURE_APPLICABLE_DAYS_PER_KID_IN-PROCESS.md](./FEATURE_APPLICABLE_DAYS_PER_KID_IN-PROCESS.md)

- Full implementation plan, 5 phases, all details

📚 **Supporting Analysis**: [FEATURE_APPLICABLE_DAYS_PER_KID_SUP_CROSS_FEATURE_ANALYSIS.md](./FEATURE_APPLICABLE_DAYS_PER_KID_SUP_CROSS_FEATURE_ANALYSIS.md)

- Data model deep-dive
- Templating feature explanation
- Option B analysis (per-kid multi-times)
- Migration strategy
- UI mockups

📄 **Initial Feasibility** (archived for reference): [FEATURE_APPLICABLE_DAYS_PER_KID_FEASIBILITY.md](./FEATURE_APPLICABLE_DAYS_PER_KID_FEASIBILITY.md)

---

## Key Files to Modify

| File              | Component                            | Complexity |
| ----------------- | ------------------------------------ | ---------- |
| `const.py`        | Constants, translation keys          | Low        |
| `flow_helpers.py` | Validation functions                 | Low        |
| `config_flow.py`  | Main chore form                      | Low        |
| `options_flow.py` | Helper form + templating             | Medium     |
| `coordinator.py`  | Due date computation, field clearing | Medium     |
| `calendar.py`     | Per-kid day lookup                   | Low        |
| `sensor.py`       | Dashboard helper, entity attributes  | Low        |
| `en.json`         | Translations                         | Low        |
| `tests/`          | Comprehensive test coverage          | Medium     |

---

## Ready to Build?

✅ **Yes** - All decisions made, Option B selected for v0.5.0
→ Hand off to Builder Agent with [FEATURE_APPLICABLE_DAYS_PER_KID_IN-PROCESS.md](./FEATURE_APPLICABLE_DAYS_PER_KID_IN-PROCESS.md)
