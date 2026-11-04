import random
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional, Union

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def get_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def parse_datetime(raw: Union[str, datetime, None]) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value or "")


def date_from_url(url: str) -> Optional[str]:
    match = re.search(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:[/-]|$)", url)
    if not match:
        match = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", url)
    if not match:
        return None
    try:
        return datetime(
            *(int(part) for part in match.groups()), tzinfo=timezone.utc
        ).isoformat()
    except ValueError:
        return None
