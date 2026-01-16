# Backup and Restore Reference

**KidsChores includes a sophisticated custom backup and recovery system** that protects your data and makes recovery from mistakes simple and fast. This guide explains how to use these built-in data protection features.

> [!TIP]
> Few Home Assistant integrations provide this level of integration level automated backup and one-click restore capabilities. We want you data to be protected and easy to recover if ever necessary.

---

## Overview

KidsChores stores all configuration and runtime data in a single file:

```
/config/.storage/kidschores_data
```

**This file contains EVERYTHING about your KidsChores instance**:

- All kids, parents, and their assignments
- All chores, rewards, badges, achievements, challenges
- All bonuses and penalties
- Current points balances
- Complete chore completion history
- Badge progress and achievement tracking
- System configuration

---

## Automatic Protection

### Home Assistant Backups

Because the data file is in the `.storage/` directory, **your normal Home Assistant backup processes automatically protect it**:

- Home Assistant Cloud backups
- Manual Home Assistant backups (**Settings** → **System** → **Backups**)
- Backup add-ons (Google Drive Backup, etc.)

All KidsChores data is included without any extra configuration needed.

### Custom Automatic Backups

**KidsChores creates automatic backups** at critical points to protect against data loss:

| Trigger                    | When                              | Backup Tag       | Example Filename                                    |
| -------------------------- | --------------------------------- | ---------------- | --------------------------------------------------- |
| **Home Assistant Restart** | Every time HA restarts            | `_reset`         | `kidschores_data_2025-12-19_03-51-10_reset`         |
| **Before Upgrade**         | Before KidsChores version upgrade | `_pre-migration` | `kidschores_data_2026-01-07_02-58-35_pre-migration` |
| **Before Restore**         | Before restoring from backup      | `_recovery`      | `kidschores_data_2026-01-15_16-56-11_recovery`      |
| **Manual Backup**          | When you create a backup          | `_manual`        | `kidschores_data_2025-12-31_00-11-17_manual`        |

All backup files are stored in `/config/.storage/` alongside the main data file.

---

## Backup Retention

KidsChores automatically manages backup files to prevent storage bloat.

### Configure Retention

**Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure** → **General Options**

**Maximum Backups to Retain**: Set the number of backup files to keep (default: `5`)

- Older backups are automatically deleted when the limit is reached
- Set to `0` to disable automatic backups (not recommended)
- Increase the count if you want more restore points

> [!NOTE]
> All retained backups are also included in your normal Home Assistant backup processes, providing off-system protection.

---

## Manual Backup Operations

### Create a Manual Backup

**Navigation**: **Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Configure** → **General Options**

1. Find **"Backup Actions"** dropdown (below Maximum Backups to Retain)
2. Select **"Create backup now"**
3. Click **Submit**

A new backup file is created with the `_manual` tag and current timestamp.

**When to create manual backups**:

- Before making bulk changes (restructuring chores, changing point values)
- Before experimenting with new automation
- Before major system changes
- As a quick safety snapshot

### Delete a Backup

**Navigation**: Same as above

1. Find **"Backup Actions"** dropdown
2. Select **"Delete a backup"**
3. Choose which backup file to delete
4. Confirm deletion

### Restore from Backup

**Navigation**: Same as above

1. Find **"Backup Actions"** dropdown
2. Select **"Restore from backup"**
3. Choose which backup file to restore from
4. Confirm restore

**The integration will**:

- Create a `_recovery` backup of your current data (before overwriting)
- Restore the selected backup
- Reload the integration with restored data

---

## Using Diagnostics as Backup

**Diagnostics downloads provide a simple one-time backup method.**

### Download Diagnostics

**Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **⋮** (three dots) → **Download Diagnostics**

This creates a JSON file like: `config_entry-kidschores-01KF1QESK1PATGSY0HJMJEJG61.json`

**The diagnostics file contains**:

- Your complete KidsChores data file
- System information
- Configuration details

> [!TIP] > **Quick backup strategy**: Download diagnostics whenever you want a snapshot. Store it somewhere safe (email it to yourself, save to cloud storage, etc.). You can restore from this file anytime.

### Restore from Diagnostics

You can restore directly from a diagnostics download file using the **Paste JSON** method (see below).

---

## Restore Methods

KidsChores provides multiple ways to restore your data.

### Method 1: Restore from Backup (In General Options)

**Best for**: Quick recovery from recent changes

