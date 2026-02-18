export type BasemapDef = {
  id: string;
  label: string;
  tiles: string[];
  tileSize?: number;
  maxzoom?: number;
  attribution: string;
};

export const BASEMAPS: BasemapDef[] = [
  {
    id: "carto_positron",
    label: "CARTO Positron (light)",
    tiles: ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
    tileSize: 256,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  {
    id: "carto_darkmatter",
    label: "CARTO Dark Matter (dark)",
    tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
    tileSize: 256,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  {
    id: "osm_standard",
    label: "OpenStreetMap Standard",
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  {
    id: "osm_hot",
    label: "OSM Humanitarian (HOT)",
    tiles: ["https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles style by <a href="https://www.hotosm.org/">Humanitarian OpenStreetMap Team</a>',
  },
  {
    id: "cyclosm",
    label: "CyclOSM",
    tiles: ["https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by <a href="https://www.cyclosm.org/">CyclOSM</a>',
  },
  {
    id: "opentopomap",
    label: "OpenTopoMap",
    tiles: ["https://a.tile.opentopomap.org/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 17,
    attribution:
      'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="https://viewfinderpanoramas.org/">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
  },
  {
    id: "wikimedia",
    label: "Wikimedia Maps",
    tiles: ["https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 18,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://www.wikimedia.org/">Wikimedia</a>',
  },
  {
    id: "esri_world_imagery",
    label: "Esri World Imagery (satellite)",
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  },
];

export const DEFAULT_BASEMAP_ID = "carto_positron";

export function getBasemap(id: string | null | undefined): BasemapDef {
  const wanted = String(id || "").trim();
  return BASEMAPS.find((b) => b.id === wanted) || BASEMAPS[0];
}

export function rasterStyleForBasemap(id: string | null | undefined) {
  const bm = getBasemap(id);
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: bm.tiles,
        tileSize: bm.tileSize ?? 256,
        maxzoom: bm.maxzoom ?? 19,
        attribution: bm.attribution,
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  } as const;
}

export const defaultRasterStyle = rasterStyleForBasemap(DEFAULT_BASEMAP_ID);
