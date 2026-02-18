<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { AreaItem } from "../../lib/types";

  export let id: number;
  export let item: AreaItem | undefined;
  export let isSelected: boolean;
  export let skeleton = false;

  const dispatch = createEventDispatcher<{
    toggle: { id: number; shiftKey: boolean };
    info: { id: number };
  }>();

  function emitToggle(shiftKey: boolean) {
    dispatch("toggle", { id, shiftKey });
  }

  function onRowClick(e: MouseEvent) {
    emitToggle(Boolean(e.shiftKey));
  }

  function onRowKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      emitToggle(Boolean(e.shiftKey));
    }
  }

  function onCheckboxClick(e: MouseEvent) {
    emitToggle(Boolean(e.shiftKey));
  }

  function onInfoClick() {
    dispatch("info", { id });
  }
</script>

{#if skeleton}
  <div class="row skeleton">
    <div class="skel-box" />
    <div class="skel-bar long" />
    <div class="skel-bar short" />
  </div>
{:else}
  <div
    class="row"
    class:selected={isSelected}
    role="button"
    tabindex="0"
    on:click={onRowClick}
    on:keydown={onRowKeydown}
  >
    <input
      class="checkbox"
      type="checkbox"
      checked={isSelected}
      on:click|stopPropagation={onCheckboxClick}
      tabindex="-1"
    />
    <span class="name">{item?.name ?? `relation ${id}`}</span>
    <button
      class="info-btn"
      type="button"
      title="Show all object tags"
      aria-label={`Show details for relation ${id}`}
      on:click|stopPropagation={onInfoClick}
    >
      i
    </button>
    <span class="rid">r{id}</span>
  </div>
{/if}

<style>
  .row {
    display: grid;
    grid-template-columns: 18px 1fr auto auto;
    gap: 8px;
    align-items: center;
    padding: 7px 10px;
    border-radius: var(--radius-sm, 6px);
    border: 1px solid rgba(15, 23, 42, 0.06);
    background: #fff;
    cursor: pointer;
    transition: all 0.12s;
    user-select: none;
  }
  .row:hover {
    border-color: var(--accent, #3b82f6);
    background: #f8fafc;
  }
  .row:focus-visible {
    outline: none;
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }
  .row.selected {
    border-color: rgba(59, 130, 246, 0.25);
    background: rgba(59, 130, 246, 0.04);
  }
  .checkbox {
    width: 15px;
    height: 15px;
    accent-color: var(--accent, #3b82f6);
    cursor: pointer;
    margin: 0;
  }
  .name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary, #0f172a);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rid {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    font-family: var(--font-mono, monospace);
    flex-shrink: 0;
  }
  .info-btn {
    width: 20px;
    height: 20px;
    border: 1px solid rgba(15, 23, 42, 0.16);
    border-radius: 999px;
    background: #fff;
    color: var(--text-secondary, #475569);
    font-size: 12px;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }
  .info-btn:hover {
    border-color: var(--accent, #3b82f6);
    color: var(--accent, #3b82f6);
    background: rgba(59, 130, 246, 0.06);
  }
  .info-btn:focus-visible {
    outline: none;
    border-color: var(--accent, #3b82f6);
    box-shadow: 0 0 0 3px var(--accent-ring, rgba(59, 130, 246, 0.15));
  }

  /* Skeleton */
  .skeleton {
    pointer-events: none;
  }
  .skel-box {
    width: 15px;
    height: 15px;
    border-radius: 3px;
    background: #e2e8f0;
    animation: pulse 1.2s ease-in-out infinite;
  }
  .skel-bar {
    height: 12px;
    border-radius: 3px;
    background: #e2e8f0;
    animation: pulse 1.2s ease-in-out infinite;
  }
  .skel-bar.long { width: 70%; }
  .skel-bar.short { width: 48px; }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
</style>
