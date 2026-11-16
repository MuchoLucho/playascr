# AGENTS.md — Costa Rica Interactive Beach Safety & Behavior Atlas (`playascr`)

This document tracks the architecture, extraction pipeline, data schemas, internationalization (`i18n`), and implementation status for `playascr` so any AI agent or developer can seamlessly resume or extend the project.

## 1. Project Overview
- **Goal**: A 100% browser-only, static, mobile-first web application hosted on **GitHub Pages** showcasing all ~747 beaches of Costa Rica from *Atlas de Playas de Costa Rica con Énfasis en la Seguridad* (Dra. Isabel Arozarena Llopis, Programa RONMAC–UNA & ICT, 2024).
- **Frontend Stack & CI Build (`npm` + `Vite`)**: Managed via [`package.json`](package.json) (`leaflet`, `leaflet.markercluster`, `vite`) and [`vite.config.js`](vite.config.js), with static runtime data/locales/PWA assets copied into `dist/` and deployed to GitHub Pages via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) (`npm ci && npm run build`). Canvas vector rendering and static JSON/GeoJSON chunked 3-tier lazy loading keep runtime 100% browser-only.
- **Copyright-Safe Policy & Software Licensing**:
  - **Code License**: Application source code, build scripts, and architecture are licensed under **Apache License 2.0** ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)).
  - **Data IP Exclusion**: Scientific classifications, indicators, and geomorphological data are derived from *Atlas de Playas de Costa Rica con Énfasis en la Seguridad* (2024) by **Dra. Isabel Arozarena Llopis, Programa RONMAC – Universidad Nacional (UNA) & Instituto Costarricense de Turismo (ICT)** ([Official Portal](https://www.ict.go.cr/es/servicios-institucionales/atlas-de-playas.html)). The data itself is **NOT licensed under Apache 2.0**.
  - Do **NOT** extract or redistribute photographs (`Figuras`) or verbatim chapters from `ATLAS DE PLAYAS COSTA RICA web 2024.pdf` (no CC license in PDF).
  - Do **NOT** commit `ATLAS DE PLAYAS COSTA RICA web 2024.pdf` (175.6 MB exceeds GitHub's 100 MB file limit; ignored in `.gitignore`).
  - Extract factual geographic, cartographic, and safety indicator classifications; synthesize concise multilingual summaries; use **Esri World Imagery** satellite layer for aerial surf-zone inspection and **custom SVG diagrams** for the rip-current safety guide.
  - Comply with all third-party reference criteria: Leaflet (BSD-2), Leaflet.markercluster (MIT), Vite (MIT), OpenStreetMap (ODbL/CC-BY-SA), CARTO (terms), Esri (terms), OpenTopoMap (CC-BY-SA).

---

## 2. 3-Tier Lazy-Loading Architecture
1. **Tier 1 (Initial Boot)**:
   - `data/beaches-index.json` (324.7 KB raw): Lightweight array of all 735 beaches with `id`, `name`, `altNames`, `ignName`, `sector`, `region`, `lat`, `lng`, and compact language-neutral indicator enum codes (`rip`, `hazards`, `swim`, `family`, `surf`, `uses`, `accessType`, `accessMode`, `accessState`, `sand`, `geo`, `infra`, `visited`). Powers instant client-side search, multi-filter chips, and marker clustering.
   - `data/sectors-overview.json`: Metadata, bounding boxes `[minLng, minLat, maxLng, maxLat]`, region code, beach count, visited count, and bilingual sector summaries for all 30 sectors (`1P`–`23P`, `1C`–`7C`).
2. **Tier 2 (Semantic Zoom / Click Lazy Load)**:
   - `data/sectors/sector-{id}.geojson` (30 files, e.g., `sector-1P.geojson` … `sector-7C.geojson`): Fetched on demand with an in-memory cache when map `zoom >= 11` and sector bounds intersect viewport, or when a user clicks a beach.
   - Contains exact simplified `WGS84` shoreline `Polygon` / `MultiPolygon` geometries and synthesized `es` / `en` sector notes.
3. **Tier 3 (On-Demand Map Tiles & Custom SVGs)**:
   - OpenStreetMap (watermark-free fallback), optional CARTO Voyager (via `import.meta.env.CARTO_API_KEY` from `.env` / GitHub Actions secret `CARTO_API_KEY`, or gitignored `js/config.local.js`), Esri World Imagery (Satellite), and OpenTopoMap tiles loaded by Leaflet as needed.
   - Original SVG rip-current identification diagrams inside the Educational Safety Guide modal.
   - Local secrets (`.env`, `js/config.local.js`), `node_modules/`, and `dist/` are ignored via `.gitignore`; `.env.example` + `js/config.example.js` + `.github/workflows/deploy.yml` handle local templates & GitHub Pages secret injection (`vite.config.js` exposes `CARTO_` env vars via `envPrefix`).

---

## 3. PDF Structure & Extraction Notes (`scripts/extract_atlas.py`)
- **Source PDF**: `ATLAS DE PLAYAS COSTA RICA web 2024.pdf` (239 pages, 1800×1800 pt layout on map/glossary pages).
- **30 Coastal Sectors**:
  - *Guanacaste y Península de Nicoya*: `1P`–`8P`
  - *Golfo de Nicoya*: `9P`–`10P`
  - *Pacífico Central*: `11P`–`17P`
  - *Pacífico Sur*: `18P`–`23P`
  - *Caribe*: `1C`–`7C`
- **4 Thematic Maps per Sector**:
  1. *Peligros*: Rip-current polygon colors (`bajo`, `medio`, `alto`, `muy_alto`, `no_visitado`) + point hazard symbols (`oleaje_fuerte`, `rocas_intermareales`, `desembocadura`, `derrumbes`, `corales`, `animales_peligrosos`, `bloqueo_marea_alta`, `contaminacion`, `cables_peligrosos`, `ninguno_conocido`).
  2. *Accesos*: Public/restricted (`publico`, `restringido`), access mode (`vehiculo`, `pie`, `bote`), access state (`bueno`, `medio`, `malo`, `consultar_desembarco`), and access/parking/detour/viewpoint pins.
  3. *Color de la Arena y Geomorfología*: Pure vector beach polygons colored by geomorphology (`recta_abierta`, `herradura_grande`, `herradura_pequena`, `rocosa`, `fluvial`, `manglar`) + sand color marker (`blanca`, `negra`, `blanca_negra`, `parda_clara`, `parda`, `parda_oscura`, `parda_rojiza`, `conchal`).
  4. *Usos*: Infrastructure (`deshabitada`, `resort_hotel`, `viviendas`, `varios_servicios`, `sin_datos`), uses (`ocio`, `surf`, `snorquel`, `caminatas`, `pesca`, `tortugas`, `kayak`, `kitesurf`, `windsurf`), SINAC protected areas, emergency services.
- **Coordinate System**: Maps use `CRTM05` (`EPSG:5367`: Transverse Mercator on WGS84 ellipsoid, `lat_0 = 0`, `lon_0 = -84.0`, `k_0 = 0.9999`, `x_0 = 500000`, `y_0 = 0`). Grid ticks and grey grid lines (`0.431 0.431 0.431`) in each map page calibrate the exact affine mapping from PDF `(x, y)` to `(Easting, Northing)` and inverse-project to `WGS84 (lat, lng)`.
- **Master Glossary Table**: Pages 217–236 contain 7 fixed-column cells (`NOMBRE EN EL ATLAS`, `MAPA DEL ATLAS`, `TOPÓNIMO IGN`, `PLAYAS DEL IGN`, `ORIGEN DEL NOMBRE`, `OTROS NOMBRES`, `OBSERVACIONES`).

---

## 4. Extensible Multi-Language (`i18n`) Architecture
- All JSON data uses **language-neutral enum keys**.
- `locales/es.json` and `locales/en.json` store all UI copy, filter chips, legend labels, indicator names, safety explanations, and the 9 bather safety rules.
- `js/i18n.js` manages `SUPPORTED_LOCALES` (`es`, `en`) and dynamic re-rendering on toggle. To add another language (e.g., `fr`, `de`, `pt`):
  1. Copy `locales/en.json` to `locales/{code}.json` and translate values.
  2. Add `{ code: '{code}', label: '{LABEL}' }` to `SUPPORTED_LOCALES` in `js/i18n.js`.

---

## 5. Progress Tracker
- [x] PDF structure inspection & license audit
- [x] Step 1: `.gitignore`, `AGENTS.md`, `GEMINI.md` (hardlinked)
- [x] Step 2: Install `pymupdf`, `pillow`, `numpy` and build `scripts/extract_atlas.py`
- [x] Step 3: Run extraction (`735` beaches, `30` sectors) and pass `scripts/verify_data.py`
- [x] Step 4: Build `locales/es.json`, `locales/en.json`, `js/i18n.js`
- [x] Step 5: Build responsive web app (`index.html`, `css/styles.css`, `js/*.js`, `manifest.json`, `sw.js`, `README.md`)
- [x] Step 6: Automated & live browser verification (desktop `1440x900` + mobile `390x844`) and final `AGENTS.md` update
- [x] Step 7: Migrate frontend dependencies & GitHub Pages CI build to `npm` + `Vite` (`package.json`, `vite.config.js`, `.github/workflows/deploy.yml`, bundled `leaflet` & `leaflet.markercluster`, `sw.js` `playascr-v3`)
