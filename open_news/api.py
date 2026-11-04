import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from queue import SimpleQueue
from time import perf_counter
from typing import Dict, List, Optional

from .processing import (
    dedupe_articles,
    filter_recent,
    search_queries,
    title_matches_query,
)
from .sources import search_news


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


def search_and_get(
    query: str,
    limit: int = 20,
    days: Optional[int] = None,
) -> List[Dict]:
    total_started = perf_counter()
    metrics = SimpleQueue() if os.getenv("NEWS_PROFILE") == "1" else None
    t = perf_counter()
    candidate_limit = max(limit * 5, 100) if days else limit * 3
    queries = search_queries(query)
    if metrics is not None:
        metrics.put(("query_expand", "-", perf_counter() - t))
    t = perf_counter()
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = list(
            pool.map(
                lambda search_query: search_news(
                    search_query, candidate_limit, metrics
                ),
                queries,
            )
        )
    if metrics is not None:
        metrics.put(("search_all", "-", perf_counter() - t))
    t = perf_counter()
    articles = dedupe_articles([article for batch in batches for article in batch])
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
