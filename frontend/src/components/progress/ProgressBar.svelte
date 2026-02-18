<script lang="ts">
  export let value = 0;
  export let max = 100;
  export let animated = true;

  $: pct = max > 0 ? Math.max(0, Math.min(100, Math.round((value / max) * 100))) : 0;
</script>

<div class="bar-wrap">
  <div class="track">
    <div
      class="fill"
      class:animated
      style:width="{pct}%"
    />
  </div>
  <span class="pct">{pct}%</span>
</div>

<style>
  .bar-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .track {
    flex: 1;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.08);
  }
  .fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--accent, #3b82f6), #60a5fa);
    min-width: 0;
  }
  .fill.animated {
    transition: width 0.4s ease;
  }
  .pct {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary, #0f172a);
    min-width: 36px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
