import { writable, derived, get } from "svelte/store";
import { apiGet, apiPost } from "./api";
import type { AreaItem, AppMode, ScopeMode, ProgressState, LiveClipReadyEvent } from "./types";
import { DEFAULT_BASEMAP_ID } from "./mapStyle";

const LS_PREFIX = "osm_batch_downloader:v1";

function lsGet<T>(key: string, fallback: T): T {
  try {
    if (typeof localStorage === "undefined") return fallback;
    const raw = localStorage.getItem(`${LS_PREFIX}:${key}`);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function lsSet<T>(key: string, value: T): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(`${LS_PREFIX}:${key}`, JSON.stringify(value));
  } catch {
    // Best-effort persistence only.
  }
}

function lsRemove(key: string): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.removeItem(`${LS_PREFIX}:${key}`);
  } catch {
    // Best-effort persistence only.
  }
}

function clearLsPrefix(): void {
  try {
    if (typeof localStorage === "undefined") return;
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith(`${LS_PREFIX}:`)) keys.push(k);
    }
    for (const k of keys) localStorage.removeItem(k);
  } catch {
    // Best-effort persistence only.
  }
}

function hydrateScopeMode(v: unknown): ScopeMode {
  return v === "parent" ? "parent" : "world";
}

function hydrateNumberOrNull(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function hydrateSet(raw: unknown): Set<number> {
  if (!Array.isArray(raw)) return new Set<number>();
  return new Set(
    raw
      .map((x) => Number(x))
      .filter((x) => Number.isFinite(x) && x > 0)
  );
}

function hydrateItemsMap(raw: unknown): Map<number, AreaItem> {
  const m = new Map<number, AreaItem>();
  if (!Array.isArray(raw)) return m;
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const rid = Number((item as Record<string, unknown>).relation_id);
    if (!Number.isFinite(rid) || rid <= 0) continue;
    const tags = (item as Record<string, unknown>).tags;
    m.set(rid, {
      relation_id: rid,
      name: String((item as Record<string, unknown>).name ?? `relation ${rid}`),
      tags: tags && typeof tags === "object" ? (tags as Record<string, unknown>) : {},
      center: ((item as Record<string, unknown>).center as AreaItem["center"]) ?? undefined,
      bounds: ((item as Record<string, unknown>).bounds as AreaItem["bounds"]) ?? undefined,
    });
  }
  return m;
}

function serializeItemsMap(map: Map<number, AreaItem>): AreaItem[] {
  return Array.from(map.values());
}

function defaultProgressState(): ProgressState {
  return {
    status: "running",
    stage: "",
    currentPhase: "",
    done: 0,
    total: 0,
    ok: 0,
    failed: 0,
    current: null,
    currentStats: null,
    sumPolygons: 0,
    sumVertices: 0,
    sumBytes: 0,
    clipCacheHits: 0,
    clipCacheMisses: 0,
    lpDone: null,
    lpTotal: null,
    log: [],
    errorMsg: "",
    startTime: Date.now(),
    objectTimes: [],
    failedObjects: [],
  };
}

// ── Config ──────────────────────────────────────────
export const adminLevel = writable(String(lsGet("adminLevel", "2") || "2"));
export const scopeMode = writable<ScopeMode>(hydrateScopeMode(lsGet("scopeMode", "world")));
export const parentRelationId = writable<number | null>(hydrateNumberOrNull(lsGet("parentRelationId", null)));
export const parentRelationName = writable(String(lsGet("parentRelationName", "") || ""));
export const parentQuery = writable(String(lsGet("parentQuery", "") || ""));
export const parentAdminLevel = writable("2");
export const parentCandidates = writable<AreaItem[]>([]);
export const clipLand = writable(Boolean(lsGet("clipLand", false)));
export const forceRefreshOsmSource = writable(Boolean(lsGet("forceRefreshOsmSource", false)));
export const fixAntimeridian = writable(Boolean(lsGet("fixAntimeridian", true)));
export const overpassUrl = writable(String(lsGet("overpassUrl", "") || ""));
export const showOnlySelectedOnMap = writable(Boolean(lsGet("showOnlySelectedOnMap", false)));
export const basemapId = writable(String(lsGet("basemapId", DEFAULT_BASEMAP_ID) || DEFAULT_BASEMAP_ID));
export const worldScopeAllowed = derived(adminLevel, ($adminLevel) => String($adminLevel).trim() === "2");
const parentPrewarmInFlight = new Set<string>();
const parentSearchCache = new Map<string, AreaItem[]>();
let parentSearchAbort: AbortController | null = null;

