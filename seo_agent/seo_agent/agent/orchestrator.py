import asyncio

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from modules.keyword_analyser import analyse_keywords
from modules.link_detector import detect_broken_links
from modules.llm_suggestions import generate_suggestions
from modules.meta_checker import check_meta
from modules.readability import score_readability
from utils.html_parser import extract_body_text, parse
from utils.page_data import PageResult

console = Console()


async def _analyse_page(
    url: str,
    status: int,
    html: str,
    seen_descriptions: set[str],
) -> PageResult:
    soup = parse(html)
    text = extract_body_text(soup)
    title = soup.find("title")
    title_str = title.get_text(strip=True) if title else ""

    meta, keywords, readability, broken_links = await asyncio.gather(
        asyncio.to_thread(check_meta, soup, seen_descriptions),
        asyncio.to_thread(analyse_keywords, text),
        asyncio.to_thread(score_readability, text),
        detect_broken_links(html, url),
    )

    result = PageResult(
        url=url,
        status_code=status,
        title=title_str,
        meta=meta,
        keywords=keywords,
        readability=readability,
        broken_links=broken_links,
    )
    result.compute_score()
    result.suggestions = await asyncio.to_thread(generate_suggestions, result)
    return result


async def run_audit(pages: dict[str, tuple[int, str]]) -> list[PageResult]:
    seen_descriptions: set[str] = set()
    sem = asyncio.Semaphore(10)

    async def bounded(url: str, status: int, html: str) -> PageResult:
        async with sem:
            return await _analyse_page(url, status, html, seen_descriptions)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task(f"Analysing {len(pages)} pages...", total=len(pages))
        tasks = [bounded(url, s, h) for url, (s, h) in pages.items()]

        results = []
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)
            progress.advance(task)

    return results
