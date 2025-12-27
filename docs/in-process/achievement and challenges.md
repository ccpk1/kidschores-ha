# Feature Request: Unify and Extend Achievement/Challenge System with Badge-Based Tracking

**Date:** 2025-12-22  
**Requested By:** ccpk1  
**Status:** Open  
**Priority:** High  
**Scope:** Achievement & Challenge System Refactor + Enhancement

---

## Overview

This feature request proposes a significant refactor and enhancement to the achievements and challenges system. The core idea is to leverage the existing badge tracking logic (which is already sophisticated and battle-tested) as a foundation, then extend both achievements and challenges to support badge-based criteria alongside existing chore-based criteria.

This enables powerful new use cases like:
- "Earn 3 badges this month" achievements
- "Earn all 5 badges" achievements  
- "Be the first to earn the Gold badge" challenges
- "Collectively earn 10 badges as a family" challenges
- Mixed criteria: "Complete 50 chores AND earn 2 badges"

---

## Current State Analysis

### Existing Badge Tracking Logic

**Location:** `sensor.py` - `BadgeSensor` and related logic

**Current Capabilities:**
```python
class BadgeSensor(CoordinatorEntity, SensorEntity):
    """Tracks badge progress and awards for a specific badge."""
    
    @property
    def native_value(self):
        """Badge state with attributes showing threshold and who earned it."""
        # Computes:
        # - threshold_type: "points" | "chore_count"
        # - threshold_value: numeric value needed
        # - points_multiplier: bonus multiplier when earned
        # - kids_earned: list of kids who earned badge
        # - days_since_earned: for each kid
```

**What Badge Tracking Does Well:**
- ✅ Tracks progress toward numeric milestones
- ✅ Evaluates completion status for multiple kids independently
- ✅ Handles both threshold-based (points/chore_count) tracking
- ✅ Supports points multipliers
- ✅ Maintains history of who earned and when
- ✅ Real-time updates as conditions change
- ✅ Works with coordinator's update loop

### Existing Achievement System

**Location:** `coordinator.py` and `sensor.py`

**Current Capabilities:**
```python
ACHIEVEMENT_TYPE_STREAK = "chore_streak"           # e.g., "Make bed 20 days in a row"
ACHIEVEMENT_TYPE_TOTAL = "chore_total"             # e.g., "Complete 100 chores overall"
ACHIEVEMENT_TYPE_DAILY_MIN = "daily_min"           # e.g., "Complete 5 chores in a day"
```

**Limitations:**
- ❌ Only supports chore-based criteria
- ❌ No badge awareness
- ❌ Streak logic is specific to achievements, hard to reuse
- ❌ Cannot track "earn X badges" milestones
- ❌ No competitive elements for challenges

### Existing Challenge System

**Location:** `coordinator.py` and `sensor.py`

**Current Capabilities:**
```python
CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW = "total_within_window"  # e.g., "50 chores in a month"
CHALLENGE_TYPE_DAILY_MIN = "daily_min"                      # e.g., "3+ chores every day"
```

**Limitations:**
- ❌ Only supports chore completions
- ❌ No badge integration
- ❌ Limited competitive logic
- ❌ Cannot track badge achievements as milestones

---

## Proposed Architecture

### Phase 1: Refactor - Create Unified Tracking Framework

#### Create New Abstract Tracking Class

Instead of having separate logic for badges, achievements, and challenges, create a unified `ProgressTracker` abstraction:

```python
# In coordinator.py
class ProgressTracker:
    """Abstract base class for tracking progress toward criteria."""
    
    def __init__(self, tracker_id: str, criteria: dict):
        """
        Args:
            tracker_id: Unique identifier (badge_1, achievement_5, challenge_3)
            criteria: Definition of what constitutes progress
        """
        self.tracker_id = tracker_id
        self.criteria = criteria
        self.progress = {}  # Per-child progress
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        """
        Evaluate current progress for a kid as percentage (0-100).
        
        Args:
            kid_id: Child to evaluate
            current_data: Current state from coordinator
            
        Returns:
            Progress percentage 0-100
        """
        raise NotImplementedError
    
    def is_complete(self, kid_id: str, current_data: dict) -> bool:
        """Check if criteria are met for this kid."""
        return self.evaluate_progress(kid_id, current_data) >= 100
    
    def get_remaining(self, kid_id: str, current_data: dict) -> dict:
        """Return data about what's needed to complete."""
        raise NotImplementedError
```

#### Specific Tracker Implementations

