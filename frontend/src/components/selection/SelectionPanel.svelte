<script lang="ts">
  import { fade } from "svelte/transition";
  import { onDestroy } from "svelte";
  import Button from "../shared/Button.svelte";
  import Toggle from "../shared/Toggle.svelte";
  import Alert from "../shared/Alert.svelte";
  import ObjectRow from "./ObjectRow.svelte";
  import LoadingSpinner from "../shared/LoadingSpinner.svelte";
  import type { AreaItem } from "../../lib/types";
  import {
    allIds,
    itemsById,
    selected,
    filterText,
    pageIds,
    totalCount,
    selectedCount,
    previewLoadProgress,
    loadingIds,
    errorMsg,
    warningMsg,
    clipLand,
    toggle,
    selectAllPage,
    deselectAllPage,
    selectAll,
    deselectAll,
    startJob,
  } from "../../lib/stores";

  let starting = false;
  let lastToggledId: number | null = null;
  let infoOpen = false;
  let infoItem: AreaItem | null = null;
  let infoRelationId: number | null = null;
  let infoTagEntries: [string, unknown][] = [];
  let infoFilter = "";
  let infoTagEntriesFiltered: [string, unknown][] = [];

  async function handleStartJob() {
    starting = true;
    try {
      await startJob();
    } finally {
      starting = false;
    }
  }

  function handleToggle(id: number, shiftKey: boolean) {
    if (shiftKey && lastToggledId !== null) {
      const ids = $pageIds;
      const a = ids.indexOf(lastToggledId);
      const b = ids.indexOf(id);
      if (a >= 0 && b >= 0) {
        const [start, end] = a <= b ? [a, b] : [b, a];
        const shouldSelect = !$selected.has(id);
        const next = new Set($selected);
        for (let i = start; i <= end; i += 1) {
          const rid = ids[i];
          if (shouldSelect) next.add(rid);
          else next.delete(rid);
        }
        selected.set(next);
        lastToggledId = id;
        return;
      }
    }
    toggle(id);
    lastToggledId = id;
  }

  function onRowToggle(e: CustomEvent<{ id: number; shiftKey: boolean }>) {
    handleToggle(e.detail.id, Boolean(e.detail.shiftKey));
  }

  function onRowInfo(e: CustomEvent<{ id: number }>) {
    const id = e.detail.id;
    const item = $itemsById.get(id);
    infoRelationId = id;
    infoItem = item ?? null;
    infoOpen = true;
  }

  function closeInfo() {
    infoOpen = false;
    infoItem = null;
    infoRelationId = null;
    infoFilter = "";
  }

  function onWindowKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && infoOpen) {
      e.preventDefault();
      closeInfo();
    }
  }

  $: infoTagEntries = Object.entries((infoItem?.tags ?? {}) as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b));

  $: infoTagEntriesFiltered = (() => {
    const q = infoFilter.trim().toLowerCase();
    if (!q) return infoTagEntries;
    return infoTagEntries.filter(([k, v]) => {
      const key = String(k || "").toLowerCase();
      const val = String(v ?? "").toLowerCase();
      return key.includes(q) || val.includes(q);
    });
  })();

  onDestroy(() => {
    infoOpen = false;
  });
</script>

