<script lang="ts">
  import { slide } from "svelte/transition";
  import Button from "../shared/Button.svelte";
  import {
    parentRelationId,
    parentRelationName,
    parentQuery,
    parentAdminLevel,
    parentCandidates,
    searchParents,
    selectParent,
    clearParent,
  } from "../../lib/stores";

  let searching = false;

  async function handleSearch() {
    searching = true;
    try {
      await searchParents();
    } finally {
      searching = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") handleSearch();
  }
</script>

<div class="parent-search" transition:slide={{ duration: 200 }}>
  <div class="current">
    <span class="label">Parent region</span>
    <div class="row">
      <span class="pill">
        {$parentRelationId ? `${$parentRelationName || "selected"} (r${$parentRelationId})` : "not set"}
      </span>
      {#if $parentRelationId}
        <Button small on:click={clearParent}>Clear</Button>
      {/if}
    </div>
  </div>

  <div class="search-row">
    <div class="field narrow">
      <span class="label">Level</span>
      <input
        class="input"
        bind:value={$parentAdminLevel}
        inputmode="numeric"
        placeholder="2"
      />
    </div>
    <div class="field grow">
      <span class="label">Search by name</span>
      <input
        class="input"
        bind:value={$parentQuery}
        placeholder="Russia, Germany, RU, ..."
        on:keydown={handleKeydown}
      />
    </div>
    <div class="field action">
      <span class="label">&nbsp;</span>
      <Button small loading={searching} disabled={!$parentQuery.trim()} on:click={handleSearch}>
        Search
      </Button>
    </div>
  </div>

  {#if $parentCandidates.length}
    <div class="candidates" transition:slide={{ duration: 150 }}>
      {#each $parentCandidates as c}
        <button class="candidate" on:click={() => selectParent(c)}>
          <span class="cand-name">{c.name}</span>
          <span class="cand-id">r{c.relation_id}</span>
        </button>
      {/each}
    </div>
  {:else if $parentQuery.trim().length >= 2}
    <div class="empty-hint">No parent regions found for this query.</div>
  {/if}
</div>

<style>
  .parent-search {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 4px;
  }
  .current {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .pill {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: var(--radius-full, 999px);
    background: var(--bg-input, #f1f5f9);
    color: var(--text-secondary, #475569);
    border: 1px solid rgba(15, 23, 42, 0.06);
  }
  .search-row {
    display: flex;
    gap: 6px;
    align-items: flex-end;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field.narrow {
    width: 56px;
    flex-shrink: 0;
  }
  .field.grow {
    flex: 1;
    min-width: 0;
  }
  .field.action {
    flex-shrink: 0;
  }
  .label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted, #94a3b8);
  }
  .input {
    padding: 6px 10px;
    border: 1px solid rgba(15, 23, 42, 0.12);
    border-radius: var(--radius-sm, 6px);
    font-size: 13px;
    font-family: inherit;
    outline: none;
    background: #fff;
    color: var(--text-primary, #0f172a);
  }
  .input:focus {
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }
  .candidates {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
  }
  .empty-hint {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    padding: 4px 2px 0;
  }
  .candidate {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: var(--radius-sm, 6px);
    background: #fff;
    cursor: pointer;
    text-align: left;
    transition: border-color 0.15s;
    font-family: inherit;
  }
  .candidate:hover {
    border-color: var(--accent, #3b82f6);
    background: #f8fafc;
  }
  .cand-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary, #0f172a);
  }
  .cand-id {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    flex-shrink: 0;
    margin-left: 8px;
  }
</style>