// ── Catalog data ────────────────────────────────────
export const allIds = writable<number[]>(
  (Array.isArray(lsGet("allIds", [])) ? lsGet("allIds", []) : [])
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x) && x > 0)
);
export const itemsById = writable<Map<number, AreaItem>>(hydrateItemsMap(lsGet("itemsById", [])));
export const selected = writable<Set<number>>(hydrateSet(lsGet("selected", [])));

// ── UI state ────────────────────────────────────────
export const appMode = writable<AppMode>(lsGet("appMode", "select") === "progress" ? "progress" : "select");
export const loadingIds = writable(false);
export const errorMsg = writable("");
export const warningMsg = writable("");
export const previewLoadProgress = writable({
  selectedTotal: 0,
  loaded: 0,
  inflight: 0,
  pending: 0,
  isLoading: false,
});

// ── Filter & pagination ─────────────────────────────
export const filterText = writable(String(lsGet("filterText", "") || ""));
export const page = writable(0);

// ── Job ─────────────────────────────────────────────
const hydratedJobIdRaw = String(lsGet("jobId", "") || "").trim();
export const jobId = writable<string | null>(hydratedJobIdRaw || null);
const hydratedAdmNameRaw = String(lsGet("admName", "") || "").trim();
export const admName = writable<string | null>(hydratedAdmNameRaw || null);
const hydratedExportAdminLevelRaw = String(lsGet("exportAdminLevel", "") || "").trim();
export const exportAdminLevel = writable<string | null>(hydratedExportAdminLevelRaw || null);
export const liveClipReadyEvent = writable<LiveClipReadyEvent | null>(null);

// ── Progress ────────────────────────────────────────
export const progress = writable<ProgressState>({
  status: "running",
  stage: "",
  currentPhase: "",
  done: 0,
  total: 0,
  ok: 0,
  failed: 0,
  current: null,
  currentStats: null,
  sumPolygons: 0,
  sumVertices: 0,
  sumBytes: 0,
  clipCacheHits: 0,
  clipCacheMisses: 0,
  lpDone: null,
  lpTotal: null,
  log: [],
  errorMsg: "",
  startTime: 0,
  objectTimes: [],
  failedObjects: [],
});

// ── Land polygons ───────────────────────────────────
export const landPolygonsStatus = writable<Record<string, unknown> | null>(null);

// ── Derived stores ──────────────────────────────────
export const totalCount = derived(allIds, ($a) => $a.length);
export const selectedCount = derived(selected, ($s) => $s.size);

function collectSearchableNames(item: AreaItem | undefined): string[] {
  if (!item) return [];
  const out = new Set<string>();
  const push = (v: unknown) => {
    if (typeof v !== "string") return;
    const t = v.trim().toLowerCase();
    if (t) out.add(t);
  };

  push(item.name);

  const tags = item.tags;
  if (tags && typeof tags === "object") {
    const primaryNameKeys = [
      "name",
      "name:ru",
      "name:en",
      "int_name",
      "official_name",
      "official_name:ru",
      "official_name:en",
      "short_name",
      "short_name:ru",
      "short_name:en",
      "alt_name",
      "loc_name",
    ];
    for (const key of primaryNameKeys) {
      push((tags as Record<string, unknown>)[key]);
    }
    // Include any localized name:* fields returned by Overpass.
    for (const [k, v] of Object.entries(tags as Record<string, unknown>)) {
      if (k.startsWith("name:")) push(v);
    }
  }

  return Array.from(out);
}

/** Global filter: searches ALL loaded items by name or ID, not just current page */
export const filteredIds = derived(
  [allIds, itemsById, filterText],
  ([$allIds, $itemsById, $filterText]) => {
    const q = $filterText.trim().toLowerCase();
    if (!q) return $allIds;
    return $allIds.filter((id) => {
      const item = $itemsById.get(id);
      if (String(id).includes(q)) return true;
      const names = collectSearchableNames(item);
      return names.some((name) => name.includes(q));
    });
  }
);

