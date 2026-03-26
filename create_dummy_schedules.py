# Script to create dummy ScheduleRule data for testing UI
from faker import Faker
from GateCore.models import ScheduleRule
from django.utils import timezone
import random

fake = Faker()

SCHEDULE_TYPES = [x[0] for x in ScheduleRule.SCHEDULE_TYPES]

def create_dummy_schedules(n=10):
    for _ in range(n):
        name = fake.unique.company()[:100]
        schedule_type = random.choice(SCHEDULE_TYPES)
        start_time = fake.time(pattern="%H:%M")
        end_time = fake.time(pattern="%H:%M")
        # Ensure start_time < end_time
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        days = {day: random.choice([True, False]) for day in [
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}
        valid_from = fake.date_this_decade()
        valid_until = fake.date_between(start_date=valid_from, end_date='+1y') if random.choice([True, False]) else None
        exclude_holidays = random.choice([True, False])
        ScheduleRule.objects.create(
            name=name,
            schedule_type=schedule_type,
            start_time=start_time,
            end_time=end_time,
            valid_from=valid_from,
            valid_until=valid_until,
            exclude_holidays=exclude_holidays,
            **days
        )
    print("Dummy schedule rules created.")

if __name__ == "__main__":
    create_dummy_schedules(10)
