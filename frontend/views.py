
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from GateCore.models import Site, Property, Unit, Person, Vehicle, AccessPoint, AccessDevice, AccessCredential, AccessLog, GuestRegistration, ScheduleRule, AccessPermission, Blacklist, Occupancy
from django.db.models import Count
import django.db.models as models

# People linked to multiple residences
@login_required
def gatecore_people_multi_residence(request):
    people = Person.objects.annotate(num_residences=Count('occupancies', filter=models.Q(occupancies__is_active=True, occupancies__is_deleted=False))).filter(num_residences__gt=1).prefetch_related('occupancies__unit__property__site').order_by('last_name', 'first_name')
    return render(request, "frontend/gatecore_people_multi_residence.html", {"people": people})

# ...existing code...

@require_POST
def ajax_link_person_to_unit(request):
    from django.utils import timezone
    person_id = request.POST.get('person_id')
    unit_id = request.POST.get('unit_id')
    if not person_id or not unit_id:
        return JsonResponse({'success': False, 'error': 'Missing person or unit.'}, status=400)
    try:
        person = Person.objects.get(id=person_id)
        unit = Unit.objects.get(id=unit_id)
        # Check if an active occupancy already exists for this person/unit
        if Occupancy.objects.filter(person=person, unit=unit, is_active=True, is_deleted=False, end_date__isnull=True).exists():
            return JsonResponse({'success': False, 'error': 'Person is already linked to this unit.'}, status=400)
        # Create new occupancy (do not end previous ones)
        Occupancy.objects.create(
            person=person,
            unit=unit,
            role='tenant',  # Default to tenant, can be extended
            start_date=timezone.now().date(),
            is_active=True,
            is_deleted=False
        )
        AuditTrail.objects.create(
            person=person,
            unit=unit,
            action="link",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Linked {person} to unit {unit}"
        )
        return JsonResponse({'success': True})
    except Person.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Person not found.'}, status=404)
    except Unit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
from django.views.decorators.http import require_POST
@require_POST
def ajax_reallocate_person(request):
    from django.utils import timezone
    person_id = request.POST.get('person_id')
    new_unit_id = request.POST.get('new_unit_id')
    if not person_id or not new_unit_id:
        return JsonResponse({'success': False, 'error': 'Missing person or unit.'}, status=400)
    try:
        person = Person.objects.get(id=person_id)
        new_unit = Unit.objects.get(id=new_unit_id)

        # End all current active occupancies for this person (preserve history)
        Occupancy.objects.filter(
            person=person,
            is_active=True,
            is_deleted=False,
            end_date__isnull=True
        ).update(is_active=False, end_date=timezone.now().date())

        # Check if person already has an occupancy in the new unit
        existing_occupancy = Occupancy.objects.filter(
            person=person,
            unit=new_unit,
            is_deleted=False
        ).first()
        AuditTrail.objects.create(
            person=person,
            unit=new_unit,
            action="move",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Moved {person} to unit {new_unit}"
        )
        if existing_occupancy:
            # Reactivate and clear end_date if needed
            existing_occupancy.end_date = None
            existing_occupancy.is_active = True
            existing_occupancy.save()
            return JsonResponse({'success': True})

        # Create new occupancy
        new_occ = Occupancy.objects.create(
            person=person,
            unit=new_unit,
            role='tenant',  # Default to tenant, can be extended
            start_date=timezone.now().date(),
            is_active=True,
            is_deleted=False
        )
        return JsonResponse({'success': True})
    except Person.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Person not found.'}, status=404)
    except Unit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from GateCore.models import Site, Property, Unit, Person, Vehicle, AccessPoint, AccessDevice, AccessCredential, AccessLog, GuestRegistration, ScheduleRule, AccessPermission, Blacklist, Occupancy
from django.views.decorators.http import require_POST
from django.http import JsonResponse