```python
class ChoreCountTracker(ProgressTracker):
    """Track progress toward completing N chores (generic)."""
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        chores_completed = self._count_chores_for_kid(kid_id, current_data)
        target = self.criteria['target_count']
        return min(100, (chores_completed / target) * 100)

class BadgeCountTracker(ProgressTracker):
    """Track progress toward earning N badges."""
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        # NEW - Count how many badges this kid has earned
        badges_earned = self._count_badges_for_kid(kid_id, current_data)
        target = self.criteria['target_badge_count']
        return min(100, (badges_earned / target) * 100)

class SpecificBadgeTracker(ProgressTracker):
    """Track progress toward earning specific badge(s)."""
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        # NEW - Check if kid has earned specific badge(s)
        required_badges = self.criteria['required_badge_ids']
        earned_badges = self._get_badges_for_kid(kid_id, current_data)
        
        # Can use "all" or "any" logic
        logic = self.criteria.get('logic', 'all')  # 'all' | 'any'
        
        if logic == 'all':
            earned_all = all(bid in earned_badges for bid in required_badges)
            return 100 if earned_all else 0
        else:  # 'any'
            earned_any = sum(1 for bid in required_badges if bid in earned_badges)
            return (earned_any / len(required_badges)) * 100

class StreakTracker(ProgressTracker):
    """Track current streak (days/completions in a row)."""
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        current_streak = self._get_streak_for_kid(kid_id, current_data)
        target = self.criteria['target_streak']
        return min(100, (current_streak / target) * 100)

class CompetitiveTracker(ProgressTracker):
    """Track competitive progress across multiple kids."""
    
    def evaluate_progress(self, kid_id: str, current_data: dict) -> float:
        # Track individual progress in competitive context
        # Used by challenges where rank matters
        return self._get_individual_progress(kid_id, current_data)
    
    def get_competitive_standings(self, current_data: dict) -> list:
        """Return ranked list of kids by progress."""
        standings = []
        for kid_id in self._get_assigned_kids(current_data):
            standings.append({
                'kid_id': kid_id,
                'kid_name': self._get_kid_name(kid_id),
                'progress': self.evaluate_progress(kid_id, current_data),
                'rank': None  # Will be assigned after sorting
            })
        
        # Sort and assign ranks
        standings.sort(key=lambda x: x['progress'], reverse=True)
        for i, standing in enumerate(standings, 1):
            standing['rank'] = i
        
        return standings
```

#### Data Structure - Unified Criteria Format

```python
# Existing badge structure stays the same
badge = {
    "id": "badge_1",
    "name": "First 50 Chores",
    "description": "Complete your first 50 chores",
    "threshold_type": "chore_count",
    "threshold_value": 50,
    "points_multiplier": 1.2,
    # ... existing fields
}

# NEW: Achievement with unified criteria
achievement = {
    "id": "achievement_1",
    "name": "Badge Collector - Bronze",
    "description": "Earn 3 badges",
    "criteria_type": "badge_count",  # NEW - can be: chore_count, badge_count, specific_badges, etc.
    "criteria": {
        "target_badge_count": 3,  # NEW - earn any 3 badges
    },
    "assigned_kids": ["kid1", "kid2"],
    "reward_points": 250,
}

# NEW: Achievement with specific badges
achievement = {
    "id": "achievement_2",
    "name": "Badge Master - Gold",
    "description": "Earn the Gold, Silver, and Bronze badges",
    "criteria_type": "specific_badges",  # NEW
    "criteria": {
        "required_badge_ids": ["badge_gold", "badge_silver", "badge_bronze"],
        "logic": "all",  # Must earn ALL specified badges
    },
    "assigned_kids": ["kid1", "kid2"],
    "reward_points": 500,
}

# NEW: Achievement with mixed criteria
achievement = {
    "id": "achievement_3",
    "name": "Master of All Trades",
    "description": "Complete 50 chores AND earn 2 badges",
    "criteria_type": "mixed",  # NEW
    "criteria": {
        "components": [
            {"type": "chore_count", "target": 50, "weight": 0.5},
            {"type": "badge_count", "target": 2, "weight": 0.5},
        ]
    },
    "assigned_kids": ["kid1", "kid2"],
    "reward_points": 400,
}

# NEW: Challenge with badge criteria
challenge = {
    "id": "challenge_1",
    "name": "Badge Race - December",
    "description": "First to earn 5 badges wins!",
    "criteria_type": "badge_count",  # NEW
    "criteria": {
        "target_badge_count": 5,
    },
    "challenge_type": "competitive",  # NEW - specific to challenges
    "tracking": {
        "mode": "first_to_complete",  # NEW - who finishes first
        "announcements": True,  # Announce when someone wins
    },
    "assigned_kids": ["kid1", "kid2", "kid3"],
    "reward_points": 750,
    "start_date": "2025-12-01",
    "end_date": "2025-12-31",
}

# NEW: Challenge with competitive badge tracking
challenge = {
    "id": "challenge_2",
    "name": "Badge Collectors Showdown",
    "description": "Who can earn the most badges?",
    "criteria_type": "badge_count",
    "criteria": {
        "target_badge_count": 10,  # Track toward this
    },
    "challenge_type": "competitive",
    "tracking": {
        "mode": "most_progress",  # Whoever has highest count by end wins
        "announcements": True,
        "checkpoint_notifications": True,  # Notify at 25%, 50%, 75%
    },
    "assigned_kids": ["kid1", "kid2", "kid3"],
    "reward_points": {
        "1st_place": 1000,
        "2nd_place": 750,
        "3rd_place": 500,
    },
    "start_date": "2025-12-01",
    "end_date": "2025-12-31",
}
```

