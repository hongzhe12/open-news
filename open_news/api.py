import asyncio
import os
import sys
from collections import defaultdict
from queue import SimpleQueue
from time import perf_counter
from typing import Dict, List, Optional

import httpx

from .processing import (
    dedupe_articles,
    filter_recent,
    search_queries,
    title_matches_query,
)
from .sources import _finalize_results, _resolve_redirect_url, search_news
from .utils import get_user_agent


_CONCURRENCY = 15


def print_profile(metrics, total):
    stats = defaultdict(list)
    while not metrics.empty():
        stage, source, elapsed = metrics.get()
        stats[(source, stage)].append(elapsed)
    print(f"\n[NEWS PROFILE] 总耗时: {total:.3f}s", file=sys.stderr)
    for (source, stage), values in sorted(stats.items()):
        print(
            f"{source:35} "
            f"{stage:15} "
            f"总计={sum(values):.3f}s "
            f"次数={len(values)} "
            f"最大={max(values):.3f}s",
            file=sys.stderr,
        )


async def _search_and_get_async(
    query: str,
    limit: int,
    days: Optional[int],
) -> List[Dict]:
    total_started = perf_counter()
    metrics = SimpleQueue() if os.getenv("NEWS_PROFILE") == "1" else None
    t = perf_counter()
    candidate_limit = max(limit * 5, 100) if days else limit * 3
    queries = search_queries(query)
    if metrics is not None:
        metrics.put(("query_expand", "-", perf_counter() - t))
    t = perf_counter()
    async with httpx.AsyncClient(
        headers={"User-Agent": get_user_agent()},
        timeout=20,
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=_CONCURRENCY,
            max_keepalive_connections=_CONCURRENCY,
        ),
    ) as client:
        semaphore = asyncio.Semaphore(_CONCURRENCY)
        batches = await asyncio.gather(
            *[
                search_news(
                    search_query,
                    candidate_limit,
                    client,
                    semaphore,
                    metrics,
                )
                for search_query in queries
            ],
            return_exceptions=True,
        )
        if metrics is not None:
            metrics.put(("search_all", "-", perf_counter() - t))
        articles = [
            article
            for batch in batches
            if not isinstance(batch, Exception)
            for article in batch
        ]
        t = perf_counter()
        urls = list(dict.fromkeys(article["url"] for article in articles))
        resolved = await asyncio.gather(
            *(
                _resolve_redirect_url(client, semaphore, url, metrics)
                for url in urls
            ),
            return_exceptions=True,
        )
        url_map = {
            url: "" if isinstance(final_url, Exception) else final_url
            for url, final_url in zip(urls, resolved)
        }
        if metrics is not None:
            metrics.put(("redirect_all", "-", perf_counter() - t))
        t = perf_counter()
        articles = _finalize_results(
            articles,
            [url_map[article["url"]] for article in articles],
        )
        if metrics is not None:
            metrics.put(("finalize", "-", perf_counter() - t))
    t = perf_counter()
    articles = dedupe_articles(articles)
    if metrics is not None:
        metrics.put(("dedupe", "-", perf_counter() - t))
    if days:
        t = perf_counter()
        articles = filter_recent(articles, days)
        if metrics is not None:
            metrics.put(("filter", "-", perf_counter() - t))
    t = perf_counter()
    articles.sort(key=lambda article: not title_matches_query(article, query))
    articles = articles[:limit]
    if metrics is not None:
        metrics.put(("rank", "-", perf_counter() - t))
        print_profile(metrics, perf_counter() - total_started)
    return articles


def search_and_get(
    query: str,
    limit: int = 20,
    days: Optional[int] = None,
) -> List[Dict]:
    return asyncio.run(_search_and_get_async(query, limit, days))
