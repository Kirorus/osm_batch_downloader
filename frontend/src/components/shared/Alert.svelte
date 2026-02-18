<script lang="ts">
  import { fade } from "svelte/transition";

  export let variant: "error" | "warning" | "info" = "info";
  export let dismissible = false;

  let visible = true;
</script>

{#if visible}
  <div class="alert {variant}" transition:fade={{ duration: 150 }}>
    <div class="content"><slot /></div>
    {#if dismissible}
      <button class="close" on:click={() => (visible = false)} aria-label="Close">&times;</button>
    {/if}
  </div>
{/if}

<style>
  .alert {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--radius-md, 10px);
    font-size: 13px;
    line-height: 1.4;
    border: 1px solid;
  }
  .content {
    flex: 1;
    min-width: 0;
    word-break: break-word;
  }
  .error {
    background: #fef2f2;
    border-color: rgba(239, 68, 68, 0.25);
    color: #991b1b;
  }
  .warning {
    background: #fffbeb;
    border-color: rgba(245, 158, 11, 0.3);
    color: #92400e;
  }
  .info {
    background: #eff6ff;
    border-color: rgba(59, 130, 246, 0.2);
    color: #1e40af;
  }
  .close {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 18px;
    line-height: 1;
    color: inherit;
    opacity: 0.5;
    padding: 0;
  }
  .close:hover { opacity: 0.8; }
</style>
