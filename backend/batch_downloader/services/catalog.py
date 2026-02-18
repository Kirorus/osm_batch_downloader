from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from batch_downloader.services.overpass import OverpassError, post_overpass
from batch_downloader.settings import settings
from batch_downloader.utils import preferred_name_from_tags


OVERPASS_AREA_OFFSET = 3600000000
IDS_CACHE_TTL_SEC = 24 * 3600
ITEMS_CACHE_TTL_SEC = 24 * 3600
SEARCH_CACHE_TTL_SEC = 6 * 3600


def _area_id_from_relation(relation_id: int) -> int:
    return OVERPASS_AREA_OFFSET + int(relation_id)


def _ids_cache_file(admin_level: str, parent_relation_id: int | None) -> Path:
    scope = f"r{int(parent_relation_id)}" if parent_relation_id else "world"
    return settings.cache_dir / "catalog" / f"ids__{scope}__al{admin_level}.json"


def _items_cache_file(admin_level: str, parent_relation_id: int | None) -> Path:
    scope = f"r{int(parent_relation_id)}" if parent_relation_id else "world"
    return settings.cache_dir / "catalog" / f"items__{scope}__al{admin_level}.json"


def _search_cache_file(query: str, admin_level: str | None, limit: int) -> Path:
    al = str(admin_level).strip() if admin_level is not None else "any"
    safe_q = "".join(ch for ch in query.lower().strip() if ch.isalnum() or ch in ("_", "-"))[:80]
    if not safe_q:
        safe_q = "empty"
    return settings.cache_dir / "catalog" / f"search__{safe_q}__al{al}__l{int(limit)}.json"


def _load_ids_cache(path: Path, *, max_age_sec: int | None) -> list[int] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    ids = payload.get("relation_ids")
    if not isinstance(ids, list):
        return None
    try:
        clean = sorted(set(int(x) for x in ids if int(x) > 0))
    except Exception:
        return None
    if max_age_sec is not None:
        ts = payload.get("updated_at_epoch")
        try:
            age = time.time() - float(ts)
        except Exception:
            return None
        if age > max_age_sec:
            return None
    return clean


def _save_ids_cache(path: Path, relation_ids: list[int]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at_epoch": time.time(), "relation_ids": relation_ids}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        # Cache failures should not break normal flow.
        return


def _load_items_cache(path: Path, *, max_age_sec: int | None) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if max_age_sec is not None:
        ts = payload.get("updated_at_epoch")
        try:
            age = time.time() - float(ts)
        except Exception:
            return None
        if age > max_age_sec:
            return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("relation_id"))
        except Exception:
            continue
        tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
        name = preferred_name_from_tags(tags) or f"relation {rid}"
        out.append(
            {
                "relation_id": rid,
                "name": str(item.get("name") or name),
                "tags": tags,
                "center": item.get("center") if isinstance(item.get("center"), dict) else None,
                "bounds": item.get("bounds") if isinstance(item.get("bounds"), dict) else None,
            }
        )
    return out


