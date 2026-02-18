<script lang="ts">
  import { fade } from "svelte/transition";
  import Button from "../shared/Button.svelte";
  import type { FailedObject, JobStatus } from "../../lib/types";

  export let status: JobStatus;
  export let ok = 0;
  export let failed = 0;
  export let totalTime = 0;
  export let sumPolygons = 0;
  export let sumVertices = 0;
  export let sumBytes = 0;
  export let failedObjects: FailedObject[] = [];
  export let admName: string | null = null;
  export let adminLevel: string | null = null;

  function fmtDuration(ms: number): string {
    const sec = Math.floor(ms / 1000);
    if (sec < 60) return `${sec}s`;
    const min = Math.floor(sec / 60);
    const s = sec % 60;
    if (min < 60) return `${min}m ${s}s`;
    const h = Math.floor(min / 60);
    return `${h}h ${min % 60}m`;
  }

  function fmtBytes(n: number): string {
    if (!n) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let u = 0;
    let x = n;
    while (x >= 1024 && u < units.length - 1) { x /= 1024; u++; }
    return `${x.toFixed(u === 0 ? 0 : 1)} ${units[u]}`;
  }

  $: isSuccess = status === "done" && failed === 0;
  $: isPartial = status === "done" && failed > 0;
  $: isCancelled = status === "cancelled";
  $: isError = status === "error";
  $: stem = admName && adminLevel ? `${admName}_admin_level_${adminLevel}` : "";
  $: displayedFailedObjects = failedObjects
    .filter((x) => x && x.relation_id > 0)
    .slice()
    .sort((a, b) => a.relation_id - b.relation_id);
</script>

<div class="summary" transition:fade={{ duration: 200 }}>
  <div class="icon" class:success={isSuccess} class:partial={isPartial} class:cancelled={isCancelled} class:error={isError}>
    {#if isSuccess}
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    {:else if isPartial}
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    {:else}
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="15" y1="9" x2="9" y2="15" />
        <line x1="9" y1="9" x2="15" y2="15" />
      </svg>
    {/if}
  </div>

  <div class="title">
    {#if isSuccess}
      Export completed!
    {:else if isPartial}
      Completed with errors
    {:else if isCancelled}
      Export cancelled
    {:else}
      Export failed
    {/if}
  </div>

  <div class="details">
    <span>{ok} of {ok + failed} objects exported</span>
    {#if totalTime > 0}
      <span>in {fmtDuration(totalTime)}</span>
    {/if}
  </div>

  {#if ok > 0}
    <div class="meta-row">
      {#if sumPolygons > 0}
        <div class="meta-item">{sumPolygons.toLocaleString()} polygons</div>
      {/if}
      {#if sumVertices > 0}
        <div class="meta-item">{sumVertices.toLocaleString()} vertices</div>
      {/if}
      {#if sumBytes > 0}
        <div class="meta-item">{fmtBytes(sumBytes)}</div>
      {/if}
    </div>
  {/if}

  {#if admName && adminLevel}
    <div class="path">
      Output: <code>data/geojson/{admName}/admin_level={adminLevel}/</code>
    </div>
    <div class="path">
      Objects:
      <code>osm_source/objects/</code>
      <code>land_only/objects/</code>
    </div>
    <div class="path">
      Combined:
      <code>{stem}_osm_source.geojson</code>
      <code>{stem}_land_only.geojson</code>
    </div>
  {/if}

  {#if displayedFailedObjects.length > 0}
    <div class="failed-wrap">
      <div class="failed-title">Failed objects ({displayedFailedObjects.length})</div>
      <div class="failed-list">
        {#each displayedFailedObjects as f (f.relation_id)}
          <div class="failed-item">
            <div class="failed-head">
              <code>r{f.relation_id}</code>
              <span>{f.name ?? `relation ${f.relation_id}`}</span>
            </div>
            <div class="failed-reason">{f.error}</div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="actions">
    <Button variant="primary" on:click>Back to selection</Button>
  </div>
</div>

<style>
  .summary {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 20px 16px;
    text-align: center;
  }
  .icon {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .icon.success {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
  }
  .icon.partial {
    background: rgba(245, 158, 11, 0.1);
    color: #f59e0b;
  }
  .icon.cancelled {
    background: rgba(100, 116, 139, 0.1);
    color: #64748b;
  }
  .icon.error {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }
  .title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary, #0f172a);
  }
  .details {
    font-size: 13px;
    color: var(--text-primary, #0f172a);
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: center;
    font-weight: 500;
  }
  .meta-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .meta-item {
    font-size: 12px;
    color: var(--text-secondary, #475569);
    font-weight: 600;
  }
  .path {
    font-size: 12px;
    color: var(--text-secondary, #475569);
    margin-top: 2px;
    font-weight: 500;
  }
  .path code {
    font-family: var(--font-mono, monospace);
    color: var(--text-primary, #0f172a);
    background: #e2e8f0;
    border: 1px solid rgba(15, 23, 42, 0.12);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
  }
  .actions {
    margin-top: 6px;
  }
  .failed-wrap {
    width: min(960px, 100%);
    text-align: left;
    margin-top: 8px;
    border: 1px solid rgba(239, 68, 68, 0.18);
    background: #fff7f7;
    border-radius: 10px;
    padding: 10px;
  }
  .failed-title {
    font-size: 13px;
    font-weight: 700;
    color: #991b1b;
    margin-bottom: 6px;
  }
  .failed-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 180px;
    overflow: auto;
    padding-right: 4px;
  }
  .failed-item {
    background: #fff;
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: 8px;
    padding: 7px 8px;
  }
  .failed-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-primary, #0f172a);
    margin-bottom: 3px;
  }
  .failed-head code {
    font-family: var(--font-mono, monospace);
    background: var(--bg-input, #f1f5f9);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
  }
  .failed-reason {
    font-size: 12px;
    color: #7f1d1d;
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
