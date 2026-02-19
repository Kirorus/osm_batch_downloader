from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from batch_downloader.services import catalog
from batch_downloader.services.jobs import JobManager, sse_format
from batch_downloader.services.land_polygons import land_polygons_status
from batch_downloader.services.overpass import OverpassError
from batch_downloader.utils import iso2_from_tags, preferred_english_name_from_tags, slugify


class CatalogIdsRequest(BaseModel):
    admin_level: str = Field(..., min_length=1)
    parent_relation_id: int | None = None


class CatalogDetailsRequest(BaseModel):
    relation_ids: list[int] = Field(default_factory=list)


class CatalogPreviewRequest(BaseModel):
    relation_ids: list[int] = Field(default_factory=list)
    admin_level: str | None = None
    parent_relation_id: int | None = None
    fix_antimeridian: bool = True
    overpass_url: str | None = None


class AreaSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    admin_level: str | None = None
    limit: int = 50


class CreateJobRequest(BaseModel):
    admin_level: str = Field(..., min_length=1)
    parent_relation_id: int | None = None
    selected_relation_ids: list[int] = Field(default_factory=list)
    relation_names: dict[str, str] = Field(default_factory=dict)
    clip_land: bool = False
    force_refresh_osm_source: bool = False
    fix_antimeridian: bool = True
    overpass_url: str | None = None


job_manager = JobManager()

app = FastAPI(title="OSM Batch Admin Boundaries Downloader")

# Frontend build is copied into the package directory inside the Docker image.
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")


@app.get("/api/health")
def health() -> dict[str, Any]:
    lp = land_polygons_status()
    active = sum(1 for j in job_manager._jobs.values() if j.status == "running")
    return {
        "ok": True,
        "land_polygons_present": lp.get("present", False),
        "active_jobs": active,
    }


@app.get("/api/land-polygons/status")
def api_land_polygons_status() -> dict[str, Any]:
    return land_polygons_status()


@app.post("/api/areas/search")
def api_area_search(body: AreaSearchRequest) -> dict[str, Any]:
    try:
        items = catalog.search_admin_areas(query=body.query, admin_level=body.admin_level, limit=body.limit)
        return {"items": items}
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/catalog/ids")
def api_catalog_ids(body: CatalogIdsRequest) -> dict[str, Any]:
    admin_level = str(body.admin_level).strip()
    is_world = int(body.parent_relation_id or 0) == 0
    if is_world and admin_level != "2":
        raise HTTPException(status_code=400, detail="Worldwide scope is available only for admin_level=2")
    try:
        if is_world and admin_level == "2":
            items = catalog.list_countries_items_fast()
            ids = [int(x["relation_id"]) for x in items if isinstance(x, dict) and int(x.get("relation_id") or 0) > 0]
            return {"relation_ids": ids, "count": len(ids), "items": items}
        if not is_world and int(body.parent_relation_id or 0) > 0:
            items = catalog.list_parent_items_fast(admin_level=admin_level, parent_relation_id=int(body.parent_relation_id))
            ids = [int(x["relation_id"]) for x in items if isinstance(x, dict) and int(x.get("relation_id") or 0) > 0]
            return {"relation_ids": ids, "count": len(ids), "items": items}
        ids = catalog.list_relation_ids(admin_level=admin_level, parent_relation_id=body.parent_relation_id)
        return {"relation_ids": ids, "count": len(ids)}
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/catalog/details")
def api_catalog_details(body: CatalogDetailsRequest) -> dict[str, Any]:
    ids = [int(x) for x in body.relation_ids if int(x) > 0]
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail="Too many relation_ids (max 500)")
    try:
        items = catalog.fetch_relation_details(ids)
        return {"items": items}
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/catalog/preview")
async def api_catalog_preview(body: CatalogPreviewRequest) -> dict[str, Any]:
    ids = [int(x) for x in body.relation_ids if int(x) > 0]
    if len(ids) > 400:
        raise HTTPException(status_code=400, detail="Too many relation_ids for preview (max 400)")
    from batch_downloader.services.preview import preview_features

    try:
        preview_adm_name: str | None = None
        preview_admin_level: str | None = None
        if body.admin_level is not None:
            preview_admin_level = str(body.admin_level).strip()
            if preview_admin_level:
                preview_adm_name = _format_adm_name(body.parent_relation_id, preview_admin_level)
        fc = await asyncio.to_thread(
            preview_features,
            ids,
            adm_name=preview_adm_name,
            admin_level=preview_admin_level,
            fix_antimeridian=bool(body.fix_antimeridian),
            overpass_url=body.overpass_url,
        )
        return fc
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/catalog/land-preview")
async def api_catalog_land_preview(body: CatalogPreviewRequest) -> dict[str, Any]:
    ids = [int(x) for x in body.relation_ids if int(x) > 0]
    if len(ids) > 200:
        raise HTTPException(status_code=400, detail="Too many relation_ids for land preview (max 200)")
    admin_level = str(body.admin_level or "").strip()
    if not admin_level:
        raise HTTPException(status_code=400, detail="admin_level is required for land preview")
    try:
        from batch_downloader.services.preview import land_preview_features

        adm_name = _format_adm_name(body.parent_relation_id, admin_level)
        fc = await asyncio.to_thread(
            land_preview_features,
            ids,
            adm_name=adm_name,
            admin_level=admin_level,
        )
        return fc
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _format_adm_name(parent_relation_id: int | None, _admin_level: str) -> str:
    if not parent_relation_id:
        return "world_GLOBAL_r0"
    details = catalog.fetch_relation_details([int(parent_relation_id)])
    if not details:
        return f"region_xx_r{int(parent_relation_id)}"
    tags = details[0].get("tags") if isinstance(details[0].get("tags"), dict) else {}
    name_en = preferred_english_name_from_tags(tags) or f"relation {int(parent_relation_id)}"
    scope_name = slugify(name_en, max_len=50).replace("-", "_")
    iso2 = iso2_from_tags(tags) or "XX"
    return f"{scope_name}_{iso2}_r{int(parent_relation_id)}"


