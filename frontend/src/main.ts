import App from "./App.svelte";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibregl from "maplibre-gl";
// Vite-friendly worker bundling for MapLibre (prevents runtime worker issues).
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import workerUrl from "maplibre-gl/dist/maplibre-gl-csp-worker?url";

// @ts-ignore
maplibregl.workerUrl = workerUrl;

new App({ target: document.getElementById("app")! });
