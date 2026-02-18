from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests
import re
from urllib.parse import urlparse

from batch_downloader.settings import settings


@dataclass(frozen=True)
class OverpassResult:
    payload: dict[str, Any]
    used_url: str
    elapsed_sec: float


class OverpassError(RuntimeError):
    pass


def _normalize_overpass_endpoint(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")

    path = (parsed.path or "").rstrip("/")
    if path.endswith("/api"):
        path = path + "/interpreter"
    elif path.endswith("/interpreter"):
        pass
    else:
        # Keep as-is; some instances expose interpreter at the provided path.
        pass
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_osm3s_error(html: str) -> str | None:
    text = html or ""
    if "OSM3S Response" not in text:
        return None
    m = re.search(r"<strong[^>]*>(.*?)</strong>", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    msg = re.sub(r"<[^>]+>", " ", m.group(1))
    msg = re.sub(r"\\s+", " ", msg).strip()
    return msg or None


def post_overpass(query: str, *, preferred_url: str | None = None, timeout_sec: int | None = None) -> OverpassResult:
    urls = []
    if preferred_url:
        urls.append(_normalize_overpass_endpoint(preferred_url))
    urls.append(_normalize_overpass_endpoint(settings.overpass_url))
    urls = [u for u in urls if u]
    urls = list(dict.fromkeys(urls))

    headers = {"User-Agent": settings.http_user_agent}
    timeout = float(timeout_sec or settings.http_timeout_sec)

    last_error: Exception | None = None
    for url in urls:
        t0 = time.time()
        try:
            # Use form-encoded "data=" which is supported by Overpass and works with more proxies.
            resp = requests.post(url, data={"data": query}, headers=headers, timeout=timeout)
            elapsed = time.time() - t0
            if resp.status_code != 200:
                html_msg = _extract_osm3s_error(resp.text)
                if html_msg:
                    raise OverpassError(f"Overpass HTTP {resp.status_code}: {html_msg}")
                raise OverpassError(f"Overpass HTTP {resp.status_code}: {resp.text[:800]}")
            try:
                payload = resp.json()
            except Exception as exc:
                raise OverpassError(f"Overpass invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise OverpassError("Overpass response is not a JSON object")
            return OverpassResult(payload=payload, used_url=url, elapsed_sec=elapsed)
        except Exception as exc:
            last_error = exc
            continue
    raise OverpassError(f"Overpass failed: {last_error}")
