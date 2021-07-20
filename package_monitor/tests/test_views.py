import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils

from .. import views
from .testdata import create_testdata

MODULE_PATH_VIEWS = "package_monitor.views"
MODULE_PATH_MANAGERS = "package_monitor.managers"


@patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
@patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", None)
class TestPackageList(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_testdata()
        cls.user = AuthUtils.create_user("Bruce Wayne")
        AuthUtils.add_permission_to_user_by_name(
            "package_monitor.basic_access", cls.user
        )
        cls.user = User.objects.get(pk=cls.user.pk)

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_index_view(self):
        request = self.factory.get(reverse("package_monitor:index"))
        request.user = self.user
        response = views.index(request)
        self.assertEqual(response.status_code, 200)

    def test_list_view_all(self):
        request = self.factory.get(reverse("package_monitor:package_list_data"))
        request.user = self.user
        response = views.package_list_data(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content.decode("utf-8"))
        package_names = [x["name"] for x in data]
        self.assertListEqual(package_names, ["dummy-1", "dummy-2", "dummy-3"])

    def test_list_view_outdated(self):
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "outdated"}
        )
        request.user = self.user
        response = views.package_list_data(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content.decode("utf-8"))
        package_names = [x["name"] for x in data]
        self.assertListEqual(package_names, ["dummy-2"])

    def test_list_view_current(self):
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "current"}
        )
        request.user = self.user
        response = views.package_list_data(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content.decode("utf-8"))
        package_names = [x["name"] for x in data]
        self.assertListEqual(package_names, ["dummy-1"])

    def test_list_view_unknown(self):
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "unknown"}
        )
        request.user = self.user
        response = views.package_list_data(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content.decode("utf-8"))
        package_names = [x["name"] for x in data]
        self.assertListEqual(package_names, ["dummy-3"])

    @patch(MODULE_PATH_VIEWS + ".Distribution.objects.update_all")
    def test_refresh_distributions_view(self, mock_update_all):
        mock_update_all.return_value = 1

        request = self.factory.get(reverse("package_monitor:refresh_distributions"))
        request.user = self.user
        response = views.refresh_distributions(request)
        self.assertEqual(response.status_code, 200)
