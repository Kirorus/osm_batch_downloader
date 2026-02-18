<script lang="ts">
  export let checked = false;
  export let label = "";
  export let disabled = false;
</script>

<label class="toggle" class:disabled>
  <div class="track" class:on={checked}>
    <div class="thumb" />
    <input type="checkbox" bind:checked {disabled} on:change />
  </div>
  {#if label}
    <span class="label">{label}</span>
  {/if}
  <slot />
</label>

<style>
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;
    font-size: 13px;
    color: var(--text-primary, #0f172a);
  }
  .toggle.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .track {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background: #cbd5e1;
    transition: background 0.2s ease;
    flex-shrink: 0;
  }
  .track.on {
    background: var(--accent, #3b82f6);
  }
  .thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.2s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  }
  .track.on .thumb {
    transform: translateX(16px);
  }
  input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }
  .label {
    line-height: 1.3;
  }
</style>
