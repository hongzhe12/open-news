import asyncio
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


async def _search_and_get_async(
    query: str,
    limit: int,
    days: Optional[int],
) -> List[Dict]:
    candidate_limit = max(limit * 5, 100) if days else limit * 3
    queries = search_queries(query)
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
                )
                for search_query in queries
            ],
            return_exceptions=True,
        )
        articles = [
            article
            for batch in batches
            if not isinstance(batch, Exception)
            for article in batch
        ]
        urls = list(dict.fromkeys(article["url"] for article in articles))
        resolved = await asyncio.gather(
            *(_resolve_redirect_url(client, semaphore, url) for url in urls),
            return_exceptions=True,
        )
        url_map = {
            url: "" if isinstance(final_url, Exception) else final_url
            for url, final_url in zip(urls, resolved)
        }
        articles = _finalize_results(
            articles,
            [url_map[article["url"]] for article in articles],
        )
    articles = dedupe_articles(articles)
    if days:
        articles = filter_recent(articles, days)
    articles.sort(key=lambda article: not title_matches_query(article, query))
    return articles[:limit]


def search_and_get(
    query: str,
    limit: int = 20,
    days: Optional[int] = None,
) -> List[Dict]:
    return asyncio.run(_search_and_get_async(query, limit, days))
