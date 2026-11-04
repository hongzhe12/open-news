import logging
import re
import warnings
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    import jieba

from .utils import nfc, parse_datetime

jieba.setLogLevel(logging.ERROR)

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "igshid",
    "ref",
    "ref_src",
    "ito",
    "smid",
}
_QUERY_TOKENS = re.compile(r'"([^"]+)"|(\S+)')
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def search_queries(query: str) -> List[str]:
    tokens = [
        token.strip()
        for token in jieba.lcut(query)
        if token.strip() and (len(token.strip()) > 1 or not _CJK.search(token))
    ]
    segmented = " ".join(tokens)
    variants = [query, segmented]
    variants.extend(" ".join(pair) for pair in combinations(tokens, 2))
    return list(dict.fromkeys(variants))[:6]


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query)
            if key.lower() not in _TRACKING_PARAMS
        )
    )
    return urlunparse(
        (
            "",
            parsed.netloc.lower().replace("www.", ""),
            parsed.path.rstrip("/"),
            "",
            query,
            "",
        )
    ).lstrip("/")


def dedupe_articles(articles: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for article in articles:
        key = normalize_url(article.get("url", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(article)
    return unique


def filter_recent(
    articles: List[Dict],
    days: int,
    now: Optional[datetime] = None,
) -> List[Dict]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    recent = []
    for article in articles:
        published = parse_datetime(
            article.get("published") or article.get("publish_date")
        )
        if not published or published >= cutoff:
            recent.append(article)
    return recent


def title_matches_query(article: Dict, query: str) -> bool:
    title = nfc(article.get("title", ""))
    keywords = []
    for quoted, bare in _QUERY_TOKENS.findall(nfc(query)):
        term = (quoted or bare).strip('".,;:!?()[]{}')
        if not term:
            continue
        if _CJK.search(term) and len(term) > 2:
            keywords.extend(term[i : i + 2] for i in range(len(term) - 1))
        else:
            keywords.append(term)
    return any(_contains(title, keyword) for keyword in keywords)


def _contains(text: str, term: str) -> bool:
    left = "" if _CJK.match(term[:1]) else r"(?<!\w)"
    right = "" if _CJK.match(term[-1:]) else r"(?!\w)"
    return bool(re.search(left + re.escape(term) + right, text, re.IGNORECASE))