def _save_items_cache(path: Path, items: list[dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at_epoch": time.time(), "items": items}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        return


def _load_search_cache(path: Path, *, max_age_sec: int | None) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if max_age_sec is not None:
        ts = payload.get("updated_at_epoch")
        try:
            age = time.time() - float(ts)
        except Exception:
            return None
        if age > max_age_sec:
            return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("relation_id"))
        except Exception:
            continue
        tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
        out.append(
            {
                "relation_id": rid,
                "name": str(item.get("name") or preferred_name_from_tags(tags) or f"relation {rid}"),
                "tags": tags,
                "center": item.get("center") if isinstance(item.get("center"), dict) else None,
                "bounds": item.get("bounds") if isinstance(item.get("bounds"), dict) else None,
            }
        )
    return out


def _save_search_cache(path: Path, items: list[dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at_epoch": time.time(), "items": items}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        return


def list_countries_items_fast(*, timeout_sec: int = 180) -> list[dict[str, Any]]:
    """
    Fast path for worldwide countries list:
    returns relation_id + tags + name in one Overpass call.
    """
    cache_path = _items_cache_file("2", None)
    fresh = _load_items_cache(cache_path, max_age_sec=ITEMS_CACHE_TTL_SEC)
    if fresh is not None:
        return fresh
    stale = _load_items_cache(cache_path, max_age_sec=None)

    q = "\n".join(
        [
            f"[out:json][timeout:{int(timeout_sec)}];",
            'rel["boundary"="administrative"]["admin_level"="2"]["type"="boundary"];',
            "out tags;",
        ]
    )
    try:
        res = post_overpass(q, timeout_sec=timeout_sec)
    except OverpassError:
        if stale is not None:
            return stale
        raise

    elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
    if not isinstance(elements, list):
        return []

    out: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if str(el.get("type") or "").lower() != "relation":
            continue
        try:
            rid = int(el.get("id"))
        except Exception:
            continue
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        out.append(
            {
                "relation_id": rid,
                "name": preferred_name_from_tags(tags) or f"relation {rid}",
                "tags": tags,
                "center": None,
                "bounds": None,
            }
        )

    out.sort(key=lambda x: x["name"])
    _save_items_cache(cache_path, out)
    return out


def list_parent_items_fast(*, admin_level: str, parent_relation_id: int, timeout_sec: int = 180) -> list[dict[str, Any]]:
    """
    Fast parent-scope list:
    returns relation_id + tags + name in one Overpass call.
    """
    admin_level = str(admin_level).strip()
    parent_relation_id = int(parent_relation_id)
    cache_path = _items_cache_file(admin_level, parent_relation_id)
    fresh = _load_items_cache(cache_path, max_age_sec=ITEMS_CACHE_TTL_SEC)
    if fresh is not None:
        return fresh
    stale = _load_items_cache(cache_path, max_age_sec=None)

    area_id = _area_id_from_relation(parent_relation_id)
    queries = [
        # Preferred: explicit map_to_area from parent relation.
        "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"relation({parent_relation_id});",
                "map_to_area->.a;",
                f'rel(area.a)["boundary"="administrative"]["admin_level"="{admin_level}"]["type"="boundary"];',
                "out tags;",
            ]
        ),
        # Fallback 1: area offset id.
        "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"area({area_id})->.a;",
                f'rel(area.a)["boundary"="administrative"]["admin_level"="{admin_level}"]["type"="boundary"];',
                "out tags;",
            ]
        ),
        # Fallback 2: relation members traversal.
        "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"relation({parent_relation_id})->.p;",
                f'rel(r.p)["boundary"="administrative"]["admin_level"="{admin_level}"]["type"="boundary"];',
                "out tags;",
            ]
        ),
    ]

    last_exc: OverpassError | None = None
    res = None
    for q in queries:
        try:
            res = post_overpass(q, timeout_sec=timeout_sec)
            break
        except OverpassError as exc:
            last_exc = exc
            continue

    if res is None:
        if stale is not None:
            return stale
        if last_exc is not None:
            raise last_exc
        return []

    elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
    if not isinstance(elements, list):
        return []

    out: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if str(el.get("type") or "").lower() != "relation":
            continue
        try:
            rid = int(el.get("id"))
        except Exception:
            continue
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        out.append(
            {
                "relation_id": rid,
                "name": preferred_name_from_tags(tags) or f"relation {rid}",
                "tags": tags,
                "center": None,
                "bounds": None,
            }
        )

    out.sort(key=lambda x: x["name"])
    _save_items_cache(cache_path, out)
    return out


