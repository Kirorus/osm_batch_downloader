<script lang="ts">
  import ConfigPanel from "../config/ConfigPanel.svelte";
  import SelectionPanel from "../selection/SelectionPanel.svelte";
  import { appMode } from "../../lib/stores";
</script>

<aside class="sidebar" class:dimmed={$appMode === "progress"}>
  <div class="scroll-area">
    <ConfigPanel />
    <SelectionPanel />
  </div>
</aside>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: var(--bg-sidebar, #1e293b);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    transition: opacity 0.3s ease;
  }
  .sidebar.dimmed {
    opacity: 0.6;
    pointer-events: none;
  }
  .scroll-area {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .scroll-area::-webkit-scrollbar {
    width: 5px;
  }
  .scroll-area::-webkit-scrollbar-track {
    background: transparent;
  }
  .scroll-area::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 3px;
  }
</style>