---

## Phase 2: Extend - New Achievement/Challenge Types

### Achievement New Types

Leveraging unified tracking, achievements can now support:

#### 1. Badge Count Achievement
"Earn N badges in a time period"

```python
ACHIEVEMENT_TYPE_BADGE_COUNT = "badge_count"
# Example: "Earn 3 badges this month"

achievement_data = {
    "criteria_type": "badge_count",
    "criteria": {
        "target_badge_count": 3,
    },
    "time_window": "month",  # optional - evaluated within month
}
```

**Tracking:**
- Child must earn any 3 distinct badges
- Progress updates as badges are earned
- Sensor shows "2 of 3 badges earned"

#### 2. Specific Badges Achievement
"Earn specific badge(s)"

```python
ACHIEVEMENT_TYPE_SPECIFIC_BADGES = "specific_badges"
# Example: "Earn the Gold, Silver, and Bronze badges"

achievement_data = {
    "criteria_type": "specific_badges",
    "criteria": {
        "required_badge_ids": ["badge_id_1", "badge_id_2", "badge_id_3"],
        "logic": "all",  # or "any"
    },
}
```

**Tracking:**
- Child must earn specific badges
- Sensor shows which badges earned/remaining
- Can use "any" logic (earn 2 of 3 specified) or "all" logic

#### 3. Badge Multiplier Achievement
"Earn badges while having another badge active (multiplier)"

```python
ACHIEVEMENT_TYPE_BADGE_WITH_MULTIPLIER = "badge_multiplier"
# Example: "Earn 2 badges while Bronze badge multiplier is active"

achievement_data = {
    "criteria_type": "badge_multiplier",
    "criteria": {
        "target_badges": 2,
        "while_badge_active": "badge_bronze",
        "multiplier_threshold": 1.2,
    },
}
```

**Tracking:**
- Count badges earned during multiplier period
- Progress shows "1 of 2 badges earned while multiplied"

#### 4. Mixed Criteria Achievement
"Combine chore + badge progress"

```python
ACHIEVEMENT_TYPE_MIXED = "mixed"
# Example: "Complete 50 chores AND earn 2 badges"

achievement_data = {
    "criteria_type": "mixed",
    "criteria": {
        "components": [
            {
                "type": "chore_count",
                "target": 50,
                "weight": 0.5,  # Contributes 50% to overall progress
            },
            {
                "type": "badge_count",
                "target": 2,
                "weight": 0.5,  # Contributes 50% to overall progress
            },
        ]
    },
}
```

**Tracking:**
- Progress is weighted average of components
- Sensor shows "Chores: 40/50 (80%), Badges: 1/2 (50%), Overall: 65%"
- Earns when all components at 100%

---

### Challenge New Types

Challenges extend achievements with competitive logic:

#### 1. Badge Count Race
"First to earn N badges"

```python
CHALLENGE_TYPE_BADGE_RACE = "badge_race"
# Example: "First to earn 5 badges wins!"

challenge_data = {
    "criteria_type": "badge_count",
    "criteria": {
        "target_badge_count": 5,
    },
    "challenge_type": "competitive",
    "tracking": {
        "mode": "first_to_complete",  # Winner is first to reach target
        "announcements": True,
        "winner_notification": True,
    },
    "reward_points": {
        "winner": 1000,
    },
}
```

**Tracking:**
- Real-time leaderboard shows each kid's progress
- First kid to earn 5 badges wins immediately
- Challenge ends for others or continues for 2nd/3rd place
- Notifications announce leaders and completion

#### 2. Badge Collection Challenge
"Earn the most badges by end date"

```python
CHALLENGE_TYPE_BADGE_MOST = "badge_most"
# Example: "Who earns the most badges by month end?"

challenge_data = {
    "criteria_type": "badge_count",
    "criteria": {
        "target_badge_count": 10,  # Track toward this
    },
    "challenge_type": "competitive",
    "tracking": {
        "mode": "most_progress",  # Highest count wins
        "announcements": True,
        "checkpoint_notifications": True,
        "checkpoints": [25, 50, 75],  # Notify at these percentages
    },
    "reward_points": {
        "1st_place": 1000,
        "2nd_place": 750,
        "3rd_place": 500,
    },
}
```