export const pageCount = derived(filteredIds, () => 1);

/** IDs currently shown in the list (all filtered results, no pagination). */
export const pageIds = derived(filteredIds, ($filteredIds) => $filteredIds);

/** IDs prioritized for map/preview loading */
export const visibleIds = derived(filteredIds, ($filteredIds) => $filteredIds);

/** Estimated time remaining in ms */
export const eta = derived(progress, ($p) => {
  if (!$p.objectTimes.length || $p.total <= 0) return null;
  const avg = $p.objectTimes.reduce((a, b) => a + b, 0) / $p.objectTimes.length;
  const remaining = $p.total - $p.done;
  if (remaining <= 0) return 0;
  return Math.round(avg * remaining);
});

// ── Actions ─────────────────────────────────────────

export async function refreshLandPolygonsStatus() {
  try {
    const res = await apiGet<Record<string, unknown>>("/api/land-polygons/status");
    landPolygonsStatus.set(res);
  } catch {
    landPolygonsStatus.set(null);
  }
}

export async function searchParents() {
  errorMsg.set("");
  const q = get(parentQuery).trim();
  if (!q) {
    parentCandidates.set([]);
    return;
  }
  if (q.length < 2) {
    errorMsg.set("Enter at least 2 characters to search parent regions.");
    parentCandidates.set([]);
    return;
  }
  const al = get(parentAdminLevel).trim() || "";
  const cacheKey = `${al}|${q.toLowerCase()}`;
  if (parentSearchCache.has(cacheKey)) {
    parentCandidates.set(parentSearchCache.get(cacheKey) || []);
    return;
  }
  parentSearchAbort?.abort();
  parentSearchAbort = new AbortController();
  try {
    const res = await apiPost<{ items: AreaItem[] }>("/api/areas/search", {
      query: q,
      admin_level: al || null,
      limit: 50,
    }, parentSearchAbort.signal);
    parentSearchCache.set(cacheKey, res.items || []);
    parentCandidates.set(res.items);
  } catch (e) {
    if ((e as Error).name === "AbortError") return;
    errorMsg.set((e as Error).message);
  }
}

export function selectParent(item: AreaItem) {
  parentRelationId.set(item.relation_id);
  parentRelationName.set(item.name || `relation ${item.relation_id}`);
  parentQuery.set(item.name || "");
  parentCandidates.set([]);
  prewarmParentScope(item.relation_id);
}

export function clearParent() {
  parentRelationId.set(null);
  parentRelationName.set("");
  parentQuery.set("");
  parentCandidates.set([]);
}

async function prewarmParentScope(parentId: number) {
  const al = String(get(adminLevel)).trim();
  if (!parentId || al === "2") return;
  const key = `${parentId}:${al}`;
  if (parentPrewarmInFlight.has(key)) return;
  parentPrewarmInFlight.add(key);
  try {
    await apiPost<{ relation_ids: number[]; count: number; items?: AreaItem[] }>("/api/catalog/ids", {
      admin_level: al,
      parent_relation_id: parentId,
    });
  } catch {
    // Warm-up is best-effort; ignore transient failures.
  } finally {
    parentPrewarmInFlight.delete(key);
  }
}

export async function loadIds() {
  errorMsg.set("");
  warningMsg.set("");
  loadingIds.set(true);
  itemsById.set(new Map());
  allIds.set([]);
  selected.set(new Set());
  page.set(0);
  filterText.set("");
  try {
    const scope = get(scopeMode);
    const al = String(get(adminLevel)).trim();
    const parentId = get(parentRelationId);
    if (scope === "world" && al !== "2") {
      throw new Error("Worldwide scope is available only for admin_level=2. Choose 'Within region'.");
    }
    if (scope === "parent" && !parentId) {
      throw new Error("Parent mode selected but no relation chosen.");
    }
    const res = await apiPost<{ relation_ids: number[]; count: number; items?: AreaItem[] }>("/api/catalog/ids", {
      admin_level: al,
      parent_relation_id: scope === "parent" ? parentId : null,
    });
    const ids = res.relation_ids;
    allIds.set(ids);
    if (Array.isArray(res.items) && res.items.length) {
      const seeded = new Map<number, AreaItem>();
      for (const item of res.items) {
        if (!item || typeof item.relation_id !== "number") continue;
        seeded.set(item.relation_id, item);
      }
      if (seeded.size) {
        itemsById.set(seeded);
      }
    }
    // Keep initial load lightweight: do not auto-select all after Load objects.
    // Users can select what they need; geometry preview loads for selected/hovered items.
    selected.set(new Set());
    if (ids.length > 20000) {
      warningMsg.set(
        "Very large list loaded. Nothing selected by default. Select items manually or narrow the scope."
      );
    }
    // No background details loading: list is built from fast tags response only.
  } catch (e) {
    errorMsg.set((e as Error).message);
  } finally {
    loadingIds.set(false);
  }
}

