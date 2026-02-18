from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or not str(v).strip() else str(v).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except Exception:
        return default


def _env_urls(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw or not str(raw).strip():
        return default
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return parts or default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    overpass_url: str
    http_user_agent: str
    http_timeout_sec: int
    download_timeout_sec: int
    osm_land_polygons_urls: list[str]

    @property
    def geojson_dir(self) -> Path:
        return self.data_dir / "geojson"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def land_polygons_zip(self) -> Path:
        return self.cache_dir / "land-polygons-split-4326.zip"


settings = Settings(
    data_dir=Path(_env("DATA_DIR", str(Path(__file__).resolve().parents[2] / "data"))),
    overpass_url=_env("OVERPASS_URL", "https://maps.mail.ru/osm/tools/overpass/api/"),
    http_user_agent=_env("HTTP_USER_AGENT", "osm-batch-downloader/0.1.0"),
    http_timeout_sec=_env_int("HTTP_TIMEOUT_SEC", 180),
    download_timeout_sec=_env_int("DOWNLOAD_TIMEOUT_SEC", 1800),
    osm_land_polygons_urls=_env_urls(
        "OSM_LAND_POLYGONS_URLS",
        ["https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip"],
    ),
)

