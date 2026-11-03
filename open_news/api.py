from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from .article import get_article
from .processing import (
    dedupe_articles,
    filter_recent,
    search_queries,
    title_matches_query,
)
from .sources import search_news


def _with_full_content(article: Dict) -> Dict:
    full = get_article(article["url"])
    return {
        **article,
        **{key: value for key, value in full.items() if value not in (None, "", [], {})},
    }


def search_and_get(
    query: str,
    limit: int = 20,
    full_content: bool = False,
    days: Optional[int] = None,
) -> List[Dict]:
    candidate_limit = max(limit * 5, 100) if days else limit * 3
    queries = search_queries(query)
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = list(pool.map(
            lambda search_query: search_news(search_query, candidate_limit),
            queries,
        ))
    articles = dedupe_articles([
        article for batch in batches for article in batch
    ])
    if days:
        articles = filter_recent(articles, days)
    articles.sort(key=lambda article: not title_matches_query(article, query))
    articles = articles[:limit]
    if full_content:
        articles = [_with_full_content(article) for article in articles]
    return articles
