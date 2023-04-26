from unittest import mock

from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.core.distribution_packages import (
    DistributionPackage,
    compile_package_requirements,
    gather_distribution_packages,
)

from ..factories import (
    DistributionPackageFactory,
    MetadataDistributionStubFactory,
    make_packages,
)

MODULE_PATH = "package_monitor.core.distribution_packages"


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
