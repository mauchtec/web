# Residence App API Schema

This document defines the stable API contract for the residence app and any other client that needs to consume GateCore data.

Machine-readable version:
- [docs/RESIDENCE_APP_API_OPENAPI.yaml](RESIDENCE_APP_API_OPENAPI.yaml)

## Scope

This schema covers the GateCore API surface under:

- `/api/gatecore/`

It also includes the mobile OTP login flow used by Android and future residence-app clients.

## Authentication

### Mobile login flow

1. `POST /api/gatecore/mobile/login/request-otp/`
   - Request body:
     - `phone` - string, required
   - Response:
     - `otp_sent` - boolean
     - `expires_in` - integer seconds
     - `memberships` - array of membership choices
     - `otp` - optional, only present in debug/test environments

2. `POST /api/gatecore/mobile/login/verify-otp/`
   - Request body:
     - `phone` - string, required
     - `membership_id` - UUID string, required
     - `otp` - string, required
     - optional device fields:
       - `device_id`
       - `device_name`
       - `device_model`
       - `device_serial`
       - `device_os`
       - `device_app_version`
       - `device_info` object
       - `device_manufacturer`
       - `device_sdk`
       - `latitude`
       - `longitude`
   - Response:
     - standard token payload returned by `build_token_response()`
     - clients must send `Authorization: Token <key>` on protected API requests

### Protected requests

- Most endpoints require authentication.
- Staff/admin endpoints require the authenticated user to be staff.
- Mobile/client endpoints use DRF token auth after OTP verify.
- Web UI shell pages may still use session auth, but the API contract itself is token-compatible.

## Common response rules

### Data envelopes

Collection endpoints return a canonical `rows` key.

Compatibility aliases may also be present:

- `people`
- `units`
- `sites`
- `vehicle_logs`
- `logs`
- `sms_logs`
- `credentials`
- `permissions`
- `guests`
- `blacklist`
- `results`

Clients should prefer `rows`.

### Field conventions

- IDs are UUID strings unless a route explicitly uses an integer primary key.
- Empty values are returned as `""` rather than `null` when practical.
- Datetimes are ISO 8601 strings.
- Booleans are native JSON booleans.
- Display labels are provided as `*_display` when useful.
- Detail links are returned as `detail_url`, `log_url`, `pdf_url`, or similar.

### Errors

Error responses usually use one of these shapes:

- `{"detail": "..."}`
- `{"success": false, "error": "..."}`

## Endpoint Summary

### Dashboard

- `GET /api/gatecore/dashboard/summary/`
- Returns dashboard counts and summary cards.

### Sites

- `GET /api/gatecore/sites/overview/`
- `GET /api/gatecore/sites/`
- `POST /api/gatecore/sites/`
- `GET /api/gatecore/sites/<uuid>/`
- `PUT /api/gatecore/sites/<uuid>/`
- `DELETE /api/gatecore/sites/<uuid>/`

### People

- `GET /api/gatecore/people/overview/`
- `GET /api/gatecore/details/people/<uuid>/`

### Units

- `GET /api/gatecore/units/overview/`
- `GET /api/gatecore/details/units/<uuid>/`

### Vehicles

- `GET /api/gatecore/vehicles/overview/`
- `GET /api/gatecore/details/vehicles/<uuid>/`

### Access logs and reports

- `GET /api/gatecore/access-logs/overview/`
- `GET /api/gatecore/access-logs/<uuid>/detail/`
- `GET /api/gatecore/reports/overview/`

### Bookings

- `GET /api/gatecore/bookings/overview/`
- `POST /api/gatecore/bookings/create/`
- `GET /api/gatecore/bookings/<uuid>/detail/`
- `POST /api/gatecore/bookings/<uuid>/cancel/`

Booking create kinds:

- `invite_contact` - pick a person from device contacts
- `invite_phone` - type a cellphone number manually
- `future_booking` - select only an end date, starts now
- `delivery_collection` - no date range, valid for 24 hours from creation

### Driver licenses

- `GET /api/gatecore/driver-licenses/overview/`

### SMS logs

- `GET /api/gatecore/sms-logs/overview/`

### Access credentials

- `GET /api/gatecore/access-credentials/overview/`
- `GET /api/gatecore/details/access-credentials/<uuid>/`