# GateCore people list
@login_required
def gatecore_people(request):
    qs = Person.objects.all()
    # Filtering by GET params
    name = request.GET.get('name', '').strip()
    gender = request.GET.get('gender', '').strip()
    id_number = request.GET.get('id_number', '').strip()
    phone = request.GET.get('phone', '').strip()
    email = request.GET.get('email', '').strip()
    tag = request.GET.get('tag', '').strip()
    unit = request.GET.get('unit', '').strip()
    address = request.GET.get('address', '').strip()
    if name:
        qs = qs.filter(first_name__icontains=name) | qs.filter(last_name__icontains=name)
    if gender:
        qs = qs.filter(gender=gender)
    if id_number:
        qs = qs.filter(id_number__icontains=id_number)
    if phone:
        qs = qs.filter(phone__icontains=phone)
    if email:
        qs = qs.filter(email__icontains=email)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    if unit:
        qs = qs.filter(occupancies__unit__unit_number__icontains=unit)
    if address:
        qs = qs.filter(occupancies__unit__property__address__icontains=address)
    people = qs.order_by('last_name', 'first_name').distinct()
    return render(request, "frontend/gatecore_people.html", {
        "people": people,
        "filter": {
            "name": name,
            "gender": gender,
            "id_number": id_number,
            "phone": phone,
            "email": email,
            "tag": tag,
            "unit": unit,
            "address": address,
        }
    })

# GateCore person detail
@login_required
def gatecore_person_detail(request, person_id):
    person = get_object_or_404(Person, id=person_id)
    occupancies = person.occupancies.select_related('unit').all()
    vehicles = person.vehicles.all()
    credentials = person.credentials.all()
    permissions = person.permissions.select_related('access_point', 'schedule_rule').all()
    access_logs = person.access_logs.select_related('access_point', 'device', 'credential').order_by('-timestamp')[:20]
    guest_registrations = person.guest_registrations.select_related('unit', 'host').all()
    hosted_guests = person.hosted_guests.select_related('unit', 'guest').all()
    blacklist_entries = person.blacklist_entries.all()
    # Audit trail for this person
    audit_trails = person.audit_trails.select_related('performed_by', 'unit').all()[:20]
    return render(request, "frontend/gatecore_person_detail.html", {
        "person": person,
        "occupancies": occupancies,
        "vehicles": vehicles,
        "credentials": credentials,
        "permissions": permissions,
        "access_logs": access_logs,
        "guest_registrations": guest_registrations,
        "hosted_guests": hosted_guests,
        "blacklist_entries": blacklist_entries,
        "audit_trails": audit_trails,
    })

# GateCore dashboard
@login_required
def gatecore_dashboard(request):
	context = {
		'sites_count': Site.objects.count(),
		'properties_count': Property.objects.count(),
		'units_count': Unit.objects.count(),
		'people_count': Person.objects.count(),
		'vehicles_count': Vehicle.objects.count(),
		'access_points_count': AccessPoint.objects.count(),
	}
	return render(request, "frontend/gatecore_dashboard.html", context)

# GateCore sites table
@login_required
def gatecore_sites(request):
	sites = Site.objects.all().order_by('name')
	return render(request, "frontend/gatecore_sites.html", {"sites": sites})

# GateCore site detail
@login_required
def gatecore_site_detail(request, site_id):
	site = get_object_or_404(Site, id=site_id)
	properties = Property.objects.filter(site=site).order_by('name')
	return render(request, "frontend/gatecore_site_detail.html", {"site": site, "properties": properties})

# GateCore vehicles list
@login_required
def gatecore_vehicles(request):
	vehicles = Vehicle.objects.select_related('person').all()
	return render(request, "frontend/gatecore_vehicles.html", {"vehicles": vehicles})

# GateCore vehicle detail
@login_required
def gatecore_vehicle_detail(request, vehicle_id):
	vehicle = get_object_or_404(Vehicle.objects.select_related('person'), id=vehicle_id)
	return render(request, "frontend/gatecore_vehicle_detail.html", {"vehicle": vehicle})

# GateCore access points list
@login_required
def gatecore_access_points(request):
    access_points = AccessPoint.objects.select_related('site').prefetch_related('devices').all()
    return render(request, "frontend/gatecore_access_points.html", {"access_points": access_points})