**Tracking:**
- Leaderboard updates as badges earned
- Checkpoint notifications: "Alice is in the lead with 3 badges!"
- Final rankings assigned at challenge end

#### 3. Specific Badge Race
"First to earn these specific badges"

```python
CHALLENGE_TYPE_SPECIFIC_BADGE_RACE = "specific_badge_race"
# Example: "First to collect Gold AND Silver badges wins!"

challenge_data = {
    "criteria_type": "specific_badges",
    "criteria": {
        "required_badge_ids": ["badge_gold", "badge_silver"],
        "logic": "all",  # Must earn all specified
    },
    "challenge_type": "competitive",
    "tracking": {
        "mode": "first_to_complete",
    },
}
```

**Tracking:**
- Show which required badges each kid has earned
- First kid to earn all specified badges wins

#### 4. Badge Team Challenge
"Collectively earn N badges as a family"

```python
CHALLENGE_TYPE_BADGE_TEAM = "badge_team"
# Example: "Together, earn 20 badges this month"

challenge_data = {
    "criteria_type": "badge_count",
    "criteria": {
        "target_badge_count": 20,
        "scope": "collective",  # NEW - count all kids' badges together
    },
    "challenge_type": "team",  # NEW - team challenge
    "tracking": {
        "mode": "collective",
        "announcements": True,
    },
    "reward_points": {
        "per_child": 500,  # All kids get this if completed
    },
}
```

**Tracking:**
- Single progress bar: "Team: 12 of 20 badges earned"
- Shows contribution by each child
- All kids win if target reached

---

## Phase 3: UI Updates

### Config Flow Updates

Add new configuration options to `flow_helpers.py` and `options_flow.py`:

#### Achievement Type Selection
```python
def build_achievement_schema(kids_dict, chores_dict, badges_dict, default=None):
    """Updated schema with new achievement types."""
    
    achievement_type_options = [
        {"value": ACHIEVEMENT_TYPE_CHORE_STREAK, "label": "Chore Streak"},
        {"value": ACHIEVEMENT_TYPE_CHORE_TOTAL, "label": "Total Chores"},
        {"value": ACHIEVEMENT_TYPE_DAILY_MIN, "label": "Daily Minimum Chores"},
        # NEW TYPES:
        {"value": ACHIEVEMENT_TYPE_BADGE_COUNT, "label": "Earn N Badges"},
        {"value": ACHIEVEMENT_TYPE_SPECIFIC_BADGES, "label": "Earn Specific Badges"},
        {"value": ACHIEVEMENT_TYPE_BADGE_MULTIPLIER, "label": "Badges with Multiplier"},
        {"value": ACHIEVEMENT_TYPE_MIXED, "label": "Mixed Criteria (Chores + Badges)"},
    ]
    
    return vol.Schema({
        vol.Required("name", default=default.get("name", "")): str,
        vol.Required("type"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=achievement_type_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        
        # Conditionally show based on type
        vol.Optional("target_badge_count"): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=20,
            )
        ),
        
        vol.Optional("required_badge_ids"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[{"value": bid, "label": badges_dict[bid]["name"]} 
                        for bid in badges_dict],
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
            )
        ),
        
        vol.Optional("badge_logic"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["all", "any"],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        
        vol.Required("reward_points"): selector.NumberSelector(...),
        vol.Required("assigned_kids"): selector.SelectSelector(...),
    })
```

#### Challenge Type Selection
```python
def build_challenge_schema(kids_dict, chores_dict, badges_dict, default=None):
    """Updated schema with new challenge types."""
    
    challenge_type_options = [
        {"value": CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW, "label": "Chores in Time Window"},
        # NEW TYPES:
        {"value": CHALLENGE_TYPE_BADGE_RACE, "label": "Badge Race (First to N)"},
        {"value": CHALLENGE_TYPE_BADGE_MOST, "label": "Most Badges by End"},
        {"value": CHALLENGE_TYPE_SPECIFIC_BADGE_RACE, "label": "Specific Badge Race"},
        {"value": CHALLENGE_TYPE_BADGE_TEAM, "label": "Team Badge Challenge"},
    ]
    
    competitive_modes = [
        {"value": "first_to_complete", "label": "First to Complete"},
        {"value": "most_progress", "label": "Most Progress by End Date"},
        {"value": "collective", "label": "Team/Collective Progress"},
    ]
    
    return vol.Schema({
        vol.Required("name"): str,
        vol.Required("type"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=challenge_type_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required("challenge_type"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "competitive", "label": "Competitive"},
                    {"value": "team", "label": "Team/Cooperative"},
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required("tracking_mode"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=competitive_modes,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("enable_announcements"): selector.BooleanSelector(),
        vol.Optional("enable_checkpoints"): selector.BooleanSelector(),
        # ... other options
    })
```

