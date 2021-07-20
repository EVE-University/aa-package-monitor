from django.utils.translation import ugettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from package_monitor.models import Distribution

from . import __title__, urls


class PackageMonitorMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _(__title__),
            "fas fa-code-branch fa-fw",
            "package_monitor:index",
            navactive=["package_monitor:"],
        )

    def render(self, request):
        if request.user.has_perm("package_monitor.basic_access"):
            app_count = Distribution.objects.currently_selected().outdated_count()
            self.count = app_count if app_count and app_count > 0 else None
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return PackageMonitorMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "package_monitor", r"^package_monitor/")
