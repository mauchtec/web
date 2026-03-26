import os
import django
import sys

# Add the project to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AccessControll.settings')
django.setup()

from GateCore.models import AccessLog
from django.db.models import Q
import json

# Check total records
total = AccessLog.objects.count()
print(f"Total AccessLog records: {total}")

# Check for license data
license_count = AccessLog.objects.filter(
    Q(raw_scan_data__license__isnull=False) | 
    Q(raw_scan_data__scan_type__iexact='license') | 
    Q(raw_scan_data__document_type__iexact='driving_license')
).count()
print(f"License logs count (current query): {license_count}")

# Check first few records to see what data exists
logs = AccessLog.objects.all()[:5]
print(f"\nFirst {len(logs)} records:")
for i, log in enumerate(logs):
    print(f"\nRecord {i+1}:")
    print(f"  ID: {log.id}")
    print(f"  Result: {log.result}")
    print(f"  Has raw_scan_data: {bool(log.raw_scan_data)}")
    print(f"  Has request_data: {bool(log.request_data)}")
    
    if log.raw_scan_data:
        print(f"  raw_scan_data type: {type(log.raw_scan_data)}")
        if isinstance(log.raw_scan_data, dict):
            print(f"  raw_scan_data keys: {list(log.raw_scan_data.keys())}")
            # Check for any license-related keys
            license_keys = [k for k in log.raw_scan_data.keys() if 'license' in k.lower() or 'id' in k.lower() or 'document' in k.lower()]
            if license_keys:
                print(f"  Possible license keys: {license_keys}")
    
    if log.request_data:
        print(f"  request_data type: {type(log.request_data)}")
        if isinstance(log.request_data, dict):
            print(f"  request_data keys: {list(log.request_data.keys())}")
            license_keys = [k for k in log.request_data.keys() if 'license' in k.lower() or 'id' in k.lower() or 'document' in k.lower()]
            if license_keys:
                print(f"  Possible license keys: {license_keys}")

# Try a broader search for any data that might be license-related
print("\n\nSearching for any license-related data in all fields...")
all_logs = AccessLog.objects.all()
license_related = []
for log in all_logs:
    found = False
    data_to_check = []
    
    if log.raw_scan_data and isinstance(log.raw_scan_data, dict):
        data_to_check.append(('raw_scan_data', log.raw_scan_data))
    if log.request_data and isinstance(log.request_data, dict):
        data_to_check.append(('request_data', log.request_data))
    
    for field_name, data in data_to_check:
        # Check for any license-like data
        for key, value in data.items():
            if isinstance(key, str) and any(term in key.lower() for term in ['license', 'id', 'document', 'driving', 'driver']):
                license_related.append((log.id, field_name, key, value))
                found = True
            # Also check values for license numbers (SA ID format or license format)
            if isinstance(value, str) and (len(value) == 13 and value.isdigit()):  # SA ID number
                license_related.append((log.id, field_name, key, value))
                found = True
    
    if found:
        print(f"Found license-related data in log {log.id}")

if license_related:
    print(f"\nFound {len(license_related)} license-related data points:")
    for log_id, field, key, value in license_related[:10]:  # Show first 10
        print(f"  Log {log_id}: {field}.{key} = {value}")
else:
    print("No license-related data found in any AccessLog records.")