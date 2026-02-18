<script lang="ts">
  import LoadingSpinner from "./LoadingSpinner.svelte";

  export let variant: "primary" | "secondary" | "ghost" | "danger" = "secondary";
  export let disabled = false;
  export let loading = false;
  export let small = false;
</script>

<button
  class="btn {variant}"
  class:small
  disabled={disabled || loading}
  on:click
>
  {#if loading}
    <LoadingSpinner size={small ? 14 : 16} />
  {/if}
  <slot />
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    border-radius: var(--radius-md, 10px);
    border: 1px solid var(--border-color, rgba(15, 23, 42, 0.12));
    background: var(--bg-card, #fff);
    color: var(--text-primary, #0f172a);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    line-height: 1.3;
    transition: all 0.15s ease;
    white-space: nowrap;
    user-select: none;
  }
  .btn:hover:not(:disabled) {
    border-color: rgba(15, 23, 42, 0.25);
    background: var(--bg-card-hover, #f8fafc);
  }
  .btn:active:not(:disabled) {
    transform: scale(0.98);
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .primary {
    background: var(--accent, #3b82f6);
    color: #fff;
    border-color: var(--accent, #3b82f6);
  }
  .primary:hover:not(:disabled) {
    background: var(--accent-hover, #2563eb);
    border-color: var(--accent-hover, #2563eb);
  }

  .ghost {
    background: transparent;
    border-color: transparent;
  }
  .ghost:hover:not(:disabled) {
    background: rgba(15, 23, 42, 0.06);
    border-color: transparent;
  }

  .danger {
    background: var(--error, #ef4444);
    color: #fff;
    border-color: var(--error, #ef4444);
  }
  .danger:hover:not(:disabled) {
    background: #dc2626;
    border-color: #dc2626;
  }

  .small {
    padding: 5px 10px;
    font-size: 12px;
  }
</style>
