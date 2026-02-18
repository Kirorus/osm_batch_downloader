<script lang="ts">
  export let size = 18;
</script>

<svg
  class="spinner"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2.5"
  stroke-linecap="round"
>
  <circle cx="12" cy="12" r="10" opacity="0.2" />
  <path d="M12 2a10 10 0 0 1 10 10" />
</svg>

<style>
  .spinner {
    animation: spin 0.7s linear infinite;
    display: inline-block;
    vertical-align: middle;
    flex-shrink: 0;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
