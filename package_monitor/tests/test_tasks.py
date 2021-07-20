from unittest.mock import patch

from django.test import TestCase

from .. import tasks


class TestTasks(TestCase):
    @patch("package_monitor.tasks.Distribution.objects.update_all")
    def test_shoud_update_all_distributions(self, update_all):
        # when
        tasks.update_distributions()
        # then
        self.assertTrue(update_all.called)
