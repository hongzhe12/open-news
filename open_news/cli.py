import argparse
import json
import sys
from time import perf_counter

from . import __version__
from .api import search_and_get


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="news",
        description="Search Chinese news by keyword.",
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--days",
        type=int,
        help="Keep articles from the last N days; retain undated results.",
    )
    _add_output_args(parser)
    return parser


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["pretty", "json"], default="pretty")
    parser.add_argument("--save", metavar="FILE")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print(f"news {__version__}")
        return
    if not args.query:
        parser.error("a search query is required")

    started = perf_counter()
    articles = search_and_get(
        args.query,
        limit=args.limit,
        days=args.days,
    )
    elapsed = perf_counter() - started
    if args.save:
        with open(args.save, "w", encoding="utf-8") as file:
            json.dump(articles, file, ensure_ascii=False, indent=2, default=str)
    if args.format == "json":
        print(json.dumps(articles, ensure_ascii=False, indent=2, default=str))
    else:
        _print_articles(articles)
    print(f"搜索用时: {elapsed:.2f} 秒", file=sys.stderr)


def _print_articles(articles) -> None:
    for index, article in enumerate(articles, 1):
        print(f"[{index}] {article.get('title') or 'Untitled'}")
        metadata = " | ".join(
            filter(
                None,
                (
                    article.get("source"),
                    article.get("published") or article.get("publish_date"),
                ),
            )
        )
        if metadata:
            print(f"    {metadata}")
        print(f"    {article.get('url', '')}")
    print(f"\n{len(articles)} article(s).")


if __name__ == "__main__":
    main()
