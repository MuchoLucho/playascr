# PlayasCR — Interactive Costa Rica Beach Safety & Behavior Atlas

A 100% browser-only, mobile-first web application ready for **GitHub Pages**, mapping **Costa Rica's Pacific and Caribbean beaches** with coastal behavior, rip-current risk, swimming suitability, family safety, surfing, road access, and sand characteristics derived from:

> **Atlas de Playas de Costa Rica con Énfasis en la Seguridad (2024)**  
> Dra. Isabel Arozarena Llopis — Programa RONMAC, Universidad Nacional (UNA) & Instituto Costarricense de Turismo (ICT)

---

## Features

- **Semantic Zoom Behavior Badges**:
  - **National overview (Zoom 7–10)**: Smart risk-colored beach clusters across Costa Rica's 30 coastal sectors (`1P`–`23P`, `1C`–`7C`).
  - **Coastal view (Zoom 11–12)**: Lazy-loads exact georeferenced shoreline polygons (`WGS84`) for intersecting sectors only.
  - **Beach level (Zoom 13+)**: Renders floating indicator pills directly above visible beaches showing Rip Currents / Tide Risk (`🌊`), Swimming (`🏊`), Children & Seniors (`👨‍👩‍👧`), and Surfing (`🏄`).
- **6 Thematic Map Lenses**: Switch marker and shoreline colors between Rip Currents & Tide, Kids & Seniors, Swimming, Surf & Activities, Access Mode, and Sand Color.
- **Instant Filtering & Search**: Quick chips (`Kids & Seniors`, `Swimmable`, `Surf`, `Snorkel`, `Car Access`, `White Sand`, `High Risk / Tide`) plus instant accent-insensitive search by beach name, alias, IGN toponym, or sector (`1P`–`7C`).
- **Multi-Basemap + Satellite Surf Inspection**: Switch between **Map** (CARTO Voyager), **Satellite** (Esri World Imagery), and **Terrain** (OpenTopoMap), or tap **Inspect Surf Zone on Satellite** inside any beach profile.
- **Educational Rip-Current Safety Guide**: Custom original SVG diagrams explaining sediment plumes, sandy channels, rocky channels, and beach cusps, plus the 9 swimmer & family safety rules.
- **Mobile-First & Extensible i18n (`ES | EN`)**: Glassmorphism side drawer on desktop (`>= 768px`), swipeable bottom sheet on mobile (`< 768px`), GPS locator, Waze/Google Maps links, and PWA offline shell support (`sw.js`).

---

## 3-Tier Lazy-Loading Architecture

1. **Tier 1 (Initial Boot)**: `data/beaches-index.json` + `data/sectors-overview.json` load immediately for instant clustering, search, and filtering across the entire country without waiting for heavy polygon coordinates.
2. **Tier 2 (On-Demand Sector GeoJSON)**: `data/sectors/sector-{id}.geojson` (30 files) is fetched only when a sector intersects the viewport at `zoom >= 11` or when a user selects a beach.
3. **Tier 3 (Tiles & Vector Guides)**: Basemap tiles load per viewport from CARTO / Esri / OpenTopoMap, and rip-current visual guides are rendered as lightweight inline SVGs.

---

## Hosting on GitHub Pages

Zero backend required, built and bundled with **npm + Vite**:

