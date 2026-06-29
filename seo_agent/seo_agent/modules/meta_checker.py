from bs4 import BeautifulSoup

from config.settings import settings
from utils.page_data import MetaIssues


def check_meta(soup: BeautifulSoup, seen_descriptions: set[str]) -> MetaIssues:
    m = MetaIssues()

    title_tag = soup.find("title")
    if not title_tag or not title_tag.get_text(strip=True):
        m.missing_title = True
    else:
        length = len(title_tag.get_text(strip=True))
        m.title_too_short = length < settings.title_min
        m.title_too_long = length > settings.title_max

    desc_tag = soup.find("meta", attrs={"name": "description"})
    if not desc_tag or not desc_tag.get("content", "").strip():
        m.missing_meta_desc = True
    else:
        content = desc_tag["content"].strip()
        if content in seen_descriptions:
            m.duplicate_meta_desc = True
        else:
            seen_descriptions.add(content)

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if not canonical:
        m.missing_canonical = True
    elif not canonical.get("href", "").strip().startswith("http"):
        m.malformed_canonical = True

    m.missing_og_title = not bool(soup.find("meta", attrs={"property": "og:title"}))
    m.missing_og_desc = not bool(soup.find("meta", attrs={"property": "og:description"}))
    m.missing_og_image = not bool(soup.find("meta", attrs={"property": "og:image"}))

    return m
