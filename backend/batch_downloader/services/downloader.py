from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape

from batch_downloader.services.land_polygons import download_land_polygons, load_land_union_for_bbox
from batch_downloader.services.osm_geometry import build_relation_geometry
from batch_downloader.services.overpass import OverpassError, post_overpass
from batch_downloader.services.preview import get_cached_preview_feature
from batch_downloader.services.storage import (
    load_manifest,
    rebuild_combined,
    save_json,
    save_manifest,
    scope_paths,
    write_object_geojson,
)
from batch_downloader.services.stats import count_polygons, count_vertices
from batch_downloader.utils import preferred_name_from_tags, slugify


@dataclass
class JobEvent:
    type: str
    data: dict[str, Any]


def _relation_fetch_query(relation_id: int, timeout_sec: int, *, with_geom: bool = True) -> str:
    out_mode = "out body geom;" if with_geom else "out body;"
    return "\n".join(
        [
            f"[out:json][timeout:{int(timeout_sec)}];",
            f"relation({int(relation_id)})->.r;",
            "(.r;>;);",
            out_mode,
        ]
    )


def _geom_bbox(geom) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = geom.bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def _tags_from_preview_properties(props: dict[str, Any]) -> dict[str, Any]:
    reserved = {"relation_id", "osm_type", "osm_id", "name", "preview_generated_at_epoch"}
    out: dict[str, Any] = {}
    for k, v in props.items():
        if not isinstance(k, str):
            continue
        if k in reserved:
            continue
        out[k] = v
    return out


def _tags_from_object_properties(props: dict[str, Any]) -> dict[str, Any]:
    reserved = {"osm_type", "osm_id", "relation_id", "name", "preview_generated_at_epoch"}
    out: dict[str, Any] = {}
    for k, v in props.items():
        if not isinstance(k, str):
            continue
        if k in reserved:
            continue
        out[k] = v
    return out


