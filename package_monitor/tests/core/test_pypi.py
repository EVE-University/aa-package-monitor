from unittest import IsolatedAsyncioTestCase

import aiohttp
from aioresponses import aioresponses

from package_monitor.core.pypi import fetch_data_from_pypi_async


class TestFetchDataFromPypi(IsolatedAsyncioTestCase):
    @aioresponses()
    async def test_should_return_data(self, requests_mocker: aioresponses):
        # given
        requests_mocker.get("https://pypi.org/pypi/alpha/json", payload={"alpha": 1})
        # when
        async with aiohttp.ClientSession() as session:
            result = await fetch_data_from_pypi_async(session, "alpha")
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
            result = await fetch_data_from_pypi_async(session, "alpha")
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
            result = await fetch_data_from_pypi_async(session, "alpha")
        # then
        self.assertIsNone(result)
