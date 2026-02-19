# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Web service for batch downloading OpenStreetMap administrative boundaries as GeoJSON, with optional land polygon clipping. Single Docker container serves both the FastAPI backend and Svelte frontend.

## Commands

### Docker (primary)

```bash
docker compose build
docker compose up -d
docker compose logs -f osm-batch-downloader
# UI available at http://localhost:8282
```

### Frontend only

```bash
cd frontend && npm ci
npm run dev       # dev server on :5176
npm run build
npm run typecheck
```

### Backend only

```bash
cd backend && pip install -r requirements.txt
uvicorn batch_downloader.main:app --host 0.0.0.0 --port 8000
```

No automated test suite exists. Use the manual verification checklist in `AGENTS.md`.

## Architecture

**Backend** (`backend/batch_downloader/`): FastAPI app with services layer. All routes are in `main.py`; business logic lives in `services/`.

**Frontend** (`frontend/src/`): Svelte + TypeScript + MapLibre GL. State managed via Svelte stores in `lib/stores.ts`. API calls in `lib/api.ts`.

### Key backend services

| File | Responsibility |
|------|----------------|
| `services/catalog.py` | Fetch OSM relation IDs/items from Overpass; 24h cache |
| `services/preview.py` | Fetch & cache preview geometries per scope |
| `services/downloader.py` | Export pipeline; reuses preview cache; optional land clipping |
| `services/jobs.py` | Async job management; SSE progress streaming |
| `services/storage.py` | **Central naming authority** — all file/path logic lives here |
| `services/overpass.py` | Overpass API HTTP client |
| `services/osm_geometry.py` | Build Shapely geometries from OSM relation members |
| `services/land_polygons.py` | Download and apply OSM land-polygons clipping |
| `utils.py` | Slugify, transliteration, English name extraction |
| `settings.py` | All env var configuration with defaults |

### Data flow

1. **Load Objects** (`POST /api/catalog/ids`): Overpass query → cached IDs/items (24h TTL). World scope is restricted to `admin_level=2` only.
2. **Preview** (`POST /api/catalog/preview`): Frontend sends `relation_ids + scope fields` → geometries fetched and cached in scoped `osm_source/objects/`.
3. **Export** (`POST /api/jobs`): Reuses scoped geometry cache when available; runs async; streams progress via SSE (`GET /api/jobs/{id}/events`).

### Output structure and naming

```
data/geojson/<scope>/admin_level=<N>/
  osm_source/
    objects/<english-name>__<ISO2>__r<ID>.geojson
    <scope>_admin_level_<N>_osm_source.geojson   # combined
  land_only/
    objects/<english-name>__<ISO2>__r<ID>.geojson
    <scope>_admin_level_<N>_land_only.geojson    # combined
```

Scope naming: `world_GLOBAL_r0` (world) or `<english_name>_<ISO2>_r<parent_id>` (e.g. `england_GB_r62149`).

Object filenames: English name first, ISO2 fallback is `xx`. Naming/path logic is centralized in `storage.py` — do not duplicate it.

### Caching layers

- Catalog: `data/cache/catalog/` (IDs/items: 24h TTL, search: 6h TTL)
- Preview/export geometry: `data/geojson/.../osm_source/objects/` (preferred, scoped)
- Legacy preview fallback: `data/cache/preview/` (keyed by Overpass endpoint hash)
- `force_refresh_osm_source=true` bypasses geometry cache

## Key constraints

- World scope is only valid for `admin_level=2` — do not reintroduce it for other levels.
- No server-side geometry simplification for preview.
- No pagination in the object results list.
- Basemap selection is persisted in `localStorage` (`basemapId`).
- Keep diffs focused; preserve cache-first strategy for export and preview.
- For naming/path changes, update backend and frontend display text together.

## Repo hygiene

Do not commit: `data/cache/`, `data/geojson/`, `frontend/node_modules/`, `frontend/dist/`, `.cursor/`, `.claude/`. All enforced by `.gitignore`.
