import sys

from open_news import api, cli
from open_news.cli import build_parser


def test_search_cli_parses_query():
    args = build_parser().parse_args([
        "徒步 爬山事故", "--limit", "5", "--days", "7",
    ])

    assert args.query == "徒步 爬山事故"
    assert args.limit == 5
    assert args.days == 7


def test_cli_prints_search_duration(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["open-news", "测试"])
    monkeypatch.setattr(cli, "search_and_get", lambda *args, **kwargs: [])

    cli.main()

    assert "搜索用时:" in capsys.readouterr().err


def test_search_keeps_unmatched_results_after_matches(monkeypatch):
    monkeypatch.setattr(api, "search_news", lambda query, limit: [
        {"title": "推荐耳机", "url": "https://a.test/1"},
        {"title": "徒步事故", "url": "https://a.test/2"},
    ])

    articles = api.search_and_get("徒步")

    assert [article["title"] for article in articles] == ["徒步事故", "推荐耳机"]


def test_search_uses_segmented_query(monkeypatch):
    queries = []

    def fake_search(query, limit):
        queries.append(query)
        return []

    monkeypatch.setattr(api, "search_news", fake_search)
    api.search_and_get("徒步爬山事故")

    assert set(queries) == {
        "徒步爬山事故",
        "徒步 爬山 事故",
        "徒步 爬山",
        "徒步 事故",
        "爬山 事故",
    }
