from __future__ import annotations

from typing import Any

from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, transform, unary_union

Coord = tuple[float, float]


def _is_antimeridian_candidate(way_coords: list[list[Coord]]) -> bool:
    if not way_coords:
        return False
    min_lon = 180.0
    max_lon = -180.0
    has_far_west = False
    has_far_east = False
    has_any = False

    for coords in way_coords:
        for lon, _lat in coords:
            has_any = True
            if lon < min_lon:
                min_lon = lon
            if lon > max_lon:
                max_lon = lon
            if lon < -150.0:
                has_far_west = True
            if lon > 150.0:
                has_far_east = True

    if not has_any:
        return False
    span = max_lon - min_lon
    return has_far_west and has_far_east and span > 300.0


def _unwrap_way_longitudes(coords: list[Coord]) -> list[Coord]:
    if len(coords) < 2:
        return coords
    out: list[Coord] = [coords[0]]
    prev_lon = coords[0][0]
    for lon, lat in coords[1:]:
        cur_lon = lon
        while (cur_lon - prev_lon) > 180.0:
            cur_lon -= 360.0
        while (cur_lon - prev_lon) < -180.0:
            cur_lon += 360.0
        out.append((cur_lon, lat))
        prev_lon = cur_lon
    return out


def _shift_geometry_to_360(geom: Any) -> Any:
    return transform(
        lambda x, y, z=None: (((x + 360.0) % 360.0), y) if z is None else (((x + 360.0) % 360.0), y, z),
        geom,
    )


def build_relation_geometry(
    elements: list[dict[str, Any]],
    relation_id: int,
    *,
    fix_antimeridian: bool = True,
) -> Polygon | Any:
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

    way_coords: list[list[Coord]] = []
    for w in ways:
        geom_list = w.get("geometry") if isinstance(w.get("geometry"), list) else []
        coords: list[Coord] = []
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
            way_coords.append(coords)

    if not way_coords:
        raise RuntimeError("Relation has no way geometry")

    use_antimeridian_fix = bool(fix_antimeridian) and _is_antimeridian_candidate(way_coords)
    prepared_way_coords = (
        [_unwrap_way_longitudes(coords) for coords in way_coords]
        if use_antimeridian_fix
        else way_coords
    )

    lines: list[LineString] = []
    for coords in prepared_way_coords:
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
    if use_antimeridian_fix:
        try:
            geom = _shift_geometry_to_360(geom)
            geom = geom.buffer(0)
        except Exception:
            pass
    return geom
