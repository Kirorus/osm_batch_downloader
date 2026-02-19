<script lang="ts">
  import maplibregl, { type GeoJSONSource, type Map } from "maplibre-gl";
  import { onDestroy, onMount } from "svelte";
  import { apiPost } from "../lib/api";
  import { rasterStyleForBasemap, getBasemap, BASEMAPS } from "../lib/mapStyle";
  import type { AreaItem } from "../lib/types";
  import MapHud from "./map/MapHud.svelte";
  import {
    adminLevel,
    allIds,
    itemsById,
    parentRelationId,
    selected,
    scopeMode,
    visibleIds,
    overpassUrl,
    showOnlySelectedOnMap,
    previewLoadProgress,
    liveClipReadyEvent,
    basemapId,
    toggle,
  } from "../lib/stores";

  type Feature = {
    type: "Feature";
    id: number;
    geometry: any;
    properties: Record<string, unknown>;
  };

  let container: HTMLDivElement;
  let map: Map | null = null;
  let source: GeoJSONSource | null = null;
  let popup: maplibregl.Popup | null = null;

  const selectedColor = "#3b82f6";
  const dimColor = "#64748b";
  const hoverColor = "#38bdf8";
  const MAX_DETAILED_PREVIEW_GEOMS = 300;
  // High-fidelity preview geometry; OOM protection is handled by the detailed-geometry cap.
  const AREAS_SOURCE_MAXZOOM = 18;
  const AREAS_SOURCE_TOLERANCE = 0.1;
  const AREAS_SOURCE_BUFFER = 128;

  const geomById = new Map<number, Feature>();
  let renderCount = 0;
  let renderTotalCount = 0;
  let loadedGeomCount = 0;
  let pendingGeomCount = 0;

  let fetchRunning = false;
  let fetchAbort: AbortController | null = null;
  let scheduleTimer: number | null = null;
  let retryEnsureTimer: number | null = null;
  const inFlightGeomIds = new Set<number>();
  const failedGeomRetryUntil = new Map<number, number>();

  let prevSelected = new Set<number>();
  let hoveredId: number | null = null;
  let lastAllIdsRef: number[] | null = null;

  // Local mirrors of store values (for use in non-reactive map callbacks)
  // Named without $ prefix to avoid Svelte auto-subscription collision
  let _allIds: number[] = [];
  let _adminLevel = "2";
  let _itemsById: Map<number, AreaItem> = new Map();
  let _parentRelationId: number | null = null;
  let _selected: Set<number> = new Set();
  let _scopeMode: "world" | "parent" = "world";
  let _visibleIds: number[] = [];
  let _overpassUrl = "";
  let _showOnlySelectedOnMap = false;
  let _basemapId = "";
  const appliedClipIds = new Set<number>();
  const pendingClipFetchIds = new Set<number>();
  let clipFetchTimer: number | null = null;
  let clipFetchRunning = false;
  let mapLoaded = false;
  let basemapControl: (maplibregl.IControl & { refresh?: () => void; close?: () => void }) | null = null;

  const unsubs: (() => void)[] = [];

  function boundsToPolygon(b: { minlat: number; minlon: number; maxlat: number; maxlon: number }) {
    const { minlon, minlat, maxlon, maxlat } = b;
    return {
      type: "Polygon",
      coordinates: [[
        [minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat],
      ]],
    } as const;
  }

  function bboxFeature(id: number): Feature | null {
    const item = _itemsById.get(id);
    const b = item?.bounds;
    if (!b) return null;
    return {
      type: "Feature",
      id,
      geometry: boundsToPolygon(b),
      properties: { relation_id: id, name: item?.name ?? `relation ${id}`, preview_kind: "bbox" },
    };
  }

  function computeRenderIds(): number[] {
    if (_showOnlySelectedOnMap) return Array.from(_selected);
    const base = (_visibleIds && _visibleIds.length ? _visibleIds : _allIds) || [];
    if (base.length <= 2000) {
      const s = new Set<number>(base);
      for (const id of _selected) s.add(id);
      return Array.from(s);
    }
    const s = new Set<number>();
    for (const id of base.slice(0, 2000)) s.add(id);
    for (const id of _selected) s.add(id);
    return Array.from(s);
  }

  function detailedPreviewTargetIds(includeHover = false): number[] {
    const ids = new Set<number>();
    let selectedCount = 0;
    for (const id of _selected) {
      ids.add(id);
      selectedCount += 1;
      if (selectedCount >= MAX_DETAILED_PREVIEW_GEOMS) break;
    }
    if (includeHover && hoveredId !== null) ids.add(hoveredId);
    return Array.from(ids);
  }

  function pruneGeometryCache(keepIds: Set<number>) {
    for (const id of Array.from(geomById.keys())) {
      if (!keepIds.has(id)) geomById.delete(id);
    }
  }

  function buildFeatureCollection() {
    const ids = computeRenderIds();
    const detailedIds = new Set<number>(detailedPreviewTargetIds(true));
    pruneGeometryCache(detailedIds);
    const features: Feature[] = [];
    for (const id of ids) {
      if (detailedIds.has(id)) {
        const geom = geomById.get(id);
        if (geom) {
          features.push(geom);
          continue;
        }
      }
      const bb = bboxFeature(id);
      if (bb) features.push(bb);
    }
    renderCount = features.length;
    renderTotalCount = ids.length;
    loadedGeomCount = geomById.size;
    return { type: "FeatureCollection", features } as const;
  }

  function updateSourceData() {
    if (!source) return;
    source.setData(buildFeatureCollection() as any);
  }

  function applySelectionDiff() {
    if (!map) return;
    const next = _selected;
    for (const id of prevSelected) {
      if (!next.has(id)) map.setFeatureState({ source: "areas", id }, { selected: false });
    }
    for (const id of next) {
      if (!prevSelected.has(id)) map.setFeatureState({ source: "areas", id }, { selected: true });
    }
    prevSelected = new Set(next);
  }

  function applySelectionForIds(ids: number[]) {
    if (!map) return;
    for (const id of ids) map.setFeatureState({ source: "areas", id }, { selected: _selected.has(id) });
  }

  function updatePreviewLoadProgress(isLoading: boolean) {
    const selectedIds = detailedPreviewTargetIds();
    const selectedTotal = selectedIds.length;
    let loaded = 0;
    let inflight = 0;
    for (const id of selectedIds) {
      if (geomById.has(id)) loaded += 1;
      else if (inFlightGeomIds.has(id)) inflight += 1;
    }
    const pending = Math.max(0, selectedTotal - loaded - inflight);
    previewLoadProgress.set({ selectedTotal, loaded, inflight, pending, isLoading });
  }

  function wantedGeomIds(): number[] {
    // Preview mode: fetch real geometry only for selected objects.
    // For very large selections we keep only a bounded number of detailed geometries in memory.
    const now = Date.now();
    return detailedPreviewTargetIds().filter((id) => {
      const retryAt = failedGeomRetryUntil.get(id) || 0;
      return retryAt <= now;
    });
  }

  function clearRetryEnsureTimer() {
    if (retryEnsureTimer !== null) {
      window.clearTimeout(retryEnsureTimer);
      retryEnsureTimer = null;
    }
  }

  function scheduleRetryEnsure(ms: number) {
    clearRetryEnsureTimer();
    retryEnsureTimer = window.setTimeout(() => {
      retryEnsureTimer = null;
      ensureGeometry().catch(() => {});
    }, Math.max(100, ms));
  }

  function chunk<T>(arr: T[], size: number): T[][] {
    const out: T[][] = [];
    for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
    return out;
  }

  async function fetchPreview(ids: number[], options: { abortPrevious?: boolean } = {}) {
    const abortPrevious = options.abortPrevious ?? true;
    const requestIds = ids.filter((id) => !geomById.has(id) && !inFlightGeomIds.has(id));
    if (!requestIds.length) return;
    for (const id of requestIds) inFlightGeomIds.add(id);

    let signal: AbortSignal | undefined;
    if (abortPrevious) {
      fetchAbort?.abort();
      fetchAbort = new AbortController();
      signal = fetchAbort.signal;
    }

    try {
      const fc = await apiPost<any>(
        "/api/catalog/preview",
        {
          relation_ids: requestIds,
          admin_level: String(_adminLevel || "").trim() || null,
          parent_relation_id: _scopeMode === "parent" ? _parentRelationId : null,
          overpass_url: _overpassUrl.trim() || null,
        },
        signal,
      );
      const feats = Array.isArray(fc?.features) ? fc.features : [];
      const justLoaded: number[] = [];
      for (const f of feats) {
        const rid = Number(f?.id ?? f?.properties?.relation_id ?? f?.properties?.osm_id);
        if (!rid || Number.isNaN(rid)) continue;
        geomById.set(rid, {
          type: "Feature",
          id: rid,
          geometry: f.geometry,
          properties: { ...(f.properties ?? {}), relation_id: rid, preview_kind: "geom" },
        });
        justLoaded.push(rid);
      }
      updateSourceData();
      applySelectionForIds(justLoaded);
      for (const rid of justLoaded) failedGeomRetryUntil.delete(rid);
      updatePreviewLoadProgress(true);
    } finally {
      for (const id of requestIds) inFlightGeomIds.delete(id);
      updatePreviewLoadProgress(fetchRunning);
    }
  }

  async function ensureHoverGeometry(id: number) {
    if (!id || Number.isNaN(id)) return;
    if (geomById.has(id) || inFlightGeomIds.has(id)) return;
    await fetchPreview([id], { abortPrevious: false });
  }

  async function ensureGeometry() {
    if (fetchRunning) return;
    fetchRunning = true;
    updatePreviewLoadProgress(true);
    try {
      while (true) {
        const wanted = wantedGeomIds().filter((id) => !geomById.has(id));
        pendingGeomCount = wanted.length;
        if (!wanted.length) {
          const now = Date.now();
          let nearestRetryAt = 0;
          for (const id of _selected) {
            if (geomById.has(id) || inFlightGeomIds.has(id)) continue;
            const retryAt = failedGeomRetryUntil.get(id) || 0;
            if (retryAt > now && (nearestRetryAt === 0 || retryAt < nearestRetryAt)) {
              nearestRetryAt = retryAt;
            }
          }
          if (nearestRetryAt > 0) {
            scheduleRetryEnsure(nearestRetryAt - now + 30);
          }
          break;
        }
        const batches = chunk(wanted, 40);
        const batch = batches[0];
        try {
          await fetchPreview(batch, { abortPrevious: false });
        } catch {
          const retryAt = Date.now() + 8000;
          for (const id of batch) failedGeomRetryUntil.set(id, retryAt);
        }
        await new Promise((r) => setTimeout(r, 50));
      }
    } finally {
      fetchRunning = false;
      updatePreviewLoadProgress(false);
    }
  }

  function scheduleEnsure() {
    clearRetryEnsureTimer();
    if (scheduleTimer !== null) window.clearTimeout(scheduleTimer);
    scheduleTimer = window.setTimeout(() => {
      scheduleTimer = null;
      updateSourceData();
      ensureGeometry().catch(() => {});
    }, 150);
  }

  async function flushClipFetchQueue() {
    if (clipFetchRunning) return;
    clipFetchRunning = true;
    try {
      while (pendingClipFetchIds.size) {
        const batch = Array.from(pendingClipFetchIds).slice(0, 20);
        for (const rid of batch) pendingClipFetchIds.delete(rid);
        const fc = await apiPost<any>("/api/catalog/land-preview", {
          relation_ids: batch,
          admin_level: String(_adminLevel || "").trim() || null,
          parent_relation_id: _scopeMode === "parent" ? _parentRelationId : null,
        });
        const feats = Array.isArray(fc?.features) ? fc.features : [];
        const detailedIds = new Set<number>(detailedPreviewTargetIds(true));
        const updatedIds: number[] = [];
        for (const f of feats) {
          const rid = Number(f?.id ?? f?.properties?.relation_id ?? f?.properties?.osm_id);
          if (!rid || Number.isNaN(rid)) continue;
          if (!detailedIds.has(rid)) continue;
          const prev = geomById.get(rid);
          geomById.set(rid, {
            type: "Feature",
            id: rid,
            geometry: f.geometry,
            properties: {
              ...(prev?.properties ?? {}),
              ...(f.properties ?? {}),
              relation_id: rid,
              name: String(f?.properties?.name ?? prev?.properties?.name ?? `relation ${rid}`),
              preview_kind: "clip_land",
            },
          });
          updatedIds.push(rid);
          appliedClipIds.add(rid);
        }
        if (updatedIds.length) {
          updateSourceData();
          applySelectionForIds(updatedIds);
        }
        await new Promise((r) => setTimeout(r, 20));
      }
    } catch {
      // Best-effort live replacement; keep export running.
    } finally {
      clipFetchRunning = false;
      if (pendingClipFetchIds.size) scheduleClipFetch();
    }
  }

  function scheduleClipFetch() {
    if (clipFetchTimer !== null) return;
    clipFetchTimer = window.setTimeout(() => {
      clipFetchTimer = null;
      flushClipFetchQueue().catch(() => {});
    }, 120);
  }

  function zoomToSelection() {
    if (!map) return;
    const bounds = new maplibregl.LngLatBounds();
    let any = false;
    for (const id of _selected) {
      const item = _itemsById.get(id);
      if (item?.bounds) {
        bounds.extend([item.bounds.minlon, item.bounds.minlat]);
        bounds.extend([item.bounds.maxlon, item.bounds.maxlat]);
        any = true;
      }
    }
    if (any) map.fitBounds(bounds, { padding: 40, maxZoom: 10 });
  }

  function applyBasemapNow(id: string) {
    if (!map || !mapLoaded) return;
    const bm = getBasemap(id);
    const sourceId = "basemap";
    const layerId = "basemap";
    try {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    } catch {
      // Best-effort: map style might be mid-update.
    }
    map.addSource(sourceId, {
      type: "raster",
      tiles: bm.tiles,
      tileSize: bm.tileSize ?? 256,
      maxzoom: bm.maxzoom ?? 19,
      attribution: bm.attribution,
    } as any);
    const beforeId = map.getLayer("areas-fill") ? "areas-fill" : undefined;
    map.addLayer({ id: layerId, type: "raster", source: sourceId } as any, beforeId);
  }

  function createBasemapControl() {
    const control = {
      _container: null as HTMLDivElement | null,
      _btn: null as HTMLButtonElement | null,
      _menu: null as HTMLDivElement | null,
      _open: false,
      _onDocDown: null as ((e: MouseEvent) => void) | null,
      _onDocKey: null as ((e: KeyboardEvent) => void) | null,

      onAdd(m: Map) {
        const container = document.createElement("div");
        container.className = "maplibregl-ctrl maplibregl-ctrl-group basemap-ctrl";
        container.addEventListener("mousedown", (e) => e.stopPropagation());
        container.addEventListener("click", (e) => e.stopPropagation());

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "basemap-btn";
        btn.title = "Basemap";
        btn.setAttribute("aria-label", "Basemap");
        btn.innerHTML =
          `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">` +
          `<path d="M12 2 2 7l10 5 10-5-10-5Z"></path>` +
          `<path d="M2 17l10 5 10-5"></path>` +
          `<path d="M2 12l10 5 10-5"></path>` +
          `</svg>`;

        const menu = document.createElement("div");
        menu.className = "basemap-menu";
        menu.setAttribute("role", "menu");
        menu.style.display = "none";

        const rebuildMenu = () => {
          menu.innerHTML = "";
          for (const bm of BASEMAPS) {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "basemap-item";
            item.setAttribute("role", "menuitemradio");
            item.setAttribute("aria-checked", bm.id === _basemapId ? "true" : "false");
            item.textContent = bm.label;
            item.addEventListener("click", () => {
              basemapId.set(bm.id);
              this.close();
            });
            menu.appendChild(item);
          }
        };

        btn.addEventListener("click", () => {
          this._open = !this._open;
          if (this._open) {
            rebuildMenu();
            menu.style.display = "block";
            this._onDocDown = (e: MouseEvent) => {
              const t = e.target as Node | null;
              if (!t) return;
              if (container.contains(t)) return;
              this.close();
            };
            this._onDocKey = (e: KeyboardEvent) => {
              if (e.key === "Escape") this.close();
            };
            document.addEventListener("mousedown", this._onDocDown, { capture: true });
            document.addEventListener("keydown", this._onDocKey, { capture: true });
          } else {
            this.close();
          }
        });

        (control as any).refresh = () => {
          if (this._open) rebuildMenu();
        };

        (control as any).close = () => {
          this._open = false;
          menu.style.display = "none";
          if (this._onDocDown) document.removeEventListener("mousedown", this._onDocDown, { capture: true } as any);
          if (this._onDocKey) document.removeEventListener("keydown", this._onDocKey, { capture: true } as any);
          this._onDocDown = null;
          this._onDocKey = null;
        };

        container.appendChild(btn);
        container.appendChild(menu);

        this._container = container;
        this._btn = btn;
        this._menu = menu;
        return container;
      },
      onRemove() {
        (this as any).close?.();
        this._container?.parentNode?.removeChild(this._container);
        this._container = null;
        this._btn = null;
        this._menu = null;
      },
    } as any;
    return control as unknown as maplibregl.IControl & { refresh?: () => void; close?: () => void };
  }

  onMount(() => {
    unsubs.push(adminLevel.subscribe((v) => { _adminLevel = String(v || "").trim(); }));
    unsubs.push(allIds.subscribe((v) => {
      const changed = v !== lastAllIdsRef;
      _allIds = v;
      if (changed) {
        lastAllIdsRef = v;
        geomById.clear();
        appliedClipIds.clear();
        scheduleEnsure();
      }
    }));
    unsubs.push(itemsById.subscribe((v) => { _itemsById = v; scheduleEnsure(); }));
    unsubs.push(parentRelationId.subscribe((v) => { _parentRelationId = v; }));
    unsubs.push(selected.subscribe((v) => { _selected = v; applySelectionDiff(); updatePreviewLoadProgress(fetchRunning); scheduleEnsure(); }));
    unsubs.push(scopeMode.subscribe((v) => { _scopeMode = v; }));
    unsubs.push(visibleIds.subscribe((v) => { _visibleIds = v; scheduleEnsure(); }));
    unsubs.push(overpassUrl.subscribe((v) => { _overpassUrl = v; }));
    unsubs.push(showOnlySelectedOnMap.subscribe((v) => { _showOnlySelectedOnMap = v; scheduleEnsure(); }));
    unsubs.push(basemapId.subscribe((v) => {
      _basemapId = String(v || "").trim();
      applyBasemapNow(_basemapId);
      basemapControl?.refresh?.();
    }));
    unsubs.push(liveClipReadyEvent.subscribe((clipped) => {
      if (!clipped) {
        // New job started / progress reset: allow live clipped updates again.
        appliedClipIds.clear();
        pendingClipFetchIds.clear();
        return;
      }
      const rid = Number(clipped.relation_id || 0);
      if (!rid || Number.isNaN(rid)) return;
      if (appliedClipIds.has(rid)) return;
      pendingClipFetchIds.add(rid);
      scheduleClipFetch();
    }));

    map = new maplibregl.Map({
      container,
      style: rasterStyleForBasemap(_basemapId) as any,
      center: [30, 20],
      zoom: 1,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    basemapControl = createBasemapControl();
    map.addControl(basemapControl, "top-right");
    popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });

    map.on("load", () => {
      mapLoaded = true;
      applyBasemapNow(_basemapId);
      map!.addSource("areas", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        maxzoom: AREAS_SOURCE_MAXZOOM,
        tolerance: AREAS_SOURCE_TOLERANCE,
        buffer: AREAS_SOURCE_BUFFER,
      });
      source = map!.getSource("areas") as GeoJSONSource;

      const isSelected = ["boolean", ["feature-state", "selected"], false] as any;
      const isHover = ["boolean", ["feature-state", "hover"], false] as any;

      const lineColor = ["case", isHover, hoverColor, ["case", isSelected, selectedColor, dimColor]] as any;
      const fillColor = ["case", isSelected, selectedColor, dimColor] as any;
      const fillOpacity = ["case", isHover, 0.22, ["case", isSelected, 0.18, 0.06]] as any;
      const lineWidth = ["case", isHover, ["case", isSelected, 3.5, 2.5], ["case", isSelected, 2.2, 1.0]] as any;

      map!.addLayer({
        id: "areas-fill",
        type: "fill",
        source: "areas",
        paint: { "fill-color": fillColor, "fill-opacity": fillOpacity },
      });
      map!.addLayer({
        id: "areas-line",
        type: "line",
        source: "areas",
        paint: { "line-color": lineColor, "line-width": lineWidth },
      });

      updateSourceData();
      applySelectionDiff();
      ensureGeometry().catch(() => {});
    });

    map.on("mouseenter", "areas-fill", () => {
      map!.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "areas-fill", () => {
      map!.getCanvas().style.cursor = "";
      if (hoveredId !== null) map!.setFeatureState({ source: "areas", id: hoveredId }, { hover: false });
      hoveredId = null;
      popup?.remove();
    });

    map.on("mousemove", "areas-fill", (e) => {
      const f = e.features?.[0] as any;
      const id = Number(f?.id);
      if (!id || Number.isNaN(id)) return;
      if (hoveredId !== null && hoveredId !== id) {
        map!.setFeatureState({ source: "areas", id: hoveredId }, { hover: false });
      }
      hoveredId = id;
      map!.setFeatureState({ source: "areas", id }, { hover: true });
      if (!geomById.has(id)) {
        ensureHoverGeometry(id).catch(() => {});
      }

      const name = String(f?.properties?.name ?? `relation ${id}`)
        .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      const isSel = _selected.has(id);
      popup
        ?.setLngLat(e.lngLat)
        .setHTML(
          `<div style="font-weight:600;font-size:13px">${name}</div>` +
          `<div style="display:flex;gap:6px;align-items:center;margin-top:3px">` +
          `<span style="font-size:11px;opacity:.65;font-family:monospace">r${id}</span>` +
          `<span style="font-size:10px;padding:1px 6px;border-radius:4px;background:${isSel ? "rgba(59,130,246,0.12)" : "rgba(15,23,42,0.06)"};color:${isSel ? "#3b82f6" : "#64748b"};font-weight:500">${isSel ? "Selected" : "Not selected"}</span>` +
          `</div>`
        )
        .addTo(map!);
    });

    map.on("click", "areas-fill", (e) => {
      const f = e.features?.[0] as any;
      const id = Number(f?.id);
      if (!id || Number.isNaN(id)) return;
      toggle(id);
    });
  });

  onDestroy(() => {
    for (const u of unsubs) u();
    fetchAbort?.abort();
    if (scheduleTimer !== null) window.clearTimeout(scheduleTimer);
    if (clipFetchTimer !== null) window.clearTimeout(clipFetchTimer);
    clearRetryEnsureTimer();
    basemapControl?.close?.();
    basemapControl = null;
    popup?.remove();
    popup = null;
    map?.remove();
    map = null;
    mapLoaded = false;
    previewLoadProgress.set({ selectedTotal: 0, loaded: 0, inflight: 0, pending: 0, isLoading: false });
  });
