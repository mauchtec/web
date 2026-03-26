#!/usr/bin/env python3
"""
Script to create dummy data for testing
Includes units, people (with user's phone +27656231093), and occupancy
"""
import os
import sys
import django
from datetime import date, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AccessControll.settings')
django.setup()

from GateCore.models import Site, Property, Unit, Person, Occupancy, Vehicle

def create_dummy_data():
    print("🏗️  Creating dummy data...")
    
    # 1. Create or get Site
    site, created = Site.objects.get_or_create(
        name="Sunset Estate",
        defaults={
            'site_type': 'estate',
            'location': 'Johannesburg, Gauteng',
            'address': '123 Main Road, Sandton, 2196',
            'description': 'Luxury residential estate with modern amenities',
            'code': 'SUNSET01'
        }
    )
    print(f"✅ Site: {site.name} ({'created' if created else 'exists'})")
    
    # 2. Create or get Property
    property_obj, created = Property.objects.get_or_create(
        site=site,
        name="Sunset Towers",
        defaults={
            'property_code': 'ST001',
            'address': '123 Main Road, Building A',
            'property_type': 'residential',
            'location': 'Block A',
            'total_floors': 10,
            'year_built': 2020
        }
    )
    print(f"✅ Property: {property_obj.name} ({'created' if created else 'exists'})")
    
    # 3. Create Units
    units_data = [
        {'code': 'A101', 'floor': 1, 'type': 'apartment', 'bedrooms': 2, 'bathrooms': 1},
        {'code': 'A102', 'floor': 1, 'type': 'apartment', 'bedrooms': 2, 'bathrooms': 2},
        {'code': 'A201', 'floor': 2, 'type': 'apartment', 'bedrooms': 3, 'bathrooms': 2},
        {'code': 'A202', 'floor': 2, 'type': 'apartment', 'bedrooms': 3, 'bathrooms': 2},
        {'code': 'A301', 'floor': 3, 'type': 'apartment', 'bedrooms': 2, 'bathrooms': 1},
        {'code': 'P01', 'floor': 10, 'type': 'penthouse', 'bedrooms': 4, 'bathrooms': 3},
    ]
    
    units = []
    for unit_data in units_data:
        unit, created = Unit.objects.get_or_create(
            property=property_obj,
            unit_code=unit_data['code'],
            defaults={
                'unit_type': unit_data['type'],
                'floor': unit_data['floor'],
                'status': 'occupied',
                'bedrooms': unit_data['bedrooms'],
                'bathrooms': unit_data['bathrooms'],
                'has_parking': True,
                'parking_spots': 1,
                'permissions': 'residence_advanced'
            }
        )
        units.append(unit)
        print(f"✅ Unit: {unit.unit_code} ({'created' if created else 'exists'})")
    
    # 4. Create People (including user's phone number)
    people_data = [
        {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+27656231093',  # User's phone number
            'email': 'john.doe@example.com',
            'id_number': '8501015800088',
            'gender': 'M',
            'unit': units[0]  # A101
        },
        {
            'first_name': 'Sarah',
            'last_name': 'Smith',
            'phone': '+27821234567',
            'email': 'sarah.smith@example.com',
            'id_number': '9203155800084',
            'gender': 'F',
            'unit': units[1]  # A102
        },
        {
            'first_name': 'Michael',
            'last_name': 'Johnson',
            'phone': '+27831234567',
            'email': 'michael.j@example.com',
            'id_number': '7809105800089',
            'gender': 'M',
            'unit': units[2]  # A201
        },
        {
            'first_name': 'Emily',
            'last_name': 'Brown',
            'phone': '+27841234567',
            'email': 'emily.brown@example.com',
            'id_number': '9505205800085',
            'gender': 'F',
            'unit': units[3]  # A202
        },
        {
            'first_name': 'David',
            'last_name': 'Williams',
            'phone': '+27851234567',
            'email': 'david.w@example.com',
            'id_number': '8112015800087',
            'gender': 'M',
            'unit': units[4]  # A301
        },
        {
            'first_name': 'Lisa',
            'last_name': 'Anderson',
            'phone': '+27861234567',
            'email': 'lisa.anderson@example.com',
            'id_number': '9008155800083',
            'gender': 'F',
            'unit': units[5]  # P01 (Penthouse)
        },
    ]
    
    people = []
    for person_data in people_data:
        unit = person_data.pop('unit')
        person, created = Person.objects.get_or_create(
            phone=person_data['phone'],
            defaults=person_data
        )
        people.append((person, unit))
        print(f"✅ Person: {person.full_name} - {person.phone} ({'created' if created else 'exists'})")
        
        # Create occupancy
        occupancy, created = Occupancy.objects.get_or_create(
            unit=unit,
            person=person,
            defaults={
                'occupancy_type': 'tenant',
                'start_date': date.today() - timedelta(days=180),
                'end_date': date.today() + timedelta(days=185),
                'is_primary': True
            }
        )
        print(f"   └─ Occupancy in {unit.unit_code} ({'created' if created else 'exists'})")
    
    # 5. Create some vehicles
    vehicles_data = [
        {
            'person': people[0][0],  # John Doe
            'license_plate': 'CA123GP',
            'vehicle_type': 'car',
            'make': 'Toyota',
            'model': 'Corolla',
            'color': 'Silver',
            'year': 2021
        },
        {
            'person': people[1][0],  # Sarah Smith
            'license_plate': 'CA456GP',
            'vehicle_type': 'car',
            'make': 'BMW',
            'model': '3 Series',
            'color': 'Black',
            'year': 2022
        },
        {
            'person': people[5][0],  # Lisa Anderson (Penthouse)
            'license_plate': 'CA999GP',
            'vehicle_type': 'car',
            'make': 'Mercedes',
            'model': 'S-Class',
            'color': 'White',
            'year': 2023
        },
    ]
    
    for vehicle_data in vehicles_data:
        vehicle, created = Vehicle.objects.get_or_create(
            license_plate=vehicle_data['license_plate'],
            person=vehicle_data['person'],
            defaults={k: v for k, v in vehicle_data.items() if k not in ['license_plate', 'person']}
        )
        print(f"✅ Vehicle: {vehicle.license_plate} - {vehicle.person.full_name} ({'created' if created else 'exists'})")
    
    print("\n✨ Dummy data creation complete!")
    print(f"\nSummary:")
    print(f"  Sites: {Site.objects.count()}")
    print(f"  Properties: {Property.objects.count()}")
    print(f"  Units: {Unit.objects.count()}")
    print(f"  People: {Person.objects.count()}")
    print(f"  Occupancies: {Occupancy.objects.count()}")
    print(f"  Vehicles: {Vehicle.objects.count()}")
    print(f"\n👤 Your test phone number: +27656231093 (John Doe, Unit A101)")

if __name__ == "__main__":
    create_dummy_data()
