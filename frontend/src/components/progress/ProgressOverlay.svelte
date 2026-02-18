<script lang="ts">
  import { fly } from "svelte/transition";
  import { onDestroy, onMount } from "svelte";
  import { apiPost } from "../../lib/api";
  import {
    jobId,
    admName,
    exportAdminLevel,
    progress,
    eta,
    resetToSelect,
    liveClipReadyEvent,
  } from "../../lib/stores";
  import type { JobStatus } from "../../lib/types";
  import ProgressBar from "./ProgressBar.svelte";
  import ProgressStats from "./ProgressStats.svelte";
  import LogPanel from "./LogPanel.svelte";
  import CompletionSummary from "./CompletionSummary.svelte";
  import Button from "../shared/Button.svelte";

  let es: EventSource | null = null;
  let currentObjectStart: number | null = null;

  function stageLabel(s: string): string {
    const x = (s || "").trim();
    if (!x) return "";
    if (x === "start") return "Starting";
    if (x === "prefetch.details") return "Loading object metadata";
    if (x === "land_polygons.ensure") return "Preparing land polygons";
    if (x === "rebuild_combined") return "Building combined GeoJSON";
    return x;
  }

  function phaseLabel(s: string): string {
    const x = (s || "").trim();
    if (!x) return "";
    if (x === "use_osm_source_cache") return "Using cached geometry";
    if (x === "use_preview_cache") return "Using preview cache";
    if (x === "fetch_overpass") return "Fetching geometry from Overpass";
    if (x === "build_geometry") return "Building geometry";
    if (x === "write_osm_source") return "Writing GeoJSON";
    if (x === "clip_land") return "Clipping to land";
    return x;
  }

  function fmtEta(ms: number | null): string {
    if (ms === null || ms <= 0) return "";
    const sec = Math.floor(ms / 1000);
    if (sec < 60) return `~${sec}s remaining`;
    const min = Math.floor(sec / 60);
    const s = sec % 60;
    if (min < 60) return `~${min}m ${s}s remaining`;
    const h = Math.floor(min / 60);
    return `~${h}h ${min % 60}m remaining`;
  }

  function fmtBytes(n: number): string {
    if (!n) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let u = 0;
    let x = n;
    while (x >= 1024 && u < units.length - 1) { x /= 1024; u++; }
    return `${x.toFixed(u === 0 ? 0 : 1)} ${units[u]}`;
  }

  async function cancel() {
    const id = $jobId;
    if (id) await apiPost(`/api/jobs/${id}/cancel`, {});
  }

  $: finished = $progress.status !== "running";
  $: totalTime = finished ? Date.now() - $progress.startTime : 0;

  onMount(() => {
    const id = $jobId;
    if (!id) return;

    es = new EventSource(`/api/jobs/${id}/events`);

    const on = (type: string, fn: (e: MessageEvent) => void) =>
      es?.addEventListener(type, ((e: Event) => {
        // Guard: native EventSource errors don't have .data
        if (!(e instanceof MessageEvent) || !e.data) return;
        fn(e);
      }) as any);

    on("stage", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({ ...p, stage: d.stage ?? "" }));
    });

    on("overall_progress", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({
        ...p,
        done: d.done ?? p.done,
        total: d.total ?? p.total,
        ok: d.ok ?? p.ok,
        failed: d.failed ?? p.failed,
      }));
    });

    on("object_started", (e) => {
      const d = JSON.parse(e.data);
      currentObjectStart = Date.now();
      progress.update((p) => ({
        ...p,
        current: {
          relation_id: d.relation_id,
          name: d.name,
          index: d.index ?? 0,
          total: d.total ?? 0,
        },
        currentPhase: "fetch_overpass",
        currentStats: null,
      }));
    });

    on("object_phase", (e) => {
      const d = JSON.parse(e.data);
      const phase = typeof d?.phase === "string" ? d.phase : "";
      progress.update((p) => ({
        ...p,
        currentPhase: phase || p.currentPhase,
      }));
    });

    on("object_stats", (e) => {
      const d = JSON.parse(e.data);
      const stats = d.stats ?? {};
      // Track object time for ETA
      if (currentObjectStart) {
        const elapsed = Date.now() - currentObjectStart;
        currentObjectStart = null;
        progress.update((p) => {
          const times = [...p.objectTimes, elapsed];
          if (times.length > 8) times.shift();
          return {
            ...p,
            currentStats: stats,
            sumPolygons: p.sumPolygons + Number(stats.polygons ?? 0),
            sumVertices: p.sumVertices + Number(stats.vertices ?? 0),
            sumBytes: p.sumBytes + Number(stats.osm_source_bytes ?? 0),
            objectTimes: times,
          };
        });
      } else {
        progress.update((p) => ({
          ...p,
          currentStats: stats,
          sumPolygons: p.sumPolygons + Number(stats.polygons ?? 0),
          sumVertices: p.sumVertices + Number(stats.vertices ?? 0),
          sumBytes: p.sumBytes + Number(stats.osm_source_bytes ?? 0),
        }));
      }
    });

    on("object_done", (e) => {
      const d = JSON.parse(e.data);
      if (d?.ok !== false) {
        progress.update((p) => ({ ...p, currentPhase: "" }));
        return;
      }
      const relationId = Number(d.relation_id || 0);
      const failure = {
        relation_id: Number.isFinite(relationId) ? relationId : 0,
        name: typeof d.name === "string" ? d.name : undefined,
        error: typeof d.error === "string" && d.error.trim() ? d.error.trim() : "Unknown error",
      };
      progress.update((p) => {
        const existingIdx = p.failedObjects.findIndex((x) => x.relation_id === failure.relation_id);
        const next = [...p.failedObjects];
        if (existingIdx >= 0) next[existingIdx] = failure;
        else next.push(failure);
        return { ...p, currentPhase: "", failedObjects: next };
      });
    });

    on("object_clipped_ready", (e) => {
      const d = JSON.parse(e.data);
      const rid = Number(d?.relation_id || 0);
      if (!rid || Number.isNaN(rid)) return;
      liveClipReadyEvent.set({
        relation_id: rid,
        name: typeof d?.name === "string" ? d.name : undefined,
      });
    });

    on("land_polygons_download_progress", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({
        ...p,
        lpDone: d.done_bytes ?? p.lpDone,
        lpTotal: d.total_bytes ?? p.lpTotal,
      }));
    });

    on("clip_cache_stats", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({
        ...p,
        clipCacheHits: Number(d.hits ?? p.clipCacheHits),
        clipCacheMisses: Number(d.misses ?? p.clipCacheMisses),
      }));
    });

    on("error", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({
        ...p,
        errorMsg: d.message ?? "Error",
        status: "error" as JobStatus,
      }));
    });

    on("log", (e) => {
      const d = JSON.parse(e.data);
      if (d.message) {
        progress.update((p) => ({
          ...p,
          log: [...p.log, d.message].slice(-200),
        }));
      }
    });

    on("job_finished", (e) => {
      const d = JSON.parse(e.data);
      progress.update((p) => ({
        ...p,
        status: (d.status ?? "done") as JobStatus,
      }));
      es?.close();
    });
  });

  onDestroy(() => {
    es?.close();
  });
