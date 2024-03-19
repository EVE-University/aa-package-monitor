"""Fetch data from PyPI."""

import asyncio
from typing import List, Optional

import aiohttp
from packaging.version import Version

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


async def fetch_data_from_pypi_async(
    session: aiohttp.ClientSession, name: str, version: str = None
) -> Optional[dict]:
    """Fetch data for a PyPI project or release and return it.

    Returns None if there was an API error.

    When the optional ``version`` is specified it will return the data
    for a specific release instead of the project data.
    """
    if not version:
        path = name
    else:
        path = f"{name}/{version}"
    url = f"https://pypi.org/pypi/{path}/json"
    logger.info("Fetching info for url: %s", url)

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


async def fetch_pypi_releases(
    session: aiohttp.ClientSession, name: str, releases: List[Version]
) -> dict:
    """Fetch and return data for releases of a pypi project."""
    tasks = [
        asyncio.create_task(fetch_data_from_pypi_async(session, name=name, version=r))
        for r in releases
    ]
    r = await asyncio.gather(*tasks)
    results = {o["info"]["version"]: o["info"] for o in r}
    return results
