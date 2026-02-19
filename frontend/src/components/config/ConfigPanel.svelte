<script lang="ts">
  import { slide } from "svelte/transition";
  import Button from "../shared/Button.svelte";
  import ParentSearch from "./ParentSearch.svelte";
  import {
    adminLevel,
    scopeMode,
    parentRelationId,
    overpassUrl,
    showOnlySelectedOnMap,
    forceRefreshOsmSource,
    worldScopeAllowed,
    allIds,
    loadIds,
    clearSearchResults,
    loadingIds,
  } from "../../lib/stores";
  import Toggle from "../shared/Toggle.svelte";

  const presets = [
    { level: "2", label: "2 — countries" },
    { level: "4", label: "4 — regions" },
    { level: "6", label: "6 — districts" },
  ];

  let showAdvanced = false;
  let loading = false;

  async function handleLoad() {
    loading = true;
    try {
      await loadIds();
    } finally {
      loading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") handleLoad();
  }

  $: if (!$worldScopeAllowed && $scopeMode === "world") {
    $scopeMode = "parent";
  }
</script>

<div class="card">
  <div class="section-title">Area & Level</div>

  <div class="field">
    <span class="label">Admin level</span>
    <div class="input-row">
      <input
        class="input level-input"
        bind:value={$adminLevel}
        inputmode="numeric"
        placeholder="2"
        on:keydown={handleKeydown}
      />
      <div class="presets">
        {#each presets as p}
          <button
            class="preset"
            class:active={$adminLevel === p.level}
            on:click={() => ($adminLevel = p.level)}
          >
            {p.label}
          </button>
        {/each}
      </div>
    </div>
  </div>

  <div class="field">
    <span class="label">Scope</span>
    <div class="seg">
      <button
        class="seg-btn"
        class:active={$scopeMode === "world"}
        disabled={!$worldScopeAllowed}
        on:click={() => ($scopeMode = "world")}
      >
        Worldwide
      </button>
      <button
        class="seg-btn"
        class:active={$scopeMode === "parent"}
        on:click={() => ($scopeMode = "parent")}
      >
        Within region
      </button>
    </div>
    <div class="hint">
      {#if !$worldScopeAllowed}
        Worldwide scope is available only for admin level 2.
      {:else if $scopeMode === "world"}
        Loads objects at this admin level worldwide.
      {:else}
        Loads objects within a specific parent region (e.g. a country).
      {/if}
    </div>
  </div>

  {#if $scopeMode === "parent"}
    <ParentSearch />
  {/if}

  <button class="advanced-toggle" on:click={() => (showAdvanced = !showAdvanced)}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
    Advanced settings
    <span class="chevron" class:open={showAdvanced}>&#9662;</span>
  </button>

  {#if showAdvanced}
    <div class="advanced" transition:slide={{ duration: 200 }}>
      <div class="field">
        <span class="label">Overpass URL (optional)</span>
        <input class="input" bind:value={$overpassUrl} placeholder="Use default" />
      </div>
      <div class="field">
        <Toggle bind:checked={$showOnlySelectedOnMap} label="Show only selected on map" />
      </div>
      <div class="field">
        <Toggle bind:checked={$forceRefreshOsmSource} label="Force refresh osm_source (ignore cached object files)" />
      </div>
      <div class="hint">
        Geometry preview is loaded only for selected objects. For very large selections, map preview falls back to bbox for stability.
      </div>
    </div>
  {/if}

  <div class="action-row">
    <Button
      variant="primary"
      {loading}
      disabled={$loadingIds || ($scopeMode === "parent" && !$parentRelationId)}
      on:click={handleLoad}
    >
      {$loadingIds ? "Loading..." : "Load objects"}
    </Button>
    <Button
      variant="secondary"
      disabled={$loadingIds || !$allIds.length}
      on:click={clearSearchResults}
    >
      Clear results
    </Button>
  </div>
</div>

<style>
  .card {
    background: var(--bg-card, #ffffff);
    border: 1px solid rgba(15, 23, 42, 0.06);
    border-radius: var(--radius-lg, 14px);
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .section-title {
    font-weight: 600;
    font-size: 13px;
    color: var(--text-primary, #0f172a);
    letter-spacing: 0.1px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted, #94a3b8);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }
  .hint {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    line-height: 1.35;
  }
  .input {
    padding: 8px 10px;
    border: 1px solid rgba(15, 23, 42, 0.12);
    border-radius: var(--radius-sm, 6px);
    font-size: 13px;
    font-family: inherit;
    outline: none;
    background: #fff;
    color: var(--text-primary, #0f172a);
    width: 100%;
    box-sizing: border-box;
  }
  .input:focus {
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }
  .input-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .level-input {
    width: 52px;
    flex-shrink: 0;
    text-align: center;
  }
  .presets {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .preset {
    font-size: 11px;
    padding: 5px 8px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: var(--radius-sm, 6px);
    background: var(--bg-input, #f1f5f9);
    cursor: pointer;
    color: var(--text-secondary, #475569);
    font-family: inherit;
    transition: all 0.15s;
    white-space: nowrap;
  }
  .preset:hover {
    border-color: var(--accent, #3b82f6);
    color: var(--accent, #3b82f6);
  }
  .preset.active {
    background: var(--accent, #3b82f6);
    color: #fff;
    border-color: var(--accent, #3b82f6);
  }

  .seg {
    display: flex;
    gap: 0;
    background: var(--bg-input, #f1f5f9);
    border-radius: var(--radius-md, 10px);
    padding: 3px;
    border: 1px solid rgba(15, 23, 42, 0.06);
  }
  .seg-btn {
    flex: 1;
    border: none;
    background: transparent;
    padding: 7px 10px;
    border-radius: calc(var(--radius-md, 10px) - 2px);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    color: var(--text-secondary, #475569);
    font-family: inherit;
    transition: all 0.15s;
  }
  .seg-btn.active {
    background: var(--bg-card, #fff);
    color: var(--text-primary, #0f172a);
    box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  }
  .seg-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .advanced-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted, #94a3b8);
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px 0;
    font-family: inherit;
  }
  .advanced-toggle:hover {
    color: var(--text-secondary, #475569);
  }
  .chevron {
    font-size: 10px;
    transition: transform 0.2s;
  }
  .chevron.open {
    transform: rotate(180deg);
  }
  .advanced {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 4px;
    border-top: 1px solid rgba(15, 23, 42, 0.06);
  }
  .action-row {
    padding-top: 4px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
</style>