# GateCore access point detail
@login_required
def gatecore_access_point_detail(request, access_point_id):
    access_point = get_object_or_404(AccessPoint.objects.select_related('site').prefetch_related('devices'), id=access_point_id)
    return render(request, "frontend/gatecore_access_point_detail.html", {"access_point": access_point})

# GateCore access devices list
@login_required
def gatecore_access_devices(request):
    devices = AccessDevice.objects.select_related('access_point').all()
    return render(request, "frontend/gatecore_access_devices.html", {"devices": devices})

# GateCore access device detail
@login_required
def gatecore_access_device_detail(request, device_id):
    device = get_object_or_404(AccessDevice.objects.select_related('access_point'), id=device_id)
    return render(request, "frontend/gatecore_access_device_detail.html", {"device": device})

# GateCore access credentials list
@login_required
def gatecore_access_credentials(request):
    credentials = AccessCredential.objects.select_related('person').all()
    return render(request, "frontend/gatecore_access_credentials.html", {"credentials": credentials})

# GateCore access credential detail
@login_required
def gatecore_access_credential_detail(request, credential_id):
    credential = get_object_or_404(AccessCredential.objects.select_related('person'), id=credential_id)
    return render(request, "frontend/gatecore_access_credential_detail.html", {"credential": credential})

# GateCore access logs list
@login_required
def gatecore_access_logs(request):
    logs = AccessLog.objects.select_related('access_point', 'person', 'credential').all().order_by('-timestamp')[:200]
    return render(request, "frontend/gatecore_access_logs.html", {"logs": logs})

# GateCore access log detail
@login_required
def gatecore_access_log_detail(request, log_id):
    log = get_object_or_404(AccessLog.objects.select_related('access_point', 'person', 'credential'), id=log_id)
    return render(request, "frontend/gatecore_access_log_detail.html", {"log": log})

# GateCore guest registrations list
@login_required
def gatecore_guest_registrations(request):
    guests = GuestRegistration.objects.select_related('person', 'unit').all()
    return render(request, "frontend/gatecore_guest_registrations.html", {"guests": guests})

# GateCore guest registration detail
@login_required
def gatecore_guest_registration_detail(request, guest_id):
    guest = get_object_or_404(GuestRegistration.objects.select_related('person', 'unit'), id=guest_id)
    return render(request, "frontend/gatecore_guest_registration_detail.html", {"guest": guest})

# GateCore schedule rules list
@login_required
def gatecore_schedule_rules(request):
    rules = ScheduleRule.objects.all()
    return render(request, "frontend/gatecore_schedule_rules.html", {"rules": rules})

# GateCore schedule rule detail
@login_required
def gatecore_schedule_rule_detail(request, rule_id):
    rule = get_object_or_404(ScheduleRule, id=rule_id)
    return render(request, "frontend/gatecore_schedule_rule_detail.html", {"rule": rule})

# GateCore access permissions list
@login_required
def gatecore_access_permissions(request):
    permissions = AccessPermission.objects.select_related('person', 'access_point', 'credential', 'schedule_rule').all()
    return render(request, "frontend/gatecore_access_permissions.html", {"permissions": permissions})

# GateCore access permission detail
@login_required
def gatecore_access_permission_detail(request, perm_id):
    perm = get_object_or_404(AccessPermission.objects.select_related('person', 'access_point', 'credential', 'schedule_rule'), id=perm_id)
    return render(request, "frontend/gatecore_access_permission_detail.html", {"perm": perm})

# GateCore blacklist list
@login_required
def gatecore_blacklist(request):
    blacklist = Blacklist.objects.select_related('person').all()
    return render(request, "frontend/gatecore_blacklist.html", {"blacklist": blacklist})

# GateCore blacklist detail
@login_required
def gatecore_blacklist_detail(request, entry_id):
    entry = get_object_or_404(Blacklist.objects.select_related('person'), id=entry_id)
    return render(request, "frontend/gatecore_blacklist_detail.html", {"entry": entry})

# List all workflows (draft and created)
from workflows.models import Workflow
from django.utils import timezone

def workflow_list(request):
	workflows = Workflow.objects.all().order_by('-created_at')
	return render(request, "frontend/workflow_list.html", {"workflows": workflows, "now": timezone.now()})

