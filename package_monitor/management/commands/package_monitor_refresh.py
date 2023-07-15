"""Commands for Package Monitor."""

from django.core.management.base import BaseCommand

from package_monitor import __title__, __version__
from package_monitor.models import Distribution


class Command(BaseCommand):
    help = "Refreshes all data about distribution packages"

    def handle(self, *args, **options):
        self.stdout.write(f"*** {__title__} v{__version__} - Refresh Distributions ***")
        package_count = Distribution.objects.count()
        outdated_count = Distribution.objects.filter_visible().outdated_count()
        self.stdout.write(
            f"Started to refresh data for currently {package_count} distribution packages. "
            f"With {outdated_count} package(s) currently showing as outdated."
        )
        self.stdout.write("This can take a minute...Please wait")
        package_count = Distribution.objects.update_all()
        outdated_count = Distribution.objects.filter_visible().outdated_count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed refreshing data for {package_count} distribution packages. "
                f"Identified {outdated_count} outdated package(s)."
            )
        )
