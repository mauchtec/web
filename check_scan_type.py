import os
import django
import sys

# Add the project to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AccessControll.settings')
django.setup()

from GateCore.models import AccessLog

logs = AccessLog.objects.all()
for log in logs:
    if log.raw_scan_data and 'scan_type' in log.raw_scan_data:
        print(f'Log {log.id}: scan_type = {log.raw_scan_data.get("scan_type")}')
    else:
        print(f'Log {log.id}: No scan_type in raw_scan_data')
    
    # Also check request_data
    if log.request_data and 'scan_type' in log.request_data:
        print(f'  request_data scan_type = {log.request_data.get("scan_type")}')
    else:
        print(f'  No scan_type in request_data')