@app.post("/api/jobs")
async def api_create_job(body: CreateJobRequest) -> dict[str, Any]:
    admin_level = str(body.admin_level).strip()
    is_world = int(body.parent_relation_id or 0) == 0
    if is_world and admin_level != "2":
        raise HTTPException(status_code=400, detail="Worldwide scope is available only for admin_level=2")

    selected = [int(x) for x in body.selected_relation_ids if int(x) > 0]
    if not selected:
        raise HTTPException(status_code=400, detail="No selected_relation_ids provided")
    if len(selected) > 5000:
        raise HTTPException(status_code=400, detail="Too many selected_relation_ids (max 5000)")

    adm_name = _format_adm_name(body.parent_relation_id, body.admin_level)
    params = {
        "adm_name": adm_name,
        "admin_level": admin_level,
        "relation_ids": selected,
        "relation_names": body.relation_names,
        "clip_land": bool(body.clip_land),
        "force_refresh_osm_source": bool(body.force_refresh_osm_source),
        "fix_antimeridian": bool(body.fix_antimeridian),
        "overpass_url": body.overpass_url,
    }
    job = await job_manager.create_job(params)
    return {"job_id": job.job_id, "adm_name": adm_name, "admin_level": admin_level}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str) -> dict[str, Any]:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "created_at_epoch": job.created_at_epoch,
        "params": job.params,
        "progress": job.progress,
        "error": job.error,
        "cancelled": job.cancelled,
    }


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel(job_id: str) -> dict[str, Any]:
    ok = await job_manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/events")
async def api_events(job_id: str) -> StreamingResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def gen():
        yield "event: hello\ndata: {}\n\n"
        while True:
            job.flush_coalesced_events()
            try:
                ev = await asyncio.wait_for(job.queue.get(), timeout=15.0)
                job.on_event_delivered(ev)
                yield sse_format(ev)
                if ev.type == "job_finished":
                    break
            except asyncio.TimeoutError:
                job.flush_coalesced_events()
                yield "event: ping\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/{path:path}")
def spa_fallback(path: str) -> Any:
    if not static_dir.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    requested = (static_dir / path).resolve()
    try:
        if requested.is_file() and str(requested).startswith(str(static_dir.resolve())):
            return FileResponse(str(requested))
    except Exception:
        pass
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="index.html not found")
