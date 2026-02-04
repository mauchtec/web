from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from GateCore.models import Site, Property, Unit, Person, Vehicle, Occupancy
from GateCore.models import GuestRegistration, AccessPoint, AccessDevice, AccessCredential, ScheduleRule, AccessPermission, AccessLog, Blacklist

class Command(BaseCommand):
    help = 'Insert demo data for GateCore app'

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username='demo_admin').exists():
            user = User.objects.create_superuser('demo_admin', 'demo@example.com', 'demopass123')
            self.stdout.write(self.style.SUCCESS('Created demo admin user: demo_admin / demopass123'))
        else:
            user = User.objects.get(username='demo_admin')
            self.stdout.write(self.style.WARNING('Demo admin user already exists.'))


        # --- Demo Sites ---
        sites_data = [
            {
                'name': 'Demo Estate',
                'site_type': 'estate',
                'location': 'Demo City',
                'address': '123 Demo Lane',
                'description': 'A demo estate for testing',
                'code': 'DEMOEST',
            },
            {
                'name': 'Office Park Alpha',
                'site_type': 'office_park',
                'location': 'Alpha City',
                'address': '456 Alpha Ave',
                'description': 'Business offices',
                'code': 'ALPHAOP',
            },
            {
                'name': 'Industrial Park Beta',
                'site_type': 'industrial',
                'location': 'Beta Town',
                'address': '789 Beta Rd',
                'description': 'Industrial area',
                'code': 'BETAIN',
            },
            {
                'name': 'Mixed Use Gamma',
                'site_type': 'mixed_use',
                'location': 'Gamma City',
                'address': '101 Gamma Blvd',
                'description': 'Mixed use development',
                'code': 'GAMMAMU',
            },
        ]
        sites = []
        for sdata in sites_data:
            site, created = Site.objects.get_or_create(
                name=sdata['name'],
                defaults={**sdata, 'created_by': user, 'modified_by': user}
            )
            sites.append(site)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Site: {site.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Site already exists: {site.name}"))

        # --- Demo Properties ---
        properties_data = [
            # Demo Estate
            {'site': sites[0], 'name': 'Demo Block A', 'property_code': 'BLOCKA', 'address': 'Block A, 123 Demo Lane', 'property_type': 'residential', 'location': 'Block A', 'total_floors': 5, 'year_built': 2020},
            {'site': sites[0], 'name': 'Demo Block B', 'property_code': 'BLOCKB', 'address': 'Block B, 123 Demo Lane', 'property_type': 'residential', 'location': 'Block B', 'total_floors': 4, 'year_built': 2021},
            # Office Park Alpha
            {'site': sites[1], 'name': 'Alpha Tower', 'property_code': 'ALPHATWR', 'address': '1 Alpha Ave', 'property_type': 'commercial', 'location': 'Tower', 'total_floors': 10, 'year_built': 2018},
            # Industrial Park Beta
            {'site': sites[2], 'name': 'Beta Warehouse', 'property_code': 'BETAWH', 'address': 'Warehouse, 789 Beta Rd', 'property_type': 'industrial', 'location': 'Warehouse', 'total_floors': 2, 'year_built': 2015},
            # Mixed Use Gamma
            {'site': sites[3], 'name': 'Gamma Mall', 'property_code': 'GAMMAMALL', 'address': 'Mall, 101 Gamma Blvd', 'property_type': 'retail', 'location': 'Mall', 'total_floors': 3, 'year_built': 2019},
        ]
        properties = []
        for pdata in properties_data:
            prop, created = Property.objects.get_or_create(
                site=pdata['site'],
                name=pdata['name'],
                defaults={**pdata, 'created_by': user, 'modified_by': user}
            )
            properties.append(prop)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Property: {prop.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Property already exists: {prop.name}"))

        # --- Demo Units ---
        units_data = [
            # Block A
            {'property': properties[0], 'unit_code': 'A-101', 'unit_type': 'apartment', 'floor': 1, 'status': 'vacant', 'area_sqft': 1200, 'bedrooms': 3, 'bathrooms': 2, 'has_parking': True, 'parking_spots': 1},
            {'property': properties[0], 'unit_code': 'A-102', 'unit_type': 'apartment', 'floor': 1, 'status': 'occupied', 'area_sqft': 1100, 'bedrooms': 2, 'bathrooms': 2, 'has_parking': True, 'parking_spots': 1},
            # Block B
            {'property': properties[1], 'unit_code': 'B-201', 'unit_type': 'apartment', 'floor': 2, 'status': 'vacant', 'area_sqft': 900, 'bedrooms': 1, 'bathrooms': 1, 'has_parking': False, 'parking_spots': 0},
            {'property': properties[1], 'unit_code': 'B-202', 'unit_type': 'apartment', 'floor': 2, 'status': 'reserved', 'area_sqft': 950, 'bedrooms': 2, 'bathrooms': 1, 'has_parking': False, 'parking_spots': 0},
            # Alpha Tower
            {'property': properties[2], 'unit_code': 'T-10A', 'unit_type': 'office', 'floor': 10, 'status': 'vacant', 'area_sqft': 2000, 'bedrooms': 0, 'bathrooms': 2, 'has_parking': True, 'parking_spots': 2},
            {'property': properties[2], 'unit_code': 'T-5B', 'unit_type': 'office', 'floor': 5, 'status': 'occupied', 'area_sqft': 1500, 'bedrooms': 0, 'bathrooms': 1, 'has_parking': True, 'parking_spots': 1},
            # Beta Warehouse
            {'property': properties[3], 'unit_code': 'WH-1', 'unit_type': 'warehouse', 'floor': 1, 'status': 'vacant', 'area_sqft': 5000, 'bedrooms': 0, 'bathrooms': 1, 'has_parking': True, 'parking_spots': 3},
            # Gamma Mall
            {'property': properties[4], 'unit_code': 'M-101', 'unit_type': 'shop', 'floor': 1, 'status': 'vacant', 'area_sqft': 300, 'bedrooms': 0, 'bathrooms': 1, 'has_parking': False, 'parking_spots': 0},
        ]
        units = []
        for udata in units_data:
            unit, created = Unit.objects.get_or_create(
                property=udata['property'],
                unit_code=udata['unit_code'],
                defaults={**udata, 'created_by': user, 'modified_by': user}
            )
            units.append(unit)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Unit: {unit.unit_code}"))
            else:
                self.stdout.write(self.style.WARNING(f"Unit already exists: {unit.unit_code}"))

        # --- Demo People ---
        people_data = [
            {'first_name': 'John', 'last_name': 'Doe', 'phone': '+12345678901', 'email': 'john.doe@example.com', 'gender': 'M'},
            {'first_name': 'Jane', 'last_name': 'Smith', 'phone': '+12345678902', 'email': 'jane.smith@example.com', 'gender': 'F'},
            {'first_name': 'Alice', 'last_name': 'Brown', 'phone': '+12345678903', 'email': 'alice.brown@example.com', 'gender': 'F'},
            {'first_name': 'Bob', 'last_name': 'Contractor', 'phone': '+12345678904', 'email': 'bob.contractor@example.com', 'gender': 'M'},
            {'first_name': 'Eve', 'last_name': 'Guest', 'phone': '+12345678905', 'email': 'eve.guest@example.com', 'gender': 'F'},
            {'first_name': 'Mallory', 'last_name': 'Employee', 'phone': '+12345678906', 'email': 'mallory.employee@example.com', 'gender': 'O'},
        ]
        people = []
        for pdata in people_data:
            person, created = Person.objects.get_or_create(
                first_name=pdata['first_name'],
                last_name=pdata['last_name'],
                defaults={**pdata, 'created_by': user, 'modified_by': user}
            )
            people.append(person)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Person: {person.first_name} {person.last_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Person already exists: {person.first_name} {person.last_name}"))

        # --- Demo Vehicles ---
        vehicles_data = [
            {'person': people[0], 'license_plate': 'DEMOCAR1', 'vehicle_type': 'car', 'make': 'DemoMake', 'model': 'DemoModel', 'color': 'Red', 'year': 2022, 'fuel_type': 'petrol', 'has_sticker': True, 'sticker_number': 'STICKER123'},
            {'person': people[1], 'license_plate': 'JSMITH1', 'vehicle_type': 'car', 'make': 'SmithAuto', 'model': 'S1', 'color': 'Blue', 'year': 2021, 'fuel_type': 'hybrid', 'has_sticker': False, 'sticker_number': ''},
            {'person': people[2], 'license_plate': 'ALICEB1', 'vehicle_type': 'bicycle', 'make': 'BikeCo', 'model': 'BMX', 'color': 'Green', 'year': 2020, 'fuel_type': '', 'has_sticker': False, 'sticker_number': ''},
            {'person': people[3], 'license_plate': 'CONTR1', 'vehicle_type': 'van', 'make': 'WorkVan', 'model': 'V200', 'color': 'White', 'year': 2019, 'fuel_type': 'diesel', 'has_sticker': True, 'sticker_number': 'WORKSTICK'},
        ]
        for vdata in vehicles_data:
            vehicle, created = Vehicle.objects.get_or_create(
                person=vdata['person'],
                license_plate=vdata['license_plate'],
                defaults={**vdata, 'created_by': user, 'modified_by': user}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Vehicle: {vehicle.license_plate}"))
            else:
                self.stdout.write(self.style.WARNING(f"Vehicle already exists: {vehicle.license_plate}"))

        # --- Demo Occupancies ---
        occupancies_data = [
            {'person': people[0], 'unit': units[0], 'role': 'owner', 'start_date': '2024-01-01', 'contract_number': 'CN-001', 'monthly_rent': 0, 'security_deposit': 0, 'is_primary': True},
            {'person': people[1], 'unit': units[1], 'role': 'tenant', 'start_date': '2024-02-01', 'contract_number': 'CN-002', 'monthly_rent': 1200, 'security_deposit': 1200, 'is_primary': True},
            {'person': people[2], 'unit': units[2], 'role': 'owner', 'start_date': '2024-03-01', 'contract_number': 'CN-003', 'monthly_rent': 0, 'security_deposit': 0, 'is_primary': True},
            {'person': people[3], 'unit': units[6], 'role': 'contractor', 'start_date': '2024-04-01', 'contract_number': 'CN-004', 'monthly_rent': 0, 'security_deposit': 0, 'is_primary': True},
            {'person': people[4], 'unit': units[3], 'role': 'guest', 'start_date': '2024-05-01', 'contract_number': 'CN-005', 'monthly_rent': 0, 'security_deposit': 0, 'is_primary': False},
            {'person': people[5], 'unit': units[4], 'role': 'employee', 'start_date': '2024-06-01', 'contract_number': 'CN-006', 'monthly_rent': 0, 'security_deposit': 0, 'is_primary': True},
        ]
        for odata in occupancies_data:
            occ, created = Occupancy.objects.get_or_create(
                person=odata['person'],
                unit=odata['unit'],
                role=odata['role'],
                defaults={**odata, 'created_by': user, 'modified_by': user}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Occupancy for {occ.person} in {occ.unit}"))
            else:
                self.stdout.write(self.style.WARNING(f"Occupancy already exists for {odata['person']} in {odata['unit']}"))

        # --- Demo Guest Registration ---
        guest_reg, created = GuestRegistration.objects.get_or_create(
            host=people[0],
            guest=people[4],
            unit=units[0],
            expected_arrival='2026-02-10T10:00:00Z',
            expected_departure='2026-02-10T18:00:00Z',
            defaults={
                'purpose': 'Visit for demo',
                'notes': 'Demo guest registration',
                'status': 'approved',
                'approved_by': user,
                'approved_at': '2026-02-04T09:00:00Z',
                'temporary_pin': '123456',
                'pin_expires_at': '2026-02-10T18:00:00Z',
                'vehicle': None,
                'created_by': user,
                'modified_by': user,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created GuestRegistration for Eve Guest'))
        else:
            self.stdout.write(self.style.WARNING('GuestRegistration already exists for Eve Guest'))

        # --- Demo Access Points ---
        ap, created = AccessPoint.objects.get_or_create(
            property=properties[0],
            name='Main Gate',
            defaults={
                'point_type': 'gate',
                'location_description': 'Front entrance',
                'location_coordinates': '0,0',
                'requires_authorization': True,
                'default_access': 'denied',
                'is_operational': True,
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Access Device ---
        ad, created = AccessDevice.objects.get_or_create(
            access_point=ap,
            device_type='rfid',
            serial_number='RFID-001',
            defaults={
                'name': 'RFID Reader 1',
                'firmware_version': '1.0',
                'ip_address': '192.168.1.10',
                'mac_address': '00:11:22:33:44:55',
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Access Credential ---
        ac, created = AccessCredential.objects.get_or_create(
            person=people[0],
            credential_type='card',
            credential_value='CARD123',
            defaults={
                'is_temporary': False,
                'notes': 'Demo card',
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Schedule Rule ---
        sr, created = ScheduleRule.objects.get_or_create(
            name='24/7 Access',
            schedule_type='24x7',
            defaults={
                'start_time': '00:00',
                'end_time': '23:59',
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': True,
                'sunday': True,
                'valid_from': '2024-01-01',
                'exclude_holidays': False,
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Access Permission ---
        apm, created = AccessPermission.objects.get_or_create(
            person=people[0],
            access_point=ap,
            schedule_rule=sr,
            defaults={
                'valid_from': '2024-01-01T00:00:00Z',
                'valid_until': '2026-12-31T23:59:59Z',
                'max_daily_uses': 10,
                'priority': 1,
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Access Log ---
        al, created = AccessLog.objects.get_or_create(
            person=people[0],
            device=ad,
            access_point=ap,
            credential=ac,
            timestamp='2026-02-04T10:00:00Z',
            defaults={
                'result': 'granted',
                'reason': 'Demo access',
                'credential_value_used': 'CARD123',
                'latitude': 0.0,
                'longitude': 0.0,
                'session_id': 'SESSION1',
                'request_data': {},
                'created_by': user,
                'modified_by': user,
            }
        )
        # --- Demo Blacklist ---
        bl, created = Blacklist.objects.get_or_create(
            target_type='person',
            person=people[3],
            reason='behavior',
            defaults={
                'details': 'Contractor misbehavior',
                'reported_by': user,
                'blacklisted_from': '2026-02-01T00:00:00Z',
                'blacklisted_until': '2026-03-01T00:00:00Z',
                'created_by': user,
                'modified_by': user,
            }
        )
        self.stdout.write(self.style.SUCCESS('Demo data insertion complete.'))
