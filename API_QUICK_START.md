# GateCore API Quick Start Guide

## 🚀 Quick Reference for New APIs

### Authentication
```bash
# Login to get token (if using token auth)
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Use token in subsequent requests
export TOKEN="your-token-here"
```

---

## 📄 Document Management APIs

### Upload Scanned Driver License
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/raw-scan-archives/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "driving_license",
    "source_device": "Scanner-001",
    "raw_json": {
      "license_number": "41220007CGHR",
      "surname": "DOE",
      "initials": "J",
      "birthdate": "1991/01/11"
    }
  }'
```

### Create Driver License
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/driver-licenses/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "person": "person-uuid",
    "license_number": "41220007CGHR",
    "issue_date": "2025-05-31",
    "expiry_date": "2030-05-30",
    "vehicle_codes": ["B", "C1"],
    "vehicle_restrictions": ["0"],
    "status": "valid"
  }'
```

### Get Licenses Expiring Soon
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-licenses/expiring_soon/" \
  -H "Authorization: Token $TOKEN"
```

### Check for Expired Licenses
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-licenses/?expired=true" \
  -H "Authorization: Token $TOKEN"
```

---

## 🚗 Vehicle Registration APIs

### Create Vehicle Registration
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/vehicle-registrations/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle": "vehicle-uuid",
    "plate_number": "BM62RTGP",
    "disk_number": "PHW801W",
    "expiry_date": "2026-06-30",
    "status": "valid"
  }'
```

### Lookup Vehicle by Plate Number
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/vehicle-registrations/by_plate/?plate=BM62RTGP" \
  -H "Authorization: Token $TOKEN"
```

### Get Registrations Expiring Soon
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/vehicle-registrations/expiring_soon/" \
  -H "Authorization: Token $TOKEN"
```

---

## 👤 Person & Vehicle Blocking

### Block a Person
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/persons/{person-id}/block/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Security concern - unauthorized entry attempt"
  }'
```

### Unblock a Person
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/persons/{person-id}/unblock/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Issue resolved"
  }'
```

### Block a Vehicle
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/vehicles/{vehicle-id}/block/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Stolen vehicle reported"
  }'
```

### Get Block History
```bash
# For a specific person
curl -X GET "http://localhost:8000/api/v1/gatecore/block-history/?entity_type=person&entity_id={person-uuid}" \
  -H "Authorization: Token $TOKEN"

# All blocking actions
curl -X GET "http://localhost:8000/api/v1/gatecore/block-history/?action=blocked" \
  -H "Authorization: Token $TOKEN"
```

---

## 🚙👤 Driver-Vehicle Associations

### Track Driver-Vehicle Pairing
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/driver-vehicle-associations/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "person": "person-uuid",
    "vehicle": "vehicle-uuid",
    "total_visits": 1,
    "is_primary_driver": true
  }'
```

### Get All Vehicles for a Person
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-vehicle-associations/?person={person-uuid}" \
  -H "Authorization: Token $TOKEN"
```

### Get Primary Driver for a Vehicle
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-vehicle-associations/?vehicle={vehicle-uuid}&is_primary_driver=true" \
  -H "Authorization: Token $TOKEN"
```

---

## 🏢 Tenant Management

### Create Tenant
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/tenants/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Smith Family",
    "company": "",
    "unit": "unit-uuid",
    "phone": "+27829876543",
    "email": "smith@example.com"
  }'
```

### Search Tenants
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/tenants/?search=Smith" \
  -H "Authorization: Token $TOKEN"
```

---

## 📝 Enhanced Access Logging

### Log Access with Vehicle & Visitor Info
```bash
curl -X POST http://localhost:8000/api/v1/gatecore/access-logs/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "person": "person-uuid",
    "vehicle": "vehicle-uuid",
    "access_point": "access-point-uuid",
    "access_method": "pin",
    "pin_hash": "sha256-hash-of-pin",
    "visiting_tenant": "tenant-uuid",
    "visit_purpose": "Delivery",
    "entry_time": "2024-01-15T10:30:00Z",
    "result": "granted"
  }'
```

### Get Access Logs by Vehicle
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/access-logs/?vehicle={vehicle-uuid}" \
  -H "Authorization: Token $TOKEN"
```

### Get Access Logs by Access Method
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/access-logs/?access_method=pin" \
  -H "Authorization: Token $TOKEN"
```

### Get Visitor Logs for a Tenant
```bash
curl -X GET "http://localhost:8000/api/v1/gatecore/access-logs/?visiting_tenant={tenant-uuid}" \
  -H "Authorization: Token $TOKEN"
```

---

## 🔍 Advanced Filtering

### Multiple Filters
```bash
# Active, non-blocked persons
curl -X GET "http://localhost:8000/api/v1/gatecore/persons/?is_active=true&is_blocked=false" \
  -H "Authorization: Token $TOKEN"

# Valid licenses for a specific person
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-licenses/?person={uuid}&status=valid" \
  -H "Authorization: Token $TOKEN"

# Recent access logs with vehicles, ordered by entry time
curl -X GET "http://localhost:8000/api/v1/gatecore/access-logs/?vehicle__isnull=false&ordering=-entry_time" \
  -H "Authorization: Token $TOKEN"