<div class="card">
  <div class="section-title">Select Objects</div>

  {#if $loadingIds}
    <div class="loading-state">
      <LoadingSpinner size={24} />
      <span>Loading objects...</span>
    </div>
  {:else if !$allIds.length}
    <div class="empty">
      Set parameters above and click <strong>Load objects</strong> to see available administrative boundaries.
      <br/><br/>
      Then select them via checkboxes or by clicking on the map.
    </div>
  {:else}
    <!-- KPI summary -->
    <div class="kpis">
      <div class="kpi">
        <div class="kpi-num">{$totalCount}</div>
        <div class="kpi-label">total</div>
      </div>
      <div class="kpi accent">
        <div class="kpi-num">{$selectedCount}</div>
        <div class="kpi-label">selected</div>
      </div>
      <div class="kpi">
        <div class="kpi-num">{$pageIds.length}</div>
        <div class="kpi-label">shown</div>
      </div>
    </div>

    <!-- Filter -->
    <div class="filter-row">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        class="filter-input"
        bind:value={$filterText}
        placeholder="Filter by name or ID..."
      />
      {#if $filterText}
        <button class="clear-btn" on:click={() => ($filterText = "")}>&times;</button>
      {/if}
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <Button small on:click={selectAllPage}>Select shown</Button>
      <Button small on:click={deselectAllPage}>Deselect shown</Button>
      <Button small on:click={selectAll}>Select all</Button>
      <Button small on:click={deselectAll}>Deselect all</Button>
    </div>

    <!-- Object list -->
    <div class="list">
      {#each $pageIds as id (id)}
        {@const item = $itemsById.get(id)}
        {#if item}
          <ObjectRow
            {id}
            {item}
            isSelected={$selected.has(id)}
            on:toggle={onRowToggle}
            on:info={onRowInfo}
          />
        {:else}
          <ObjectRow {id} item={undefined} isSelected={$selected.has(id)} skeleton={true} />
        {/if}
      {/each}
      {#if !$pageIds.length && $filterText}
        <div class="empty-filter">No matches for "{$filterText}"</div>
      {/if}
    </div>

    {#if $selectedCount > 0}
      <div class="loading-hint">
        {#if $previewLoadProgress.isLoading || $previewLoadProgress.inflight > 0 || $previewLoadProgress.pending > 0}
          <LoadingSpinner size={14} />
          <span>
            Loading selected previews...
            {$previewLoadProgress.loaded} / {$previewLoadProgress.selectedTotal}
            {#if $previewLoadProgress.inflight > 0}
              (in flight: {$previewLoadProgress.inflight})
            {/if}
          </span>
        {:else}
          <span>
            Selected previews ready: {$previewLoadProgress.loaded} / {$previewLoadProgress.selectedTotal}
          </span>
        {/if}
      </div>
    {/if}

  {/if}

  <!-- Alerts (keyed to force recreation when message changes) -->
  {#if $errorMsg}
    {#key $errorMsg}
      <div transition:fade={{ duration: 150 }}>
        <Alert variant="error" dismissible>{$errorMsg}</Alert>
      </div>
    {/key}
  {/if}
  {#if $warningMsg}
    {#key $warningMsg}
      <div transition:fade={{ duration: 150 }}>
        <Alert variant="warning" dismissible>{$warningMsg}</Alert>
      </div>
    {/key}
  {/if}

  <!-- Action bar -->
  {#if $allIds.length > 0}
    <div class="action-bar">
      <Toggle bind:checked={$clipLand} label="Clip to land" />
      <Button
        variant="primary"
        disabled={!$selectedCount}
        loading={starting}
        on:click={handleStartJob}
      >
        Start Export{$selectedCount ? ` (${$selectedCount})` : ""}
      </Button>
    </div>
  {/if}
</div>

<svelte:window on:keydown={onWindowKeydown} />

{#if infoOpen}
  <div class="info-modal-backdrop" on:click={closeInfo}>
    <div
      class="info-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Object information"
      on:click|stopPropagation
    >
      <div class="info-modal-head">
        <div>
          <div class="info-modal-title">{infoItem?.name ?? `relation ${infoRelationId}`}</div>
          <div class="info-modal-subtitle">r{infoRelationId}</div>
        </div>
        <button class="info-close-btn" type="button" on:click={closeInfo} aria-label="Close details">×</button>
      </div>

      {#if infoTagEntries.length}
        <div class="info-filter">
          <svg class="info-filter-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            class="info-filter-input"
            bind:value={infoFilter}
            placeholder="Search tags (key or value)..."
          />
          {#if infoFilter.trim()}
            <button class="info-filter-clear" type="button" on:click={() => (infoFilter = "")} aria-label="Clear tag search">
              ×
            </button>
          {/if}
          <div class="info-filter-count">
            {infoTagEntriesFiltered.length} / {infoTagEntries.length}
          </div>
        </div>
        <div class="info-tags-wrap">
          <table class="info-tags-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {#if infoTagEntriesFiltered.length}
                {#each infoTagEntriesFiltered as [key, value] (key)}
                  <tr>
                    <td class="tag-key">{key}</td>
                    <td class="tag-value">{String(value)}</td>
                  </tr>
                {/each}
              {:else}
                <tr>
                  <td class="tag-empty" colspan="2">No matches for "{infoFilter.trim()}"</td>
                </tr>
              {/if}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="info-empty">No tags are available for this object.</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .card {
    background: var(--bg-card, #ffffff);
    border: 1px solid rgba(15, 23, 42, 0.06);
    border-radius: var(--radius-lg, 14px);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
    min-height: 0;
  }
  .section-title {
    font-weight: 600;
    font-size: 13px;
    color: var(--text-primary, #0f172a);
    letter-spacing: 0.1px;
  }

  .loading-state {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 20px 0;
    color: var(--text-muted, #94a3b8);
    font-size: 13px;
    justify-content: center;
  }

  .empty {
    font-size: 13px;
    color: var(--text-secondary, #475569);
    line-height: 1.5;
    padding: 12px 0;
  }

  /* KPIs */
  .kpis {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
  }
  .kpi {
    background: var(--bg-input, #f1f5f9);
    border-radius: var(--radius-sm, 6px);
    padding: 8px 10px;
    text-align: center;
  }
  .kpi.accent {
    background: rgba(59, 130, 246, 0.08);
  }
  .kpi-num {
    font-weight: 700;
    font-size: 16px;
    color: var(--text-primary, #0f172a);
  }
  .kpi.accent .kpi-num {
    color: var(--accent, #3b82f6);
  }
  .kpi-label {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    margin-top: 1px;
  }

  /* Filter */
  .filter-row {
    display: flex;
    align-items: center;
    gap: 0;
    position: relative;
  }
  .search-icon {
    position: absolute;
    left: 10px;
    color: var(--text-muted, #94a3b8);
    pointer-events: none;
  }
  .filter-input {
    flex: 1;
    padding: 7px 10px 7px 30px;
    border: 1px solid rgba(15, 23, 42, 0.12);
    border-radius: var(--radius-sm, 6px);
    font-size: 13px;
    font-family: inherit;
    outline: none;
    background: #fff;
    color: var(--text-primary, #0f172a);
  }
  .filter-input:focus {
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }
  .filter-input::placeholder {
    color: var(--text-muted, #94a3b8);
  }
  .clear-btn {
    position: absolute;
    right: 6px;
    width: 22px;
    height: 22px;
    border: none;
    border-radius: 50%;
    background: rgba(15, 23, 42, 0.06);
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }
  .clear-btn:hover {
    background: rgba(15, 23, 42, 0.12);
  }

  /* Toolbar */
  .toolbar {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  /* List */
  .list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-height: 380px;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 4px;
    min-height: 60px;
  }
  .list::-webkit-scrollbar {
    width: 4px;
  }
  .list::-webkit-scrollbar-track {
    background: transparent;
  }
  .list::-webkit-scrollbar-thumb {
    background: rgba(15, 23, 42, 0.1);
    border-radius: 2px;
  }

  .empty-filter {
    font-size: 13px;
    color: var(--text-muted, #94a3b8);
    text-align: center;
    padding: 16px 0;
  }

  .loading-hint {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
  }

  /* Action bar */
  .action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding-top: 8px;
    border-top: 1px solid rgba(15, 23, 42, 0.06);
    margin-top: 2px;
  }

  .info-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    z-index: 2000;
  }
  .info-modal {
    width: min(860px, 100%);
    max-height: min(80vh, 720px);
    background: #fff;
    border-radius: 12px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.22);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .info-modal-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px 10px;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  }
  .info-modal-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary, #0f172a);
  }
  .info-modal-subtitle {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    font-family: var(--font-mono, monospace);
  }
  .info-close-btn {
    width: 28px;
    height: 28px;
    border: 1px solid rgba(15, 23, 42, 0.14);
    border-radius: 8px;
    background: #fff;
    color: var(--text-secondary, #475569);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }
  .info-close-btn:hover {
    border-color: rgba(15, 23, 42, 0.24);
    background: #f8fafc;
  }
  .info-filter {
    display: grid;
    grid-template-columns: 16px 1fr auto;
    gap: 8px;
    align-items: center;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(15, 23, 42, 0.06);
    position: relative;
  }
  .info-filter-icon {
    color: var(--text-muted, #94a3b8);
    pointer-events: none;
  }
  .info-filter-input {
    width: 100%;
    padding: 7px 10px;
    border: 1px solid rgba(15, 23, 42, 0.12);
    border-radius: 8px;
    font-size: 13px;
    font-family: inherit;
    outline: none;
    background: #fff;
    color: var(--text-primary, #0f172a);
  }
  .info-filter-input:focus {
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }
  .info-filter-clear {
    position: absolute;
    right: 64px;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.06);
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    font-size: 18px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .info-filter-clear:hover {
    background: rgba(15, 23, 42, 0.12);
  }
  .info-filter-count {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .info-tags-wrap {
    overflow: auto;
    padding: 0 14px 14px;
  }
  .info-tags-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }
  .info-tags-table th {
    text-align: left;
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    padding: 10px 10px;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    position: sticky;
    top: 0;
    background: #fff;
    z-index: 1;
  }
  .info-tags-table td {
    border-bottom: 1px solid rgba(15, 23, 42, 0.06);
    padding: 8px 10px;
    vertical-align: top;
    font-size: 12px;
  }
  .info-tags-table tbody tr:nth-child(even) td {
    background: #f8fafc;
  }
  .info-tags-table tbody tr:hover td {
    background: rgba(59, 130, 246, 0.08);
  }
  .info-tags-table tbody tr:focus-within td {
    background: rgba(59, 130, 246, 0.10);
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.18);
  }
  .info-tags-table td + td {
    border-left: 1px solid rgba(15, 23, 42, 0.06);
  }
  .tag-key {
    width: 34%;
    color: var(--text-secondary, #475569);
    font-family: var(--font-mono, monospace);
    word-break: break-word;
  }
  .tag-value {
    color: var(--text-primary, #0f172a);
    word-break: break-word;
  }
  .tag-empty {
    padding: 10px 10px;
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    text-align: center;
  }
  .info-empty {
    padding: 16px 14px;
    font-size: 13px;
    color: var(--text-muted, #94a3b8);
  }
</style>
