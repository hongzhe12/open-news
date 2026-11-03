from open_news import sources
from open_news.sources import _finalize_results, parse_link_page, parse_search_page


def test_parse_search_page_extracts_article_links():
    html = """
    <ul class="result">
      <li class="res-list">
        <a href="https://example.com/2026/11-03/1.shtml" title="徒步事故">
          <h3>徒步事故</h3>
          <p>两人受伤。</p>
          <p class="info"><cite>示例新闻</cite><span class="time">2026-11-03 08:00</span></p>
        </a>
      </li>
    </ul>
    """

    articles = parse_search_page(html, limit=10)

    assert articles[0]["title"] == "徒步事故"
    assert articles[0]["published"] == "2026-11-03T08:00:00+00:00"
    assert articles[0]["source"] == "示例新闻"


def test_parse_link_page_extracts_titles_and_links():
    html = """
    <h3><a href="/link?url=abc">徒步爬山事故</a></h3>
    <h3><a href="https://example.com/2">登山安全</a></h3>
    """

    articles = parse_link_page(html, limit=10)

    assert [article["title"] for article in articles] == ["徒步爬山事故", "登山安全"]


def test_search_news_skips_failed_sources(monkeypatch):
    monkeypatch.setattr(sources, "_search_360", lambda query, limit: [{"title": "A"}])
    monkeypatch.setattr(sources, "_search_360_web", lambda query, limit: 1 / 0)
    monkeypatch.setattr(sources, "_search_sogou", lambda query, limit: [{"title": "B"}])
    monkeypatch.setattr(sources, "_search_sogou_news", lambda query, limit: [])
    monkeypatch.setattr(sources, "_search_weixin", lambda query, limit: [{"title": "C"}])

    assert [article["title"] for article in sources.search_news("test")] == ["A", "B", "C"]


def test_url_date_takes_priority_over_search_page_date():
    results = [{
        "title": "旧文章",
        "url": "https://example.com/2017/02-03/story.shtml",
        "source": "",
        "published": "2026-10-16T00:00:00+00:00",
    }]

    finalized = _finalize_results(results, [results[0]["url"]])

    assert finalized[0]["published"] == "2017-02-03T00:00:00+00:00"
