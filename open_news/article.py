from typing import Dict
from urllib.parse import urlparse

import httpx

from .extractor import extract_article
from .utils import date_from_url, get_user_agent


def get_article(url: str, timeout: int = 15) -> Dict:
    response = httpx.get(
        url,
        headers={"User-Agent": get_user_agent()},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    extracted = extract_article(response.text, url=url)
    return {
        "url": url,
        "title": extracted["title"],
        "text": extracted["text"],
        "authors": extracted["authors"],
        "publish_date": extracted["publish_date"] or date_from_url(url),
        "category": extracted["category"],
        "top_image": extracted["top_image"],
        "images": extracted["images"],
        "videos": extracted["videos"],
        "source": extracted["source"] or urlparse(url).netloc.replace("www.", ""),
        "description": extracted["description"],
        "meta": extracted["meta"],
    }
