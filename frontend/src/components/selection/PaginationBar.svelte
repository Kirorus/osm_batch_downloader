<script lang="ts">
  import { page, pageCount, setPage } from "../../lib/stores";
  import Button from "../shared/Button.svelte";

  function prev() { setPage($page - 1); }
  function next() { setPage($page + 1); }
  function goTo(p: number) { setPage(p); }

  /** Generate visible page numbers with ellipsis */
  function getPageNumbers(current: number, total: number): (number | "...")[] {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i);
    const pages: (number | "...")[] = [0];
    let start = Math.max(1, current - 1);
    let end = Math.min(total - 2, current + 1);
    if (start > 1) pages.push("...");
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < total - 2) pages.push("...");
    pages.push(total - 1);
    return pages;
  }

  $: pages = getPageNumbers($page, $pageCount);
</script>

<div class="pager">
  <Button small disabled={$page === 0} on:click={prev}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  </Button>

  <div class="numbers">
    {#each pages as p}
      {#if p === "..."}
        <span class="ellipsis">...</span>
      {:else}
        <button
          class="page-btn"
          class:active={p === $page}
          on:click={() => goTo(p)}
        >
          {p + 1}
        </button>
      {/if}
    {/each}
  </div>

  <Button small disabled={$page + 1 >= $pageCount} on:click={next}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  </Button>
</div>

<style>
  .pager {
    display: flex;
    align-items: center;
    gap: 4px;
    justify-content: center;
  }
  .numbers {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .page-btn {
    min-width: 28px;
    height: 28px;
    border: none;
    border-radius: var(--radius-sm, 6px);
    background: transparent;
    font-size: 12px;
    font-weight: 500;
    font-family: inherit;
    color: var(--text-secondary, #475569);
    cursor: pointer;
    transition: all 0.12s;
    padding: 0 4px;
  }
  .page-btn:hover {
    background: var(--bg-input, #f1f5f9);
  }
  .page-btn.active {
    background: var(--accent, #3b82f6);
    color: #fff;
  }
  .ellipsis {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    padding: 0 2px;
  }
</style>
