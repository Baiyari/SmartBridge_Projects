import asyncio
from collections import deque
from urllib.parse import urlparse

import aiohttp
import tldextract

from config.settings import settings
from utils.html_parser import extract_links, parse


class Crawler:
    def __init__(self, root: str):
        self._root = self._normalize_root(root)
        self._domain = tldextract.extract(self._root).registered_domain
        self._visited: set[str] = set()
        self._queue: deque[str] = deque([self._root])

    @staticmethod
    def _normalize_root(root: str) -> str:
        """
        Normalize a user-supplied target URL:
          - Strip trailing slashes/whitespace.
          - Fix common scheme typos (e.g. "ttps://" -> "https://", "tp://" -> "http://").
          - If no scheme is present at all, default to "https://".
          - Never double-prefix an already-valid http(s) URL.
        """
        root = root.strip().rstrip("/")
        if not root:
            raise ValueError("Target URL cannot be empty")

        parsed = urlparse(root)
        scheme = parsed.scheme.lower()

        if scheme in ("http", "https"):
            return root

        # Common typo'd schemes — missing a leading character
        scheme_fixes = {
            "ttps": "https",
            "ttp": "http",
            "tps": "https",
            "ps": "https",
        }
        if scheme in scheme_fixes:
            fixed_scheme = scheme_fixes[scheme]
            # parsed.path/netloc already hold everything after "scheme://"
            rest = root.split("://", 1)[1] if "://" in root else root
            return f"{fixed_scheme}://{rest}"

        # No recognizable scheme at all — treat the whole string as host/path
        if not scheme:
            return f"https://{root}"

        # Unknown scheme — fall back to https with the netloc/path portion
        rest = root.split("://", 1)[1] if "://" in root else root
        return f"https://{rest}"

    def _is_internal(self, url: str) -> bool:
        return tldextract.extract(url).registered_domain == self._domain

    def _clean(self, url: str) -> str:
        # Defensive fix for accidentally double-prefixed URLs, e.g.
        # "https://ttps://example.com" or "http://ttp://example.com"
        for bad, good in (("https://ttps://", "https://"), ("http://ttp://", "http://"),
                          ("https://ttp://", "https://"), ("http://ttps://", "https://")):
            if url.startswith(bad):
                url = good + url[len(bad):]
                break

        p = urlparse(url)
        return p._replace(fragment="", query="").geturl().rstrip("/")

    async def _fetch(self, session: aiohttp.ClientSession, url: str) -> tuple[int, str]:
        try:
            async with session.get(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=settings.crawl_timeout),
            ) as r:
                html = ""
                if r.content_type and "html" in r.content_type:
                    html = await r.text(errors="replace")
                return r.status, html
        except Exception:
            return 0, ""

    async def crawl(self) -> dict[str, tuple[int, str]]:
        pages: dict[str, tuple[int, str]] = {}
        headers = {"User-Agent": settings.user_agent}
        connector = aiohttp.TCPConnector(limit=settings.max_concurrent)

        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._queue and len(self._visited) < settings.max_pages:
                batch = []
                while self._queue and len(batch) < settings.max_concurrent:
                    url = self._clean(self._queue.popleft())
                    if url not in self._visited:
                        self._visited.add(url)
                        batch.append(url)

                for url, (status, html) in zip(batch, await asyncio.gather(*[self._fetch(session, u) for u in batch])):
                    pages[url] = (status, html)
                    if html and status == 200:
                        for link, _ in extract_links(parse(html), url):
                            clean = self._clean(link)
                            if self._is_internal(clean) and clean not in self._visited:
                                self._queue.append(clean)

        return pages