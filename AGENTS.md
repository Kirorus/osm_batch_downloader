# AGENTS.md

This file is a handoff guide for AI agents working on `osm_batch_downloader`.

## Project at a glance

- Purpose: batch download of OSM administrative boundaries, with optional land clipping.
- Frontend: `Svelte + Vite + TypeScript` (`frontend/`).
- Backend: `FastAPI` (`backend/batch_downloader/`).
- Runtime: single Docker service (`docker-compose.yml`) exposing API/UI on `:8282`.

## Key tech and heavy deps

- Python: `fastapi`, `uvicorn`, `requests`.
- Geo stack (heavy/native): `geopandas`, `shapely`, `fiona`, `pyproj`, GDAL libs in Docker image.
- Frontend mapping: `maplibre-gl`.

## Source layout

- `backend/batch_downloader/main.py`: API routes and job creation.
- `backend/batch_downloader/services/catalog.py`: IDs/items/search from Overpass + caches.
- `backend/batch_downloader/services/preview.py`: preview geometry fetch + scoped caching.
- `backend/batch_downloader/services/downloader.py`: export pipeline and land clipping.
- `backend/batch_downloader/services/storage.py`: file naming + output paths + combined rebuild.
- `frontend/src/lib/stores.ts`: app state and API payloads.
- `frontend/src/components/MapView.svelte`: preview fetching and map rendering.
- `frontend/src/components/progress/*`: export progress UI.
- `frontend/src/lib/mapStyle.ts`: basemap provider list and raster style builder.

## Current output structure and naming (important)

### Scope folder

Outputs are written under:

- `data/geojson/<scope>/admin_level=<N>/`

Scope naming:

- World: `world_GLOBAL_r0`
- Parent scope: `<english_name>_<ISO2>_r<parent_relation_id>`
  - Example: `england_GB_r62149`

### Object files

Stored in:

- `osm_source/objects/`
- `land_only/objects/`

Filename format:

- `english-name__ISO2__r<ID>.geojson`
- English name first. Transliteration only when no English name is available.
- ISO2 fallback is `xx`.

### Combined files

Stored in:

- `osm_source/`
- `land_only/`

Filename format:

- `<scope>_admin_level_<N>_osm_source.geojson`
- `<scope>_admin_level_<N>_land_only.geojson`

## Data flow (high level)

1. `Load Objects` -> `POST /api/catalog/ids`
   - World is allowed only for `admin_level=2`.
   - Fast paths return items with tags to avoid extra details loading.
2. Map preview -> `POST /api/catalog/preview`
   - Frontend sends `relation_ids`, `admin_level`, `parent_relation_id`, `overpass_url`.
   - Backend resolves scope and caches preview geometry into scoped `osm_source/objects` for normal UI flow.
3. Export -> `POST /api/jobs`
   - Uses selected IDs.
   - Reuses valid geometry cache from scoped `osm_source/objects` when available.
   - Optional `clip_land`.

## Caching behavior

- Catalog caches: `data/cache/catalog/...`
  - IDs/items TTL: 24h
  - Search TTL: 6h
- Preview cache files (`data/cache/preview/...`) are now mainly fallback/non-scoped path.
- Preferred geometry cache for export/preview is scoped `data/geojson/.../osm_source/objects`.

## Product constraints already implemented

- No pagination in results list (full filtered list shown).
- No server-side geometry simplification for preview.
- Geometry preview loads for selected/hovered objects; not all objects at once.
- Background details loading (`bounds/center` post-load) is intentionally removed.
- Object list checkbox and shift-range selection are implemented.
- Basemap switching is done via a map control (top-right), stored in `localStorage` (`basemapId`).

## GitHub / repo hygiene (important)

- Do **not** commit generated data and caches:
  - `data/cache/`
  - `data/geojson/`
- Do **not** commit frontend artifacts:
  - `frontend/node_modules/`
  - `frontend/dist/`
- Do **not** commit local AI/editor files:
  - `.cursor/`, `.claude/`
- These are enforced by `.gitignore`/`.dockerignore` in the repo root.

## Commands

### Docker (primary)

- Build: `docker compose build`
- Run: `docker compose up -d`
- Logs: `docker compose logs -f osm-batch-downloader`

### Frontend only

- `cd frontend && npm ci`
- `npm run dev`
- `npm run build`

### Backend only

- `cd backend && pip install -r requirements.txt`
- `uvicorn batch_downloader.main:app --host 0.0.0.0 --port 8000`

## Manual verification checklist

- `Load Objects` works for world (`admin_level=2`) and parent scopes.
- Preview request no longer causes repeated `502` due to fallback logic.
- Selected preview geometries appear and progress updates correctly.
- Export writes files to new scope folder naming.
- Object filenames and combined filenames match current conventions.
- Re-run export on same scope uses cache from `osm_source/objects` (no unnecessary Overpass fetch).

## Common pitfalls

- Docker credential helper issue can fail build with `error getting credentials`; re-run build or restart Docker Desktop.
- If preview caching appears wrong, verify frontend still sends scope fields in `/api/catalog/preview` payload.
- Do not reintroduce world scope for `admin_level != 2`.
- Keep naming logic centralized in `storage.py`/`utils.py` to avoid drift.

## Editing guidance

- Keep diffs focused; avoid broad refactors without need.
- For naming/path changes, update backend + frontend display text together.
- Preserve current cache-first strategy for export and preview.
