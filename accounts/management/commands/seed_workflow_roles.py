from django.core.management.base import BaseCommand

from accounts.utils import ensure_workflow_role_groups


class Command(BaseCommand):
    help = "Create workflow role groups and assign the appropriate permissions."

    def handle(self, *args, **kwargs):
        ensure_workflow_role_groups(verbosity=self.verbosity, stdout=self.stdout)