def _load_cached_osm_object(
    objects_dir: Path, relation_id: int
) -> tuple[Any, dict[str, Any], Path] | None:
    """
    Load already-exported osm_source object as a reusable geometry cache.
    Returns (shapely_geom, tags, path) when a valid file exists.
    """
    rid = int(relation_id)
    by_path: dict[str, Path] = {}
    for p in objects_dir.glob(f"r{rid}__*.geojson"):
        by_path[str(p)] = p
    for p in objects_dir.glob(f"*__r{rid}.geojson"):
        by_path[str(p)] = p
    candidates = sorted(
        by_path.values(),
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    for p in candidates:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            feats = raw.get("features") if isinstance(raw, dict) else None
            if not isinstance(feats, list) or not feats:
                continue
            feat = feats[0]
            if not isinstance(feat, dict):
                continue
            geometry = feat.get("geometry")
            props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
            try:
                if int(props.get("osm_id") or relation_id) != int(relation_id):
                    continue
            except Exception:
                continue
            if not isinstance(geometry, dict):
                continue
            geom = shape(geometry)
            if getattr(geom, "is_empty", False):
                continue
            tags = _tags_from_object_properties(props)
            return geom, tags, p
        except Exception:
            continue
    return None


def _load_cached_land_object(
    objects_dir: Path, relation_id: int
) -> tuple[Any, dict[str, Any], Path] | None:
    """
    Load already clipped land_only object for relation_id.
    Returns (shapely_geom, tags, path) when a valid file exists.
    """
    return _load_cached_osm_object(objects_dir, relation_id)


def download_admin_boundaries(
    *,
    adm_name: str,
    admin_level: str,
    relation_ids: list[int],
    relation_names: dict[str, str] | None = None,
    clip_land: bool,
    force_refresh_osm_source: bool = False,
    overpass_url: str | None,
    emit: callable,
    should_cancel: callable | None = None,
) -> None:
    p = scope_paths(adm_name=adm_name, admin_level=admin_level)
    manifest = load_manifest(p.manifest_path)
    objects = manifest.get("objects") if isinstance(manifest.get("objects"), dict) else {}

    emit(JobEvent("stage", {"stage": "start", "adm_name": adm_name, "admin_level": admin_level}))
    emit(
        JobEvent(
            "log",
            {
                "message": (
                    "OSM source cache mode: force refresh (ignore cached object files)"
                    if force_refresh_osm_source
                    else "OSM source cache mode: reuse cached object files when valid"
                )
            },
        )
    )
    t_job0 = time.time()

    if clip_land:
        emit(JobEvent("stage", {"stage": "land_polygons.ensure"}))

        def _on_lp_progress(done: int, total: int | None, elapsed: float) -> None:
            emit(
                JobEvent(
                    "land_polygons_download_progress",
                    {"done_bytes": done, "total_bytes": total, "elapsed_sec": elapsed},
                )
            )

        download_land_polygons(force=False, on_progress=_on_lp_progress, should_cancel=should_cancel)

    total = len(relation_ids)
    ok = 0
    failed = 0
    per_object_stats: dict[str, Any] = {}
    clip_cache_hits = 0
    clip_cache_misses = 0
    land_object_cache_hits = 0
    land_object_cache_misses = 0
    emit(JobEvent("overall_progress", {"done": 0, "total": total, "ok": 0, "failed": 0}))

    for idx, rid in enumerate(relation_ids, start=1):
        if should_cancel and should_cancel():
            emit(JobEvent("done", {"cancelled": True}))
            return
        provided_name = ""
        if isinstance(relation_names, dict):
            maybe_name = relation_names.get(str(int(rid)))
            if isinstance(maybe_name, str):
                provided_name = maybe_name.strip()
        cached_meta = objects.get(str(rid)) if isinstance(objects.get(str(rid)), dict) else {}
        obj_name = provided_name or str(cached_meta.get("name") or "").strip() or f"relation {rid}"
        emit(JobEvent("object_started", {"relation_id": rid, "name": obj_name, "index": idx, "total": total}))
        t0 = time.time()
        try:
            t_fetch0 = time.time()
            used_url = ""
            used_elapsed = 0.0
            tags: dict[str, Any] = {}
            t_build = 0.0
            t_write = 0.0
            osm_reused_from_cache = False

            osm_cached = None if force_refresh_osm_source else _load_cached_osm_object(p.osm_objects_dir, rid)
            if osm_cached is not None:
                emit(JobEvent("object_phase", {"relation_id": rid, "phase": "use_osm_source_cache"}))
                geom, tags, osm_path = osm_cached
                osm_reused_from_cache = True
                used_url = "osm_source_cache"
                used_elapsed = 0.0
                t_fetch = time.time() - t_fetch0
            else:
                cached = get_cached_preview_feature(rid, overpass_url=overpass_url)
                if cached is not None:
                    emit(JobEvent("object_phase", {"relation_id": rid, "phase": "use_preview_cache"}))
                    props = cached.get("properties") if isinstance(cached.get("properties"), dict) else {}
                    tags = _tags_from_preview_properties(props)
                    emit(JobEvent("object_phase", {"relation_id": rid, "phase": "build_geometry"}))
                    t_build0 = time.time()
                    geom = shape(cached.get("geometry"))
                    t_build = time.time() - t_build0
                    used_url = "preview_cache"
                    used_elapsed = 0.0
                    t_fetch = time.time() - t_fetch0
                else:
                    emit(JobEvent("object_phase", {"relation_id": rid, "phase": "fetch_overpass"}))
                    q = _relation_fetch_query(rid, 180, with_geom=True)
                    try:
                        res = post_overpass(q, preferred_url=overpass_url, timeout_sec=180)
                    except OverpassError:
                        # Some Overpass endpoints reject `out ... geom;` with HTTP 400.
                        q_fallback = _relation_fetch_query(rid, 180, with_geom=False)
                        res = post_overpass(q_fallback, preferred_url=overpass_url, timeout_sec=180)
                    t_fetch = time.time() - t_fetch0
                    used_url = res.used_url
                    used_elapsed = res.elapsed_sec
                    elements = res.payload.get("elements") if isinstance(res.payload, dict) else []
                    if not isinstance(elements, list):
                        raise RuntimeError("Overpass elements missing")
                    rel_el = next(
                        (
                            e
                            for e in elements
                            if isinstance(e, dict)
                            and str(e.get("type") or "").lower() == "relation"
                            and int(e.get("id") or 0) == int(rid)
                        ),
                        None,
                    )
                    tags = rel_el.get("tags") if isinstance(rel_el, dict) and isinstance(rel_el.get("tags"), dict) else {}
                    emit(JobEvent("object_phase", {"relation_id": rid, "phase": "build_geometry"}))
                    t_build0 = time.time()
                    geom = build_relation_geometry([e for e in elements if isinstance(e, dict)], rid)
                    t_build = time.time() - t_build0

                # Prefer fresh/fetched tags when available, otherwise fallback to preloaded details.
                if not tags:
                    tags = {}

                emit(JobEvent("object_phase", {"relation_id": rid, "phase": "write_osm_source"}))
                t_write0 = time.time()
                osm_path = write_object_geojson(p.osm_objects_dir, rid, tags, mapping(geom))
                t_write = time.time() - t_write0

            # Fallback tags for cache hits that may have incomplete properties.
            if not tags:
                tags = {}

            poly_count = count_polygons(geom)
            vertex_count = count_vertices(geom)

            land_path = None
            clipped_empty = False
            clipped_poly_count = None
            clipped_vertex_count = None
            t_clip = None
            if clip_land:
                emit(JobEvent("object_phase", {"relation_id": rid, "phase": "clip_land"}))
                t_clip0 = time.time()
                can_reuse_land_object = bool(osm_reused_from_cache and not force_refresh_osm_source)
                land_cached = _load_cached_land_object(p.land_objects_dir, rid) if can_reuse_land_object else None
                if land_cached is not None:
                    emit(JobEvent("object_phase", {"relation_id": rid, "phase": "use_land_only_cache"}))
                    cached_clipped_geom, _, cached_land_path = land_cached
                    land_object_cache_hits += 1
                    clipped = cached_clipped_geom
                    clipped_empty = False
                    clipped_poly_count = count_polygons(clipped)
                    clipped_vertex_count = count_vertices(clipped)
                    land_path = cached_land_path
                    emit(JobEvent("object_clipped_ready", {"relation_id": rid, "name": obj_name}))
                    t_clip = time.time() - t_clip0
                else:
                    land_object_cache_misses += 1
                    bbox = _geom_bbox(geom)
                    land_union, cache_hit = load_land_union_for_bbox(bbox, bbox_pad_deg=1.0)
                    if cache_hit:
                        clip_cache_hits += 1
                    else:
                        clip_cache_misses += 1
                    emit(
                        JobEvent(
                            "clip_cache_stats",
                            {"hits": int(clip_cache_hits), "misses": int(clip_cache_misses)},
                        )
                    )
                    clipped = geom.intersection(land_union)
                    if not getattr(clipped, "is_valid", True):
                        try:
                            clipped = clipped.buffer(0)
                        except Exception:
                            pass
                    t_clip = time.time() - t_clip0
                    if getattr(clipped, "is_empty", False):
                        clipped_empty = True
                    else:
                        clipped_poly_count = count_polygons(clipped)
                        clipped_vertex_count = count_vertices(clipped)
                        clipped_geojson = mapping(clipped)
                        land_path = write_object_geojson(p.land_objects_dir, rid, tags, clipped_geojson)
                        emit(JobEvent("object_clipped_ready", {"relation_id": rid, "name": obj_name}))

            name = preferred_name_from_tags(tags) or provided_name or obj_name or f"relation {rid}"
            per_object_stats[str(rid)] = {
                "name": name,
                "osm_source_path": str(osm_path),
                "land_only_path": str(land_path) if land_path else None,
                "clipped_empty": clipped_empty,
                "polygons": poly_count,
                "vertices": vertex_count,
                "land_only_polygons": clipped_poly_count,
                "land_only_vertices": clipped_vertex_count,
                "overpass_used": used_url,
                "overpass_elapsed_sec": used_elapsed,
                "time_fetch_sec": t_fetch,
                "time_build_sec": t_build,
                "time_write_sec": t_write,
                "time_clip_sec": t_clip,
                "osm_source_bytes": int(osm_path.stat().st_size) if osm_path.exists() else None,
                "land_only_bytes": int(land_path.stat().st_size) if land_path and land_path.exists() else None,
                "elapsed_sec": time.time() - t0,
                "updated_at_epoch": time.time(),
            }

            emit(JobEvent("object_stats", {"relation_id": rid, "stats": per_object_stats[str(rid)]}))

            objects[str(rid)] = {
                "relation_id": rid,
                "name": name,
                "slug": slugify(name),
                "updated_at_epoch": per_object_stats[str(rid)]["updated_at_epoch"],
                "osm_source_file": osm_path.name,
                "land_only_file": land_path.name if land_path else None,
            }

            ok += 1
            emit(JobEvent("object_done", {"relation_id": rid, "name": name, "ok": True}))
        except Exception as exc:
            failed += 1
            emit(JobEvent("object_done", {"relation_id": rid, "name": obj_name, "ok": False, "error": str(exc)}))
        emit(JobEvent("overall_progress", {"done": idx, "total": total, "ok": ok, "failed": failed}))

    manifest["adm_name"] = adm_name
    manifest["admin_level"] = admin_level
    manifest["updated_at_epoch"] = time.time()
    manifest["objects"] = objects
    save_manifest(p.manifest_path, manifest)

    emit(JobEvent("stage", {"stage": "rebuild_combined"}))
    rebuild_combined(p.osm_objects_dir, p.osm_combined_path)
    if clip_land:
        rebuild_combined(p.land_objects_dir, p.land_combined_path)

    stats = {
        "adm_name": adm_name,
        "admin_level": admin_level,
        "updated_at_epoch": time.time(),
        "job_elapsed_sec": time.time() - t_job0,
        "selected_count": total,
        "ok": ok,
        "failed": failed,
        "clip_cache_hits": int(clip_cache_hits),
        "clip_cache_misses": int(clip_cache_misses),
    }
    save_json(p.stats_path, stats)
    if clip_land:
        emit(
            JobEvent(
                "log",
                {
                    "message": (
                        f"Clip cache stats: hits={int(clip_cache_hits)}, "
                        f"misses={int(clip_cache_misses)}"
                    )
                },
            )
        )
        emit(
            JobEvent(
                "log",
                {
                    "message": (
                        "Land-only object cache: "
                        f"hits={int(land_object_cache_hits)}, misses={int(land_object_cache_misses)}"
                    )
                },
            )
        )
    emit(JobEvent("done", {"stats": stats}))
