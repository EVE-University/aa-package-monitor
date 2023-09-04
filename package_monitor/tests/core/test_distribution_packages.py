from collections import namedtuple
from unittest import IsolatedAsyncioTestCase, mock

import aiohttp
from aioresponses import aioresponses
from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.core.distribution_packages import (
    DistributionPackage,
    compile_package_requirements,
    gather_distribution_packages,
)
from package_monitor.tests.factories import (
    DistributionPackageFactory,
    MetadataDistributionStubFactory,
    PypiFactory,
    PypiReleaseFactory,
    make_packages,
)

MODULE_PATH = "package_monitor.core.distribution_packages"


SysVersionInfo = namedtuple("SysVersionInfo", ["major", "minor", "micro"])


class TestDistributionPackage(NoSocketsTestCase):
    @mock.patch(
        MODULE_PATH + ".metadata_helpers.identify_installed_django_apps", spec=True
    )
    def test_should_create_from_importlib_distribution(self, mock_identify_django_apps):
        # given
        dist = MetadataDistributionStubFactory(
            name="Alpha",
            version="1.2.3",
            requires=["bravo>=1.0.0"],
            files=["alpha/__init__.py"],
            homepage_url="https://www.alpha.com",
        )
        mock_identify_django_apps.return_value = ["alpha_app"]
        # when
        obj = DistributionPackage.create_from_metadata_distribution(dist)
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

    def test_should_have_str(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest=None)
        # when/then
        self.assertIsInstance(str(obj), str)

    def test_should_detect_as_prerelease(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0a1")
        # when/then
        self.assertTrue(obj.is_prerelease())

    def test_should_detect_not_as_prerelease(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0")
        # when/then
        self.assertFalse(obj.is_prerelease())


@mock.patch(MODULE_PATH + ".importlib_metadata.distributions", spec=True)
class TestFetchRelevantPackages(NoSocketsTestCase):
    def test_should_fetch_all_packages(self, mock_distributions):
        # given
        dist_alpha = MetadataDistributionStubFactory(name="alpha")
        dist_bravo = MetadataDistributionStubFactory(
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
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_include_requirements_from_settings(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        with mock.patch(
            MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", ["alpha>2"]
        ):
            result = compile_package_requirements(packages)
        # then
        expected = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0"), "CUSTOM": SpecifierSet(">2")}
        }
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements_in_setting(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        with mock.patch(
            MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", ["alpha>2", "x!"]
        ):
            result = compile_package_requirements(packages)
        # then
        expected = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0"), "CUSTOM": SpecifierSet(">2")}
        }
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(name="charlie", requires=["123"])
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_python_version_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(
            name="charlie", requires=['alpha >= 1.0.0 ; python_version < "3.7"']
        )
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_extra_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(
            name="charlie", requires=['alpha>=1.0.0; extra == "certs"']
        )
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)


@mock.patch(MODULE_PATH + ".DistributionPackage._fetch_data_from_pypi_async")
class TestUpdatePackagesFromPyPi(IsolatedAsyncioTestCase):
    async def test_should_update_packages(self, mock_fetch_data_from_pypi_async):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.1.0")
        self.assertEqual(dist_alpha.homepage_url, "https://pypi.org/project/alpha/")

    async def test_should_ignore_prereleases_when_stable(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0a1"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_include_prereleases_when_prerelease(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0a1")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.0.0a2"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.0.0a2")

    async def test_should_not_update_package_on_network_error(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = None
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(dist_alpha.latest, "")

    async def test_should_ignore_yanked_releases(self, mock_fetch_data_from_pypi_async):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(yanked=True)]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_releases_with_incompatible_python_requirement(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.7")]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        with mock.patch(MODULE_PATH + ".sys") as mock_sys:
            mock_sys.version_info = SysVersionInfo(3, 6, 9)
            await dist_alpha.update_from_pypi_async(
                requirements=requirements, session=mock.MagicMock()
            )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_invalid_release_version(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["a3"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_releases_not_matching_consolidated_requirements(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"alpha": {"bravo": SpecifierSet("<=1.0.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_invalid_python_release_spec(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.4.*")]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            requirements=requirements, session=mock.MagicMock()
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")


class TestFetchDataFromPypi(IsolatedAsyncioTestCase):
    @aioresponses()
    async def test_should_return_data(self, requests_mocker: aioresponses):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.get("https://pypi.org/pypi/alpha/json", payload={"alpha": 1})
        # when
        async with aiohttp.ClientSession() as session:
            result = await obj._fetch_data_from_pypi_async(session)
        # then
        self.assertEqual(result, {"alpha": 1})

    @aioresponses()
    async def test_should_return_none_when_package_does_not_exist(
        self, requests_mocker: aioresponses
    ):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.get("https://pypi.org/pypi/alpha/json", status=404)
        # when
        async with aiohttp.ClientSession() as session:
            result = await obj._fetch_data_from_pypi_async(session)
        # then
        self.assertIsNone(result)

    @aioresponses()
    async def test_should_return_none_on_other_http_errors(
        self, requests_mocker: aioresponses
    ):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.get("https://pypi.org/pypi/alpha/json", status=500)
        # when
        async with aiohttp.ClientSession() as session:
            result = await obj._fetch_data_from_pypi_async(session)
        # then
        self.assertIsNone(result)
