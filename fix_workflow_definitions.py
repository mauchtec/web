
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AccessControll.settings')
django.setup()

from workflows.models import Workflow

def fix_workflow_definitions():
    fixed = 0
    for wf in Workflow.objects.all():
        definition = wf.definition
        # If definition is not a dict or doesn't have 'components', fix it
        if not isinstance(definition, dict) or 'components' not in definition:
            # If it's a list, wrap it
            if isinstance(definition, list):
                wf.definition = {'components': definition}
                wf.save()
                fixed += 1
            # If it's something else, skip
            else:
                continue
    print(f"Fixed {fixed} workflows.")

if __name__ == '__main__':
    fix_workflow_definitions()