### Sensor Updates

New sensors for achievements and challenges:

```python
class AchievementProgressSensor(CoordinatorEntity, SensorEntity):
    """Enhanced to show progress for badge-based achievements."""
    
    @property
    def native_value(self):
        """Show progress toward achievement."""
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        progress = self._compute_progress(achievement)
        return f"{progress}%"
    
    @property
    def extra_state_attributes(self):
        """Show detailed progress breakdown."""
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        criteria_type = achievement.get("criteria_type")
        
        if criteria_type == "badge_count":
            badges_earned = self._count_badges_for_kid()
            target = achievement["criteria"]["target_badge_count"]
            return {
                "criteria_type": "badge_count",
                "badges_earned": badges_earned,
                "target_badges": target,
                "remaining": max(0, target - badges_earned),
                "progress_percentage": (badges_earned / target) * 100,
            }
        
        elif criteria_type == "specific_badges":
            required = achievement["criteria"]["required_badge_ids"]
            earned = self._get_earned_badges_for_kid()
            earned_required = [b for b in required if b in earned]
            return {
                "criteria_type": "specific_badges",
                "required_badges": len(required),
                "earned_badges": len(earned_required),
                "earned_badge_names": [self.coordinator.badges_data[b]["name"] 
                                      for b in earned_required],
                "remaining_badges": [self.coordinator.badges_data[b]["name"] 
                                    for b in required if b not in earned],
            }
        
        elif criteria_type == "mixed":
            breakdown = {}
            components = achievement["criteria"]["components"]
            for i, comp in enumerate(components):
                comp_progress = self._compute_component_progress(comp)
                breakdown[f"component_{i}"] = {
                    "type": comp["type"],
                    "progress": comp_progress,
                    "weight": comp["weight"],
                }
            return {
                "criteria_type": "mixed",
                "components": breakdown,
                "overall_progress": self._compute_progress(achievement),
            }


class ChallengeProgressSensor(CoordinatorEntity, SensorEntity):
    """Enhanced to show competitive progress for badge-based challenges."""
    
    @property
    def native_value(self):
        """Show current standings."""
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        challenge_type = challenge.get("challenge_type")
        
        if challenge_type == "competitive":
            standings = self._get_competitive_standings()
            leader = standings[0]
            return f"1st: {leader['kid_name']} ({leader['progress']}%)"
        else:  # team
            return f"Team Progress: {self._get_team_progress()}%"
    
    @property
    def extra_state_attributes(self):
        """Show full leaderboard."""
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        challenge_type = challenge.get("challenge_type")
        
        if challenge_type == "competitive":
            standings = self._get_competitive_standings()
            return {
                "leaderboard": [
                    {
                        "rank": s["rank"],
                        "child_name": s["kid_name"],
                        "progress": s["progress"],
                        "status": self._get_status_label(s),
                    }
                    for s in standings
                ],
                "challenge_type": "competitive",
            }
        else:  # team
            team_progress = self._get_team_progress()
            contributions = self._get_team_contributions()
            return {
                "team_progress": team_progress,
                "contributions": contributions,
                "challenge_type": "team",
            }
```

### Dashboard Card Examples

#### Achievement Progress Card
```yaml
type: custom:stack-in-card
title: "🏆 Achievements in Progress"
cards:
  - type: entities
    entities:
      - entity: sensor.kc_alice_badge_collector_bronze_progress
        name: "Badge Collector - Bronze (Alice)"
        
      - entity: sensor.kc_bob_master_all_trades_progress
        name: "Master of All Trades (Bob)"

custom_ui_state_card: state-card-custom-ui
card_mod:
  entity-row$: |
    .state {
      min-width: 60px;
    }
```

#### Achievement Badge Breakdown Card
```yaml
type: markdown
title: "📊 Badge-Based Achievements"
content: |
  {% for achievement_id, achievement in states.sensor.items() 
      if 'progress' in achievement_id and 'badge' in achievement_id.lower() %}
  
  ### {{ state_attr(achievement.entity_id, 'friendly_name') }}
  
  {% if state_attr(achievement.entity_id, 'criteria_type') == 'badge_count' %}
  **Badges Earned:** {{ state_attr(achievement.entity_id, 'badges_earned') }} of {{ state_attr(achievement.entity_id, 'target_badges') }}
  
  Progress: 
  ```
  ████████░░ {{ state_attr(achievement.entity_id, 'progress_percentage') | round }}%
  ```
  
  {% elif state_attr(achievement.entity_id, 'criteria_type') == 'specific_badges' %}
  **Required Badges:**
  {% for badge_name in state_attr(achievement.entity_id, 'remaining_badges') %}
  - ❌ {{ badge_name }}
  {% endfor %}
  
  **Earned:**
  {% for badge_name in state_attr(achievement.entity_id, 'earned_badge_names') %}
  - ✅ {{ badge_name }}
  {% endfor %}
  {% endif %}
  
  ---
  {% endfor %}
```

