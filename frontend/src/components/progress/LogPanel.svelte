<script lang="ts">
  import { afterUpdate } from "svelte";

  export let log: string[] = [];
  export let expanded = false;

  let logEl: HTMLPreElement;
  let hasNew = false;
  let prevLen = 0;

  afterUpdate(() => {
    if (log.length !== prevLen) {
      hasNew = true;
      prevLen = log.length;
      setTimeout(() => (hasNew = false), 800);
      if (expanded && logEl) {
        logEl.scrollTop = logEl.scrollHeight;
      }
    }
  });
</script>

<div class="log-panel">
  <button class="log-header" on:click={() => (expanded = !expanded)}>
    <span class="log-title">
      Log
      {#if hasNew}
        <span class="pulse" />
      {/if}
    </span>
    <span class="log-count">{log.length} entries</span>
    <span class="chevron" class:open={expanded}>&#9662;</span>
  </button>

  {#if !expanded && log.length > 0}
    <div class="preview">
      {#each log.slice(-3) as line}
        <div class="preview-line">{line}</div>
      {/each}
    </div>
  {/if}

  {#if expanded}
    <pre class="log-body" bind:this={logEl}>{log.join("\n")}</pre>
  {/if}
</div>

<style>
  .log-panel {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .log-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    background: none;
    border: none;
    cursor: pointer;
    font-family: inherit;
    color: var(--text-primary, #0f172a);
  }
  .log-title {
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .log-count {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    flex: 1;
    text-align: left;
  }
  .chevron {
    font-size: 10px;
    color: var(--text-muted, #94a3b8);
    transition: transform 0.2s;
  }
  .chevron.open {
    transform: rotate(180deg);
  }
  .pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent, #3b82f6);
    animation: blink 0.8s ease-in-out;
  }
  @keyframes blink {
    0% { opacity: 1; }
    100% { opacity: 0; }
  }

  .preview {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 4px 0;
  }
  .preview-line {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    color: var(--text-muted, #94a3b8);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
  }

  .log-body {
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
    background: #0f172a;
    color: #e2e8f0;
    padding: 10px 12px;
    border-radius: var(--radius-md, 10px);
    max-height: 200px;
    overflow-y: auto;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    line-height: 1.5;
  }
  .log-body::-webkit-scrollbar {
    width: 4px;
  }
  .log-body::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 2px;
  }
</style>
