import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from agent.orchestrator import run_audit
from modules.crawler import Crawler
from utils.sheets_writer import write_results

console = Console()


def _summary_table(results) -> None:
    table = Table(title="SEO Audit Report", show_lines=True, expand=True)
    table.add_column("URL", style="cyan", max_width=55, no_wrap=False)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Meta Issues", justify="right", width=12)
    table.add_column("Broken Links", justify="right", width=13)
    table.add_column("Readability", width=16)

    for r in sorted(results, key=lambda x: x.score):
        color = "green" if r.score >= 75 else ("yellow" if r.score >= 50 else "red")
        table.add_row(
            r.url,
            f"[{color}]{r.score}[/{color}]",
            str(r.meta.count()),
            str(len(r.broken_links)),
            r.readability.grade_label or "n/a",
        )

    console.print(table)
    avg = sum(r.score for r in results) / len(results) if results else 0
    console.print(f"\n[bold]Pages audited:[/bold] {len(results)}   [bold]Average score:[/bold] {avg:.1f} / 100\n")


async def main(url: str, sheet_id: str | None) -> None:
    console.rule("[bold cyan]SEO Audit Agent")
    console.print(f"Target: [white]{url}[/white]\n")

    console.print("[dim]Crawling website...[/dim]")
    pages = await Crawler(url).crawl()
    console.print(f"[dim]Found {len(pages)} pages[/dim]\n")

    results = await run_audit(pages)
    _summary_table(results)

    if sheet_id:
        console.print("[dim]Writing report to Google Sheets...[/dim]")
        await asyncio.to_thread(write_results, sheet_id, results)
        console.print("[green]Done.[/green]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Website SEO Auditing Agent")
    parser.add_argument("--url", required=True, help="Target website URL")
    parser.add_argument("--sheet-id", default=None, help="Google Sheets document ID")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.url, args.sheet_id))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
