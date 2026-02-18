export type Bounds = {
  minlat: number;
  minlon: number;
  maxlat: number;
  maxlon: number;
};

export type Center = { lat: number; lon: number };

export type AreaItem = {
  relation_id: number;
  name: string;
  tags: Record<string, unknown>;
  center?: Center;
  bounds?: Bounds;
};

export type AppMode = "select" | "progress";
export type ScopeMode = "world" | "parent";

export type JobStatus = "running" | "done" | "error" | "cancelled";

export type ObjectProgress = {
  relation_id: number;
  name?: string;
  index: number;
  total: number;
};

export type ObjectStats = {
  polygons: number;
  vertices: number;
  osm_source_bytes: number;
  time_fetch_sec?: number;
  time_build_sec?: number;
  time_write_sec?: number;
  time_clip_sec?: number;
};

export type FailedObject = {
  relation_id: number;
  name?: string;
  error: string;
};

export type LiveClipReadyEvent = {
  relation_id: number;
  name?: string;
};

export type ProgressState = {
  status: JobStatus;
  stage: string;
  currentPhase: string;
  done: number;
  total: number;
  ok: number;
  failed: number;
  current: ObjectProgress | null;
  currentStats: ObjectStats | null;
  sumPolygons: number;
  sumVertices: number;
  sumBytes: number;
  clipCacheHits: number;
  clipCacheMisses: number;
  lpDone: number | null;
  lpTotal: number | null;
  log: string[];
  errorMsg: string;
  startTime: number;
  objectTimes: number[];
  failedObjects: FailedObject[];
};
