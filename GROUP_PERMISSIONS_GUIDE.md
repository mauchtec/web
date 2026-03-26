# Group-Based Permission System Guide

## Overview

The system now supports **group-based permissions** that allow you to:
1. Create groups (e.g., "Android App Group")
2. Assign units to groups
3. Assign Android apps to groups
4. Grant permissions to groups (instead of individual people)
5. Automatically grant permissions to all people in units that belong to a group

## Architecture

### New Models

1. **Group** - Represents a collection of units and Android apps
   - `name` - Unique group name
   - `description` - Optional description
   - `code` - Optional unique code

2. **UnitGroupMembership** - Links units to groups (many-to-many)
   - `unit` - The unit
   - `group` - The group
   - `joined_at` - When the unit joined the group

3. **AndroidApp** - Represents an Android app installation
   - `name` - App name/identifier
   - `device_identifier` - Unique device identifier
   - `device_token` - Authentication token
   - `group` - The group this app belongs to

4. **GroupAccessPermission** - Permissions granted to a group
   - `group` - The group
   - `access_point` - The access point
   - `schedule_rule` - Optional schedule restrictions
   - `valid_from` / `valid_until` - Time validity
   - `max_daily_uses` - Daily usage limit (0 = unlimited)

## How It Works

### Permission Checking Flow

When checking if a person can access an access point:

1. **Direct Permissions** (existing behavior)
   - Check if person has direct `AccessPermission` for the access point
   - If found and valid, grant access

2. **Group-Based Permissions** (new)
   - Find all units where the person is an active occupant
   - Find all groups those units belong to
   - Check if any of those groups have `GroupAccessPermission` for the access point
   - If found and valid, grant access

### Example Workflow

1. **Create a Group**
   ```
   POST /api/gatecore/groups/
   {
     "name": "Android App Group",
     "description": "Units accessible via Android app",
     "code": "ANDROID_APP"
   }
   ```

2. **Assign Units to Group**
   ```
   POST /api/gatecore/unit-group-memberships/
   {
     "unit": "<unit-uuid>",
     "group": "<group-uuid>"
   }
   ```

3. **Register Android App**
   ```
   POST /api/gatecore/android-apps/
   {
     "name": "Gate Access App",
     "device_identifier": "device-12345",
     "device_token": "token-abc123",
     "group": "<group-uuid>"
   }
   ```

4. **Grant Group Permissions**
   ```
   POST /api/gatecore/group-access-permissions/
   {
     "group": "<group-uuid>",
     "access_point": "<access-point-uuid>",
     "valid_from": "2024-01-01T00:00:00Z",
     "valid_until": null,
     "max_daily_uses": 0
   }
   ```

5. **Automatic Permission Grant**
   - Any person who is an active occupant of a unit in the group
   - Automatically gets access to all access points the group has permissions for
   - No need to create individual `AccessPermission` records

## New Groups for Permissions

### Security Group
- Name: Security
- Description: Group for security personnel
- Code: SECURITY

### Residence Basic Group
- Name: Residence Basic
- Description: Group for basic residence permissions
- Code: RESIDENCE_BASIC

### Residence Advanced Group
- Name: Residence Advanced
- Description: Group for advanced residence permissions
- Code: RESIDENCE_ADVANCED

### Amenity Group
- Name: Amenity
- Description: Group for amenity permissions
- Code: AMENITY

### Permissions Assignment
- Security group inherits permissions from `+15551234567`.
- Residence Basic, Residence Advanced, and Amenity groups have their own permissions defined using `GroupAccessPermission`.

## API Endpoints

### Groups
- `GET /api/gatecore/groups/` - List all groups
- `POST /api/gatecore/groups/` - Create a group
- `GET /api/gatecore/groups/{id}/` - Get group details
- `PUT /api/gatecore/groups/{id}/` - Update group
- `DELETE /api/gatecore/groups/{id}/` - Delete group

### Unit Group Memberships
- `GET /api/gatecore/unit-group-memberships/` - List memberships
- `POST /api/gatecore/unit-group-memberships/` - Add unit to group
- `DELETE /api/gatecore/unit-group-memberships/{id}/` - Remove unit from group

### Android Apps
- `GET /api/gatecore/android-apps/` - List all Android apps
- `POST /api/gatecore/android-apps/` - Register Android app
- `GET /api/gatecore/android-apps/{id}/` - Get app details
- `PUT /api/gatecore/android-apps/{id}/` - Update app
- `DELETE /api/gatecore/android-apps/{id}/` - Delete app

### Group Access Permissions
- `GET /api/gatecore/group-access-permissions/` - List group permissions
- `POST /api/gatecore/group-access-permissions/` - Grant permission to group
- `PUT /api/gatecore/group-access-permissions/{id}/` - Update permission
- `DELETE /api/gatecore/group-access-permissions/{id}/` - Revoke permission

## Benefits

1. **Scalability** - No need to create individual permissions for each person
2. **Flexibility** - Units can belong to multiple groups
3. **Centralized Management** - Manage permissions at group level
4. **Automatic Updates** - When a person moves to a unit in a group, they automatically get group permissions
5. **Android App Integration** - Android apps can be assigned to groups for easier management

## Migration Notes

- Existing direct `AccessPermission` records continue to work
- Group-based permissions are checked after direct permissions
- Both systems can coexist
- No breaking changes to existing API endpoints

## Next Steps

1. Run migrations: `python manage.py makemigrations` then `python manage.py migrate`
2. Create groups for your Android apps
3. Assign units to groups
4. Register Android apps and assign them to groups
5. Grant group permissions to access points
6. Test permission checking with people in group units
