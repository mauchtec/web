# GateCore API Documentation

## New API Endpoints for Document Management & Access Control

### Base URL
All API endpoints are available at: `/api/v1/gatecore/`

---

## New Model Endpoints

### 1. Tenants API
**Endpoint:** `/api/v1/gatecore/tenants/`

Manage visitor destinations and people being visited.

**Methods:**
- `GET` - List all tenants
- `POST` - Create new tenant
- `GET /{id}/` - Get tenant details
- `PUT/PATCH /{id}/` - Update tenant
- `DELETE /{id}/` - Delete tenant

**Filters:**
- `unit` - Filter by unit ID
- `is_active` - Filter by active status

**Search:** name, company, phone, email

**Example:**
```bash
GET /api/v1/gatecore/tenants/?unit=<unit-id>
GET /api/v1/gatecore/tenants/?search=Smith
```

---

### 2. Raw Scan Archives API
**Endpoint:** `/api/v1/gatecore/raw-scan-archives/`

Immutable storage for scanned documents (licenses, vehicle disks).

**Methods:**
- `GET` - List all scans
- `POST` - Upload new scan (SHA256 auto-generated)
- `GET /{id}/` - Get scan details
- `DELETE /{id}/` - Delete scan (admin only)

**Filters:**
- `document_type` - "driving_license" or "vehicle_disk"
- `processed` - Boolean
- `source_device` - Device identifier

**Search:** sha256_hash, source_device

**Example:**
```bash
POST /api/v1/gatecore/raw-scan-archives/
{
  "document_type": "driving_license",
  "source_device": "Scanner-001",
  "raw_json": { ... }
}
```

---

### 3. Driver Licenses API
**Endpoint:** `/api/v1/gatecore/driver-licenses/`

Driver license tracking with expiry and status management.

**Methods:**
- `GET` - List all licenses
- `POST` - Create new license
- `GET /{id}/` - Get license details
- `PUT/PATCH /{id}/` - Update license
- `DELETE /{id}/` - Delete license
- `POST /{id}/block/` - Block a license
- `GET /expiring_soon/` - Get licenses expiring in 30 days

**Filters:**
- `person` - Filter by person ID
- `status` - "valid", "expired", or "blocked"
- `is_active` - Active status
- `expired=true/false` - Filter by expiry status

**Search:** license_number, driver_restriction_codes

**Custom Actions:**
```bash
# Get licenses expiring soon
GET /api/v1/gatecore/driver-licenses/expiring_soon/

# Block a license
POST /api/v1/gatecore/driver-licenses/{id}/block/
{
  "reason": "Security concern"
}

# Filter expired licenses
GET /api/v1/gatecore/driver-licenses/?expired=true
```

---

### 4. Vehicle Registrations API
**Endpoint:** `/api/v1/gatecore/vehicle-registrations/`

Vehicle registration disk tracking with expiry dates.

**Methods:**
- `GET` - List all registrations
- `POST` - Create new registration
- `GET /{id}/` - Get registration details
- `PUT/PATCH /{id}/` - Update registration
- `DELETE /{id}/` - Delete registration
- `GET /expiring_soon/` - Get registrations expiring in 30 days
- `GET /by_plate/?plate=ABC123` - Lookup by plate number

**Filters:**
- `vehicle` - Filter by vehicle ID
- `status` - "valid", "expired", or "blocked"
- `is_active` - Active status
- `expired=true/false` - Filter by expiry status

**Search:** plate_number, disk_number, vehicle_register_number

**Custom Actions:**
```bash
# Get registrations expiring soon
GET /api/v1/gatecore/vehicle-registrations/expiring_soon/

# Lookup by plate number
GET /api/v1/gatecore/vehicle-registrations/by_plate/?plate=BM62RTGP

# Filter expired registrations
GET /api/v1/gatecore/vehicle-registrations/?expired=true
```

---

### 5. Driver-Vehicle Associations API
**Endpoint:** `/api/v1/gatecore/driver-vehicle-associations/`

Track driver-vehicle pairings over time.

**Methods:**
- `GET` - List all associations
- `POST` - Create new association
- `GET /{id}/` - Get association details
- `PUT/PATCH /{id}/` - Update association
- `DELETE /{id}/` - Delete association

**Filters:**
- `person` - Filter by person ID
- `vehicle` - Filter by vehicle ID
- `is_primary_driver` - Boolean
- `is_active` - Active status

**Ordering:** total_visits, last_seen, first_seen

**Example:**
```bash
# Get all vehicles for a person
GET /api/v1/gatecore/driver-vehicle-associations/?person=<person-id>

# Get primary driver for a vehicle
GET /api/v1/gatecore/driver-vehicle-associations/?vehicle=<vehicle-id>&is_primary_driver=true
```

---

### 6. Block History API
**Endpoint:** `/api/v1/gatecore/block-history/`

Audit trail for blocking/unblocking actions.

**Methods:**
- `GET` - List all block history
- `POST` - Create block history entry
- `GET /{id}/` - Get history details

**Filters:**
- `entity_type` - "person" or "vehicle"
- `action` - "blocked" or "unblocked"
- `actioned_by` - User ID

