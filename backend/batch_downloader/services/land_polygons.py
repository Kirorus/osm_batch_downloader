from __future__ import annotations

import json
import time
import zipfile
from collections import OrderedDict
from math import ceil, floor
from pathlib import Path
from typing import Any, Callable
import threading

import geopandas as gpd
import requests
from shapely.geometry import box
from requests.adapters import HTTPAdapter

from batch_downloader.settings import settings


class LandPolygonsError(RuntimeError):
    pass


_LAND_UNION_CACHE_MAX = 96
_BBOX_TILE_DEG = 5.0
_land_union_cache: "OrderedDict[tuple[int, int, int, int, int], Any]" = OrderedDict()
_land_geometry_store: gpd.GeoDataFrame | None = None
_SESSION_LOCAL = threading.local()


def _get_http_session() -> requests.Session:
    session = getattr(_SESSION_LOCAL, "session", None)
    if session is not None:
        return session
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    _SESSION_LOCAL.session = session
    return session


def _resolve_shapefile_in_zip(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        shp_files = [name for name in zf.namelist() if name.lower().endswith(".shp")]
    if not shp_files:
        raise LandPolygonsError("No .shp found in land polygons archive")
    preferred = [name for name in shp_files if name.lower().endswith("land_polygons.shp")]
    shp_name = preferred[0] if preferred else shp_files[0]
    return f"zip://{zip_path}!{shp_name}"


def land_polygons_status() -> dict[str, Any]:
    p = settings.land_polygons_zip
    if not p.exists():
        return {"present": False}
    st = p.stat()
    meta_path = p.with_suffix(".meta.json")
    meta = None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text("utf-8"))
        except Exception:
            meta = None
    return {
        "present": True,
        "path": str(p),
        "size_bytes": int(st.st_size),
        "mtime_epoch": float(st.st_mtime),
        "meta": meta,
    }


def download_land_polygons(
    *,
    force: bool = False,
    on_progress: Callable[[int, int | None, float], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    dst = settings.land_polygons_zip
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        return dst

    urls = settings.osm_land_polygons_urls or []
    session = _get_http_session()
    last_error: Exception | None = None
    for url in urls:
        try:
            tmp = dst.with_suffix(dst.suffix + ".tmp")
            t0 = time.time()
            with session.get(url, stream=True, timeout=float(settings.download_timeout_sec)) as r:
                r.raise_for_status()
                total = r.headers.get("Content-Length")
                total_i = int(total) if total and total.isdigit() else None
                done = 0
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if should_cancel and should_cancel():
                            raise LandPolygonsError("Cancelled")
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, total_i, time.time() - t0)
            tmp.replace(dst)
            meta = {"download_url": url, "downloaded_at_epoch": time.time()}
            dst.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
            return dst
        except Exception as exc:
            last_error = exc
            continue
    raise LandPolygonsError(f"Failed to download land polygons: {last_error}")


def load_land_polygons_for_bbox(
    bbox: tuple[float, float, float, float],
    *,
    bbox_pad_deg: float = 1.0,
) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox
    padded = (minx - bbox_pad_deg, miny - bbox_pad_deg, maxx + bbox_pad_deg, maxy + bbox_pad_deg)
    shp_path = _resolve_shapefile_in_zip(settings.land_polygons_zip)
    land = gpd.read_file(shp_path, bbox=padded)
    if land.empty:
        raise LandPolygonsError("Land polygons empty for this area")
    if land.crs is None:
        land = land.set_crs("EPSG:4326")
    return land[["geometry"]]


def _bbox_cache_key(bbox: tuple[float, float, float, float], bbox_pad_deg: float) -> tuple[int, int, int, int, int]:
    minx, miny, maxx, maxy = bbox
    padded_minx = minx - bbox_pad_deg
    padded_miny = miny - bbox_pad_deg
    padded_maxx = maxx + bbox_pad_deg
    padded_maxy = maxy + bbox_pad_deg
    # Use coarse tiles to maximize reuse across neighboring/nearby objects.
    tile = float(_BBOX_TILE_DEG)
    return (
        floor(padded_minx / tile),
        floor(padded_miny / tile),
        ceil(padded_maxx / tile),
        ceil(padded_maxy / tile),
        int(round(bbox_pad_deg * 100)),
    )


def _get_land_geometry_store() -> gpd.GeoDataFrame:
    global _land_geometry_store
    if _land_geometry_store is not None:
        return _land_geometry_store
    shp_path = _resolve_shapefile_in_zip(settings.land_polygons_zip)
    land = gpd.read_file(shp_path)[["geometry"]]
    if land.empty:
        raise LandPolygonsError("Land polygons dataset is empty")
    if land.crs is None:
        land = land.set_crs("EPSG:4326")
    _land_geometry_store = land
    return _land_geometry_store


def load_land_union_for_bbox(
    bbox: tuple[float, float, float, float],
    *,
    bbox_pad_deg: float = 1.0,
):
    key = _bbox_cache_key(bbox, bbox_pad_deg)
    cached = _land_union_cache.get(key)
    if cached is not None:
        _land_union_cache.move_to_end(key)
        return cached, True

    minx_i, miny_i, maxx_i, maxy_i, _ = key
    tile = float(_BBOX_TILE_DEG)
    query_bbox = (minx_i * tile, miny_i * tile, maxx_i * tile, maxy_i * tile)
    # Fast path: global in-memory land dataset + spatial index.
    # Fallback to coarse bbox disk read if memory/index path is unavailable.
    try:
        land_store = _get_land_geometry_store()
        query_geom = box(*query_bbox)
        subset = None
        try:
            sidx = land_store.sindex
            idx = list(sidx.intersection(query_geom.bounds))
            if idx:
                subset = land_store.iloc[idx]
        except Exception:
            subset = None
        if subset is None:
            mask = land_store.intersects(query_geom)
            subset = land_store[mask]
        if subset.empty:
            raise LandPolygonsError("Land polygons empty for this area")
        land = subset
    except Exception:
        land = load_land_polygons_for_bbox(query_bbox, bbox_pad_deg=0.0)

    unioned = land.geometry.union_all()
    if getattr(unioned, "is_empty", False):
        raise LandPolygonsError("Land polygons union is empty for this area")

    _land_union_cache[key] = unioned
    if len(_land_union_cache) > _LAND_UNION_CACHE_MAX:
        _land_union_cache.popitem(last=False)
    return unioned, False
