from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from batch_downloader.settings import settings
from batch_downloader.utils import iso2_from_tags, preferred_english_name_from_tags, slugify


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, obj: Any) -> None:
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=False))


def _rel_glob(prefix_dir: Path, relation_id: int) -> list[Path]:
    rid = int(relation_id)
    seen: dict[str, Path] = {}
    for p in prefix_dir.glob(f"r{rid}__*.geojson"):
        seen[str(p)] = p
    for p in prefix_dir.glob(f"*__r{rid}.geojson"):
        seen[str(p)] = p
    return list(seen.values())


def object_filename(relation_id: int, tags: dict[str, Any]) -> str:
    name = preferred_english_name_from_tags(tags) or f"relation {int(relation_id)}"
    iso2 = iso2_from_tags(tags) or "xx"
    return f"{slugify(name)}__{iso2}__r{int(relation_id)}.geojson"


@dataclass(frozen=True)
class ScopePaths:
    base_dir: Path
    manifest_path: Path
    stats_path: Path
    osm_objects_dir: Path
    osm_combined_path: Path
    land_objects_dir: Path
    land_combined_path: Path


def scope_paths(*, adm_name: str, admin_level: str) -> ScopePaths:
    base = settings.geojson_dir / adm_name / f"admin_level={admin_level}"
    stem = f"{adm_name}_admin_level_{admin_level}"
    return ScopePaths(
        base_dir=base,
        manifest_path=base / "manifest.json",
        stats_path=base / "stats.json",
        osm_objects_dir=base / "osm_source" / "objects",
        osm_combined_path=base / "osm_source" / f"{stem}_osm_source.geojson",
        land_objects_dir=base / "land_only" / "objects",
        land_combined_path=base / "land_only" / f"{stem}_land_only.geojson",
    )


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"objects": {}}
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else {"objects": {}}
    except Exception:
        return {"objects": {}}


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    _atomic_write_json(path, manifest)


def save_json(path: Path, obj: Any) -> None:
    _atomic_write_json(path, obj)


def write_object_geojson(objects_dir: Path, relation_id: int, tags: dict[str, Any], geometry_geojson: dict[str, Any]) -> Path:
    safe_tags = tags if isinstance(tags, dict) else {}
    objects_dir.mkdir(parents=True, exist_ok=True)

    filename = object_filename(relation_id, safe_tags)
    out_path = objects_dir / filename

    for p in _rel_glob(objects_dir, relation_id):
        if p.name != filename:
            try:
                p.unlink()
            except Exception:
                pass

    feature = {
        "type": "Feature",
        "geometry": geometry_geojson,
        "properties": {
                **safe_tags,
            "osm_type": "relation",
            "osm_id": int(relation_id),
        },
    }
    fc = {"type": "FeatureCollection", "features": [feature]}
    _atomic_write_json(out_path, fc)
    return out_path


def rebuild_combined(objects_dir: Path, combined_path: Path) -> None:
    objects_dir.mkdir(parents=True, exist_ok=True)
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = combined_path.with_suffix(combined_path.suffix + f".{os.getpid()}.tmp")

    files = sorted(objects_dir.glob("*.geojson"))
    with tmp.open("w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[')
        first = True
        for p in files:
            try:
                raw = json.loads(p.read_text("utf-8"))
                feats = raw.get("features") if isinstance(raw, dict) else None
                if not isinstance(feats, list) or not feats:
                    continue
                feat = feats[0]
                if not isinstance(feat, dict):
                    continue
            except Exception:
                continue
            if not first:
                f.write(",")
            first = False
            json.dump(feat, f, ensure_ascii=False)
        f.write("]}")
    tmp.replace(combined_path)