def list_relation_ids(*, admin_level: str, parent_relation_id: int | None, timeout_sec: int = 180) -> list[int]:
    admin_level = str(admin_level).strip()
    cache_path = _ids_cache_file(admin_level, parent_relation_id)
    fresh = _load_ids_cache(cache_path, max_age_sec=IDS_CACHE_TTL_SEC)
    if fresh is not None:
        return fresh
    stale = _load_ids_cache(cache_path, max_age_sec=None)

    if parent_relation_id:
        area_id = _area_id_from_relation(int(parent_relation_id))
        q_area = "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"area({area_id})->.a;",
                f'rel(area.a)["boundary"="administrative"]["admin_level"="{admin_level}"];',
                "out ids;",
            ]
        )
        q_members = "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"relation({int(parent_relation_id)})->.p;",
                f'rel(r.p)["boundary"="administrative"]["admin_level"="{admin_level}"];',
                "out ids;",
            ]
        )
        try:
            res = post_overpass(q_area, timeout_sec=timeout_sec)
        except OverpassError:
            # Some endpoints may not have area indexes for the target relation.
            try:
                res = post_overpass(q_members, timeout_sec=timeout_sec)
            except OverpassError:
                if stale is not None:
                    return stale
                raise
    else:
        q = "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f'rel["boundary"="administrative"]["admin_level"="{admin_level}"];',
                "out ids;",
            ]
        )
        try:
            res = post_overpass(q, timeout_sec=timeout_sec)
        except OverpassError:
            if stale is not None:
                return stale
            raise
    elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
    if not isinstance(elements, list):
        return []
    ids: list[int] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if str(el.get("type") or "").lower() != "relation":
            continue
        try:
            ids.append(int(el.get("id")))
        except Exception:
            continue
    out = sorted(set(ids))
    _save_ids_cache(cache_path, out)
    return out


def fetch_relation_details(relation_ids: list[int], *, timeout_sec: int = 180) -> list[dict[str, Any]]:
    ids = [int(x) for x in relation_ids if int(x) > 0]
    if not ids:
        return []
    out: list[dict[str, Any]] = []

    def _parse_elements(elements: list[Any]) -> list[dict[str, Any]]:
        chunk_out: list[dict[str, Any]] = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            if str(el.get("type") or "").lower() != "relation":
                continue
            rid = el.get("id")
            try:
                rid_i = int(rid)
            except Exception:
                continue
            tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
            name = preferred_name_from_tags(tags) or f"relation {rid_i}"
            center = el.get("center") if isinstance(el.get("center"), dict) else None
            bounds = el.get("bounds") if isinstance(el.get("bounds"), dict) else None
            chunk_out.append(
                {
                    "relation_id": rid_i,
                    "name": name,
                    "tags": tags,
                    "center": center,
                    "bounds": bounds,
                }
            )
        return chunk_out

    def _fetch_chunk(chunk_ids: list[int]) -> list[dict[str, Any]]:
        joined = ",".join(str(x) for x in chunk_ids)
        # Try to get bounds+center when supported; fallback to center-only.
        q1 = "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"relation({joined});",
                "out tags bb center;",
            ]
        )
        q2 = "\n".join(
            [
                f"[out:json][timeout:{int(timeout_sec)}];",
                f"relation({joined});",
                "out tags center;",
            ]
        )
        try:
            res = post_overpass(q1, timeout_sec=timeout_sec)
        except OverpassError:
            res = post_overpass(q2, timeout_sec=timeout_sec)
        elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
        if not isinstance(elements, list):
            return []
        return _parse_elements(elements)

    # Larger chunks reduce round-trips; fallback logic still handles strict endpoints.
    chunk_size = 120
    for i in range(0, len(ids), chunk_size):
        chunk_ids = ids[i : i + chunk_size]
        try:
            out.extend(_fetch_chunk(chunk_ids))
        except OverpassError:
            # Last-resort compatibility fallback: query each relation separately.
            for rid in chunk_ids:
                try:
                    out.extend(_fetch_chunk([rid]))
                except OverpassError:
                    continue

    out.sort(key=lambda x: x["name"])
    return out


