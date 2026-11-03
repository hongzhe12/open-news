from datetime import datetime, timedelta, timezone

from open_news.processing import (
    dedupe_articles,
    filter_recent,
    normalize_url,
    search_queries,
    title_matches_query,
)


def test_dedupe_ignores_tracking_parameters():
    articles = [
        {"url": "https://www.example.com/news/1?utm_source=a", "title": "One"},
        {"url": "https://example.com/news/1?ref=home", "title": "Two"},
    ]

    assert normalize_url(articles[0]["url"]) == normalize_url(articles[1]["url"])
    assert len(dedupe_articles(articles)) == 1


def test_search_title_filter_rejects_unrelated_ads():
    assert title_matches_query({"title": "推荐耳机"}, "徒步 爬山事故") is False
    assert title_matches_query({"title": "登山滑坠事故"}, "徒步 爬山事故") is True


def test_date_filter_keeps_recent_and_undated_articles():
    now = datetime.now(timezone.utc)
    articles = [
        {"url": "https://a.test/1", "published": now.isoformat()},
        {"url": "https://a.test/2", "published": (now - timedelta(days=10)).isoformat()},
        {"url": "https://a.test/3", "published": None},
    ]

    assert [article["url"] for article in filter_recent(articles, 7, now)] == [
        "https://a.test/1",
        "https://a.test/3",
    ]


def test_search_queries_adds_chinese_segmentation():
    assert search_queries("徒步爬山事故") == [
        "徒步爬山事故",
        "徒步 爬山 事故",
        "徒步 爬山",
        "徒步 事故",
        "爬山 事故",
    ]


def test_query_expansion_is_domain_agnostic():
    assert search_queries("上海 人工智能 政策") == [
        "上海 人工智能 政策",
        "上海 人工智能",
        "上海 政策",
        "人工智能 政策",
    ]