export function clearSearchResults() {
  itemsById.set(new Map());
  allIds.set([]);
  selected.set(new Set());
  page.set(0);
  filterText.set("");
  warningMsg.set("");
  errorMsg.set("");
  previewLoadProgress.set({ selectedTotal: 0, loaded: 0, inflight: 0, pending: 0, isLoading: false });
}

export function toggle(id: number) {
  const s = new Set(get(selected));
  if (s.has(id)) s.delete(id);
  else s.add(id);
  selected.set(s);
}

export function selectAllPage() {
  const s = new Set(get(selected));
  for (const id of get(pageIds)) s.add(id);
  selected.set(s);
}

export function deselectAllPage() {
  const s = new Set(get(selected));
  for (const id of get(pageIds)) s.delete(id);
  selected.set(s);
}

export function selectAll() {
  const ids = get(allIds);
  if (ids.length > 20000) {
    warningMsg.set("Select all for very large lists may use significant memory. Consider narrowing the scope.");
  }
  selected.set(new Set(ids));
}

export function deselectAll() {
  selected.set(new Set());
}

export function setPage(p: number) {
  // Pagination disabled; keep API-compatible no-op for legacy callers.
  page.set(0);
}

export async function startJob() {
  errorMsg.set("");
  const ids = Array.from(get(selected));
  if (!ids.length) {
    errorMsg.set("Nothing selected");
    return;
  }
  try {
    const scope = get(scopeMode);
    const parentId = get(parentRelationId);
    const byId = get(itemsById);
    const relationNames: Record<string, string> = {};
    for (const rid of ids) {
      const item = byId.get(rid);
      const tags = (item?.tags ?? {}) as Record<string, unknown>;
      const nameRu = typeof tags["name:ru"] === "string" ? String(tags["name:ru"]).trim() : "";
      const name = nameRu || String(item?.name ?? "").trim();
      if (name) relationNames[String(rid)] = name;
    }
    const res = await apiPost<{ job_id: string; adm_name: string; admin_level: string }>("/api/jobs", {
      admin_level: get(adminLevel),
      parent_relation_id: scope === "parent" ? parentId : null,
      selected_relation_ids: ids,
      relation_names: relationNames,
      clip_land: get(clipLand),
      force_refresh_osm_source: get(forceRefreshOsmSource),
      fix_antimeridian: get(fixAntimeridian),
      overpass_url: get(overpassUrl).trim() || null,
    });
    jobId.set(res.job_id);
    admName.set(res.adm_name);
    exportAdminLevel.set(String(res.admin_level || get(adminLevel)).trim());
    progress.set(defaultProgressState());
    liveClipReadyEvent.set(null);
    appMode.set("progress");
  } catch (e) {
    errorMsg.set((e as Error).message);
  }
}

export function resetToSelect() {
  appMode.set("select");
  jobId.set(null);
  admName.set(null);
  exportAdminLevel.set(null);
  errorMsg.set("");
  liveClipReadyEvent.set(null);
  lsRemove("jobId");
  lsRemove("admName");
  lsRemove("exportAdminLevel");
  lsSet("appMode", "select");
}

function clearPersistedJobSession() {
  lsRemove("jobId");
  lsRemove("admName");
  lsRemove("exportAdminLevel");
}

