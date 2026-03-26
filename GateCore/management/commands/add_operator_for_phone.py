"""
One-off: Add Django Operator group to the user linked to a person with this phone.
Use after adding their unit to Security, so they get workflow access without re-login.

  python manage.py add_operator_for_phone 0656231093
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as AuthGroup

from GateCore.models import Person
from GateCore.services.mobile_auth import normalize_phone, phone_numbers_equal

User = get_user_model()


class Command(BaseCommand):
    help = "Add Operator group to the user for the person with the given phone number."

    def add_arguments(self, parser):
        parser.add_argument("phone", type=str, help="Phone number (e.g. 0656231093 or +27...)")

    def handle(self, *args, **options):
        raw = (options["phone"] or "").strip()
        if not raw:
            self.stdout.write(self.style.ERROR("Provide a phone number."))
            return
        normalized = normalize_phone(raw)
        if not normalized:
            self.stdout.write(self.style.ERROR("Could not normalize phone: %s" % raw))
            return
        persons = [p for p in Person.objects.filter(is_active=True, is_deleted=False)
                   if phone_numbers_equal(p.phone, normalized)]
        if not persons:
            self.stdout.write(self.style.ERROR("No person found with phone: %s" % raw))
            return
        person = persons[0]
        if not person.user_id:
            self.stdout.write(self.style.WARNING(
                "Person %s has no linked user. They must log in once (OTP) to create a user, then run this again."
                % person.phone
            ))
            return
        operator_group, _ = AuthGroup.objects.get_or_create(name="Operator")
        user = person.user
        if user.groups.filter(name="Operator").exists():
            self.stdout.write(self.style.SUCCESS("User for %s already has Operator." % person.phone))
            return
        user.groups.add(operator_group)
        self.stdout.write(self.style.SUCCESS("Added Operator to user for %s (%s). Workflow access should work now." % (person.full_name, person.phone)))
