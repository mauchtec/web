# Face Device Management Plan

## Goal
Build a dedicated face-device management surface that covers:
- inventory and online status
- remote actions
- settings visibility and config drift
- user sync visibility
- access logs with snapshots
- operator audit trail

This plan is the working source of truth for the `face_devices` Django app.

## Scope
We already have:
- websocket protocol handshake
- device settings pull
- user count and user ID pull
- single-user add flow
- image preparation that the device accepts

We still need:
- operator-facing APIs
- persistent event/action/log models
- UI for device list and device detail
- remote control workflows
- recognition/access-log ingestion

## Product Areas

### 1. Device Inventory
Must show:
- display name
- serial number
- IP address
- site
- direction
- approval status
- model and firmware
- websocket/API endpoints
- last seen
- last heartbeat
- online or offline state

### 2. Device Detail
Must show:
- reported settings snapshot
- desired backend settings
- config diff
- current sync state
- people count on device
- backend approved people count
- last successful action
- last failed action
- raw protocol debug payloads for support use

### 3. Remote Actions
Must support:
- ping
- pull settings
- pull user count
- pull user IDs
- sync missing users
- add one user
- delete one user
- delete all users
- reboot if protocol support is confirmed

Each action must record:
- operator
- device
- request payload
- response payload
- status
- timestamps
- failure reason

### 4. Access Logs And Snapshots
Need an API and UI for:
- who accessed through a face device
- pass or deny result
- timestamp
- device
- matched person
- confidence if available
- face snapshot
- panoramic snapshot if available
- raw device event payload

### 5. Sync Visibility
Per device we need:
- approved backend users
- reported device users
- missing users
- unexpected users
- last synced user
- last sync error
- pending actions

### 6. Settings Management
Need:
- reported settings storage
- desired settings storage
- diff view
- controlled push workflow later
- advanced raw settings viewer for unsupported fields

## Backend Architecture

### App Boundary
Use the `face_devices` Django app for new operator-facing device management work.

Keep low-level websocket protocol handling in `GateCore.services.face_device_ws` for now.

### Existing Models Reused
- `GateTerminal`
- `DeviceSyncJob`
- `Person`
- `AuditTrail`

### New Models To Add

#### `FaceDeviceEvent`
Purpose:
- store inbound and outbound protocol messages

Fields:
- `device`
- `direction` (`inbound` or `outbound`)
- `command`
- `payload`
- `status`
- `created_at`

#### `FaceDeviceAction`
Purpose:
- record operator-triggered remote actions

Fields:
- `device`
- `action`
- `requested_by`
- `request_payload`
- `response_payload`
- `status`
- `started_at`
- `completed_at`
- `error`

#### `FaceDeviceAccessLog`
Purpose:
- normalized recognition/access history with snapshots

Fields:
- `device`
- `person`
- `event_time`
- `result`
- `confidence`
- `snapshot_image`
- `panoramic_image`
- `payload`

#### `FaceDeviceUserState`
Purpose:
- cached per-device user presence state for reconciliation

Fields:
- `device`
- `user_identifier`
- `person`
- `state`
- `last_seen_on_device_at`
- `payload`

## API Plan

### Phase 1
- `GET /api/v1/face-devices/`
- `GET /api/v1/face-devices/<id>/`
- `GET /api/v1/face-devices/<id>/status/`
- `GET /api/v1/face-devices/<id>/settings/`
- `GET /api/v1/face-devices/<id>/events/`
- `GET /api/v1/face-devices/<id>/sync/`

### Phase 2
- `POST /api/v1/face-devices/<id>/actions/ping/`
- `POST /api/v1/face-devices/<id>/actions/pull-settings/`
- `POST /api/v1/face-devices/<id>/actions/pull-users/`
- `POST /api/v1/face-devices/<id>/actions/sync-users/`
- `POST /api/v1/face-devices/<id>/actions/add-user/`
- `POST /api/v1/face-devices/<id>/actions/delete-user/`

### Phase 3
- `GET /api/v1/face-devices/<id>/access-logs/`
- `GET /api/v1/face-devices/access-logs/`
- `GET /api/v1/face-devices/actions/`

## UI Plan

### Device List Page
Columns:
- device name
- serial
- site
- online status
- approval
- last heartbeat
- backend user count
- device user count
- sync status

Filters:
- site
- online or offline
- approval status
- sync error state

### Device Detail Page
Tabs:
- overview
- settings
- users and sync
- access logs
- events
- actions

### Access Logs Page
Must support:
- image thumbnails
- person search
- device filter
- date range
- result filter

## Implementation Phases

### Phase A. Foundation
- scaffold `face_devices` app
- add plan document
- add base URLs
- add event and action models
- add serializers and permissions

Acceptance:
- app is installed
- overview endpoint works
- migrations apply cleanly

### Phase B. Inventory And Status
- list devices
- detail endpoint
- online status calculation
- reported settings exposure
- sync summary exposure

Acceptance:
- operator can see all face devices and current health

### Phase C. Actions
- persist remote actions
- add ping and pull-settings
- add pull-users
- expose results in event stream

Acceptance:
- operator can trigger safe read-only actions and inspect results

### Phase D. User Sync
- expose reconciliation status
- add sync-missing-users action
- add add-user and delete-user actions
- store per-user sync results

Acceptance:
- operator can see which users are missing and sync them intentionally

### Phase E. Access Logs
- ingest facial access events
- store snapshots
- build searchable APIs
- build UI for incident review

Acceptance:
- operator can answer who accessed, when, using which device, with image evidence

### Phase F. Settings Diff
- store desired config
- compare desired vs reported
- show diff
- later add controlled push workflow

Acceptance:
- operator can spot config drift without inspecting raw JSON

## Risks
- protocol support for remote reboot and destructive commands is not yet confirmed
- access-log upload format from device is not fully traced yet
- image retention can grow quickly
- operator permissions must be strict for remote actions

## Non-Negotiables
- every remote action must be audited
- every device event must be traceable
- image data should be stored as files, not giant inline blobs in API responses
- read-only operations should come before destructive operations

## Immediate Next Steps
1. Add device-detail page tabs (overview/settings/users/actions/events/access logs) with richer UX than alert dialogs.
2. Add role-based permissions for destructive actions (`delete_user`, `delete_all_users`, `reboot`).
3. Add user reconciliation API (`missing_users`, `unexpected_users`) backed by `FaceDeviceUserState`.
4. Add pagination + date-range filters for access logs and events.
5. Add automated tests for action queueing and access-log ingestion.

## Progress Snapshot

Completed:
- Phase A foundation app + URLs + migrations.
- Phase B inventory/status APIs and list UI.
- Phase C action queueing (read-only + mutating action plumbing) with websocket execution and action result correlation.
- Device event persistence for inbound/outbound websocket traffic.
- Access-log storage model (`FaceDeviceAccessLog`) and API endpoints.
- Access-log ingestion hook from websocket inbound payloads with snapshot decoding and person matching.
- Device list UI actions now include `sync_users`, `add_user`, `delete_user`, plus event and access-log quick views.
- Destructive action permission hardening (`delete_user`, `delete_all_users`, `reboot`) in API and UI.
- Pagination and date-range filters for events and access logs in API and device detail UI.

In progress:
- Better structured UI workflows for add/delete user payloads.
- Access-log command mapping hardening as more device event samples are captured.
- Manual access-log pull workflow (`pull_access_logs` -> `getRecord`) to support devices that do not push recognition events automatically.
