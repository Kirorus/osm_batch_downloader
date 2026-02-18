from __future__ import annotations

from typing import Any

from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union


def build_relation_geometry(elements: list[dict[str, Any]], relation_id: int) -> Polygon | Any:
    rel_el: dict[str, Any] | None = None
    ways: list[dict[str, Any]] = []
    nodes_by_id: dict[int, tuple[float, float]] = {}
    for el in elements:
        t = str(el.get("type") or "").lower()
        if t == "relation" and int(el.get("id") or 0) == int(relation_id):
            rel_el = el
        elif t == "way":
            ways.append(el)
        elif t == "node":
            try:
                nid = int(el.get("id"))
                lat = float(el.get("lat"))
                lon = float(el.get("lon"))
                nodes_by_id[nid] = (lon, lat)
            except Exception:
                continue

    if not rel_el:
        raise RuntimeError("Relation element not found in Overpass response")

    member_way_ids: set[int] = set()
    members = rel_el.get("members") if isinstance(rel_el.get("members"), list) else []
    for m in members:
        if not isinstance(m, dict):
            continue
        if str(m.get("type") or "").lower() != "way":
            continue
        try:
            member_way_ids.add(int(m.get("ref")))
        except Exception:
            continue
    if member_way_ids:
        ways = [w for w in ways if int(w.get("id") or 0) in member_way_ids]

    lines: list[LineString] = []
    for w in ways:
        geom_list = w.get("geometry") if isinstance(w.get("geometry"), list) else []
        coords: list[tuple[float, float]] = []
        if geom_list:
            for pt in geom_list:
                if not isinstance(pt, dict):
                    continue
                lat = pt.get("lat")
                lon = pt.get("lon")
                if lat is None or lon is None:
                    continue
                try:
                    coords.append((float(lon), float(lat)))
                except Exception:
                    continue
        else:
            node_refs = w.get("nodes") if isinstance(w.get("nodes"), list) else []
            for ref in node_refs:
                try:
                    nid = int(ref)
                except Exception:
                    continue
                if nid in nodes_by_id:
                    coords.append(nodes_by_id[nid])
        if len(coords) >= 2:
            try:
                lines.append(LineString(coords))
            except Exception:
                continue

    if not lines:
        raise RuntimeError("Relation has no way geometry")

    unioned = unary_union(lines)
    try:
        merged = linemerge(unioned)
    except Exception:
        # Some relations collapse to a single LineString here; linemerge then raises
        # "Cannot linemerge LINESTRING ...". Keep the unioned geometry and continue.
        merged = unioned
    if not merged or getattr(merged, "is_empty", False):
        raise RuntimeError("Relation geometry merge failed")

    polys = list(polygonize(unioned))
    geom = polys[0] if len(polys) == 1 else unary_union(polys) if polys else merged
    try:
        geom = geom.buffer(0)
    except Exception:
        pass
    return geom