@login_required
def frontend_index(request):
	"""Serve the main frontend builder page."""
	return render(request, "frontend/builder.html")

# Estate/Unit/Company People Overview (interactive)
@login_required
def gatecore_estate_people(request):
    units = Unit.objects.select_related('property__site').filter(property__site__site_type='estate').order_by('property__site__name', 'property__name', 'unit_code')
    # Only load people for first unit by default
    selected_unit_id = request.GET.get('unit')
    selected_unit = None
    people = []
    page_obj = None
    page_number = request.GET.get('page', 1)
    page_size = 10  # Default page size, can be made configurable
    if selected_unit_id:
        try:
            selected_unit = Unit.objects.get(id=selected_unit_id)
            people_qs = [occ.person for occ in selected_unit.occupancies.select_related('person').filter(is_active=True, is_deleted=False)]
        except Unit.DoesNotExist:
            selected_unit = None
            people_qs = []
    elif units:
        selected_unit = units[0]
        people_qs = [occ.person for occ in selected_unit.occupancies.select_related('person').filter(is_active=True, is_deleted=False)]
    else:
        people_qs = []

    # Paginate people_qs
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(people_qs, page_size)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    people = page_obj.object_list if page_obj else []

    return render(request, "frontend/gatecore_estate_people.html", {
        "units": units,
        "selected_unit": selected_unit,
        "people": people,
        "page_obj": page_obj,
        "paginator": paginator,
    })

@require_POST
def ajax_add_person(request):
    # Extract form data
    data = request.POST
    unit_id = request.GET.get('unit') or data.get('unit')
    unit = Unit.objects.get(id=unit_id)
    # Create Person
    from django.db import IntegrityError
    try:
        person = Person.objects.create(
            first_name=data.get('full_name', '').split(' ')[0],
            last_name=' '.join(data.get('full_name', '').split(' ')[1:]),
            id_number=data.get('id_number'),
            phone=data.get('phone'),
            phone_device_type=data.get('phone_device_type'),
            phone_otp=data.get('phone_otp'),
            facial_recognition_enabled=(data.get('facial_recognition_enabled') == 'Yes'),
            email=data.get('email'),
            date_of_birth=data.get('date_of_birth') or None,
            emergency_contact_name=data.get('emergency_contact', ''),
            tags=data.get('tags', '').split(',') if data.get('tags') else [],
        )
        AuditTrail.objects.create(
            person=person,
            action="create",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Created person {person} in unit {unit}"
        )
        # Add Occupancy (unit, role, start_date)
        from django.utils import timezone
        start_date = data.get('start_date')
        if not start_date or start_date == '':
            start_date = timezone.now().date()
        Occupancy.objects.create(
            person=person,
            unit=unit,
            role=data.get('role', 'tenant'),
            start_date=start_date,
        )
        return JsonResponse({'success': True, 'person_id': str(person.id)})
    except IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return JsonResponse({'success': False, 'error': 'ID Number must be unique.'}, status=400)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
def ajax_update_person(request, person_id):
    data = request.POST
    person = Person.objects.get(id=person_id)
    person.first_name = data.get('full_name', '').split(' ')[0]
    person.last_name = ' '.join(data.get('full_name', '').split(' ')[1:])
    person.id_number = data.get('id_number')
    person.phone = data.get('phone')
    person.phone_device_type = data.get('phone_device_type')
    person.phone_otp = data.get('phone_otp')
    person.facial_recognition_enabled = (data.get('facial_recognition_enabled') == 'Yes')
    person.email = data.get('email')
    dob = data.get('date_of_birth')
    if dob in [None, '', '-', '–']:
        person.date_of_birth = None
    else:
        person.date_of_birth = dob
    person.emergency_contact_name = data.get('emergency_contact', '')
    person.tags = data.get('tags', '').split(',') if data.get('tags') else []
    person.save()
    AuditTrail.objects.create(
        person=person,
        action="edit",
        performed_by=request.user if request.user.is_authenticated else None,
        details=f"Edited person {person}"
    )
    return JsonResponse({'success': True})
