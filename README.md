# Open News Search

搜索中文新闻。

## 安装

```bash
uv sync --default-index https://pypi.tuna.tsinghua.edu.cn/simple/
```

## 使用

```bash
news "徒步 爬山事故"
news "人工智能" --limit 30
news "人工智能" --days 7
news "经济" --format json --save news.json
```

搜索结束后会显示本次耗时。JSON 输出和耗时提示相互独立。
默认聚合 360 新闻、360 网页、搜狗网页、搜狗新闻和微信文章搜索结果，并统一去重、解析原文链接和相关度排序。
中文查询会自动分词并生成通用的两词组合，不依赖具体新闻领域。
使用 `--days N` 会排除已知日期超过 N 天的文章；无法解析日期的结果仍保留，避免漏报。

## Python API

```python
from open_news import search_and_get, search_and_get_async

articles = search_and_get("徒步 爬山事故", limit=20)
```

## MCP

本地 Codex 可直接通过 `uvx` 启动 MCP 服务：

```toml
[mcp_servers.news]
command = "uvx"
args = ["--from", "open-news-search", "news-mcp"]
```

工具名为 `search_news`，参数为 `query`、`limit` 和 `days`。