**Steps**: See [Restore from Backup](#restore-from-backup) above

---

### Method 2: Paste JSON

**Best for**: Restoring from diagnostics downloads or copied data files

**When to use**:

- Restoring from a diagnostics download
- Restoring from a backup file you copied elsewhere
- Migrating between Home Assistant instances

**Steps**:

1. **Delete the KidsChores integration** (if currently installed)

   - **Settings** → **Devices & Services** → **Integrations** → **KidsChores** → **Delete**
   - This is safe because you have the backup data

2. **Re-add the integration**

   - **Settings** → **Devices & Services** → **Add Integration** → **KidsChores**

3. **Data Recovery Options dialog appears**

4. **Select "Paste JSON from data file or diagnostics"**

5. **Paste the JSON content**:

   - Copy entire contents from `kidschores_data` backup file, OR
   - Copy entire contents from diagnostics download file
   - KidsChores automatically detects which format and processes it correctly

6. **Submit** - Your complete KidsChores instance is restored

> [!NOTE]
> The paste JSON process automatically removes the diagnostics wrapper if present. You don't need to extract anything - just paste the entire file contents.

---

### Method 3: Data Recovery Options on Re-Add

**Best for**: Recovering after deleting the integration

**Steps**:

1. **Re-add the integration**
   **Settings** → **Devices & Services** → **Add Integration** → **KidsChores**

2. **Data Recovery Options dialog appears**

   KidsChores automatically detects existing data in `/config/.storage/`:

   - If `kidschores_data` file exists (your current/last production data), it appears as an option
   - All backup files (`kidschores_data_YYYY-MM-DD_HH-MM-SS_*`) appear in the dropdown

3. **Select which data to restore from**:

   - Choose the main `kidschores_data` file to continue where you left off
   - Or choose a dated backup to restore from a specific point in time

4. **Submit** - Integration restores from selected file

---

## Backup File Naming

Understanding backup file naming helps you identify the right restore point:

```
kidschores_data_YYYY-MM-DD_HH-MM-SS_TAG
```

**Examples**:

- `kidschores_data_2025-12-31_00-11-17_manual` - Manual backup created on Dec 31 at 12:11 AM
- `kidschores_data_2026-01-07_02-58-35_pre-migration` - Automatic backup before v0.5.0 upgrade
- `kidschores_data_2026-01-15_16-56-11_recovery` - Backup before restoring another backup

**Tags**:

- `_reset` - Created on Home Assistant restart
- `_pre-migration` - Created before KidsChores version upgrade
- `_recovery` - Created before restore operation
- `_manual` - Created by user via "Create backup now"

---

## Troubleshooting

### Backup Files Not Appearing in Dropdown

**Check**:

1. Verify files exist: `/config/.storage/kidschores_data_*`
2. Ensure files follow naming pattern with date/time stamp
3. Try refreshing the configuration page

### Restore Fails with Error

**Try**:

1. Check Home Assistant logs: **Settings** → **System** → **Logs** (search "kidschores")
2. Verify backup file is valid JSON (open in text editor, check structure)
3. Try the Paste JSON method as alternative
4. Report issue with log details if problem persists

### Lost All Backup Files

**If you have**:

- **Home Assistant backup**: Restore the full HA backup to recover `/config/.storage/`
- **Diagnostics download**: Use Paste JSON method to restore
- **No backups**: You'll need to reconfigure KidsChores from scratch

---

## Best Practices

**KidsChores-specific recommendations**:

- **Adjust retention count** based on your needs (**General Options** → **Maximum Backups to Retain**)
- **Download diagnostics before major KidsChores changes** (bulk edits, point restructuring, testing automation)
- **Create manual backups** before experimenting (**General Options** → **Backup Actions** → **Create backup now**)

For overall backup strategy, follow standard Home Assistant best practices. KidsChores data is automatically included in all normal backup methods.

---

## Why This Matters

### History

Early versions of KidsChores had implementation issues that could corrupt data. **Recovery was extremely difficult** because there was no automated backup system.

### Current Solution

The custom backup system ensures:

- ✅ **Automatic protection** at every critical point
- ✅ **One-click restore** from any backup
- ✅ **Multiple restore methods** for different scenarios
- ✅ **Diagnostics-as-backup** for portability
- ✅ **No configuration needed** - it just works

**This level of data protection is rare in Home Assistant integrations** and provides peace of mind that your family's chore tracking data is always safe and easily recoverable.

---

## Getting Help

If you experience backup or restore issues:

- **[GitHub Issues](https://github.com/ad-ha/kidschores-ha/issues)** - Report backup system bugs
- **[Community Forum](https://community.home-assistant.io/t/kidschores-family-chore-management-integration)** - Ask for help with recovery

When reporting issues, include:

- Home Assistant version
- KidsChores version
- Steps that led to the problem
- Relevant log entries from **Settings** → **System** → **Logs**
