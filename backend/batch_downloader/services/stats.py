from __future__ import annotations

from typing import Any


def _iter_geoms(geom: Any):
    if geom is None:
        return
    t = getattr(geom, "geom_type", None)
    if t in {"GeometryCollection", "MultiPolygon", "MultiLineString", "MultiPoint"}:
        for g in getattr(geom, "geoms", []) or []:
            yield from _iter_geoms(g)
    else:
        yield geom


def count_polygons(geom: Any) -> int:
    c = 0
    for g in _iter_geoms(geom):
        if getattr(g, "geom_type", None) == "Polygon":
            c += 1
    return c


def _count_coords(obj: Any) -> int:
    if obj is None:
        return 0
    if isinstance(obj, (list, tuple)):
        if len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
            return 1
        return sum(_count_coords(x) for x in obj)
    return 0


def count_vertices(geom: Any) -> int:
    try:
        gj = geom.__geo_interface__
    except Exception:
        return 0
    coords = gj.get("coordinates") if isinstance(gj, dict) else None
    return _count_coords(coords)

