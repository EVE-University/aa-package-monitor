from unittest import mock

from app_utils.testing import NoSocketsTestCase

from package_monitor.core.metadata_helpers import (
    _extract_files,
    is_distribution_editable,
    metadata_value,
)

from ..factories import MetadataDistributionStubFactory

MODULE_PATH = "package_monitor.core.metadata_helpers"


@mock.patch(MODULE_PATH + ".os.path.isfile")
class TestIsDistributionEditable(NoSocketsTestCase):
    def test_should_not_be_editable(self, mock_isfile):
        # given
        mock_isfile.return_value = False
        obj = MetadataDistributionStubFactory(name="alpha")
        # when/then
        self.assertFalse(is_distribution_editable(obj))

    def test_should_be_editable_old_version(self, mock_isfile):
        # given
        mock_isfile.return_value = True
        obj = MetadataDistributionStubFactory(name="alpha")
        # when/then
        self.assertTrue(is_distribution_editable(obj))

    def test_should_be_editable_pep660(self, mock_isfile):
        # given
        mock_isfile.return_value = False

        obj = MetadataDistributionStubFactory(name="alpha")
        obj._files_content = {
            "direct_url.json": '{"dir_info": {"editable": true}, "url": "xxx"}'
        }
        # when/then
        self.assertTrue(is_distribution_editable(obj))

    def test_should_not_be_editable_pep660(self, mock_isfile):
        # given
        mock_isfile.return_value = False

        obj = MetadataDistributionStubFactory(name="alpha")
        obj._files_content = {
            "direct_url.json": '{"dir_info": {"editable": false}, "url": "xxx"}'
        }
        # when/then
        self.assertFalse(is_distribution_editable(obj))


class TestExtractFiles(NoSocketsTestCase):
    def test_should_return_empty_list_when_no_files_match(self):
        # given
        dist = MetadataDistributionStubFactory()
        # when/then
        self.assertListEqual(_extract_files(dist, "__init__.py"), [])

    def test_should_return_matching_files(self):
        # given
        dist = MetadataDistributionStubFactory(
            files=["/alpha/xx.py", "/bravo/green/__init__.py", "/charlie/yy.py"]
        )
        # when/then
        self.assertListEqual(
            _extract_files(dist, "__init__.py"), ["/bravo/green/__init__.py"]
        )


# class TestDetermineHomePageUrl(NoSocketsTestCase):
#     def test_should_identify_homepage_old_style(self):
#         # given
#         dist = ImportlibDistributionStubFactory(homepage_url="my-homepage-url")
#         # when
#         url = _determine_homepage_url(dist)
#         # then
#         self.assertEqual(url, "my-homepage-url")

#     def test_should_identify_homepage_pep_621_style(self):
#         # given
#         dist = ImportlibDistributionStubFactory(homepage_url="")
#         for v in [
#             "Documentation, other-url",
#             "Homepage, my-homepage-url",
#             "Issues, other-url",
#         ]:
#             dist.metadata["Project-URL"] = v
#         # when
#         url = _determine_homepage_url(dist)
#         # then
#         self.assertEqual(url, "my-homepage-url")

#     def test_should_identify_homepage_pep_621_style_other_case(self):
#         # given
#         dist = ImportlibDistributionStubFactory(homepage_url="")
#         for v in [
#             "Documentation, other-url",
#             "homepage, my-homepage-url",
#             "Issues, other-url",
#         ]:
#             dist.metadata["Project-URL"] = v
#         # when
#         url = _determine_homepage_url(dist)
#         # then
#         self.assertEqual(url, "my-homepage-url")

#     def test_should_return_empty_string_when_no_url_found_with_pep_621(self):
#         # given
#         dist = ImportlibDistributionStubFactory(homepage_url="")
#         for v in ["Documentation, other-url", "Issues, other-url"]:
#             dist.metadata["Project-URL"] = v
#         # when
#         url = _determine_homepage_url(dist)
#         # then
#         self.assertEqual(url, "")


class TestDistMetadataValue(NoSocketsTestCase):
    def test_should_return_value_when_exists(self):
        # given
        dist = MetadataDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(metadata_value(dist, "Name"), "Alpha")

    def test_should_return_empty_string_when_prop_does_not_exist(self):
        # given
        dist = MetadataDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(metadata_value(dist, "XXX"), "")

    def test_should_return_name(self):
        # given
        dist = MetadataDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(metadata_value(dist, "Name"), "Alpha")

    def test_should_return_empty_string_when_value_is_undefined(self):
        # given
        dist = MetadataDistributionStubFactory(homepage_url="")
        # when/then
        self.assertEqual(metadata_value(dist, "Home-page"), "")

    def test_should_return_empty_string_when_value_is_none(self):
        # given
        dist = MetadataDistributionStubFactory(homepage_url=None)
        # when/then
        self.assertEqual(metadata_value(dist, "Home-page"), "")
