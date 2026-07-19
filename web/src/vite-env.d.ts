/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Mapbox public access token (pk.…). Set in web/.env.local. Optional —
   *  without it the map falls back to tokenless raster basemaps. */
  readonly VITE_MAPBOX_TOKEN?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