#### Challenge Leaderboard Card
```yaml
type: custom:html-template-card
title: "🏁 Active Challenges"
entity_id: sensor.kc_december_badge_race_progress
content: |
  <style>
    .leaderboard {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
    }
    .leaderboard th {
      background: #333;
      color: white;
      padding: 8px;
      text-align: left;
    }
    .leaderboard td {
      padding: 8px;
      border-bottom: 1px solid #ddd;
    }
    .leaderboard tr.lead {
      background: #fff3cd;
      font-weight: bold;
    }
    .leaderboard tr.second {
      background: #f0f0f0;
    }
  </style>
  
  <h3>December Badge Race</h3>
  <table class="leaderboard">
    <tr>
      <th>Rank</th>
      <th>Child</th>
      <th>Badges Earned</th>
      <th>Progress</th>
    </tr>
    ${
      (state_attr('sensor.kc_december_badge_race_progress', 'leaderboard') || [])
        .map((leader, i) => `
          <tr class="${i === 0 ? 'lead' : i === 1 ? 'second' : ''}">
            <td>🥇 ${leader.rank}</td>
            <td>${leader.child_name}</td>
            <td>${leader.badges_earned || leader.progress}%</td>
            <td>
              <div style="background: #ddd; width: 100px; height: 20px; border-radius: 4px; overflow: hidden;">
                <div style="background: #4CAF50; height: 100%; width: ${leader.progress}%;"></div>
              </div>
            </td>
          </tr>
        `)
        .join('')
    }
  </table>
```

---

## Phase 4: Coordinator Logic Updates

### Enhanced Achievement Evaluation

```python
# In coordinator.py

def _evaluate_achievement(self, achievement_id: str, kid_id: str) -> bool:
    """Check if kid has earned achievement."""
    achievement = self.achievements_data.get(achievement_id, {})
    criteria_type = achievement.get("criteria_type")
    criteria = achievement.get("criteria", {})
    
    if criteria_type == "chore_streak":
        return self._check_chore_streak(kid_id, criteria)
    
    elif criteria_type == "chore_total":
        return self._check_chore_total(kid_id, criteria)
    
    elif criteria_type == "daily_min":
        return self._check_daily_min(kid_id, criteria)
    
    # NEW: Badge-based criteria
    elif criteria_type == "badge_count":
        badges_earned = self._count_badges_for_kid(kid_id)
        return badges_earned >= criteria["target_badge_count"]
    
    elif criteria_type == "specific_badges":
        required = criteria["required_badge_ids"]
        earned = self._get_earned_badges_for_kid(kid_id)
        logic = criteria.get("logic", "all")
        
        if logic == "all":
            return all(bid in earned for bid in required)
        else:  # "any"
            target_any = criteria.get("target_any", 1)
            earned_count = sum(1 for bid in required if bid in earned)
            return earned_count >= target_any
    
    elif criteria_type == "badge_multiplier":
        return self._check_badge_with_multiplier(kid_id, criteria)
    
    elif criteria_type == "mixed":
        # Weighted combination
        components = criteria.get("components", [])
        weighted_progress = 0
        
        for component in components:
            comp_progress = self._evaluate_component_progress(kid_id, component)
            weight = component.get("weight", 1.0)
            weighted_progress += comp_progress * weight
        
        return weighted_progress >= 100
    
    return False

def _get_earned_badges_for_kid(self, kid_id: str) -> list[str]:
    """Return list of badge IDs earned by this kid."""
    earned = []
    for badge_id, badge_data in self.badges_data.items():
        if kid_id in badge_data.get("kids_earned", []):
            earned.append(badge_id)
    return earned

def _count_badges_for_kid(self, kid_id: str) -> int:
    """Count total badges earned by kid."""
    return len(self._get_earned_badges_for_kid(kid_id))
```

### Enhanced Challenge Evaluation

