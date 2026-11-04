# Open News Search

搜索中文新闻的 MCP 服务。

## MCP

在 Codex 中配置：

```toml
[mcp_servers.news]
command = "uvx"
args = ["--from", "open-news-search", "news-mcp"]
```

工具名为 `search_news`，参数为 `query`、`limit` 和 `days`。

默认聚合 360 新闻、360 网页、搜狗网页、搜狗新闻和微信文章搜索结果，并统一去重、解析原文链接和相关度排序。
中文查询会自动分词并生成通用的两词组合，不依赖具体新闻领域。
使用 `days` 参数会排除已知日期超过指定天数的文章；无法解析日期的结果仍保留，避免漏报。

## Python API

```python
from open_news import search_and_get, search_and_get_async

articles = search_and_get("徒步 爬山事故", limit=20)
```

## 发布

更新 `pyproject.toml` 和 `open_news/__init__.py` 中的版本号后执行：

```bash
uv build
TWINE_USERNAME=__token__ \
TWINE_PASSWORD=pypi-你的Token \
uvx twine upload dist/*
```

Token 只通过环境变量传入，不要写入仓库。
