/**
 * Copyright 2026 PlayasCR Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import L from './leaflet-shim.js';
import 'leaflet.markercluster';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { t } from './i18n.js';
import { iconSvg } from './icons.js';

export const LENS_OPTIONS = ['rip', 'family', 'swim', 'surf', 'access', 'sand'];

const RIP_SEVERITY = {
  muy_alto: 4,
  alto: 3,
  medio: 2,
  bajo: 1,
  no_visitado: 0,
};

const COLORS = {
  rip: {
    bajo: '#16a34a',
    medio: '#ca8a04',
    alto: '#ea580c',
    muy_alto: '#dc2626',
    no_visitado: '#64748b',
  },
  family: {
    adecuada: '#16a34a',
    supervision: '#ca8a04',
    no_recomendada: '#dc2626',
    desconocida: '#64748b',
  },
  swim: {
    favorable: '#0d9488',
    precaucion: '#ca8a04',
    peligrosa: '#dc2626',
    desconocida: '#64748b',
  },
  surf: {
    favorable: '#0284c7',
    posible: '#38bdf8',
    calma: '#94a3b8',
  },
  access: {
    restringido: '#eab308',
    vehiculo: '#16a34a',
    pie: '#0ea5e9',
    bote: '#8b5cf6',
  },
  sand: {
    blanca: '#f8fafc',
    blanca_negra: '#94a3b8',
    parda_clara: '#e7d8a5',
    parda: '#c69f59',
    parda_oscura: '#855814',
    parda_rojiza: '#c2410c',
    negra: '#1e293b',
    sin_datos: '#cbd5e1',
  },
};

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function createOsmLayer() {
  return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  });
}

function createCartoVoyagerLayer(apiKey) {
  const qs = apiKey ? `?key=${encodeURIComponent(apiKey)}` : '';
  return L.tileLayer(`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png${qs}`, {
    attribution: '&copy; OpenStreetMap contributors, &copy; CARTO',
    maxZoom: 19,
  });
}

function createBasemaps() {
  return {
    street: createOsmLayer(),
    satellite: L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: 'Tiles &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics',
        maxZoom: 19,
      }
    ),
    topo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap, SRTM | &copy; OpenTopoMap',
      maxZoom: 17,
    }),
  };
}

export class BeachMap {
  constructor({ containerId = 'map', onBeachSelect, onSectorLoaded, onLocateError } = {}) {
    this.onBeachSelect = onBeachSelect;
    this.onSectorLoaded = onSectorLoaded;
    this.onLocateError = onLocateError;

    this.lens = 'rip';
    this.basemapMode = 'street';
    this.allBeachesById = new Map();
    this.filteredBeaches = [];
    this.sectorsOverview = [];
    this.sectorCache = new Map();
    this.sectorPromises = new Map();
    this.sectorLayers = new Map();
    this.selectedBeachId = null;

    this.map = L.map(containerId, {
      center: [9.75, -84.25],
      zoom: 8,
      minZoom: 6,
      maxZoom: 19,
      zoomControl: false,
      preferCanvas: true,
    });

    this.canvasRenderer = L.canvas({ padding: 0.5 });
    this.basemaps = createBasemaps();
    this.#configureCartoStreetBasemap();

    this.polygonGroup = L.layerGroup().addTo(this.map);
    this.pillsLayer = L.layerGroup().addTo(this.map);
    this.userMarker = null;

    this.clusterGroup = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 46,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      disableClusteringAtZoom: 13,
      iconCreateFunction: (cluster) => this.#buildClusterIcon(cluster),
    }).addTo(this.map);

    this._viewportTimer = null;
    this.map.on('zoomend', () => this.#scheduleViewportUpdate(true));
    this.map.on('moveend', () => this.#scheduleViewportUpdate(false));

    this.renderLegend();
  }

  async #configureCartoStreetBasemap() {
    const ensureStreetAdded = (layer) => {
      if (this.basemapMode === 'street' && !this.map.hasLayer(layer)) {
        layer.addTo(this.map);
      }
    };

    const fallbackToOsm = () => {
      const osmLayer = createOsmLayer();
      const prev = this.basemaps.street;
      this.basemaps.street = osmLayer;
      if (this.basemapMode === 'street') {
        if (this.map.hasLayer(prev)) this.map.removeLayer(prev);
        osmLayer.addTo(this.map);
      }
    };

    try {
      const envKey = (typeof import.meta !== 'undefined' && import.meta.env?.CARTO_API_KEY) || '';
      let apiKey = String(envKey || window.CARTO_API_KEY || '').trim();
      if (!apiKey) {
        const localCfgPath = './config.local.js';
        const cfg = await import(/* @vite-ignore */ localCfgPath).catch(() => ({}));
        apiKey = String(cfg?.CARTO_API_KEY || '').trim();
      }
      if (!apiKey) {
        ensureStreetAdded(this.basemaps.street);
        return;
      }

      const cartoLayer = createCartoVoyagerLayer(apiKey);
      const oldStreet = this.basemaps.street;
      this.basemaps.street = cartoLayer;
      if (this.basemapMode === 'street') {
        if (this.map.hasLayer(oldStreet)) this.map.removeLayer(oldStreet);
        cartoLayer.addTo(this.map);
      }

      // Verify the key is Basemaps-enabled (CARTO returns a 2049-byte "wm-*" watermark tile otherwise)
      const probeUrl = `https://basemaps.cartocdn.com/rastertiles/voyager/10/273/483.png?key=${encodeURIComponent(apiKey)}`;
      const res = await fetch(probeUrl, { cache: 'no-store' });
      if (!res.ok) {
        fallbackToOsm();
        return;
      }
      const etag = (res.headers.get('etag') || '').toLowerCase();
      const buf = await res.arrayBuffer();
      if (etag.includes('wm-') || buf.byteLength === 2049) {
        console.info('CARTO key returned watermark placeholder; keeping OpenStreetMap basemap.');
        fallbackToOsm();
      }
    } catch {
      fallbackToOsm();
    }
  }

  #buildClusterIcon(cluster) {
    const markers = cluster.getAllChildMarkers();
    const count = markers.length;
    let surveyedCount = 0;
    let sumRisk = 0;
    let highCount = 0;

    for (const m of markers) {
      const sev = RIP_SEVERITY[m.options.ripRisk] ?? 0;
      if (sev > 0) {
        surveyedCount += 1;
        sumRisk += sev;
        if (sev >= 3) highCount += 1;
      }
    }

    let bg = '#64748b';
    if (surveyedCount > 0) {
      const avg = sumRisk / surveyedCount;
      const highRatio = highCount / surveyedCount;
      if (avg >= 2.75 || highRatio >= 0.45) bg = '#dc2626';
      else if (avg >= 2.0) bg = '#ea580c';
      else if (avg >= 1.45) bg = '#ca8a04';
      else bg = '#16a34a';
    }

    const size = count < 10 ? 34 : count < 50 ? 40 : 46;
    return L.divIcon({
      html: `<span>${count}</span>`,
      className: 'cr-cluster',
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      // Set dynamic color cleanly via a wrapper callback after Leaflet attaches, or inline span below
      ...(function () {
        return {
          html: `<span style="display:flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;background:${bg};color:#fff;">${count}</span>`,
        };
      })(),
    });
  }

  getBeachColor(beach, lens = this.lens) {
    if (lens === 'access') {
      if (beach.accessType === 'restringido') return COLORS.access.restringido;
      return COLORS.access[beach.accessMode] || '#16a34a';
    }
    const map = COLORS[lens] || COLORS.rip;
    return map[beach[lens]] || '#64748b';
  }

  setSectorsOverview(sectors) {
    this.sectorsOverview = Array.isArray(sectors) ? sectors : [];
  }

  setAllBeaches(beaches) {
    this.allBeachesById.clear();
    for (const b of beaches) {
      this.allBeachesById.set(b.id, b);
    }
  }

  setFilteredBeaches(beaches) {
    this.filteredBeaches = Array.isArray(beaches) ? beaches : [];
    this.#rebuildMarkers();
    this.#renderBehaviorPills();
  }

  setLens(lens) {
    if (!LENS_OPTIONS.includes(lens)) return;
    this.lens = lens;
    this.#rebuildMarkers();
    this.#restylePolygonLayers();
    this.renderLegend();
  }

  setBasemap(mode) {
    if (!this.basemaps[mode] || mode === this.basemapMode) return;
    this.map.removeLayer(this.basemaps[this.basemapMode]);
    this.basemaps[mode].addTo(this.map);
    this.basemapMode = mode;
  }

  zoomIn() {
    this.map.zoomIn();
  }

  zoomOut() {
    this.map.zoomOut();
  }

  getSectorFeature(sectorId, beachId) {
    const gj = this.sectorCache.get(sectorId);
    if (!gj?.features) return null;
    return gj.features.find((f) => f.properties?.id === beachId) || null;
  }

  getSectorData(sectorId) {
    return this.sectorCache.get(sectorId) || null;
  }

  async loadSector(sectorId) {
    if (this.sectorCache.has(sectorId)) {
      return this.sectorCache.get(sectorId);
    }
    if (this.sectorPromises.has(sectorId)) {
      return this.sectorPromises.get(sectorId);
    }

    const promise = fetch(`./data/sectors/sector-${sectorId}.geojson`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} loading sector ${sectorId}`);
        return res.json();
      })
      .then((geojson) => {
        this.sectorCache.set(sectorId, geojson);
        this.sectorPromises.delete(sectorId);
        this.#mountSectorLayer(sectorId, geojson);
        this.onSectorLoaded?.(sectorId, geojson);
        return geojson;
      })
      .catch((err) => {
        this.sectorPromises.delete(sectorId);
        console.warn('Sector lazy-load error:', err);
        return null;
      });

    this.sectorPromises.set(sectorId, promise);
    return promise;
  }

  #mountSectorLayer(sectorId, geojson) {
    if (this.sectorLayers.has(sectorId)) return;

    const layer = L.geoJSON(geojson, {
      renderer: this.canvasRenderer,
      style: (feature) => this.#polygonStyle(feature),
      onEachFeature: (feature, polyLayer) => {
        polyLayer.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          const beach = this.allBeachesById.get(feature.properties?.id);
          if (beach) {
            this.selectedBeachId = beach.id;
            this.#restylePolygonLayers();
            this.onBeachSelect?.(beach, this.getSectorData(beach.sector));
          }
        });
      },
    });

    this.sectorLayers.set(sectorId, layer);
    if (this.map.getZoom() >= 11) {
      layer.addTo(this.polygonGroup);
    }
  }

  #polygonStyle(feature) {
    const props = feature?.properties || {};
    const beach = this.allBeachesById.get(props.id) || props;
    const fill = this.getBeachColor(beach, this.lens);
    const isSelected = props.id && props.id === this.selectedBeachId;

    return {
      color: isSelected ? '#0f172a' : this.lens === 'sand' && fill === '#f8fafc' ? '#64748b' : '#ffffff',
      weight: isSelected ? 3.5 : 1.5,
      opacity: 0.95,
      fillColor: fill,
      fillOpacity: isSelected ? 0.85 : 0.62,
    };
  }

  #restylePolygonLayers() {
    for (const layer of this.sectorLayers.values()) {
      layer.setStyle((feature) => this.#polygonStyle(feature));
    }
  }

  #rebuildMarkers() {
    const markers = [];
    for (const beach of this.filteredBeaches) {
      const color = this.getBeachColor(beach, this.lens);
      const border = color === '#f8fafc' ? '#475569' : '#ffffff';
      const dotIcon = L.divIcon({
        className: 'beach-dot-marker',
        html: `<span style="display:block;width:14px;height:14px;border-radius:50%;background:${color};border:2.5px solid ${border};box-shadow:0 1px 4px rgba(15,23,42,0.45);"></span>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });
      const marker = L.marker([beach.lat, beach.lng], {
        icon: dotIcon,
        ripRisk: beach.rip,
        title: beach.name,
      });
      marker.on('click', async () => {
        this.selectedBeachId = beach.id;
        const sectorData = await this.loadSector(beach.sector);
        this.#restylePolygonLayers();
        this.onBeachSelect?.(beach, sectorData);
      });
      markers.push(marker);
    }

    this.clusterGroup.clearLayers();
    if (markers.length > 0) {
      this.clusterGroup.addLayers(markers);
    }
  }

  #scheduleViewportUpdate(immediate) {
    clearTimeout(this._viewportTimer);
    if (immediate) {
      this.#handleViewportChange();
    } else {
      this._viewportTimer = setTimeout(() => this.#handleViewportChange(), 110);
    }
  }

  #handleViewportChange() {
    const zoom = this.map.getZoom();

    if (zoom >= 11) {
      const bounds = this.map.getBounds();
      for (const sec of this.sectorsOverview) {
        const [minLng, minLat, maxLng, maxLat] = sec.bounds || [0, 0, 0, 0];
        const secBounds = L.latLngBounds([minLat, minLng], [maxLat, maxLng]);
        if (bounds.intersects(secBounds)) {
          this.loadSector(sec.id);
          const existing = this.sectorLayers.get(sec.id);
          if (existing && !this.polygonGroup.hasLayer(existing)) {
            existing.addTo(this.polygonGroup);
          }
        }
      }
    } else {
      this.polygonGroup.clearLayers();
    }

    this.#renderBehaviorPills();
  }

  #renderBehaviorPills() {
    this.pillsLayer.clearLayers();
    const zoom = this.map.getZoom();
    if (zoom < 13) return;

    const bounds = this.map.getBounds();
    const center = this.map.getCenter();
    const visible = this.filteredBeaches
      .filter((b) => bounds.contains([b.lat, b.lng]))
      .sort((a, b) => {
        if (a.visited !== b.visited) return a.visited ? -1 : 1;
        const da = (a.lat - center.lat) ** 2 + (a.lng - center.lng) ** 2;
        const db = (b.lat - center.lat) ** 2 + (b.lng - center.lng) ** 2;
        return da - db;
      });

    const isMobile = window.innerWidth < 768;
    const maxPills = isMobile ? 28 : 48;
    const placedPoints = [];

    for (const beach of visible) {
      if (placedPoints.length >= maxPills) break;
      const pt = this.map.latLngToContainerPoint([beach.lat, beach.lng]);

      // De-overlap pills cleanly so clusters of coves stay readable
      const overlaps = placedPoints.some(
        (p) => Math.abs(p.x - pt.x) < (zoom >= 15 ? 85 : 112) && Math.abs(p.y - pt.y) < 38
      );
      if (overlaps && beach.id !== this.selectedBeachId) continue;
      placedPoints.push(pt);

      const ripClass =
        {
          bajo: 'low',
          medio: 'med',
          alto: 'high',
          muy_alto: 'vhigh',
          no_visitado: 'na',
        }[beach.rip] || 'na';

      const swimClass =
        {
          favorable: 'low',
          precaucion: 'med',
          peligrosa: 'vhigh',
          desconocida: 'na',
        }[beach.swim] || 'na';

      const famClass =
        {
          adecuada: 'low',
          supervision: 'med',
          no_recomendada: 'high',
          desconocida: 'na',
        }[beach.family] || 'na';

      const surfBadge =
        beach.surf === 'favorable'
          ? `<span class="mini-badge surf">${iconSvg('surf', { size: 11, strokeWidth: 2.2 })}<span>${escapeHtml(t('surfShort.favorable'))}</span></span>`
          : '';

      const html = `
        <div class="beach-pill" data-beach-id="${escapeHtml(beach.id)}">
          <div class="beach-pill-name">${escapeHtml(beach.name)}</div>
          <div class="beach-pill-badges">
            <span class="mini-badge ${ripClass}">${iconSvg('waves', { size: 11, strokeWidth: 2.2 })}<span>${escapeHtml(t(`rip.${beach.rip}`))}</span></span>
            <span class="mini-badge ${swimClass}">${iconSvg('swim', { size: 11, strokeWidth: 2.2 })}<span>${escapeHtml(t(`swimShort.${beach.swim}`))}</span></span>
            <span class="mini-badge ${famClass}">${iconSvg('family', { size: 11, strokeWidth: 2.2 })}<span>${escapeHtml(t(`familyShort.${beach.family}`))}</span></span>
            ${surfBadge}
          </div>
        </div>
      `;

      const pillMarker = L.marker([beach.lat, beach.lng], {
        icon: L.divIcon({
          className: 'beach-behavior-marker',
          html,
          iconSize: null,
          iconAnchor: [0, 12],
        }),
        zIndexOffset: beach.id === this.selectedBeachId ? 900 : 300,
      });

      pillMarker.on('click', async () => {
        this.selectedBeachId = beach.id;
        const sectorData = await this.loadSector(beach.sector);
        this.#restylePolygonLayers();
        this.onBeachSelect?.(beach, sectorData);
      });

      pillMarker.addTo(this.pillsLayer);
    }
  }

  async focusBeach(beach, zoom = 15) {
    if (!beach) return null;
    this.selectedBeachId = beach.id;
    const isDesktop = window.innerWidth >= 768;
    const targetZoom = Math.max(this.map.getZoom(), zoom);
    this.map.flyTo([beach.lat, beach.lng], targetZoom, { duration: 0.65 });
    if (isDesktop) {
      // Shift view slightly left on desktop so drawer on the right doesn't cover the beach
      this.map.once('moveend', () => {
        this.map.panBy([130, 0], { animate: true, duration: 0.25 });
      });
    }
    const sectorData = await this.loadSector(beach.sector);
    this.#restylePolygonLayers();
    return sectorData;
  }

  locateUser() {
    if (!navigator.geolocation) {
      this.onLocateError?.();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        if (this.userMarker) {
          this.userMarker.setLatLng([latitude, longitude]);
        } else {
          this.userMarker = L.circleMarker([latitude, longitude], {
            radius: 8,
            color: '#ffffff',
            weight: 3,
            fillColor: '#0284c7',
            fillOpacity: 1,
          }).addTo(this.map);
        }
        this.map.flyTo([latitude, longitude], 13, { duration: 0.7 });
      },
      () => {
        this.onLocateError?.();
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }

  renderLegend() {
    const container = document.getElementById('legend-items');
    if (!container) return;

    const specs = {
      rip: [
        ['bajo', COLORS.rip.bajo, t('rip.bajo')],
        ['medio', COLORS.rip.medio, t('rip.medio')],
        ['alto', COLORS.rip.alto, t('rip.alto')],
        ['muy_alto', COLORS.rip.muy_alto, t('rip.muy_alto')],
        ['no_visitado', COLORS.rip.no_visitado, t('rip.no_visitado')],
      ],
      family: [
        ['adecuada', COLORS.family.adecuada, t('family.adecuada')],
        ['supervision', COLORS.family.supervision, t('family.supervision')],
        ['no_recomendada', COLORS.family.no_recomendada, t('family.no_recomendada')],
        ['desconocida', COLORS.family.desconocida, t('family.desconocida')],
      ],
      swim: [
        ['favorable', COLORS.swim.favorable, t('swim.favorable')],
        ['precaucion', COLORS.swim.precaucion, t('swim.precaucion')],
        ['peligrosa', COLORS.swim.peligrosa, t('swim.peligrosa')],
        ['desconocida', COLORS.swim.desconocida, t('swim.desconocida')],
      ],
      surf: [
        ['favorable', COLORS.surf.favorable, t('surf.favorable')],
        ['posible', COLORS.surf.posible, t('surf.posible')],
        ['calma', COLORS.surf.calma, t('surf.calma')],
      ],
      access: [
        ['vehiculo', COLORS.access.vehiculo, t('accessMode.vehiculo')],
        ['pie', COLORS.access.pie, t('accessMode.pie')],
        ['bote', COLORS.access.bote, t('accessMode.bote')],
        ['restringido', COLORS.access.restringido, t('accessType.restringido')],
      ],
      sand: [
        ['blanca', COLORS.sand.blanca, t('sand.blanca')],
        ['blanca_negra', COLORS.sand.blanca_negra, t('sand.blanca_negra')],
        ['parda_clara', COLORS.sand.parda_clara, t('sand.parda_clara')],
        ['parda', COLORS.sand.parda, t('sand.parda')],
        ['parda_oscura', COLORS.sand.parda_oscura, t('sand.parda_oscura')],
        ['parda_rojiza', COLORS.sand.parda_rojiza, t('sand.parda_rojiza')],
        ['negra', COLORS.sand.negra, t('sand.negra')],
        ['sin_datos', COLORS.sand.sin_datos, t('sand.sin_datos')],
      ],
    };

    const rows = specs[this.lens] || specs.rip;
    container.innerHTML = rows
      .map(
        ([, color, label]) => `
        <span class="legend-item">
          <span class="legend-dot" style="background:${color}"></span>
          <span>${escapeHtml(label)}</span>
        </span>
      `
      )
      .join('');
  }

  refreshTranslations() {
    this.renderLegend();
    this.#renderBehaviorPills();
  }
}
