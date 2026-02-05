from django.core.management.base import BaseCommand
from django.utils import timezone
from GateCore.models import DriverLicense, VehicleRegistration


class Command(BaseCommand):
    help = 'Auto-expire driver licenses and vehicle registrations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be expired without making changes',
        )
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        dry_run = options.get('dry_run', False)
        
        # Find expired licenses
        expired_licenses = DriverLicense.objects.filter(
            expiry_date__lt=today,
            status='valid'
        )
        
        # Find expired registrations
        expired_regs = VehicleRegistration.objects.filter(
            expiry_date__lt=today,
            status='valid'
        )
        
        license_count = expired_licenses.count()
        reg_count = expired_regs.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would expire {license_count} licenses and {reg_count} registrations'
                )
            )
            
            if license_count > 0:
                self.stdout.write("\nExpired Licenses:")
                for lic in expired_licenses[:10]:  # Show first 10
                    self.stdout.write(f"  - {lic.license_number} ({lic.person}) - expired {lic.expiry_date}")
                if license_count > 10:
                    self.stdout.write(f"  ... and {license_count - 10} more")
            
            if reg_count > 0:
                self.stdout.write("\nExpired Registrations:")
                for reg in expired_regs[:10]:  # Show first 10
                    self.stdout.write(f"  - {reg.plate_number} ({reg.disk_number}) - expired {reg.expiry_date}")
                if reg_count > 10:
                    self.stdout.write(f"  ... and {reg_count - 10} more")
        else:
            # Actually update the status
            expired_licenses.update(status='expired')
            expired_regs.update(status='expired')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Expired {license_count} licenses and {reg_count} registrations'
                )
            )
