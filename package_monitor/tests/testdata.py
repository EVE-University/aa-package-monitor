import json

from ..models import Distribution


def create_testdata():
    Distribution.objects.all().delete()
    Distribution.objects.create(
        name="dummy-2",
        apps=json.dumps([]),
        installed_version="0.1.0",
        latest_version="0.2.0",
        is_outdated=True,
    )
    Distribution.objects.create(
        name="dummy-3", apps=json.dumps([]), installed_version="0.1.0"
    )
    Distribution.objects.create(
        name="dummy-1",
        apps=json.dumps(["app_1"]),
        installed_version="0.1.0",
        latest_version="0.1.0",
        is_outdated=False,
    )
