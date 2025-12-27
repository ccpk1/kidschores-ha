# Feature Request: Enhanced Parent Dashboard

**Date:** 2025-12-22  
**Requested By:** ccpk1  
**Status:** Open  
**Priority:** Medium-High

---

## Overview

This feature request proposes three significant enhancements to the parent dashboard in Kids Chores HA to provide parents with more comprehensive visibility, control, and customization over their children's chore and reward activities.

---

## Enhancement 1: On-Demand Detailed Stats Service

### Current State

Currently, the parent dashboard displays limited statistics exposed through Home Assistant sensors. The underlying data available in the system is not fully exposed in a user-friendly format, limiting parents' ability to drill down into detailed performance metrics.

**Current Limitations:**
- Sensors expose only summary/aggregate data
- No detailed breakdown by child, time period, or chore type
- Historical trends are difficult to analyze
- Missing insights into productivity patterns

### Use Cases

1. **Performance Analysis:** Parents want to understand which children are most reliable, which chores take longest to complete, and identify patterns in task completion.
2. **Incentive Planning:** Data-driven decision making for reward allocation based on actual performance metrics.
3. **Chore Assignment Optimization:** Identify which children excel at which types of chores to assign tasks more effectively.
4. **Accountability Tracking:** Generate detailed reports for family meetings or motivational purposes.

### Proposed Solution

Implement a new service `kidschores_ha.get_detailed_stats` that provides comprehensive statistics data which can be displayed via custom cards on the dashboard.

**Service Definition:**
```yaml
service: kidschores_ha.get_detailed_stats
data:
  stat_type: "chores_by_child"  # or rewards, activity_summary, completion_rates, time_analysis
  child_name: "optional_filter"
  time_period: "week"  # day, week, month, year, all
  include_archived: false
```

**Response Data Structure:**
```json
{
  "stat_type": "chores_by_child",
  "time_period": "week",
  "generated_at": "2025-12-22T13:40:11Z",
  "summary": {
    "total_chores_assigned": 24,
    "total_chores_completed": 18,
    "completion_rate": "75%",
    "average_completion_time_hours": 2.5
  },
  "by_child": [
    {
      "name": "Alice",
      "assigned": 6,
      "completed": 6,
      "completion_rate": "100%",
      "avg_time_hours": 1.5,
      "points_earned": 450,
      "pending_rewards": 2
    },
    {
      "name": "Bob",
      "assigned": 6,
      "completed": 4,
      "completion_rate": "67%",
      "avg_time_hours": 3.0,
      "points_earned": 280,
      "pending_rewards": 1
    }
  ],
  "by_chore_type": [
    {
      "chore_name": "Dishes",
      "times_assigned": 8,
      "times_completed": 6,
      "avg_completion_time_hours": 0.5,
      "points_per_completion": 50
    }
  ]
}
```

### Implementation Considerations

- **Data Source:** Query underlying Kids Chores database/state machine for detailed records
- **Performance:** Implement caching for frequently requested stat types to avoid performance degradation
- **Filtering:** Support multiple filtering dimensions (child, chore type, time period, status)
- **Card Integration:** Create or recommend custom card templates (e.g., custom:stack-in-card, auto-entities) to display data
- **Formatting:** Return data in JSON format suitable for templating in front-end cards

### Example Dashboard Integration

```yaml
type: custom:stack-in-card
cards:
  - type: custom:template-entity-row
    entity: sensor.chores_completion_rate
    state_template: |
      {% set data = service('kidschores_ha.get_detailed_stats', {'stat_type': 'completion_rates', 'time_period': 'week'}) %}
      {{ data.summary.completion_rate }}
    
  - type: custom:auto-entities
    template: detailed_chores_table
    entity_ids:
      - service_data:
          service: kidschores_ha.get_detailed_stats
          data:
            stat_type: "chores_by_child"
            time_period: "month"
```

---

## Enhancement 2: Enhanced Approval Action Buttons with Claim Timestamps

### Current State

Currently, approval action buttons for pending chores and rewards lack detailed timing information. Parents cannot easily see when a child claimed a chore or reward, making it difficult to assess timeliness and manage the approval workflow effectively.

**Current Limitations:**
- No timestamp displayed for pending claims
- Difficult to identify which items are aging in the approval queue
- No indication of request urgency
- Cannot easily prioritize approvals

### Use Cases

1. **Queue Management:** Parents can see which claims have been waiting longest and prioritize urgent ones.
2. **Accountability:** Visible timestamps help track response time and ensure fair, consistent approval processes.
3. **Incentive Fairness:** Parents can verify children are claiming rewards promptly after completion.
4. **Dispute Resolution:** Timestamps provide evidence for discussing delays or fairness concerns.

### Proposed Solution

Enhance the approval action buttons to include:

1. **Timestamp Display:** Show when the chore was claimed or reward was requested
2. **Age Indicator:** Display how long the item has been awaiting approval (e.g., "claimed 2 hours ago")
3. **Visual Urgency:** Use color coding to indicate aging items (red for >24h, yellow for >4h, green for recent)
4. **Tooltip Information:** Hover details showing full timestamp and child name

