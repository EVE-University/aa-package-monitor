from unittest import IsolatedAsyncioTestCase

import aiohttp
from aioresponses import aioresponses
from packaging.version import Version

from package_monitor.core.pypi import (
    clear_cache,
    fetch_project_from_pypi_async,
    fetch_pypi_releases,
    fetch_release_from_pypi_async,
)
from package_monitor.tests.factories import DistributionPackageFactory, PypiFactory


class TestFetchDataFromPypi(IsolatedAsyncioTestCase):
    @aioresponses()
    async def test_should_return_data(self, requests_mocker: aioresponses):
        # given
        requests_mocker.get("https://pypi.org/pypi/alpha/json", payload={"alpha": 1})
        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_project_from_pypi_async(session, "alpha")
        # then
        self.assertEqual(result, {"alpha": 1})

    @aioresponses()
    async def test_should_return_none_when_package_does_not_exist(
        self, requests_mocker: aioresponses
    ):
        # given
        requests_mocker.get("https://pypi.org/pypi/alpha/json", status=404)
        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_project_from_pypi_async(session, "alpha")
        # then
        self.assertIsNone(result)

    @aioresponses()
    async def test_should_return_none_on_other_http_errors(
        self, requests_mocker: aioresponses
    ):
        # given
        requests_mocker.get("https://pypi.org/pypi/alpha/json", status=500)
        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_project_from_pypi_async(session, "alpha")
        # then
        self.assertIsNone(result)


class TestFetchPypiReleases(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        clear_cache()

    @aioresponses()
    async def test_should_return_data(self, requests_mocker: aioresponses):
        # given
        dist_1 = DistributionPackageFactory(name="alpha", current="1.2.3")
        pypi_1 = PypiFactory(distribution=dist_1)
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/1.2.3/json", payload=pypi_1.asdict()
        )
        dist_2 = DistributionPackageFactory(name="alpha", current="1.2.5")
        pypi_2 = PypiFactory(distribution=dist_2)
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/1.2.5/json", payload=pypi_2.asdict()
        )
        versions = [Version("1.2.3"), Version("1.2.5")]

        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_pypi_releases(session, "alpha", versions)

        # then
        self.assertEqual(len(result), 2)
        p = result[0]
        self.assertEqual(p["info"]["name"], "alpha")
        self.assertEqual(p["info"]["version"], "1.2.3")
        p = result[1]
        self.assertEqual(p["info"]["name"], "alpha")
        self.assertEqual(p["info"]["version"], "1.2.5")


class TestFetchPypiRelease(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        clear_cache()

    @aioresponses()
    async def test_should_return_data(self, requests_mocker: aioresponses):
        # given
        dist = DistributionPackageFactory(name="alpha", current="1.2.3")
        pypi = PypiFactory(distribution=dist)
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/1.2.3/json", payload=pypi.asdict()
        )

        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_release_from_pypi_async(session, "alpha", "1.2.3")

        # then
        self.assertEqual(result["info"]["name"], "alpha")
        self.assertEqual(result["info"]["version"], "1.2.3")
        requests_mocker.assert_called_once()

    @aioresponses()
    async def test_should_use_cache(self, requests_mocker: aioresponses):
        # given
        dist = DistributionPackageFactory(name="alpha", current="1.2.3")
        pypi = PypiFactory(distribution=dist)
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/1.2.3/json", payload=pypi.asdict()
        )

        # when
        async with aiohttp.ClientSession() as session:
            await fetch_release_from_pypi_async(session, "alpha", "1.2.3")
            await fetch_release_from_pypi_async(session, "alpha", "1.2.3")
            result = await fetch_release_from_pypi_async(session, "alpha", "1.2.3")

        # then
        self.assertEqual(result["info"]["version"], "1.2.3")
        requests_mocker.assert_called_once()