1. Push the repository to GitHub (the large PDF `ATLAS DE PLAYAS COSTA RICA web 2024.pdf`, `.env`, `js/config.local.js`, `node_modules/`, and `dist/` are excluded via `.gitignore`, while `package-lock.json` is tracked for deterministic CI installs).
2. **Optional CARTO Basemap Key**:
   - **Local dev**: Copy [`.env.example`](.env.example) to `.env` (gitignored) and set `CARTO_API_KEY`.
   - **GitHub Pages CI**: Add `CARTO_API_KEY` as a repository secret in **Settings -> Secrets and variables -> Actions**, then enable **Settings -> Pages -> Source: GitHub Actions**. [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs `npm ci && npm run build` with `CARTO_API_KEY` injected and deploys `./dist`. Note: CARTO Basemaps requires a key from `https://carto.com/basemaps/apikey/`; if no Basemaps-enabled key is present (or if CARTO returns watermarked tiles), the app automatically falls back to watermark-free **OpenStreetMap** tiles.
3. Open your GitHub Pages URL on desktop or mobile.

---

## Adding More Languages

All data records use language-neutral enum keys. To add a new language (e.g., French `fr` or German `de`):

1. Copy [`locales/en.json`](locales/en.json) to `locales/<code>.json` and translate the UI strings.
2. Add `{ code: '<code>', label: '<LABEL>' }` to `SUPPORTED_LOCALES` in [`js/i18n.js`](js/i18n.js).

---

## Local Development & Data Verification

Install dependencies and run the Vite dev/preview server:

```bash
npm install
npm run dev
```

Or build and preview the production `./dist` bundle locally on port `8080`:

```bash
npm run build
npm run preview
```

To verify extracted data integrity, coordinate bounds, locale enum parity, and file-size budgets:

```bash
npm run verify:data
```

If you have a local copy of `ATLAS DE PLAYAS COSTA RICA web 2024.pdf` in the repository root, you can regenerate `data/` via:

```bash
pip install pymupdf pillow numpy
python scripts/extract_atlas.py
```

---

## Licensing, Attribution & Third-Party References

### 1. Software License (Apache License 2.0)
The application source code, build configuration, user interface implementation, vector diagrams, and software architecture are licensed under the **Apache License, Version 2.0**. See the full license text in [LICENSE](LICENSE) and attribution records in [NOTICE](NOTICE).

```text
Copyright 2026 PlayasCR Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

### 2. Atlas Data & Research Attribution (Exclusion from Apache 2.0)
> [!IMPORTANT]
> **The underlying research, coastal indicators, safety ratings, and cartographic data from the *Atlas de Playas de Costa Rica con Énfasis en la Seguridad* (2024) are NOT licensed under Apache 2.0.**

- **Principal Investigator & Author**: Dra. Isabel Arozarena Llopis (Coastal Geomorphologist).
- **Institutions**: Programa RONMAC – Universidad Nacional de Costa Rica (UNA) & Instituto Costarricense de Turismo (ICT) ([ict.go.cr/es/servicios-institucionales/atlas-de-playas.html](https://www.ict.go.cr/es/servicios-institucionales/atlas-de-playas.html)).
- **Official Publication Portal**: [ICT — Atlas de Playas de Costa Rica](https://www.ict.go.cr/es/servicios-institucionales/atlas-de-playas.html)
- **Citation**: Arozarena Llopis, I. (2024). *Atlas de Playas de Costa Rica con Énfasis en la Seguridad*. Programa RONMAC–UNA & ICT, San José, Costa Rica.
- **Copyright-Safe Policy**:
  - All factual geographic data, rip-current hazard classifications, access classifications, and sand characteristics are synthesized and referenced exclusively for **public beach safety, tourist awareness, and scientific dissemination**.
  - **No original photographs (`Figuras`) or verbatim chapter texts** from the PDF publication are redistributed or hosted in this repository.
  - The source PDF exceeds GitHub file size limits and is excluded from git tracking via `.gitignore`.
  - The authors and institutions retain all original intellectual property rights to their research and publication.

---

### 3. Open-Source Software Libraries
The web application and its toolchain incorporate the following open-source dependencies:

| Library | License | Copyright / Author | Reference / Repository |
| :--- | :--- | :--- | :--- |
| **[Leaflet](https://leafletjs.com/)** (`v1.9.4`) | BSD 2-Clause | © 2010–2024 Vladimir Agafonkin, © 2010–2011 CloudMade | [Leaflet License](https://github.com/Leaflet/Leaflet/blob/main/LICENSE) |
| **[Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster)** (`v1.5.3`) | MIT License | © 2012–2021 Dave Leaver | [Leaflet.markercluster License](https://github.com/Leaflet/Leaflet.markercluster/blob/master/MIT-LICENCE.txt) |
| **[Lucide](https://lucide.dev/)** (`v1.x`) | ISC / MIT License | © 2022–present Lucide Contributors | [Lucide License](https://github.com/lucide-icons/lucide/blob/main/LICENSE) |
| **[Vite](https://vite.dev/)** (`v6.x`) | MIT License | © 2019–present Evan You & Vite Contributors | [Vite License](https://github.com/vitejs/vite/blob/main/LICENSE) |
| **[PyMuPDF](https://pymupdf.readthedocs.io/)** *(offline extraction script only)* | AGPLv3 / Commercial | © Artifex Software, Inc. | [PyMuPDF License](https://github.com/pymupdf/PyMuPDF/blob/master/COPYING) |
| **[Pillow](https://python-pillow.org/)** *(offline extraction script only)* | HPND License | © 1997–2024 Secret Labs AB, Jeffrey A. Clark & contributors | [Pillow License](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| **[NumPy](https://numpy.org/)** *(offline extraction script only)* | BSD 3-Clause | © 2005–2024 NumPy Developers | [NumPy License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |

---

### 4. Basemap Tiles & Cartographic Providers

- **[OpenStreetMap](https://www.openstreetmap.org/)**: Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1.0/). Map tiles are licensed under [Creative Commons Attribution-ShareAlike 2.0 (CC-BY-SA 2.0)](https://creativecommons.org/licenses/by-sa/2.0/).
- **[CARTO](https://carto.com/)**: CARTO Voyager raster tiles © CARTO, © OpenStreetMap contributors. Used in accordance with [CARTO Basemaps Terms and Attributions](https://carto.com/attributions).
- **[Esri World Imagery](https://www.esri.com/)**: Tiles © Esri — Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community.
- **[OpenTopoMap](https://opentopomap.org/)**: Map data © OpenStreetMap contributors, SRTM; Map display & style © OpenTopoMap ([CC-BY-SA](https://creativecommons.org/licenses/by-sa/3.0/de/deed.en)).

---

### 5. Disclaimer
Ocean conditions, rip currents, wave energy, tidal cutoffs, road conditions, and lifeguard availability change dynamically with weather, swell, and tides. This application provides educational and informational guidance based on published geomorphological surveys; it **never replaces on-site observation, posted beach warning flags, or direct instructions from certified lifeguards and local emergency authorities**.