**Enhanced Button Structure:**
```
┌─────────────────────────────────────────┐
│ Approve  [Claimed: 2h 15m ago]   Deny  │
│ ✓ Alice - Kitchen Cleanup              │
│ └─ Claimed: Mon 22 Dec, 11:25 AM       │
└─────────────────────────────────────────┘

[Color coded background based on age]
```

### Implementation Considerations

- **Storage:** Ensure claim timestamps are properly stored in the data model
- **Formatting:** Display human-readable relative time ("2 hours ago") with timezone awareness
- **Styling:** Implement conditional styling based on claim age thresholds
- **Performance:** Load only pending approvals to keep dashboard responsive
- **Notifications:** Optionally trigger notifications for very old pending claims

### Example YAML Configuration

```yaml
type: custom:button-card
entity: sensor.pending_approvals
show_state: true
custom_fields:
  pending_item: |
    [[[
      let pending = states['sensor.pending_approvals'].attributes.pending_items;
      if (!pending || pending.length === 0) return 'No pending approvals';
      
      return pending.map(item => {
        let age = new Date() - new Date(item.claim_timestamp);
        let ageHours = Math.floor(age / 3600000);
        let ageText = ageHours < 24 ? `${ageHours}h ago` : `${Math.floor(ageHours/24)}d ago`;
        
        return `
          <div style="padding: 8px; border-bottom: 1px solid #ddd;">
            <div>${item.child}: ${item.task_name}</div>
            <div style="font-size: 0.85em; color: #666;">Claimed: ${ageText}</div>
          </div>
        `;
      }).join('');
    ]]]
styles:
  card:
    - border-color: |
        [[[
          let maxAge = Math.max(...states['sensor.pending_approvals']
            .attributes.pending_items
            .map(i => new Date() - new Date(i.claim_timestamp)));
          
          if (maxAge > 86400000) return 'red';
          if (maxAge > 14400000) return 'orange';
          return 'green';
        ]]]
```

---

## Enhancement 3: Activity Log Filtering and Selection

### Current State

The activity log on the parent dashboard shows all recorded activities, which can become cluttered and difficult to navigate as the number of children and chores increases. Parents have no way to focus on specific types of activities or relevant data.

**Current Limitations:**
- All activities displayed without filtering options
- Dashboard becomes overwhelming with large families
- Cannot focus on specific children or activity types
- Historical clutter reduces relevance of current information
- No way to customize which activity types matter most

### Use Cases

1. **Focused Monitoring:** Parents want to see only activities relevant to specific children or task types.
2. **Dashboard Space Optimization:** Filter to show only high-priority activities instead of everything.
3. **Activity Type Focus:** Show only completions, or approvals, or disputes separately.
4. **Time-Based Filtering:** View only recent activities or specific time periods.
5. **Customized Views:** Different family members might want different activity visibility.

### Proposed Solution

Implement activity log filtering through:

1. **Service-based Filtering:** New service `kidschores_ha.get_activity_log` with comprehensive filtering
2. **Sensor State Attributes:** Expose filter options in sensor attributes for dashboard controls
3. **Template Cards:** Create customizable activity log cards with dropdown/button filters

**Service Definition:**
```yaml
service: kidschores_ha.get_activity_log
data:
  children: ["Alice", "Bob"]  # optional, array of child names
  activity_types: ["completion", "approval", "dispute"]  # optional
  time_period: "week"  # hour, day, week, month, all
  limit: 20  # maximum entries to return
  sort_order: "descending"  # ascending, descending
```

**Response Structure:**
```json
{
  "time_period": "week",
  "filters_applied": {
    "children": ["Alice", "Bob"],
    "activity_types": ["completion", "approval", "dispute"],
    "limit": 20
  },
  "total_available": 156,
  "total_returned": 20,
  "activities": [
    {
      "timestamp": "2025-12-22T13:30:00Z",
      "child": "Alice",
      "activity_type": "completion",
      "task": "Kitchen Cleanup",
      "points_earned": 100,
      "status": "pending_approval"
    },
    {
      "timestamp": "2025-12-22T12:15:00Z",
      "child": "Bob",
      "activity_type": "dispute",
      "task": "Lawn Mowing",
      "dispute_reason": "Task incomplete - only front done",
      "resolution": "pending"
    },
    {
      "timestamp": "2025-12-22T10:00:00Z",
      "child": "Alice",
      "activity_type": "approval",
      "task": "Reward - Ice Cream Outing",
      "points_used": 250,
      "approved_by": "parent@home"
    }
  ]
}
```

### Implementation Considerations

- **Query Performance:** Index activity log by child, activity type, and timestamp
- **Storage Optimization:** Implement archiving for very old activities
- **State Attributes:** Expose available filter options in sensor attributes (children list, activity types)
- **Card Integration:** Create reusable template cards with filter controls
- **Real-time Updates:** Ensure new activities appear in filtered views quickly
- **Multiple Views:** Support saving favorite filter combinations

### Example Dashboard Implementation