</script>

<div class="wrap">
  <div bind:this={container} class="map" />
  <MapHud
    {renderCount}
    totalCount={renderTotalCount}
    {loadedGeomCount}
    {pendingGeomCount}
    on:click={zoomToSelection}
  />
</div>

<style>
  .wrap {
    height: 100%;
    width: 100%;
    position: relative;
  }
  .map {
    height: 100%;
    width: 100%;
  }

  :global(.basemap-ctrl) {
    position: relative;
    overflow: visible;
  }
  :global(.basemap-btn) {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  :global(.basemap-menu) {
    position: absolute;
    right: 0;
    top: 40px;
    min-width: 240px;
    max-width: 320px;
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid rgba(15, 23, 42, 0.12);
    border-radius: 10px;
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.12);
    padding: 6px;
    z-index: 1000;
    backdrop-filter: blur(10px);
    color: #0f172a;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans", "Liberation Sans", sans-serif;
  }

  /* MapLibre control CSS targets `.maplibregl-ctrl-group button` and would shrink menu items to 29x29.
     Force sane defaults for our menu buttons. */
  :global(.basemap-menu .basemap-item) {
    all: unset;
    display: block;
    width: 100%;
    box-sizing: border-box;
    text-align: left;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    color: inherit;
    line-height: 1.25;
    white-space: normal;
    overflow-wrap: anywhere;
    user-select: none;
  }
  :global(.basemap-menu .basemap-item:hover) {
    background: rgba(59, 130, 246, 0.10);
    color: #1d4ed8;
  }
  :global(.basemap-menu .basemap-item:focus-visible) {
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.22);
  }
  :global(.basemap-menu .basemap-item[aria-checked="true"]) {
    background: rgba(59, 130, 246, 0.14);
    color: #1d4ed8;
    font-weight: 700;
  }
</style>
