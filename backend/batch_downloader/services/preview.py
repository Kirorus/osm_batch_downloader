from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from shapely.geometry import mapping

from batch_downloader.services.osm_geometry import build_relation_geometry
from batch_downloader.services.overpass import OverpassError, post_overpass
from batch_downloader.services.storage import scope_paths, write_object_geojson
from batch_downloader.settings import settings
from batch_downloader.utils import preferred_name_from_tags

logger = logging.getLogger(__name__)


def _relations_fetch_query(relation_ids: list[int], timeout_sec: int, *, with_geom: bool = True) -> str:
    joined = ",".join(str(int(x)) for x in relation_ids)
    out_mode = "out body geom;" if with_geom else "out body;"
    return "\n".join(
        [
            f"[out:json][timeout:{int(timeout_sec)}];",
            f"relation({joined})->.r;",
            "(.r;>;);",
            out_mode,
        ]
    )


def _cache_root() -> Path:
    return settings.cache_dir / "preview"


def _cache_key(overpass_url: str | None) -> str:
    src = str(overpass_url or settings.overpass_url).strip().lower()
    endpoint_key = hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]
    return f"op_{endpoint_key}"


def _cache_file(relation_id: int, overpass_url: str | None) -> Path:
    return _cache_root() / _cache_key(overpass_url) / f"r{int(relation_id)}.json"


def _load_cached_feature(relation_id: int, overpass_url: str | None) -> dict[str, Any] | None:
    p = _cache_file(relation_id, overpass_url)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "Feature":
        return None
    geom = payload.get("geometry")
    props = payload.get("properties")
    if not isinstance(geom, dict) or not isinstance(props, dict):
        return None
    return {
        "type": "Feature",
        "id": int(relation_id),
        "geometry": geom,
        "properties": props,
    }


def _save_cached_feature(feature: dict[str, Any], relation_id: int, overpass_url: str | None) -> None:
    p = _cache_file(relation_id, overpass_url)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(feature), encoding="utf-8")
    except Exception:
        # Cache write failures should never fail preview.
        return


def _tags_from_feature_properties(props: dict[str, Any]) -> dict[str, Any]:
    reserved = {"relation_id", "osm_type", "osm_id", "name", "preview_generated_at_epoch"}
    out: dict[str, Any] = {}
    for k, v in props.items():
        if not isinstance(k, str):
            continue
        if k in reserved:
            continue
        out[k] = v
    return out


def _load_scoped_object_feature(
    relation_id: int, *, adm_name: str, admin_level: str, source_kind: str = "osm"
) -> dict[str, Any] | None:
    p = scope_paths(adm_name=adm_name, admin_level=admin_level)
    rid = int(relation_id)
    objects_dir = p.osm_objects_dir if source_kind != "land" else p.land_objects_dir
    candidates = sorted(
        objects_dir.glob(f"*__r{rid}.geojson"),
        key=lambda x: x.stat().st_mtime if x.exists() else 0.0,
        reverse=True,
    )
    for fp in candidates:
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            feats = raw.get("features") if isinstance(raw, dict) else None
            if not isinstance(feats, list) or not feats:
                continue
            feat = feats[0]
            if not isinstance(feat, dict):
                continue
            geom = feat.get("geometry")
            props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
            if not isinstance(geom, dict):
                continue
            return {
                "type": "Feature",
                "id": rid,
                "geometry": geom,
                "properties": {
                    **props,
                    "relation_id": rid,
                    "osm_type": "relation",
                    "osm_id": rid,
                    "name": str(props.get("name") or preferred_name_from_tags(props) or f"relation {rid}"),
                },
            }
        except Exception:
            continue
    return None


def land_preview_features(
    relation_ids: list[int],
    *,
    adm_name: str,
    admin_level: str,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(int(x) for x in relation_ids if int(x) > 0))
    feats: list[dict[str, Any]] = []
    for rid in ids:
        f = _load_scoped_object_feature(
            rid, adm_name=str(adm_name).strip(), admin_level=str(admin_level).strip(), source_kind="land"
        )
        if f is not None:
            feats.append(f)
    return {"type": "FeatureCollection", "features": feats}


def get_cached_preview_feature(relation_id: int, *, overpass_url: str | None = None) -> dict[str, Any] | None:
    """
    Public helper for other services (e.g. export) to reuse preview geometry cache.
    """
    return _load_cached_feature(int(relation_id), overpass_url)


