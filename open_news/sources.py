import asyncio
import re
from time import perf_counter
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import httpx
from lxml.html import fromstring

from .utils import date_from_url, get_user_agent, parse_datetime

_SOURCES = (
    ("https://news.so.com/ns", "q", {"src": "srp"}, "pn", 4, False),
    ("https://www.so.com/s", "q", {}, "pn", 4, True),
    ("https://www.sogou.com/web", "query", {}, None, 1, True),
    ("https://news.sogou.com/news", "query", {}, None, 1, True),
    ("https://weixin.sogou.com/weixin", "query", {"type": "2"}, "page", 5, True),
)


def _record(metrics, stage, source, elapsed):
    if metrics is not None:
        metrics.put((stage, source, elapsed))


async def search_news(
    query: str,
    limit: int,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    metrics=None,
) -> List[Dict]:
    results = await asyncio.gather(
        *[
            _search_source(query, limit, *source, client, semaphore, metrics)
            for source in _SOURCES
        ],
        return_exceptions=True,
    )
    return [
        article
        for result in results
        if not isinstance(result, Exception)
        for article in result
    ]


async def _search_source(
    query: str,
    limit: int,
    url: str,
    query_key: str,
    extra_params: Dict,
    page_key,
    pages: int,
    resolve_links: bool,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    metrics=None,
) -> List[Dict]:
    started = perf_counter()
    source = urlparse(url).netloc + urlparse(url).path

    async def fetch_page(page):
        params = {**extra_params, query_key: query}
        if page_key:
            params[page_key] = page
        t = perf_counter()
        try:
            async with semaphore:
                response = await client.get(url, params=params)
            response.raise_for_status()
        finally:
            _record(metrics, "page_request", source, perf_counter() - t)
        if "antispider" in str(response.url):
            return page, [], True
        parser = parse_link_page if resolve_links else parse_search_page
        t = perf_counter()
        try:
            articles = parser(response.text, limit)
        finally:
            _record(metrics, "parse", source, perf_counter() - t)
        return page, articles, False

    try:
        page_results = await asyncio.gather(
            *(fetch_page(page) for page in range(1, pages + 1)),
            return_exceptions=True,
        )
        results = []
        for _, page_articles, stop in sorted(
            (result for result in page_results if not isinstance(result, Exception)),
            key=lambda result: result[0],
        ):
            results.extend(page_articles)
            if stop:
                break
        return results
    finally:
        _record(metrics, "source_total", source, perf_counter() - started)


def _finalize_results(results: List[Dict], urls: List[str]) -> List[Dict]:
    articles = []
    for result, url in zip(results, urls):
        if not url:
            continue
        result["url"] = url
        result["source"] = result["source"] or urlparse(url).netloc.replace("www.", "")
        result["published"] = date_from_url(url) or result["published"]
        articles.append(result)
    return articles


async def _resolve_redirect_url(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    metrics=None,
    source="-",
) -> str:
    t = perf_counter()
    try:
        target = urljoin("https://www.sogou.com", url)
        if not target.startswith(("http://", "https://")) or target.startswith(
            "javascript:"
        ):
            return ""
        if not any(host in target for host in ("sogou.com/link", "so.com/link")):
            return target
        if "so.com/link" in target:
            referer = "https://www.so.com/"
        elif "weixin.sogou.com" in target:
            referer = "https://weixin.sogou.com/"
        else:
            referer = "https://www.sogou.com/"
        try:
            async with semaphore:
                response = await client.get(target, headers={"Referer": referer})
            response.raise_for_status()
        except httpx.HTTPError:
            return ""
        parts = re.findall(r"url \+= '([^']*)'", response.text)
        if parts:
            return "".join(parts)
        match = re.search(r'window\.location\.replace\("([^"]+)"\)', response.text)
        if not match:
            match = re.search(r"URL='([^']+)'", response.text)
        return match.group(1) if match else ""
    finally:
        _record(metrics, "redirect", source, perf_counter() - t)


def parse_link_page(html: str, limit: int) -> List[Dict]:
    document = fromstring(html)
    articles = []
    seen = set()
    for link in document.xpath("//h3/a[@href]"):
        title = " ".join(link.text_content().split())
        url = link.get("href", "")
        if not title or not url or url.startswith("javascript:") or url in seen:
            continue
        containers = link.xpath(
            "ancestor::div[contains(@class, 'vrwrap')][1] | ancestor::li[1]"
        )
        container = containers[0] if containers else link.getparent()
        text = " ".join(container.text_content().split())
        dates = re.findall(
            r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})",
            text,
        )
        published = None
        if dates:
            year, month, day = dates[-1]
            published = parse_datetime(f"{year}-{month}-{day}")
        source = " ".join("".join(container.xpath(".//cite//text()")).split())
        description = " ".join(
            " ".join(
                paragraph.text_content()
                for paragraph in container.xpath(".//p[not(contains(@class, 'info'))]")
            ).split()
        )
        seen.add(url)
        articles.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "published": published.isoformat() if published else None,
                "description": description[:500],
            }
        )
        if len(articles) >= limit:
            break
    return articles


def parse_search_page(html: str, limit: int) -> List[Dict]:
    document = fromstring(html)
    articles = []
    seen = set()
    for result in document.xpath(
        "//li[contains(concat(' ', normalize-space(@class), ' '), ' res-list ')]"
    ):
        links = result.xpath(".//a[@href]")
        if not links:
            continue
        title = links[0].get("title") or " ".join(links[0].xpath(".//h3//text()"))
        title = " ".join(title.split())
        url = links[0].get("href", "")
        if not title or not url.startswith("http") or url in seen:
            continue
        snippet = " ".join(
            " ".join(
                paragraph.text_content()
                for paragraph in result.xpath(".//p[not(contains(@class, 'info'))]")
            ).split()
        )
        source = " ".join("".join(result.xpath(".//cite//text()")).split())
        published = parse_datetime(
            "".join(result.xpath(".//span[contains(@class, 'time')]//text()"))
        )
        seen.add(url)
        articles.append(
            {
                "title": title,
                "url": url,
                "source": source or urlparse(url).netloc.replace("www.", ""),
                "published": published.isoformat() if published else date_from_url(url),
                "description": snippet[:500],
            }
        )
        if len(articles) >= limit:
            break
    return articles
