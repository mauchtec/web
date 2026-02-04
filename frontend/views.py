
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from GateCore.models import Site, Property, Unit, Person, Vehicle, AccessPoint, AccessDevice, AccessCredential, AccessLog, GuestRegistration, ScheduleRule, AccessPermission, Blacklist

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