```yaml
type: custom:stack-in-card
title: Activity Log - Customizable View
cards:
  # Filter Selection
  - type: custom:layout-card
    layout_type: grid
    cards:
      - type: custom:button-card
        entity: input_boolean.activity_show_completions
        label: Show Completions
        state:
          - value: 'on'
            color: green
          - value: 'off'
            color: grey
      
      - type: custom:button-card
        entity: input_boolean.activity_show_approvals
        label: Show Approvals
      
      - type: custom:button-card
        entity: input_boolean.activity_show_disputes
        label: Show Disputes
      
      - type: custom:dropdown-card
        entity: input_select.activity_child_filter
        label: Child Filter
        options:
          - "All Children"
          - "Alice"
          - "Bob"
  
  # Activity Log Display
  - type: entities
    entity_ids:
      - sensor.activity_log
    state_format: |
      [[[
        let filters = {
          completions: states['input_boolean.activity_show_completions'].state === 'on',
          approvals: states['input_boolean.activity_show_approvals'].state === 'on',
          disputes: states['input_boolean.activity_show_disputes'].state === 'on',
          child: states['input_select.activity_child_filter'].state
        };
        
        let activities = states['sensor.activity_log'].attributes.activities || [];
        
        let filtered = activities.filter(a => {
          if (filters.child !== 'All Children' && a.child !== filters.child) return false;
          if (a.activity_type === 'completion' && !filters.completions) return false;
          if (a.activity_type === 'approval' && !filters.approvals) return false;
          if (a.activity_type === 'dispute' && !filters.disputes) return false;
          return true;
        });
        
        return filtered.map(a => 
          `${new Date(a.timestamp).toLocaleTimeString()}: ${a.child} - ${a.task} (${a.activity_type})`
        ).join('\n');
      ]]]

  # Alternative: Table View
  - type: custom:auto-entities
    filter:
      include:
        - entity_id: sensor.activity_log
    template: |
      [[[
        const filtered = [{
          type: 'custom:html-template-card',
          entity_id: 'sensor.activity_log',
          content: |
            <table style="width: 100%; border-collapse: collapse;">
              <tr style="background: #f0f0f0;">
                <th style="padding: 8px; text-align: left;">Time</th>
                <th style="padding: 8px; text-align: left;">Child</th>
                <th style="padding: 8px; text-align: left;">Task</th>
                <th style="padding: 8px; text-align: left;">Type</th>
              </tr>
              ${
                (states['sensor.activity_log'].attributes.activities || [])
                  .slice(0, 10)
                  .map(a => `
                    <tr>
                      <td style="padding: 8px; border-bottom: 1px solid #ddd;">
                        ${new Date(a.timestamp).toLocaleTimeString()}
                      </td>
                      <td style="padding: 8px; border-bottom: 1px solid #ddd;">${a.child}</td>
                      <td style="padding: 8px; border-bottom: 1px solid #ddd;">${a.task}</td>
                      <td style="padding: 8px; border-bottom: 1px solid #ddd;">
                        <span style="padding: 2px 6px; border-radius: 3px; 
                          background: ${a.activity_type === 'completion' ? '#4CAF50' : 
                                        a.activity_type === 'approval' ? '#2196F3' : '#FF9800'};
                          color: white; font-size: 0.8em;">
                          ${a.activity_type.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  `)
                  .join('')
              }
            </table>
        }];
        return filtered;
      ]]]
```

---

## Implementation Priority and Timeline

### Phase 1: Foundation (Weeks 1-2)
- Implement Enhanced Approval Action Buttons with timestamps
- Minimal breaking changes, straightforward enhancement
- High user impact for approval workflow

### Phase 2: Advanced Features (Weeks 3-4)
- Implement On-Demand Detailed Stats Service
- Requires data structure analysis and service creation
- Enables powerful analytics capabilities

### Phase 3: Customization (Weeks 5-6)
- Implement Activity Log Filtering and Selection
- Builds on Phase 1-2 infrastructure
- Provides dashboard flexibility

---

## Related Issues and Dependencies

- Requires Home Assistant version 2025.12 or later (or specify minimum version)
- Compatible with existing Kids Chores HA architecture
- May require custom card dependencies:
  - `custom:button-card`
  - `custom:stack-in-card`
  - `custom:auto-entities`
  - `custom:html-template-card`

---

## Success Metrics

1. **Enhancement 1 - Detailed Stats:**
   - All stat types returning accurate data within 1 second
   - Stats service called by at least 2 custom dashboard cards
   
2. **Enhancement 2 - Timestamps:**
   - 100% of pending approvals displaying claim time
   - Color-coded urgency visible on dashboard
   
3. **Enhancement 3 - Activity Filtering:**
   - Users can filter to <5 activities on average (vs. 50+ unfiltered)
   - Custom filter combinations can be saved and reused

---

## Notes for Developers

- Consider implementing a unified data query layer to support all three enhancements
- Ensure backward compatibility with existing sensor entities
- Document new services in the integration documentation
- Provide example YAML configurations and custom card templates
- Consider performance implications for large families (20+ children)

---

## Feedback and Discussion

This feature request is open for discussion and feedback. Please review and comment on:
- Technical feasibility and approach
- Priority ordering of enhancements
- Alternative implementation methods
- Additional use cases or features to consider
