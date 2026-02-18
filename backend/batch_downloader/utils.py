from __future__ import annotations

import re
import unicodedata


_CYR_MAP: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _translit_ru(text: str) -> str:
    out: list[str] = []
    for ch in text:
        low = ch.lower()
        if low in _CYR_MAP:
            tr = _CYR_MAP[low]
            out.append(tr.upper() if ch.isupper() and tr else tr)
        else:
            out.append(ch)
    return "".join(out)


def slugify(text: str, *, max_len: int = 80) -> str:
    t = (text or "").strip()
    if not t:
        return "unnamed"
    t = _translit_ru(t)
    t = unicodedata.normalize("NFKD", t)
    t = t.encode("ascii", "ignore").decode("ascii")
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    t = re.sub(r"-{2,}", "-", t)
    return (t[:max_len].rstrip("-") or "unnamed") if t else "unnamed"


def preferred_name_from_tags(tags: dict) -> str:
    if not isinstance(tags, dict):
        return ""
    for key in ("name:ru", "name", "name:en", "official_name:ru", "official_name", "short_name:ru", "short_name"):
        v = tags.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def preferred_english_name_from_tags(tags: dict) -> str:
    if not isinstance(tags, dict):
        return ""
    for key in ("name:en", "int_name", "official_name:en", "official_name", "name", "short_name:en", "short_name"):
        v = tags.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def iso2_from_tags(tags: dict) -> str:
    if not isinstance(tags, dict):
        return ""
    for key in ("ISO3166-1:alpha2", "ISO3166-1", "iso3166-1:alpha2", "iso3166-1"):
        v = tags.get(key)
        if not isinstance(v, str):
            continue
        v_norm = v.strip().upper()
        if len(v_norm) == 2 and v_norm.isascii() and v_norm.isalpha():
            return v_norm
    return ""

