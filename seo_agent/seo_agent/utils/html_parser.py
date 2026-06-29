from urllib.parse import urljoin
from bs4 import BeautifulSoup


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_body_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def extract_links(soup: BeautifulSoup, base: str) -> list[tuple[str, str]]:
    links = []
    for tag in soup.find_all(["a", "link"], href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        links.append((urljoin(base, href), tag.name))
    for tag in soup.find_all("img", src=True):
        links.append((urljoin(base, tag["src"].strip()), "img"))
    return links