### Access permissions

- `GET /api/gatecore/access-permissions/overview/`
- `GET /api/gatecore/details/access-permissions/<uuid>/`

### Guest registrations

- `GET /api/gatecore/guest-registrations/overview/`
- `GET /api/gatecore/details/guest-registrations/<uuid>/`

### Blacklist

- `GET /api/gatecore/blacklist/overview/`
- `GET /api/gatecore/details/blacklist/<uuid>/`

### Access rules

- `GET /api/gatecore/accessrules/`
- `POST /api/gatecore/accessrules/`
- `GET /api/gatecore/accessrules/<int:pk>/`
- `PUT /api/gatecore/accessrules/<int:pk>/`
- `DELETE /api/gatecore/accessrules/<int:pk>/`

### Runtime settings

- `GET /api/gatecore/settings/api/`
- `PUT /api/gatecore/settings/api/`

### Mutation endpoints

- `POST /api/gatecore/mutations/add-unit/`
- `POST /api/gatecore/mutations/update-unit/<uuid:unit_id>/`
- `POST /api/gatecore/mutations/add-person/`
- `POST /api/gatecore/mutations/update-person/<uuid:person_id>/`
- `POST /api/gatecore/mutations/link-person-to-unit/`
- `POST /api/gatecore/mutations/reallocate-person/`

## Resource Schemas

### Site row

- `id` - UUID string
- `name` - string
- `site_type` - string
- `type_display` - string
- `location` - string
- `code` - string
- `description` - string
- `is_active` - boolean

### Person row

- `id` - UUID string
- `full_name` - string
- `id_number` - string
- `phone` - string
- `email` - string
- `residences` - string
- `detail_url` - string

### Unit row

- `id` - UUID string
- `site_name` - string
- `property_name` - string
- `unit_code` - string
- `unit_type` - string
- `unit_type_display` - string
- `status` - string
- `status_display` - string
- `floor` - string or number rendered as string
- `area_sqft` - string or number rendered as string
- `detail_url` - string

### Vehicle row

- `id` - UUID string
- `plate_number` - string
- `record_type` - string
- `register_number` - string
- `disk_number` - string
- `expiry_date` - string
- `vehicle_type` - string
- `make` - string
- `model` - string
- `colour` - string
- `vin` - string
- `engine_number` - string
- `status` - string
- `detail_url` - string

### Access log row

- `id` - UUID string
- `timestamp` - ISO 8601 string
- `timestamp_display` - string
- `access_point` - object with `id`, `name`
- `person` - object with `id`, `full_name`
- `credential` - object with `id`, `value`
- `result` - string
- `result_display` - string
- `reason` - string
- `session_id` - string
- `detail_url` - string
- `report_url` - string
- `pdf_url` - string
- `component_items` - array of component label/value objects
- `request_data` - object
- `raw_data` - object
- `driver_details` - object
- `vehicle_details` - object
- `trailer_details` - object
- `license_details` - object
- `component_values` - object
- `entry_summary` - object or null
- `exit_summary` - object or null

### Report row

- `id` - UUID string
- `timestamp` - string
- `workflow_name` - string
- `direction` - string
- `access_point` - string
- `result` - string
- `pin_code` - string
- `pin_source` - string
- `recording_url` - string
- `id_number` - string
- `gender` - string
- `full_name` - string
- `visitor_phone_number` - string
- `destination_residence` - string
- `vehicle_plate` - string
- `trailer` - string
- `vehicle_make_model` - string
- `vehicle_color` - string
- `company_selection` - string
- `workflow_id` - string
- `workflow_version` - string
- `scan_type` - string
- `person_name` - string
- `credential` - string
- `log_url` - string

### Driver license row

- `id_number` - string
- `license_number` - string
- `driver_license_id` - string
- `surname` - string
- `initials` - string
- `birthdate` - string
- `gender` - string
- `license_issue_date` - string
- `license_expiry_date` - string
- `status` - string
- `vehicle_codes` - string
- `vehicle_restrictions` - string
- `license_code_issue_dates` - string
- `driver_restriction_codes` - string
- `prdp_code` - string
- `prdp_expiry_date` - string
- `id_country_of_issue` - string
- `timestamp` - string

