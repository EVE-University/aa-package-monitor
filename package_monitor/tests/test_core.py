from collections import namedtuple
from unittest import mock

import requests_mock
from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.core import (
    DistributionPackage,
    _is_distribution_editable,
    compile_package_requirements,
    dist_metadata_value,
    gather_distribution_packages,
    update_packages_from_pypi,
)

from .factories import (
    DistributionPackageFactory,
    DjangoAppConfigStub,
    ImportlibDistributionStubFactory,
    PypiFactory,
    PypiReleaseFactory,
    make_packages,
)

MODULE_PATH = "package_monitor.core"

SysVersionInfo = namedtuple("SysVersionInfo", ["major", "minor", "micro"])


class TestDistributionPackage(NoSocketsTestCase):
    @mock.patch(MODULE_PATH + ".os.path.isfile", lambda *args, **kwargs: False)
    @mock.patch(MODULE_PATH + ".django_apps", spec=True)
    def test_should_create_from_importlib_distribution(self, mock_django_apps):
        # given
        dist = ImportlibDistributionStubFactory(
            name="Alpha",
            version="1.2.3",
            requires=["bravo>=1.0.0"],
            files=["alpha/__init__.py"],
            homepage_url="https://www.alpha.com",
        )
        mock_django_apps.get_app_configs.return_value = [
            DjangoAppConfigStub("alpha_app", "/alpha/__init__.py")
        ]
        # when
        obj = DistributionPackage.create_from_distribution(dist)
        # then
        self.assertEqual(obj.name, "Alpha")
        self.assertEqual(obj.name_normalized, "alpha")
        self.assertEqual(obj.current, "1.2.3")
        self.assertEqual(obj.latest, "")
        self.assertListEqual([str(x) for x in obj.requirements], ["bravo>=1.0.0"])
        self.assertEqual(obj.apps, ["alpha_app"])
        self.assertEqual(obj.homepage_url, "")

    def test_should_not_be_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest="1.0.0")
        # when/then
        self.assertFalse(obj.is_outdated())

    def test_should_be_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest="1.1.0")
        # when/then
        self.assertTrue(obj.is_outdated())

    def test_should_return_none_as_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest=None)
        # when/then
        self.assertIsNone(obj.is_outdated())


@mock.patch(MODULE_PATH + ".os.path.isfile")
class TestIsDistributionEditable(NoSocketsTestCase):
    def test_should_not_be_editable(self, mock_isfile):
        # given
        mock_isfile.return_value = False
        obj = ImportlibDistributionStubFactory(name="alpha")
        # when/then
        self.assertFalse(_is_distribution_editable(obj))

    def test_should_be_editable_old_version(self, mock_isfile):
        # given
        mock_isfile.return_value = True
        obj = ImportlibDistributionStubFactory(name="alpha")
        # when/then
        self.assertTrue(_is_distribution_editable(obj))

    def test_should_be_editable_pep660(self, mock_isfile):
        # given
        mock_isfile.return_value = False

        obj = ImportlibDistributionStubFactory(name="alpha")
        obj._files_content = {
            "direct_url.json": '{"dir_info": {"editable": true}, "url": "xxx"}'
        }
        # when/then
        self.assertTrue(_is_distribution_editable(obj))

    def test_should_not_be_editable_pep660(self, mock_isfile):
        # given
        mock_isfile.return_value = False

        obj = ImportlibDistributionStubFactory(name="alpha")
        obj._files_content = {
            "direct_url.json": '{"dir_info": {"editable": false}, "url": "xxx"}'
        }
        # when/then
        self.assertFalse(_is_distribution_editable(obj))


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


@mock.patch(MODULE_PATH + ".importlib_metadata.distributions", spec=True)
class TestFetchRelevantPackages(NoSocketsTestCase):
    def test_should_fetch_all_packages(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        distributions = lambda: iter([dist_alpha, dist_bravo])  # noqa: E731
        mock_distributions.side_effect = distributions
        # when
        result = gather_distribution_packages()
        # then
        self.assertSetEqual({"alpha", "bravo"}, set(result.keys()))


class TestCompilePackageRequirements(NoSocketsTestCase):
    def test_should_compile_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(name="charlie", requires=["123"])
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    # def test_should_ignore_python_version_requirements(self):
    #     # given
    #     dist_alpha = DistributionPackageFactory(name="alpha")
    #     dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
    #     dist_charlie = DistributionPackageFactory(
    #         name="charlie", requires=["alpha >= 1.0.0 ; python_version < 3.7"]
    #     )
    #     packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
    #     # when
    #     result = compile_package_requirements(packages)
    #     # then
    #     expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
    #     self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_extra_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(
            name="charlie", requires=['alpha>=1.0.0; extra == "certs"']
        )
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)


@requests_mock.Mocker()
class TestUpdatePackagesFromPyPi(NoSocketsTestCase):
    def test_should_update_packages(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.1.0")
        self.assertEqual(
            packages["alpha"].homepage_url, "https://pypi.org/project/alpha/"
        )

    def test_should_ignore_prereleases_when_stable(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0a1"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    def test_should_include_prereleases_when_prerelease(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0a1")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.0.0a2"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0a2")

    def test_should_set_latest_to_empty_string_on_network_error(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET",
            "https://pypi.org/pypi/alpha/json",
            status_code=500,
            reason="Test error",
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "")

    def test_should_ignore_yanked_releases(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(yanked=True)]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    @mock.patch(MODULE_PATH + ".sys")
    def test_should_ignore_releases_with_incompatible_python_requirement(
        self, requests_mocker, mock_sys
    ):
        # given
        mock_sys.version_info = SysVersionInfo(3, 6, 9)
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.7")]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    def test_should_ignore_invalid_release_version(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["a3"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    # TODO: This test breaks with packaging<22, which is currently required by Auth.

    # def test_should_ignore_invalid_python_release_spec(self, requests_mocker):
    #     # given
    #     dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
    #     packages = make_packages(dist_alpha)
    #     requirements = {}
    #     pypi_alpha = PypiFactory(distribution=dist_alpha)
    #     pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.4.*")]
    #     requests_mocker.register_uri(
    #         "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
    #     )
    #     # when
    #     update_packages_from_pypi(
    #         packages=packages, requirements=requirements, use_threads=False
    #     )
    #     # then
    #     self.assertEqual(packages["alpha"].latest, "1.0.0")


class TestDistMetadataValue(NoSocketsTestCase):
    def test_should_return_value_when_exists(self):
        # given
        dist = ImportlibDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(dist_metadata_value(dist, "Name"), "Alpha")

    def test_should_return_empty_string_when_prop_does_not_exist(self):
        # given
        dist = ImportlibDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(dist_metadata_value(dist, "XXX"), "")

    def test_should_return_name(self):
        # given
        dist = ImportlibDistributionStubFactory(name="Alpha")
        # when/then
        self.assertEqual(dist_metadata_value(dist, "Name"), "Alpha")

    def test_should_return_empty_string_when_value_is_undefined(self):
        # given
        dist = ImportlibDistributionStubFactory(homepage_url="")
        # when/then
        self.assertEqual(dist_metadata_value(dist, "Home-page"), "")

    def test_should_return_empty_string_when_value_is_none(self):
        # given
        dist = ImportlibDistributionStubFactory(homepage_url=None)
        # when/then
        self.assertEqual(dist_metadata_value(dist, "Home-page"), "")
