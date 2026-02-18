<script lang="ts">
  export let done = 0;
  export let total = 0;
  export let ok = 0;
  export let failed = 0;
  export let sumPolygons = 0;
  export let sumVertices = 0;
  export let sumBytes = 0;

  function fmtBytes(n: number): string {
    if (!n || Number.isNaN(n)) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let u = 0;
    let x = n;
    while (x >= 1024 && u < units.length - 1) { x /= 1024; u++; }
    return `${x.toFixed(u === 0 ? 0 : 1)} ${units[u]}`;
  }
</script>

<div class="stats">
  <div class="chip">
    <span class="chip-value">{done}/{total}</span>
    <span class="chip-label">done</span>
  </div>
  <div class="chip ok">
    <span class="chip-value">{ok}</span>
    <span class="chip-label">ok</span>
  </div>
  {#if failed > 0}
    <div class="chip fail">
      <span class="chip-value">{failed}</span>
      <span class="chip-label">failed</span>
    </div>
  {/if}
  {#if sumPolygons > 0}
    <div class="chip">
      <span class="chip-value">{sumPolygons.toLocaleString()}</span>
      <span class="chip-label">polygons</span>
    </div>
  {/if}
  {#if sumVertices > 0}
    <div class="chip">
      <span class="chip-value">{sumVertices.toLocaleString()}</span>
      <span class="chip-label">vertices</span>
    </div>
  {/if}
  {#if sumBytes > 0}
    <div class="chip">
      <span class="chip-value">{fmtBytes(sumBytes)}</span>
      <span class="chip-label">data</span>
    </div>
  {/if}
</div>

<style>
  .stats {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .chip {
    display: flex;
    align-items: baseline;
    gap: 4px;
    padding: 4px 10px;
    border-radius: var(--radius-full, 999px);
    background: var(--bg-input, #f1f5f9);
    border: 1px solid rgba(15, 23, 42, 0.04);
    font-size: 12px;
  }
  .chip-value {
    font-weight: 600;
    color: var(--text-primary, #0f172a);
    font-variant-numeric: tabular-nums;
  }
  .chip-label {
    color: var(--text-muted, #94a3b8);
  }
  .chip.ok {
    background: rgba(34, 197, 94, 0.08);
  }
  .chip.ok .chip-value {
    color: #16a34a;
  }
  .chip.fail {
    background: rgba(239, 68, 68, 0.08);
  }
  .chip.fail .chip-value {
    color: var(--error, #ef4444);
  }
</style>