export async function restoreSessionJobIfRunning(): Promise<boolean> {
  const id = get(jobId);
  if (!id) {
    if (get(appMode) === "progress") appMode.set("select");
    return false;
  }
  try {
    const j = await apiGet<{
      status: string;
      created_at_epoch?: number;
      params?: Record<string, unknown>;
      progress?: Record<string, unknown>;
    }>(`/api/jobs/${id}`);
    const status = String(j?.status || "").trim();
    const isActive = status === "running" || status === "queued";
    if (!isActive) {
      clearPersistedJobSession();
      if (get(appMode) === "progress") appMode.set("select");
      return false;
    }

    const p = j?.progress ?? {};
    progress.update((prev) => ({
      ...prev,
      done: Number(p.done ?? prev.done ?? 0),
      total: Number(p.total ?? prev.total ?? 0),
      ok: Number(p.ok ?? prev.ok ?? 0),
      failed: Number(p.failed ?? prev.failed ?? 0),
      status: "running",
      startTime: (typeof j?.created_at_epoch === "number" ? Math.round(j.created_at_epoch * 1000) : prev.startTime || Date.now()),
    }));

    const savedAdm = String(get(admName) || "").trim();
    if (!savedAdm) {
      const fromParams = String((j?.params?.adm_name as string | undefined) || "").trim();
      if (fromParams) admName.set(fromParams);
    }
    const savedAl = String(get(exportAdminLevel) || "").trim();
    if (!savedAl) {
      const fromParamsAl = String((j?.params?.admin_level as string | undefined) || "").trim();
      if (fromParamsAl) exportAdminLevel.set(fromParamsAl);
    }

    appMode.set("progress");
    return true;
  } catch {
    clearPersistedJobSession();
    if (get(appMode) === "progress") appMode.set("select");
    return false;
  }
}

export function resetSavedSession() {
  clearLsPrefix();
  adminLevel.set("2");
  scopeMode.set("world");
  parentRelationId.set(null);
  parentRelationName.set("");
  parentQuery.set("");
  parentCandidates.set([]);
  clipLand.set(false);
  forceRefreshOsmSource.set(false);
  fixAntimeridian.set(true);
  overpassUrl.set("");
  showOnlySelectedOnMap.set(false);
  basemapId.set(DEFAULT_BASEMAP_ID);
  allIds.set([]);
  itemsById.set(new Map());
  selected.set(new Set());
  filterText.set("");
  page.set(0);
  appMode.set("select");
  loadingIds.set(false);
  errorMsg.set("");
  warningMsg.set("");
  previewLoadProgress.set({ selectedTotal: 0, loaded: 0, inflight: 0, pending: 0, isLoading: false });
  jobId.set(null);
  admName.set(null);
  exportAdminLevel.set(null);
  liveClipReadyEvent.set(null);
  progress.set(defaultProgressState());
}

// ── Local persistence (best-effort) ─────────────────
adminLevel.subscribe((v) => lsSet("adminLevel", v));
scopeMode.subscribe((v) => lsSet("scopeMode", v));
parentRelationId.subscribe((v) => lsSet("parentRelationId", v));
parentRelationName.subscribe((v) => lsSet("parentRelationName", v));
parentQuery.subscribe((v) => lsSet("parentQuery", v));
clipLand.subscribe((v) => lsSet("clipLand", v));
forceRefreshOsmSource.subscribe((v) => lsSet("forceRefreshOsmSource", v));
fixAntimeridian.subscribe((v) => lsSet("fixAntimeridian", v));
overpassUrl.subscribe((v) => lsSet("overpassUrl", v));
showOnlySelectedOnMap.subscribe((v) => lsSet("showOnlySelectedOnMap", v));
basemapId.subscribe((v) => lsSet("basemapId", v));
filterText.subscribe((v) => lsSet("filterText", v));
allIds.subscribe((v) => lsSet("allIds", v));
selected.subscribe((v) => lsSet("selected", Array.from(v)));
itemsById.subscribe((v) => lsSet("itemsById", serializeItemsMap(v)));
appMode.subscribe((v) => lsSet("appMode", v));
jobId.subscribe((v) => {
  if (v) lsSet("jobId", v);
  else lsRemove("jobId");
});
admName.subscribe((v) => {
  if (v) lsSet("admName", v);
  else lsRemove("admName");
});
exportAdminLevel.subscribe((v) => {
  if (v) lsSet("exportAdminLevel", v);
  else lsRemove("exportAdminLevel");
});
