# Event Pattern Analysis - Supporting Document

**Parent Plan**: [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md)

## Purpose

This document analyzes event communication patterns for the manager-to-manager communication layer in the layered architecture refactor.

---

## Option 1: Home Assistant Dispatcher (Recommended)

Home Assistant provides `async_dispatcher_send` and `async_dispatcher_connect` for in-process pub/sub communication.

### Pros

- ✅ Built into Home Assistant - no external dependencies
- ✅ Already used by many HA integrations
- ✅ Async-native design
- ✅ Automatic cleanup with `async_dispatcher_connect` + `entry.async_on_unload`
- ✅ Type-safe signal names with constants

### Cons

- ⚠️ Signals are global to the HA instance (namespace carefully)
- ⚠️ No built-in filtering (receivers get all signals of that name)

### Implementation Pattern

```python
# const.py
SIGNAL_POINTS_CHANGE = f"{DOMAIN}_points_change"
SIGNAL_CHORE_APPROVED = f"{DOMAIN}_chore_approved"
SIGNAL_BADGE_EARNED = f"{DOMAIN}_badge_earned"

# managers/economy_manager.py
from homeassistant.helpers.dispatcher import async_dispatcher_send

class EconomyManager:
    async def deposit(self, kid_id: str, amount: float, source: str) -> float:
        # ... business logic ...
        new_balance = kid_data["points"]

        # Emit event for listeners
        async_dispatcher_send(
            self.hass,
            SIGNAL_POINTS_CHANGE,
            kid_id=kid_id,
            new_balance=new_balance,
            delta=amount,
            source=source,
        )
        return new_balance

# managers/gamification_manager.py
from homeassistant.helpers.dispatcher import async_dispatcher_connect

class GamificationManager:
    def __init__(self, hass, coordinator, ...):
        self.hass = hass
        self._unsubscribe_points = async_dispatcher_connect(
            hass,
            SIGNAL_POINTS_CHANGE,
            self._on_points_change,
        )

    async def _on_points_change(self, kid_id: str, new_balance: float, **kwargs) -> None:
        """React to point changes."""
        await self.evaluate_badges_for_kid(kid_id)

    def unsubscribe(self) -> None:
        """Cleanup on unload."""
        if self._unsubscribe_points:
            self._unsubscribe_points()
```

### Cleanup Pattern

```python
# __init__.py (async_setup_entry)
async def async_setup_entry(hass, entry):
    coordinator = KidsChoresDataCoordinator(...)

    # Register cleanup for all managers
    entry.async_on_unload(coordinator.gamification_manager.unsubscribe)
    entry.async_on_unload(coordinator.economy_manager.unsubscribe)
```

---

## Option 2: Custom Event Bus (Not Recommended)

Build a custom pub/sub system within the integration.

### Pros

- ✅ Full control over implementation
- ✅ Can add filtering, priorities, etc.

### Cons

- ❌ Reinventing the wheel
- ❌ More code to maintain
- ❌ No automatic lifecycle management
- ❌ Not consistent with HA patterns

### Verdict: Skip this option

---

## Option 3: HA Event Bus (hass.bus.async_fire)

Use Home Assistant's core event bus.

### Pros

- ✅ Can be listened to by automations
- ✅ Visible in HA Developer Tools → Events

### Cons

- ❌ Heavier weight than dispatcher (serialization overhead)
- ❌ Events are global and visible to all integrations
- ❌ Designed for external consumption, not internal coordination

### When to Use

- Only use `hass.bus.async_fire` when you want **external consumers** (automations, other integrations) to react
- For internal manager-to-manager communication, use dispatcher

---

## Recommendation

**Use Home Assistant Dispatcher** (`async_dispatcher_send` / `async_dispatcher_connect`) for all internal manager communication.

### Event Naming Convention

```python
# const.py - Event constants (all prefixed with SIGNAL_)

# Economy events
SIGNAL_POINTS_CHANGE = f"{DOMAIN}_points_change"
SIGNAL_POINTS_INSUFFICIENT = f"{DOMAIN}_points_insufficient"  # NSF

# Chore events
SIGNAL_CHORE_CLAIMED = f"{DOMAIN}_chore_claimed"
SIGNAL_CHORE_APPROVED = f"{DOMAIN}_chore_approved"
SIGNAL_CHORE_DISAPPROVED = f"{DOMAIN}_chore_disapproved"
SIGNAL_CHORE_OVERDUE = f"{DOMAIN}_chore_overdue"
SIGNAL_CHORE_RESET = f"{DOMAIN}_chore_reset"

# Reward events
SIGNAL_REWARD_CLAIMED = f"{DOMAIN}_reward_claimed"
SIGNAL_REWARD_APPROVED = f"{DOMAIN}_reward_approved"
SIGNAL_REWARD_DISAPPROVED = f"{DOMAIN}_reward_disapproved"

# Gamification events
SIGNAL_BADGE_EARNED = f"{DOMAIN}_badge_earned"
SIGNAL_BADGE_LOST = f"{DOMAIN}_badge_lost"  # Maintenance decay
SIGNAL_ACHIEVEMENT_UNLOCKED = f"{DOMAIN}_achievement_unlocked"
SIGNAL_CHALLENGE_COMPLETED = f"{DOMAIN}_challenge_completed"
```

### Event Payload Patterns

```python
# All events should include kid_id for filtering
# Additional fields depend on event type

# SIGNAL_POINTS_CHANGE payload:
{
    "kid_id": str,
    "old_balance": float,
    "new_balance": float,
    "delta": float,
    "source": str,  # "chore_approval", "reward_redemption", "penalty", "bonus", "adjustment"
    "reference_id": str | None,  # chore_id, reward_id, etc.
}

# SIGNAL_CHORE_APPROVED payload:
{
    "kid_id": str,
    "chore_id": str,
    "parent_name": str,
    "points_awarded": float,
    "is_shared": bool,
}

# SIGNAL_BADGE_EARNED payload:
{
    "kid_id": str,
    "badge_id": str,
    "badge_name": str,
    "level": int | None,  # For cumulative badges
    "points_bonus": float | None,
}
```

---

## Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EVENT FLOW                                       │
└─────────────────────────────────────────────────────────────────────────┘

User Action: Parent approves chore
       │
       ▼
┌──────────────────┐
│   ChoreManager   │ ──── SIGNAL_CHORE_APPROVED ────┐
│  approve(...)    │                                │
└────────┬─────────┘                                │
         │ calls                                    │
         ▼                                          ▼
┌──────────────────┐                    ┌──────────────────────┐
│  EconomyManager  │                    │ GamificationManager  │
│  deposit(...)    │                    │ _on_chore_approved() │
└────────┬─────────┘                    │ - update streak      │
         │                              │ - check achievements │
         │ emits                        └──────────────────────┘
         ▼
  SIGNAL_POINTS_CHANGE
         │
         ▼
┌──────────────────────┐
│ GamificationManager  │
│ _on_points_change()  │
│ - check badges       │
│ - emit if earned     │
└────────┬─────────────┘
         │ emits (if badge earned)
         ▼
  SIGNAL_BADGE_EARNED
         │
         ▼
┌──────────────────────┐
│ NotificationManager  │
│ _on_badge_earned()   │
│ - send notification  │
└──────────────────────┘
```

---

## Implementation Checklist

- [ ] Add `SIGNAL_*` constants to `const.py`
- [ ] Create base manager class with subscription helper
- [ ] Implement dispatcher connections in each manager
- [ ] Register unsubscribe callbacks in `async_setup_entry`
- [ ] Add integration tests for event propagation
- [ ] Document event payloads in `ARCHITECTURE.md`