</script>

<div class="overlay" transition:fly={{ y: 300, duration: 300 }}>
  <div class="handle-bar">
    <div class="handle" />
  </div>

  {#if finished}
    <CompletionSummary
      status={$progress.status}
      ok={$progress.ok}
      failed={$progress.failed}
      {totalTime}
      sumPolygons={$progress.sumPolygons}
      sumVertices={$progress.sumVertices}
      sumBytes={$progress.sumBytes}
      failedObjects={$progress.failedObjects}
      admName={$admName}
      adminLevel={$exportAdminLevel}
      on:click={resetToSelect}
    />
  {:else}
    <div class="content">
      <header class="head">
        <div class="head-left">
          <h3 class="title">Exporting</h3>
          {#if $progress.stage}
            <span class="stage">{stageLabel($progress.stage)}</span>
          {/if}
        </div>
        <div class="head-right">
          {#if $eta}
            <span class="eta">{fmtEta($eta)}</span>
          {/if}
          <Button small variant="danger" on:click={cancel}>Cancel</Button>
        </div>
      </header>

      <ProgressBar value={$progress.done} max={$progress.total} />

      <ProgressStats
        done={$progress.done}
        total={$progress.total}
        ok={$progress.ok}
        failed={$progress.failed}
        sumPolygons={$progress.sumPolygons}
        sumVertices={$progress.sumVertices}
        sumBytes={$progress.sumBytes}
      />

      {#if $progress.current}
        <div class="current-obj">
          <span class="current-label">Processing:</span>
          <strong class="current-name">
            {$progress.current.name ?? `r${$progress.current.relation_id}`}
          </strong>
          <span class="current-index">
            ({$progress.current.index}/{$progress.current.total})
          </span>
        </div>
        {#if $progress.currentPhase}
          <div class="current-phase">
            {phaseLabel($progress.currentPhase)}
          </div>
        {/if}
      {/if}

      {#if $progress.lpDone !== null}
        <div class="land-section">
          <span class="land-label">Downloading land polygons:</span>
          <span class="land-progress">
            {fmtBytes($progress.lpDone ?? 0)} / {$progress.lpTotal ? fmtBytes($progress.lpTotal) : "?"}
          </span>
        </div>
      {/if}
      {#if $progress.clipCacheHits > 0 || $progress.clipCacheMisses > 0}
        <div class="land-section">
          <span class="land-label">Clip cache:</span>
          <span class="land-progress">
            hits {$progress.clipCacheHits}, misses {$progress.clipCacheMisses}
          </span>
        </div>
      {/if}

      {#if $progress.errorMsg}
        <div class="error-msg">{$progress.errorMsg}</div>
      {/if}

      <LogPanel log={$progress.log} />
    </div>
  {/if}
</div>

<style>
  .overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    max-height: 50%;
    min-height: 180px;
    background: var(--bg-card, #fff);
    border-top: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: var(--radius-lg, 14px) var(--radius-lg, 14px) 0 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
    z-index: 20;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .handle-bar {
    display: flex;
    justify-content: center;
    padding: 8px 0 4px;
    cursor: grab;
    flex-shrink: 0;
  }
  .handle {
    width: 36px;
    height: 4px;
    border-radius: 2px;
    background: rgba(15, 23, 42, 0.12);
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 0 16px 14px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  .head-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .head-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .title {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary, #0f172a);
  }
  .stage {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    font-weight: 500;
  }
  .eta {
    font-size: 12px;
    color: var(--text-secondary, #475569);
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .current-obj {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 13px;
    flex-wrap: wrap;
  }
  .current-label {
    color: var(--text-muted, #94a3b8);
  }
  .current-name {
    color: var(--text-primary, #0f172a);
  }
  .current-index {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
  }
  .current-phase {
    font-size: 12px;
    color: var(--text-secondary, #475569);
    font-weight: 500;
  }

  .land-section {
    display: flex;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary, #475569);
    flex-wrap: wrap;
  }
  .land-label {
    color: var(--text-muted, #94a3b8);
  }
  .land-progress {
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .error-msg {
    padding: 8px 10px;
    border-radius: var(--radius-sm, 6px);
    background: #fef2f2;
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #991b1b;
    font-size: 13px;
  }
</style>