```python
def _evaluate_challenge(self, challenge_id: str, kid_id: str) -> dict:
    """Evaluate challenge progress for a kid."""
    challenge = self.challenges_data.get(challenge_id, {})
    criteria_type = challenge.get("criteria_type")
    criteria = challenge.get("criteria", {})
    tracking = challenge.get("tracking", {})
    
    progress = {
        "kid_id": kid_id,
        "kid_name": self._get_kid_name_by_id(kid_id),
        "progress_percentage": 0,
        "is_complete": False,
        "ranking": None,
    }
    
    # Evaluate based on criteria type
    if criteria_type == "chore_count":
        chores_completed = self._count_chores_for_kid_in_window(kid_id, challenge)
        target = criteria.get("target_chore_count")
        progress["progress_percentage"] = min(100, (chores_completed / target) * 100)
        progress["is_complete"] = progress["progress_percentage"] >= 100
    
    # NEW: Badge-based challenge types
    elif criteria_type == "badge_count":
        badges_earned = self._count_badges_for_kid(kid_id)
        target = criteria.get("target_badge_count")
        progress["progress_percentage"] = min(100, (badges_earned / target) * 100)
        progress["is_complete"] = progress["progress_percentage"] >= 100
        progress["badges_earned"] = badges_earned  # Add detail
    
    elif criteria_type == "specific_badges":
        required = criteria.get("required_badge_ids", [])
        earned = self._get_earned_badges_for_kid(kid_id)
        earned_required = [b for b in required if b in earned]
        progress["progress_percentage"] = (len(earned_required) / len(required)) * 100
        progress["is_complete"] = progress["progress_percentage"] >= 100
        progress["earned_badges"] = earned_required
    
    return progress

def _get_challenge_standings(self, challenge_id: str) -> list[dict]:
    """Get ranked standings for competitive challenge."""
    challenge = self.challenges_data.get(challenge_id, {})
    assigned_kids = challenge.get("assigned_kids", [])
    
    standings = []
    for kid_id in assigned_kids:
        progress = self._evaluate_challenge(challenge_id, kid_id)
        standings.append(progress)
    
    # Sort by progress, then by completion time if available
    standings.sort(
        key=lambda x: (
            -x["progress_percentage"],
            x.get("completed_at", float('inf'))  # Earlier completion is better
        )
    )
    
    # Assign rankings
    for i, standing in enumerate(standings, 1):
        standing["ranking"] = i
        standing["place"] = self._get_place_label(i)  # "1st", "2nd", etc.
    
    return standings
```

---

## Data Migration Strategy

### Existing Data Compatibility

For existing achievements and challenges, auto-migrate to new format:

```python
def _migrate_achievements_to_new_format(self) -> None:
    """Auto-migrate existing achievements to new unified format."""
    achievements = self._data.get(DATA_ACHIEVEMENTS, {})
    
    for achievement_id, achievement in achievements.items():
        old_type = achievement.get("type")
        
        # Already migrated?
        if "criteria_type" in achievement:
            continue
        
        # Migrate old format to new
        if old_type == ACHIEVEMENT_TYPE_STREAK:
            achievement["criteria_type"] = "chore_streak"
            achievement["criteria"] = {
                "chore_id": achievement.get("selected_chore_id"),
                "target_streak": int(achievement.get("criteria", "").split()[0]),
            }
        
        elif old_type == ACHIEVEMENT_TYPE_TOTAL:
            achievement["criteria_type"] = "chore_total"
            achievement["criteria"] = {
                "target_count": int(achievement.get("criteria", "").split()[0]),
            }
        
        elif old_type == ACHIEVEMENT_TYPE_DAILY_MIN:
            achievement["criteria_type"] = "daily_min"
            achievement["criteria"] = {
                "target_per_day": int(achievement.get("criteria", "").split()[0]),
            }
        
        # Store new format, keep old for backward compat during transition
        achievement["type_old"] = old_type  # For debugging
        
        LOGGER.info(f"Migrated achievement {achievement_id} to new format")
```

---

## Testing Strategy

### Unit Tests

