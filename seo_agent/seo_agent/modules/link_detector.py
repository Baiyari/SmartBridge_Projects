import asyncio

import aiohttp

from config.settings import settings
from utils.html_parser import extract_links, parse
from utils.page_data import BrokenLink


async def _check(session: aiohttp.ClientSession, url: str, element: str) -> BrokenLink | None:
    try:
        async with session.head(
            url,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=settings.link_timeout),
            max_redirects=settings.max_redirects,
        ) as r:
            if r.status >= 400:
                return BrokenLink(url=url, element=element, status_code=r.status)
    except aiohttp.TooManyRedirects:
        return BrokenLink(url=url, element=element, error="too_many_redirects")
    except Exception as exc:
        return BrokenLink(url=url, element=element, error=str(exc)[:80])
    return None


async def detect_broken_links(html: str, page_url: str) -> list[BrokenLink]:
    links = extract_links(parse(html), page_url)
    connector = aiohttp.TCPConnector(limit=settings.max_concurrent)
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": settings.user_agent}) as session:
        results = await asyncio.gather(*[_check(session, url, el) for url, el in links])
    return [r for r in results if r is not None]