def preview_features(
    relation_ids: list[int],
    *,
    adm_name: str | None = None,
    admin_level: str | None = None,
    overpass_url: str | None = None,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    feats: list[dict[str, Any]] = []
    ids = list(dict.fromkeys(int(x) for x in relation_ids if int(x) > 0))
    if not ids:
        return {"type": "FeatureCollection", "features": []}

    scoped = bool(str(adm_name or "").strip() and str(admin_level or "").strip())
    scope_name = str(adm_name or "").strip()
    scope_al = str(admin_level or "").strip()
    target_cache = f"osm_source objects ({scope_name}/admin_level={scope_al})" if scoped else "preview cache files"
    logger.info(
        "preview_features start: ids=%d, target_cache=%s, overpass_url=%s",
        len(ids),
        target_cache,
        str(overpass_url or settings.overpass_url).strip(),
    )

    missing_ids: list[int] = []
    hit_scoped = 0
    hit_preview_cache = 0
    fetched_overpass = 0
    for rid in ids:
        if scoped:
            scoped_cached = _load_scoped_object_feature(rid, adm_name=scope_name, admin_level=scope_al)
            if scoped_cached is not None:
                feats.append(scoped_cached)
                hit_scoped += 1
                continue
        cached = _load_cached_feature(rid, overpass_url)
        if cached is not None:
            feats.append(cached)
            hit_preview_cache += 1
            if scoped:
                props = cached.get("properties") if isinstance(cached.get("properties"), dict) else {}
                tags = _tags_from_feature_properties(props)
                try:
                    write_object_geojson(
                        scope_paths(adm_name=scope_name, admin_level=scope_al).osm_objects_dir,
                        rid,
                        tags,
                        cached.get("geometry") if isinstance(cached.get("geometry"), dict) else {},
                    )
                except Exception:
                    pass
        else:
            missing_ids.append(rid)
    if not missing_ids:
        return {"type": "FeatureCollection", "features": feats}

    def _fetch_elements(chunk_ids: list[int]) -> list[dict[str, Any]]:
        q = _relations_fetch_query(chunk_ids, timeout_sec, with_geom=True)
        try:
            res = post_overpass(q, preferred_url=overpass_url, timeout_sec=timeout_sec)
        except OverpassError:
            q_fallback = _relations_fetch_query(chunk_ids, timeout_sec, with_geom=False)
            res = post_overpass(q_fallback, preferred_url=overpass_url, timeout_sec=timeout_sec)
        elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
        if not isinstance(elements, list):
            return []
        return [e for e in elements if isinstance(e, dict)]

    chunk_size = 25
    for i in range(0, len(missing_ids), chunk_size):
        chunk = missing_ids[i : i + chunk_size]
        try:
            elements = _fetch_elements(chunk)
        except OverpassError:
            # Be resilient for preview: split the failing chunk and continue with what can be fetched.
            elements = []
            half = max(1, len(chunk) // 2)
            subchunks = [chunk[:half], chunk[half:]] if len(chunk) > 1 else [chunk]
            for sub in subchunks:
                if not sub:
                    continue
                try:
                    elements.extend(_fetch_elements(sub))
                    continue
                except OverpassError:
                    pass
                # Last fallback: by one relation; skip IDs that still fail.
                for rid in sub:
                    try:
                        elements.extend(_fetch_elements([rid]))
                    except OverpassError:
                        continue

        for rid in chunk:
            try:
                rel_el = next(
                    (
                        e
                        for e in elements
                        if str(e.get("type") or "").lower() == "relation" and int(e.get("id") or 0) == int(rid)
                    ),
                    None,
                )
                tags = rel_el.get("tags") if isinstance(rel_el, dict) and isinstance(rel_el.get("tags"), dict) else {}
                name = preferred_name_from_tags(tags) or f"relation {int(rid)}"
                geom = build_relation_geometry(elements, int(rid))
                feature = {
                    "type": "Feature",
                    "id": int(rid),
                    "geometry": mapping(geom),
                    "properties": {
                        **(tags if isinstance(tags, dict) else {}),
                        "relation_id": int(rid),
                        "osm_type": "relation",
                        "osm_id": int(rid),
                        "name": name,
                        "preview_generated_at_epoch": time.time(),
                    },
                }
                feats.append(feature)
                fetched_overpass += 1
                if scoped:
                    tags = _tags_from_feature_properties(feature.get("properties") if isinstance(feature.get("properties"), dict) else {})
                    try:
                        write_object_geojson(
                            scope_paths(adm_name=scope_name, admin_level=scope_al).osm_objects_dir,
                            int(rid),
                            tags,
                            feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {},
                        )
                    except Exception:
                        pass
                else:
                    _save_cached_feature(feature, int(rid), overpass_url)
            except Exception:
                continue
    logger.info(
        "preview_features done: returned=%d, scoped_hits=%d, preview_hits=%d, overpass_fetched=%d",
        len(feats),
        hit_scoped,
        hit_preview_cache,
        fetched_overpass,
    )
    return {"type": "FeatureCollection", "features": feats}
