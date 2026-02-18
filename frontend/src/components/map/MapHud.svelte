<script lang="ts">
  import { selectedCount } from "../../lib/stores";

  export let renderCount: number;
  export let totalCount: number;
  export let loadedGeomCount: number;
  export let pendingGeomCount: number;

  $: loadPct = Math.min(100, Math.round((loadedGeomCount / Math.max(1, totalCount)) * 100));
</script>

<div class="hud">
  <div class="legend">
    <span class="dot selected" /><span>Selected</span>
    <span class="dot unselected" /><span>Unselected</span>
    <span class="dot hover" /><span>Hover</span>
  </div>

  <div class="stats">
    <div class="stat-line">
      <span class="stat-label">On map:</span>
      <span class="stat-value">{renderCount} / {totalCount}</span>
    </div>
    <div class="stat-line">
      <span class="stat-label">Geometry loaded:</span>
      <span class="stat-value">{loadedGeomCount}</span>
      {#if pendingGeomCount > 0}
        <span class="pending">+{pendingGeomCount} pending</span>
      {/if}
    </div>
  </div>

  {#if renderCount > 0}
    <div class="bar">
      <div class="fill" style:width="{loadPct}%" />
    </div>
  {/if}

  {#if $selectedCount > 0}
    <button class="zoom-btn" on:click>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="15 3 21 3 21 9" />
        <polyline points="9 21 3 21 3 15" />
        <line x1="21" y1="3" x2="14" y2="10" />
        <line x1="3" y1="21" x2="10" y2="14" />
      </svg>
      Zoom to selection
    </button>
  {/if}
</div>

<style>
  .hud {
    position: absolute;
    left: 10px;
    bottom: 10px;
    background: rgba(255, 255, 255, 0.92);
    color: var(--text-primary, #0f172a);
    padding: 10px 12px;
    border-radius: var(--radius-md, 10px);
    font-size: 11px;
    line-height: 1.35;
    width: 220px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    pointer-events: auto;
    backdrop-filter: blur(8px);
    display: flex;
    flex-direction: column;
    gap: 7px;
  }

  .legend {
    display: grid;
    grid-template-columns: 10px auto 10px auto 10px auto;
    gap: 5px;
    align-items: center;
    opacity: 0.85;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .dot.selected { background: #3b82f6; }
  .dot.unselected { background: #94a3b8; }
  .dot.hover { background: #38bdf8; }

  .stats {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .stat-line {
    display: flex;
    gap: 4px;
    align-items: baseline;
  }
  .stat-label {
    color: var(--text-muted, #94a3b8);
  }
  .stat-value {
    font-weight: 600;
  }
  .pending {
    color: var(--text-muted, #94a3b8);
    font-style: italic;
  }

  .bar {
    height: 4px;
    border-radius: 2px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.08);
  }
  .fill {
    height: 100%;
    background: var(--accent, #3b82f6);
    transition: width 0.3s ease;
  }

  .zoom-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    font-family: inherit;
    color: var(--accent, #3b82f6);
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 0;
  }
  .zoom-btn:hover {
    text-decoration: underline;
  }
</style>
