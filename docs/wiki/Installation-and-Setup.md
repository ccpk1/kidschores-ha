# Installation and Setup

Get KidsChores up and running in your Home Assistant instance. This guide covers fresh installations for v0.5.0+.

> [!TIP] > **Upgrading from v0.3.x or v0.4.x?** See [Backup and Restore Reference](Backup-and-Restore-Reference.md) for migration guidance.

---

## Prerequisites

Before installing KidsChores, ensure you have:

- **Home Assistant**: Version 2024.1.0 or higher
- **HACS** (recommended): Installed and configured ([HACS installation guide](https://hacs.xyz/docs/installation/manual))
- **Storage**: ~5MB for integration files
- **Network**: Internet access for installation (runs locally after install)

---

## Installation Methods

### Method 1: HACS (Recommended)

HACS provides automatic updates and easier management of custom integrations.

1. **Ensure HACS is installed**
   If you haven't installed HACS yet, follow the [official HACS installation guide](https://hacs.xyz/docs/installation/manual).

2. **Navigate to HACS**
   In Home Assistant, go to **HACS** from the sidebar.

3. **Install KidsChores**

   - Search for **"KidsChores"** in HACS
   - Click on the KidsChores integration
   - Click **"Download"** or **"Install"**

4. **Restart Home Assistant**
   **Settings** → **System** → **Restart** (required to load the integration)

---

### Method 2: Manual Installation

For users who prefer manual installation or don't use HACS.

1. **Download Latest Release**
   Visit the [KidsChores GitHub releases page](https://github.com/ad-ha/kidschores-ha/releases) and download the latest version.

2. **Extract Files**
   Unzip the downloaded file to access the `kidschores` directory.

3. **Copy to Custom Components**
   Copy the entire `kidschores` directory to your Home Assistant `custom_components` folder:

   ```
   <config>/custom_components/kidschores/
   ```

   Your directory structure should look like:

   ```
   config/
   └── custom_components/
       └── kidschores/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           └── ...
   ```

4. **Restart Home Assistant**
   **Settings** → **System** → **Restart** (required to recognize the new integration)

---

## Initial Configuration

After installation and restart, configure KidsChores through the Home Assistant UI.

### Add the Integration

1. **Navigate to Integrations**
   **Settings** → **Devices & Services** → **Integrations**

2. **Add Integration**
   Click **"+ Add Integration"** in the bottom-right corner

3. **Search for KidsChores**
   Type "KidsChores" in the search box and select it

   > [!NOTE]
   > You can also use this direct link: [Add KidsChores Integration](https://my.home-assistant.io/redirect/config_flow_start?domain=kidschores)

---

### Configuration Wizard

#### Data Recovery Options (First Screen)

When you first add the KidsChores integration, the **Data Recovery Options** dialog appears before anything else.

**For brand new installations**, select **"Start fresh (creates backup of existing data)"**. This is the most common choice for first-time users.

**Other options** (for advanced scenarios):

- If you have an existing backup or data file, see [Backup and Restore Reference](Backup-and-Restore-Reference.md) for guidance on using these recovery options

> [!TIP] > **Keep it simple!** The configuration wizard only requires setting up your **Points System**. We strongly recommend starting there, then reviewing the guides before adding kids, parents, and chores. Adding 20 chores during initial setup wastes time - add them one at a time as you learn the system.

After selecting your data recovery option, the setup wizard guides you through initial configuration:

#### Step 1: Points System (Required)

- **Points Label**: Choose your family's points name (e.g., "Stars", "Bucks", "Coins", "Points")
- **Icon** (optional): Select an icon to represent points

This name appears throughout the integration (sensors, notifications, dashboards).

#### Step 2-4: Kids, Parents, and Chores (Optional - Recommended to Skip)

You _can_ add kids, parents, and chores during setup, but we recommend new user skip or add minimal items in these steps initially:

- Review the [Quick Start Guide](Quick-Start-Guide.md) first
- Understand the workflow before creating entities
- Add them one at a time through Options Flow after reviewing relevant guides:
  - **[Kids and Parents Guide](Kids-and-Parents.md)** - Learn about user management
  - **[Chores Guide](Chores.md)** - Understand chore configuration options

**To skip**: Simply click **"Submit"** without filling in optional fields, or close the wizard after completing Points setup.

---

## Verification

After completing setup, verify the integration loaded successfully:

**Settings** → **Devices & Services** → **Integrations**

You should see **KidsChores** listed with a checkmark.

> [!NOTE]
> To view specific sensors and entities created, see the [Entities Overview](Entities-Overview.md) guide.

---

## Next Steps

**Start here**: **[Quick Start Guide](Quick-Start-Guide.md)** - Walk through creating your first kid, parent, and chore with a complete workflow demonstration.

After completing the Quick Start, explore:

- **[Kids and Parents Guide](Kids-and-Parents.md)** - User management and parent approvals
- **[Chores Guide](Chores.md)** - Chore configuration and scheduling options
- **[Rewards Guide](Rewards.md)** - Create a reward redemption system
- **[Badges Guide](Badges.md)** - Set up badges to motivate kids with milestones
- **[Entities Overview](Entities-Overview.md)** - Understand all entities created
- **[Services Reference](Services-Reference.md)** - Automate with KidsChores services

---

## Managing Your Installation

### Adding More Kids, Parents, or Chores

**Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure**

The conguration setting allow you to manage all aspectes of the integration:

- Add/edit/remove kids
- Add/edit/remove parents
- Add/edit/remove chores
- Add/edit/remove rewards
- Add/edit/remove badges
- Configure bonuses and penalties
- Set up achievements and challenges
- General options / backup and recovery

### Backup Your Configuration

See [Backup and Restore Reference](Backup-and-Restore-Reference.md) for:

- Backing up your KidsChores data
- Migrating between Home Assistant instances
- Version upgrade procedures
- Disaster recovery

---

## Troubleshooting

### Integration Not Appearing

**Problem**: KidsChores doesn't show up in Add Integration list

**Solutions**:

1. Verify files copied correctly to `custom_components/kidschores/`
2. Check Home Assistant logs: **Settings** → **System** → **Logs**
3. Restart Home Assistant again
4. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)

### Entities Not Created

**Problem**: Entities missing after setup

**Solutions**:

1. Check integration status in **Settings** → **Devices & Services**
2. Verify kids and chores created in Options Flow
3. Check logs for errors: **Settings** → **System** → **Logs**, search "kidschores"
4. Reload integration: **Settings** → **Devices & Services** → **KidsChores** → **⋮** → **Reload**

### Configuration Changes Not Applying

**Problem**: Changes made in Options Flow don't take effect

**Solutions**:

1. Wait 30-60 seconds for entity updates
2. Refresh browser page
3. Check Developer Tools → States for updated values
4. Reload integration if necessary

---

## Getting Help

- **[FAQ](Frequently-Asked-Questions.md)** - Common questions answered
- **[Troubleshooting Guide](Troubleshooting-Guide.md)** - Detailed troubleshooting
- **[Community Forum](https://community.home-assistant.io/t/kidschores-family-chore-management-integration)** - Ask questions, share ideas
- **[GitHub Issues](https://github.com/ad-ha/kidschores-ha/issues)** - Report bugs, request features

---

**Important**: Please report any installation issues via [GitHub Issues](https://github.com/ad-ha/kidschores-ha/issues) so we can improve this guide.
