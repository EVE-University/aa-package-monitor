"""Fetch data from PyPI."""

import asyncio
from typing import List, Optional

import aiohttp
from packaging.version import Version

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

BASE_URL = "https://pypi.org/pypi"


async def fetch_pypi_releases(
    session: aiohttp.ClientSession, name: str, releases: List[Version]
) -> List[dict]:
    """Fetch and return data for releases of a pypi project."""
    tasks = [
        asyncio.create_task(
            _fetch_data_from_pypi_async(
                session, _make_pypi_url(name=name, version=str(r))
            )
        )
        for r in releases
    ]
    r = await asyncio.gather(*tasks)
    return r


async def fetch_data_from_pypi_async(
    session: aiohttp.ClientSession, name: str
) -> Optional[dict]:
    """Fetch JSON data for a URL and return it.

    Returns None if there was an API error.
    """
    return await _fetch_data_from_pypi_async(session, _make_pypi_url(name))


def _make_pypi_url(name: str, version: Optional[str] = None) -> str:
    if not version:
        return f"{BASE_URL}/{name}/json"
    return f"{BASE_URL}/{name}/{version}/json"


async def _fetch_data_from_pypi_async(
    session: aiohttp.ClientSession, url: str
) -> Optional[dict]:
    """Fetch JSON data for a URL and return it.

    Returns None if there was an API error.
    """
    logger.info("Fetching data from PyPI for url: %s", url)

    async with session.get(url) as resp:
        if not resp.ok:
            if resp.status == 404:
                logger.info("PyPI URL not found: %s", url)
            else:
                logger.warning(
                    "Failed to retrieve data from PyPI for "
                    "url '%s'. "
                    "Status code: %d, "
                    "response: %s",
                    url,
                    resp.status,
                    await resp.text(),
                )
            return None

        pypi_data = await resp.json()
        return pypi_data
