<script lang="ts">
  import TopBar from "./components/layout/TopBar.svelte";
  import Sidebar from "./components/layout/Sidebar.svelte";
  import MapView from "./components/MapView.svelte";
  import ProgressOverlay from "./components/progress/ProgressOverlay.svelte";
  import { appMode } from "./lib/stores";
</script>

<div class="app">
  <TopBar />
  <div class="body">
    <Sidebar />
    <section class="map-wrap">
      <MapView />
      {#if $appMode === "progress"}
        <ProgressOverlay />
      {/if}
    </section>
  </div>
</div>

<style>
  /* ── Design System: CSS Custom Properties ── */
  :global(:root) {
    --bg-app: #111827;
    --bg-sidebar: #1e293b;
    --bg-card: #ffffff;
    --bg-card-hover: #f8fafc;
    --bg-input: #f1f5f9;
    --bg-overlay: rgba(15, 23, 42, 0.80);

    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --text-on-dark: #e2e8f0;
    --text-on-dark-muted: rgba(226, 232, 240, 0.55);

    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --accent-light: rgba(59, 130, 246, 0.12);
    --accent-ring: rgba(59, 130, 246, 0.2);

    --success: #22c55e;
    --warning: #f59e0b;
    --error: #ef4444;

    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --radius-full: 999px;

    --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
    --shadow-elevated: 0 4px 12px rgba(0, 0, 0, 0.1);

    --font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  }

  :global(body) {
    margin: 0;
    background: var(--bg-app);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }

  /* MapLibre popup override */
  :global(.maplibregl-popup-content) {
    font-family: var(--font-sans) !important;
    border-radius: var(--radius-sm) !important;
    padding: 8px 10px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12) !important;
  }

  .app {
    height: 100vh;
    display: flex;
    flex-direction: column;
    color: var(--text-primary);
  }

  .body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 380px 1fr;
    background: var(--bg-app);
  }

  .map-wrap {
    min-height: 0;
    position: relative;
  }

  /* Responsive */
  @media (max-width: 1100px) {
    .body {
      grid-template-columns: 320px 1fr;
    }
  }
  @media (max-width: 768px) {
    .body {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr;
    }
    .map-wrap {
      order: -1;
    }
  }
</style>