```

### Pagination
```bash
# Get page 2 with 50 results per page
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-licenses/?page=2&page_size=50" \
  -H "Authorization: Token $TOKEN"
```

---

## 🔧 Common Workflows

### 1. Complete Document Scan & License Creation
```bash
# Step 1: Upload scan
SCAN_RESPONSE=$(curl -X POST http://localhost:8000/api/v1/gatecore/raw-scan-archives/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_type": "driving_license", "source_device": "Scanner-001", "raw_json": {...}}')

SCAN_ID=$(echo $SCAN_RESPONSE | jq -r '.id')

# Step 2: Create license linked to scan
curl -X POST http://localhost:8000/api/v1/gatecore/driver-licenses/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"person\": \"person-uuid\",
    \"license_number\": \"41220007CGHR\",
    \"issue_date\": \"2025-05-31\",
    \"expiry_date\": \"2030-05-30\",
    \"vehicle_codes\": [\"B\", \"C1\"],
    \"status\": \"valid\",
    \"raw_scan\": \"$SCAN_ID\"
  }"
```

### 2. Vehicle Access with Driver Tracking
```bash
# Step 1: Update driver-vehicle association
curl -X PATCH http://localhost:8000/api/v1/gatecore/driver-vehicle-associations/{assoc-id}/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"total_visits": 5}'

# Step 2: Log the access
curl -X POST http://localhost:8000/api/v1/gatecore/access-logs/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "person": "person-uuid",
    "vehicle": "vehicle-uuid",
    "access_point": "gate-uuid",
    "access_method": "pin",
    "entry_time": "2024-01-15T10:30:00Z",
    "result": "granted"
  }'
```

---

## 📊 Monitoring & Reports

### Check Expiring Documents
```bash
# Licenses expiring soon
curl -X GET "http://localhost:8000/api/v1/gatecore/driver-licenses/expiring_soon/" \
  -H "Authorization: Token $TOKEN"

# Registrations expiring soon
curl -X GET "http://localhost:8000/api/v1/gatecore/vehicle-registrations/expiring_soon/" \
  -H "Authorization: Token $TOKEN"
```

### Security Monitoring
```bash
# Get all blocked persons
curl -X GET "http://localhost:8000/api/v1/gatecore/persons/?is_blocked=true" \
  -H "Authorization: Token $TOKEN"

# Get all blocked vehicles
curl -X GET "http://localhost:8000/api/v1/gatecore/vehicles/?is_blocked=true" \
  -H "Authorization: Token $TOKEN"

# Recent blocking actions
curl -X GET "http://localhost:8000/api/v1/gatecore/block-history/?ordering=-actioned_at" \
  -H "Authorization: Token $TOKEN"
```

---

## 🐍 Python Examples

```python
import requests

API_URL = "http://localhost:8000/api/v1/gatecore"
TOKEN = "your-token-here"
headers = {"Authorization": f"Token {TOKEN}"}

# Create a driver license
license_data = {
    "person": "person-uuid",
    "license_number": "41220007CGHR",
    "issue_date": "2025-05-31",
    "expiry_date": "2030-05-30",
    "vehicle_codes": ["B", "C1"],
    "status": "valid"
}
response = requests.post(f"{API_URL}/driver-licenses/", json=license_data, headers=headers)
print(response.json())

# Get licenses expiring soon
response = requests.get(f"{API_URL}/driver-licenses/expiring_soon/", headers=headers)
expiring = response.json()
print(f"Found {len(expiring)} licenses expiring soon")

# Block a person
block_data = {"reason": "Security concern"}
response = requests.post(
    f"{API_URL}/persons/{person_id}/block/",
    json=block_data,
    headers=headers
)
print(response.json())
```

---

## 📱 JavaScript/React Examples

```javascript
const API_URL = 'http://localhost:8000/api/v1/gatecore';
const token = 'your-token-here';

// Fetch licenses expiring soon
async function getExpiringLicenses() {
  const response = await fetch(`${API_URL}/driver-licenses/expiring_soon/`, {
    headers: {
      'Authorization': `Token ${token}`,
    }
  });
  const data = await response.json();
  console.log('Expiring licenses:', data);
  return data;
}

// Block a vehicle
async function blockVehicle(vehicleId, reason) {
  const response = await fetch(`${API_URL}/vehicles/${vehicleId}/block/`, {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ reason })
  });
  return response.json();
}

// Lookup by plate
async function lookupByPlate(plateNumber) {
  const response = await fetch(
    `${API_URL}/vehicle-registrations/by_plate/?plate=${plateNumber}`,
    {
      headers: { 'Authorization': `Token ${token}` }
    }
  );
  return response.json();
}
```

---

## 🎯 Tips

1. **Always check expiry status** before granting access
2. **Use the block history API** for audit trails
3. **Leverage custom actions** like `expiring_soon` for monitoring
4. **Use pagination** for large datasets
5. **Filter by multiple criteria** to get precise results
6. **Create associations** between drivers and vehicles for better tracking

---

## 📞 Support

For detailed API documentation, see: `API_DOCUMENTATION.md`

For issues or questions: support@gatecore.com
