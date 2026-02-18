<script lang="ts">
  import { onMount } from "svelte";
  import { appMode, landPolygonsStatus, refreshLandPolygonsStatus, resetSavedSession, restoreSessionJobIfRunning } from "../../lib/stores";

  let healthy = false;

  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      healthy = res.ok;
    } catch {
      healthy = false;
    }
  }

  onMount(() => {
    restoreSessionJobIfRunning().catch(() => {});
    checkHealth();
    refreshLandPolygonsStatus();
    const iv = setInterval(checkHealth, 30000);
    return () => clearInterval(iv);
  });

  function handleResetSession() {
    resetSavedSession();
  }
</script>

<header class="topbar">
  <div class="brand">
    <div class="logo">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    </div>
    <div class="titles">
      <div class="title">OSM Boundary Exporter</div>
      <div class="subtitle">Batch download administrative boundaries as GeoJSON</div>
    </div>
  </div>

  <div class="status-row">
    {#if $appMode === "progress"}
      <div class="badge active">Exporting...</div>
    {/if}
    <div class="indicator" class:ok={healthy} title={healthy ? "Backend connected" : "Backend unreachable"}>
      <span class="dot" />
      <span class="label">{healthy ? "Connected" : "Offline"}</span>
    </div>
    {#if $landPolygonsStatus?.present}
      <div class="badge land">Land: cached</div>
    {/if}
    <button class="reset-btn" on:click={handleResetSession} title="Clear saved state and reset UI">
      Reset saved session
    </button>
  </div>
</header>

<style>
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    height: 48px;
    background: var(--bg-app, #111827);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--text-on-dark, #e2e8f0);
    flex-shrink: 0;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .logo {
    opacity: 0.8;
  }
  .title {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  .subtitle {
    font-size: 11px;
    opacity: 0.55;
    margin-top: 1px;
  }

  .status-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .indicator {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    opacity: 0.6;
  }
  .indicator.ok { opacity: 0.8; }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ef4444;
  }
  .indicator.ok .dot {
    background: #22c55e;
  }
  .indicator .label {
    display: none;
  }
  @media (min-width: 640px) {
    .indicator .label { display: inline; }
  }

  .badge {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: var(--radius-full, 999px);
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-on-dark, #e2e8f0);
    white-space: nowrap;
  }
  .badge.active {
    background: rgba(59, 130, 246, 0.2);
    color: #93c5fd;
  }
  .badge.land {
    background: rgba(34, 197, 94, 0.15);
    color: #86efac;
  }
  .reset-btn {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: var(--radius-full, 999px);
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-on-dark, #e2e8f0);
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
  }
  .reset-btn:hover {
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.28);
  }
</style>
