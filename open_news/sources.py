import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import httpx
from lxml.html import fromstring

from .utils import date_from_url, get_user_agent, parse_datetime


def search_news(query: str, limit: int = 20) -> List[Dict]:
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [
            pool.submit(search_source, query, limit)
            for search_source in (
                _search_360,
                _search_360_web,
                _search_sogou,
                _search_sogou_news,
                _search_weixin,
            )
        ]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception:
                continue
    return [
        article
        for result in results
        for article in result
    ]


def _search_360(query: str, limit: int) -> List[Dict]:
    articles = []
    with httpx.Client(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
    ) as client:
        for page in (1, 2, 3, 4):
            response = client.get(
                "https://news.so.com/ns",
                params={"q": query, "src": "srp", "pn": page},
            )
            response.raise_for_status()
            if "antispider" in str(response.url):
                break
            articles.extend(parse_search_page(response.text, limit))
    return articles


def _search_sogou(query: str, limit: int) -> List[Dict]:
    with httpx.Client(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
    ) as client:
        response = client.get(
            "https://www.sogou.com/web",
            params={"query": query},
        )
        response.raise_for_status()
        results = parse_link_page(response.text, limit)
        with ThreadPoolExecutor(max_workers=8) as pool:
            urls = list(pool.map(
                lambda result: _resolve_redirect_url(client, result["url"]),
                results,
            ))
    return _finalize_results(results, urls)


def _search_sogou_news(query: str, limit: int) -> List[Dict]:
    with httpx.Client(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
    ) as client:
        response = client.get(
            "https://news.sogou.com/news",
            params={"query": query},
        )
        response.raise_for_status()
        results = parse_link_page(response.text, limit)
        with ThreadPoolExecutor(max_workers=8) as pool:
            urls = list(pool.map(
                lambda result: _resolve_redirect_url(client, result["url"]),
                results,
            ))
    return _finalize_results(results, urls)


def _search_360_web(query: str, limit: int) -> List[Dict]:
    with httpx.Client(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
    ) as client:
        results = []
        for page in (1, 2, 3, 4):
            response = client.get(
                "https://www.so.com/s",
                params={"q": query, "pn": page},
            )
            response.raise_for_status()
            results.extend(parse_link_page(response.text, limit))
        with ThreadPoolExecutor(max_workers=8) as pool:
            urls = list(pool.map(
                lambda result: _resolve_redirect_url(client, result["url"]),
                results,
            ))
    return _finalize_results(results, urls)


def _search_weixin(query: str, limit: int) -> List[Dict]:
    with httpx.Client(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
    ) as client:
        results = []
        for page in (1, 2, 3, 4, 5):
            response = client.get(
                "https://weixin.sogou.com/weixin",
                params={"type": "2", "query": query, "page": page},
            )
            response.raise_for_status()
            results.extend(parse_link_page(response.text, limit))
        with ThreadPoolExecutor(max_workers=8) as pool:
            urls = list(pool.map(
                lambda result: _resolve_redirect_url(client, result["url"]),
                results,
            ))
    return _finalize_results(results, urls)


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


def _resolve_redirect_url(client: httpx.Client, url: str) -> str:
    target = urljoin("https://www.sogou.com", url)
    if not target.startswith(("http://", "https://")) or target.startswith("javascript:"):
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
        response = client.get(target, headers={"Referer": referer})
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


def parse_link_page(html: str, limit: int) -> List[Dict]:
    document = fromstring(html)
    articles = []
    seen = set()
    for link in document.xpath("//h3/a[@href]"):
        title = " ".join(link.text_content().split())
        url = link.get("href", "")
        if (
            not title
            or not url
            or url.startswith("javascript:")
            or url in seen
        ):
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
        description = " ".join(" ".join(
            paragraph.text_content()
            for paragraph in container.xpath(".//p[not(contains(@class, 'info'))]")
        ).split())
        seen.add(url)
        articles.append({
            "title": title,
            "url": url,
            "source": source,
            "published": published.isoformat() if published else None,
            "description": description[:500],
        })
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
        snippet = " ".join(" ".join(
            paragraph.text_content()
            for paragraph in result.xpath(".//p[not(contains(@class, 'info'))]")
        ).split())
        source = " ".join("".join(result.xpath(".//cite//text()")).split())
        published = parse_datetime(
            "".join(result.xpath(".//span[contains(@class, 'time')]//text()"))
        )
        seen.add(url)
        articles.append({
            "title": title,
            "url": url,
            "source": source or urlparse(url).netloc.replace("www.", ""),
            "published": published.isoformat() if published else date_from_url(url),
            "description": snippet[:500],
        })
        if len(articles) >= limit:
            break
    return articles