### SMS log row

- `id` - UUID string
- `created_at` - ISO 8601 string
- `created_at_display` - string
- `status` - string
- `status_display` - string
- `provider` - string
- `trigger` - string
- `unit` - object with `id`, `unit_code`
- `person` - object with `id`, `full_name`
- `visitor_name` - string
- `visitor_phone` - string
- `recipient_phone` - string
- `message` - string
- `provider_message_id` - string
- `error_message` - string
- `completed_at` - ISO 8601 string or empty string
- `completed_at_display` - string

### Access credential row

- `id` - UUID string
- `credential_value` - string
- `credential_type` - string
- `credential_type_display` - string
- `person` - object with `id`, `full_name`
- `is_active` - boolean
- `is_deleted` - boolean
- `status_label` - string
- `detail_url` - string

### Access permission row

- `id` - UUID string
- `person` - object with `id`, `full_name`
- `access_point` - object with `id`, `name`
- `schedule_rule` - object with `id`, `name`
- `schedule_display` - string
- `status_label` - string
- `detail_url` - string

### Guest registration row

- `id` - UUID string
- `guest_name` - string
- `person` - object with `id`, `full_name`
- `unit` - object with `id`, `unit_code`
- `expected_arrival` - ISO 8601 string
- `expected_departure` - ISO 8601 string
- `expected_arrival_display` - string
- `expected_departure_display` - string
- `status` - string
- `status_display` - string
- `detail_url` - string

### Blacklist row

- `id` - UUID string
- `person` - object with `id`, `full_name`
- `vehicle` - object with `id`, `license_plate`
- `credential` - object with `id`, `credential_value`
- `target_type` - string
- `target_type_display` - string
- `reason` - string
- `reason_display` - string
- `details` - string
- `blacklisted_from` - ISO 8601 string
- `blacklisted_from_display` - string
- `blacklisted_until` - ISO 8601 string
- `blacklisted_until_display` - string
- `detail_url` - string

### Access rule row

- `id` - integer
- `name` - string
- `group` - string
- `location` - string
- `start_time` - ISO 8601 time string
- `end_time` - ISO 8601 time string
- `days_of_week` - string
- `is_active` - boolean
- `temporary` - boolean
- `expires_at` - ISO 8601 datetime string
- `expires_at_display` - string

### Runtime settings

- `pin_length` - integer
- `allow_sip_calls` - boolean
- `send_visitor_sms` - boolean
- `send_visitor_sms_otp` - boolean
- `send_visitor_sms_exitcode` - boolean
- `anti_passback_enabled` - boolean
- `anti_passback_window_hours` - integer
- `anti_passback_no_reentry_without_exit` - boolean
- `anti_passback_allow_manual_override` - boolean
- `anti_passback_override_comment_required` - boolean
- `anti_passback_warning_message` - string

## Mutation payloads

### Add unit

`POST /api/gatecore/mutations/add-unit/`

- `site`
- `property`
- `unit_code`
- `unit_type`
- `status`
- `permissions`
- `is_active`

### Update unit

`POST /api/gatecore/mutations/update-unit/<uuid:unit_id>/`

- same fields as add unit, optional

### Add person

`POST /api/gatecore/mutations/add-person/`

- `unit_id` or `unit`
- `full_name`
- `id_number`
- `phone`
- `phone_device_type`
- `phone_otp`
- `facial_recognition_enabled`
- `email`
- `date_of_birth`
- `emergency_contact`
- `tags`
- `start_date`
- `role`
- device metadata fields

### Update person

`POST /api/gatecore/mutations/update-person/<uuid:person_id>/`

- same editable person fields as add person

### Link person to unit

`POST /api/gatecore/mutations/link-person-to-unit/`

- `person_id`
- `unit_id`

### Reallocate person

`POST /api/gatecore/mutations/reallocate-person/`

- `person_id`
- `new_unit_id` or `unit_id`

## Notes for the app team

- Prefer `rows` for all collections.
- Prefer UUIDs for identifiers unless the endpoint explicitly uses an integer PK.
- Treat the GateCore API as the source of truth for the residence app.
- The web UI is now a thin shell over the same API and should not be used as the client contract.