**Search:** reason, entity_id

**Example:**
```bash
# Get block history for a person
GET /api/v1/gatecore/block-history/?entity_type=person&entity_id=<person-id>

# Get all blocking actions
GET /api/v1/gatecore/block-history/?action=blocked
```

---

## Enhanced Existing Endpoints

### Persons API (Enhanced)
**Endpoint:** `/api/v1/gatecore/persons/`

**New Filters:**
- `is_blocked` - Boolean filter for blocked persons

**New Actions:**
```bash
# Block a person
POST /api/v1/gatecore/persons/{id}/block/
{
  "reason": "Security concern"
}

# Unblock a person
POST /api/v1/gatecore/persons/{id}/unblock/
{
  "reason": "Issue resolved"
}
```

---

### Vehicles API (Enhanced)
**Endpoint:** `/api/v1/gatecore/vehicles/`

**New Filters:**
- `is_blocked` - Boolean filter for blocked vehicles

**New Search Fields:**
- `vin` - Vehicle Identification Number
- `engine_number` - Engine serial number

**New Actions:**
```bash
# Block a vehicle
POST /api/v1/gatecore/vehicles/{id}/block/
{
  "reason": "Stolen vehicle"
}

# Unblock a vehicle
POST /api/v1/gatecore/vehicles/{id}/unblock/
{
  "reason": "Vehicle recovered"
}
```

---

### Access Logs API (Enhanced)
**Endpoint:** `/api/v1/gatecore/access-logs/`

**New Filters:**
- `vehicle` - Filter by vehicle ID
- `access_method` - "pin", "voice", "manual", "rfid", "biometric", "qr"
- `visiting_tenant` - Filter by tenant ID

**New Search Fields:**
- `visit_purpose` - Purpose of visit
- `visiting_freeform` - Freeform visitor destination

**New Ordering:**
- `entry_time` - Entry timestamp
- `exit_time` - Exit timestamp

**Example:**
```bash
# Get all PIN access logs
GET /api/v1/gatecore/access-logs/?access_method=pin

# Get logs for a specific vehicle
GET /api/v1/gatecore/access-logs/?vehicle=<vehicle-id>

# Get visitor logs for a tenant
GET /api/v1/gatecore/access-logs/?visiting_tenant=<tenant-id>

# Get access logs with entry/exit times
GET /api/v1/gatecore/access-logs/?ordering=-entry_time
```

---

## Common Response Format

### Success Response
```json
{
  "count": 100,
  "next": "http://api/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

### Single Object
```json
{
  "id": "uuid",
  "field1": "value1",
  ...
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

---

## Pagination

All list endpoints support pagination:
- Default page size: 20
- Query params: `?page=2&page_size=50`

---

## Filtering Examples

### Complex Filters
```bash
# Active, non-blocked persons
GET /api/v1/gatecore/persons/?is_active=true&is_blocked=false

# Valid licenses expiring in 2024
GET /api/v1/gatecore/driver-licenses/?status=valid&expiry_date__year=2024

# Recent access logs with vehicles
GET /api/v1/gatecore/access-logs/?vehicle__isnull=false&ordering=-entry_time
```

---

## Authentication

All endpoints require authentication. Include token in header:
```bash
Authorization: Token <your-token>
```

Or use session authentication via Django admin login.

---

## Sample Workflows

### 1. Document Scanning Workflow
```bash
# 1. Upload scanned document
POST /api/v1/gatecore/raw-scan-archives/
{
  "document_type": "driving_license",
  "source_device": "Scanner-001",
  "raw_json": {...}
}

# 2. Create driver license from scan
POST /api/v1/gatecore/driver-licenses/
{
  "person": "<person-id>",
  "license_number": "41220007CGHR",
  "issue_date": "2025-05-31",
  "expiry_date": "2030-05-30",
  "vehicle_codes": ["B", "C1"],
  "status": "valid",
  "raw_scan": "<scan-id>"
}
```

### 2. Vehicle Access Tracking
```bash
# 1. Create/update driver-vehicle association
POST /api/v1/gatecore/driver-vehicle-associations/
{
  "person": "<person-id>",
  "vehicle": "<vehicle-id>",
  "is_primary_driver": true,
  "total_visits": 1
}

# 2. Log access with vehicle
POST /api/v1/gatecore/access-logs/
{
  "person": "<person-id>",
  "vehicle": "<vehicle-id>",
  "access_point": "<point-id>",
  "access_method": "pin",
  "visiting_tenant": "<tenant-id>",
  "entry_time": "2024-01-15T10:30:00Z",
  "result": "granted"
}
```

### 3. Blocking Workflow
```bash
# 1. Block a person
POST /api/v1/gatecore/persons/{id}/block/
{
  "reason": "Security concern - unauthorized entry attempt"
}

# 2. Check block history
GET /api/v1/gatecore/block-history/?entity_type=person&entity_id=<person-id>
```

---

## Rate Limiting

- Standard: 100 requests/minute
- Authenticated: 1000 requests/minute

---

## Support

For API support, contact: support@gatecore.com
Documentation version: 1.0
Last updated: 2024
