from django.utils.translation import ugettext_lazy as _

from allianceauth.services.hooks import MenuItemHook, UrlHook
from allianceauth import hooks

from . import urls


class AppMonitorMenuItem(MenuItemHook):
    """ This class ensures only authorized users will see the menu entry """

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Installed Packages"),
            "fas fa-code-branch fa-fw",
            "app_monitor:index",
            navactive=["app_monitor:index"],
        )

    def render(self, request):
        if request.user.has_perm("app_monitor.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return AppMonitorMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "app_monitor", r"^app_monitor/")