def search_admin_areas(*, query: str, admin_level: str | None, limit: int = 50, timeout_sec: int = 180) -> list[dict]:
    qtxt = (query or "").strip()
    if not qtxt:
        return []
    cache_path = _search_cache_file(qtxt, admin_level, limit)
    cached = _load_search_cache(cache_path, max_age_sec=SEARCH_CACHE_TTL_SEC)
    if cached is not None:
        return cached[: max(1, int(limit))]

    # Overpass uses a regex string here; escape quotes and backslashes to avoid breaking QL.
    qtxt = qtxt.replace("\\", "\\\\").replace('"', '\\"')
    qtxt_upper = qtxt.upper()
    al = str(admin_level).strip() if admin_level is not None else ""

    # Fast path: for countries, search locally in cached country items.
    if al == "2":
        items = list_countries_items_fast(timeout_sec=timeout_sec)
        q_norm = qtxt.lower()
        iso_query = qtxt_upper if 2 <= len(qtxt_upper) <= 3 and all(ch.isalpha() for ch in qtxt_upper) else ""
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
            name = str(item.get("name") or preferred_name_from_tags(tags) or "").strip()
            if not name:
                continue
            haystacks = [
                name.lower(),
                str(tags.get("name:en") or "").lower(),
                str(tags.get("int_name") or "").lower(),
                str(tags.get("official_name") or "").lower(),
                str(tags.get("ISO3166-1") or "").upper(),
                str(tags.get("ISO3166-1:alpha2") or "").upper(),
                str(tags.get("ISO3166-1:alpha3") or "").upper(),
            ]
            matched = any(q_norm in h for h in haystacks if h)
            if iso_query:
                matched = matched or any(iso_query == h for h in haystacks if h and h.isupper())
            if not matched:
                continue
            score = 100
            if name.lower().startswith(q_norm):
                score -= 25
            if iso_query and any(iso_query == h for h in haystacks if h and h.isupper()):
                score -= 40
            scored.append((score, item))
        scored.sort(key=lambda x: (x[0], str(x[1].get("name") or "")))
        out = [x[1] for x in scored[: max(1, int(limit))]]
        _save_search_cache(cache_path, out)
        return out

    al_clause = f'["admin_level"="{al}"]' if al else ""
    queries = []
    # Main multilingual lookup for parent search quality.
    queries.append(f'rel["boundary"="administrative"]{al_clause}[name~"{qtxt}",i];')
    queries.append(f'rel["boundary"="administrative"]{al_clause}["name:en"~"{qtxt}",i];')
    queries.append(f'rel["boundary"="administrative"]{al_clause}[int_name~"{qtxt}",i];')
    queries.append(f'rel["boundary"="administrative"]{al_clause}[official_name~"{qtxt}",i];')
    # ISO shortcuts: RU, DE, USA, etc.
    if 2 <= len(qtxt_upper) <= 3 and all(ch.isalpha() for ch in qtxt_upper):
        queries.append(f'rel["boundary"="administrative"]{al_clause}["ISO3166-1"="{qtxt_upper}"];')
        queries.append(f'rel["boundary"="administrative"]{al_clause}["ISO3166-1:alpha2"="{qtxt_upper}"];')
        queries.append(f'rel["boundary"="administrative"]{al_clause}["ISO3166-1:alpha3"="{qtxt_upper}"];')

    body = "\n".join(queries)
    q1 = "\n".join(
        [
            f"[out:json][timeout:{int(timeout_sec)}];",
            "(",
            body,
            ");",
            "out tags bb center;",
        ]
    )
    q2 = "\n".join(
        [
            f"[out:json][timeout:{int(timeout_sec)}];",
            "(",
            body,
            ");",
            "out tags center;",
        ]
    )
    try:
        res = post_overpass(q1, timeout_sec=timeout_sec)
    except OverpassError:
        res = post_overpass(q2, timeout_sec=timeout_sec)
    elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
    if not isinstance(elements, list):
        return []
    out: list[dict] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if str(el.get("type") or "").lower() != "relation":
            continue
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        name = preferred_name_from_tags(tags) or ""
        if not name:
            continue
        try:
            rid = int(el.get("id"))
        except Exception:
            continue
        out.append(
            {
                "relation_id": rid,
                "name": name,
                "tags": tags,
                "center": el.get("center") if isinstance(el.get("center"), dict) else None,
                "bounds": el.get("bounds") if isinstance(el.get("bounds"), dict) else None,
            }
        )
    out.sort(key=lambda x: x["name"])
    out = out[: max(1, int(limit))]
    _save_search_cache(cache_path, out)
    return out