```python
def test_badge_count_achievement():
    """Test achievement: Earn 3 badges."""
    coordinator = setup_test_coordinator()
    
    # Kid has earned 2 badges
    achievement = coordinator.achievements_data['test_badge_count']
    assert not coordinator._evaluate_achievement('test_badge_count', 'kid1')
    assert coordinator._compute_progress(achievement, 'kid1') == 67  # 2 of 3
    
    # Kid earns 3rd badge
    coordinator._award_badge('kid1', 'badge3')
    assert coordinator._evaluate_achievement('test_badge_count', 'kid1')

def test_specific_badges_achievement():
    """Test achievement: Earn specific badges."""
    coordinator = setup_test_coordinator()
    achievement = coordinator.achievements_data['test_specific']
    
    # Requires: badge_gold, badge_silver, badge_bronze
    # Kid has only gold
    assert not coordinator._evaluate_achievement('test_specific', 'kid1')
    
    # Kid gets silver (2 of 3)
    coordinator._award_badge('kid1', 'badge_silver')
    assert not coordinator._evaluate_achievement('test_specific', 'kid1')
    
    # Kid gets bronze (3 of 3)
    coordinator._award_badge('kid1', 'badge_bronze')
    assert coordinator._evaluate_achievement('test_specific', 'kid1')

def test_mixed_criteria_achievement():
    """Test achievement: 50 chores + 2 badges."""
    coordinator = setup_test_coordinator()
    
    # 0 chores, 0 badges: 0% overall
    assert coordinator._compute_progress(achievement, 'kid1') == 0
    
    # 50 chores, 0 badges: 50% overall (0.5 weight on chores)
    coordinator._complete_chore('kid1', 'chore1', times=50)
    assert coordinator._compute_progress(achievement, 'kid1') == 50
    
    # 50 chores, 2 badges: 100% overall
    coordinator._award_badge('kid1', 'badge1')
    coordinator._award_badge('kid1', 'badge2')
    assert coordinator._compute_progress(achievement, 'kid1') == 100

def test_badge_race_challenge():
    """Test competitive challenge: First to 5 badges."""
    coordinator = setup_test_coordinator()
    
    # Initial standings
    standings = coordinator._get_challenge_standings('badge_race')
    assert len(standings) == 3
    for standing in standings:
        assert standing["progress_percentage"] == 0
    
    # Alice earns 5 badges, wins
    for i in range(5):
        coordinator._award_badge('alice', f'badge_{i}')
    
    standings = coordinator._get_challenge_standings('badge_race')
    assert standings[0]['kid_name'] == 'alice'
    assert standings[0]['is_complete'] == True
    assert standings[1]['is_complete'] == False

def test_badge_team_challenge():
    """Test team challenge: Collectively earn 20 badges."""
    coordinator = setup_test_coordinator()
    
    challenge = coordinator.challenges_data['team_badges']
    
    # Collectively 0 badges
    progress = coordinator._evaluate_challenge('team_badges', 'team')
    assert progress['progress_percentage'] == 0
    
    # Alice 5, Bob 8, Charlie 7 = 20 total
    for i in range(5):
        coordinator._award_badge('alice', f'badge_a_{i}')
    for i in range(8):
        coordinator._award_badge('bob', f'badge_b_{i}')
    for i in range(7):
        coordinator._award_badge('charlie', f'badge_c_{i}')
    
    progress = coordinator._evaluate_challenge('team_badges', 'team')
    assert progress['progress_percentage'] == 100
```

### Integration Tests

- Achievement unlock notifications
- Challenge completion handling
- Leaderboard updates
- Sensor value accuracy
- UI rendering of progress

---

## Benefits and Use Cases

### Benefits of Unified Framework

1. **Code Reusability:** Achievement and challenge logic shares tracking framework
2. **Extensibility:** Easy to add new tracking types without duplicating code
3. **Consistency:** All progress tracked with same methodology
4. **Flexibility:** Mix-and-match criteria types

### New Use Cases Enabled

1. **Badge Motivations:** Incentivize earning badges themselves, not just chores
2. **Collection Goals:** "Collect all the badges" achievements
3. **Competitive Badge Races:** "First to earn Gold badge wins!"
4. **Mixed Challenges:** "Complete chores OR earn badges toward challenge"
5. **Progressive Goals:** "Earn 1 badge" → "Earn 3 badges" → "Earn all 5 badges"
6. **Family Teamwork:** "As a family, earn 30 badges this year"

---

## Implementation Timeline

| Phase | Duration | Focus |
|-------|----------|-------|
| Phase 1 | Weeks 1-3 | Create unified ProgressTracker framework |
| Phase 2 | Weeks 4-6 | Implement new achievement types |
| Phase 3 | Weeks 7-8 | Implement new challenge types |
| Phase 4 | Weeks 9-10 | UI/UX updates and configuration |
| Phase 5 | Weeks 11-12 | Testing, documentation, optimization |

---

## Backward Compatibility

- Existing achievements/challenges continue to work unchanged
- Auto-migration to new format happens transparently
- Old criteria types supported alongside new ones
- No breaking changes to sensors or buttons
- Config flow supports both old and new options

---

## Success Metrics

1. ✅ All existing achievements/challenges still work
2. ✅ 5+ new achievement types functional
3. ✅ 4+ new challenge types functional
4. ✅ Sensors show accurate progress for all types
5. ✅ Competitive leaderboards update correctly
6. ✅ <5% performance impact on coordinator updates
7. ✅ Documentation with examples for each type

---

This refactor significantly expands the capabilities of achievements and challenges while maintaining backward compatibility and leveraging existing, battle-tested badge logic as the foundation.