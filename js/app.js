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

import {
  SUPPORTED_LOCALES,
  getLocale,
  initI18n,
  loadLocale,
  onLocaleChange,
  t,
} from './i18n.js';
import { FILTER_DEFS, filterBeaches, normalizeText } from './filters.js';
import { BeachMap, LENS_OPTIONS } from './map.js';
import { BeachDrawer, renderGuideModalContent } from './drawer.js';
import { iconSvg } from './icons.js';
import { initTheme, updateThemeLabels } from './theme.js';

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const RIP_BADGE_COLORS = {
  bajo: 'background:var(--risk-low-bg);color:var(--risk-low-fg)',
  medio: 'background:var(--risk-med-bg);color:var(--risk-med-fg)',
  alto: 'background:var(--risk-high-bg);color:var(--risk-high-fg)',
  muy_alto: 'background:var(--risk-vhigh-bg);color:var(--risk-vhigh-fg)',
  no_visitado: 'background:var(--risk-na-bg);color:var(--risk-na-fg)',
};

async function boot() {
  await initI18n();

  const [beachesRes, overviewRes] = await Promise.all([
    fetch('./data/beaches-index.json'),
    fetch('./data/sectors-overview.json'),
  ]);

  if (!beachesRes.ok || !overviewRes.ok) {
    throw new Error('Failed to load initial beach atlas index.');
  }

  const allBeaches = await beachesRes.json();
  const sectorsOverview = await overviewRes.json();
  const sectorMetaById = new Map((sectorsOverview.sectors || []).map((s) => [s.id, s]));

  let activeFilter = 'all';
  let searchQuery = '';

  const langSwitchEl = document.getElementById('lang-switch');
  const filterChipsEl = document.getElementById('filter-chips');
  const beachesCountEl = document.getElementById('beaches-count');
  const lensSelectEl = document.getElementById('lens-select');
  const searchInputEl = document.getElementById('search-input');
  const clearSearchEl = document.getElementById('clear-search');
  const searchResultsEl = document.getElementById('search-results');

  let drawer;

  const beachMap = new BeachMap({
    containerId: 'map',
    onBeachSelect: (beach, sectorData) => {
      openBeachPanel(beach, sectorData);
    },
    onSectorLoaded: (sectorId, sectorData) => {
      if (drawer?.currentBeach?.sector === sectorId && drawer.el.classList.contains('open')) {
        drawer.open(drawer.currentBeach, sectorData);
      }
    },
    onLocateError: () => {
      alert(t('app.locatingError'));
    },
  });

  beachMap.setSectorsOverview(sectorsOverview.sectors || []);
  beachMap.setAllBeaches(allBeaches);

  function syncBasemapButtons(mode) {
    document.querySelectorAll('.basemap-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.basemap === mode);
    });
  }

  drawer = new BeachDrawer({
    onInspectSatellite: async (beach) => {
      beachMap.setBasemap('satellite');
      syncBasemapButtons('satellite');
      if (window.innerWidth < 768) {
        drawer.el.classList.add('peek');
      }
      await beachMap.focusBeach(beach, 17);
    },
  });

  function openBeachPanel(beach, loadedSectorData = null) {
    if (!beach) return;
    const fallbackSector = sectorMetaById.get(beach.sector);
    const sectorPayload = loadedSectorData || beachMap.getSectorData(beach.sector) || fallbackSector || null;
    drawer.open(beach, sectorPayload);
    const targetHash = `#playa=${encodeURIComponent(beach.id)}`;
    if (window.location.hash !== targetHash) {
      history.replaceState(null, '', targetHash);
    }
    if (!beachMap.getSectorData(beach.sector)) {
      beachMap.loadSector(beach.sector);
    }
  }

  function renderLanguageSwitch() {
    if (!langSwitchEl) return;
    const current = getLocale();
    langSwitchEl.innerHTML = SUPPORTED_LOCALES.map(
      (loc) =>
        `<button type="button" class="lang-btn ${loc.code === current ? 'active' : ''}" data-lang="${escapeHtml(loc.code)}">${escapeHtml(loc.label)}</button>`
    ).join('');

    langSwitchEl.querySelectorAll('.lang-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const next = btn.dataset.lang;
        if (next && next !== getLocale()) {
          loadLocale(next);
        }
      });
    });
  }

  function renderFilterChips() {
    if (!filterChipsEl) return;
    filterChipsEl.innerHTML = FILTER_DEFS.map(
      (f) =>
        `<button type="button" class="chip ${f.id === activeFilter ? 'active' : ''}" data-filter="${escapeHtml(f.id)}"><span class="chip-icon">${iconSvg(f.iconName, { size: 15 })}</span><span>${escapeHtml(t(f.key))}</span></button>`
    ).join('');

    filterChipsEl.querySelectorAll('.chip').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeFilter = btn.dataset.filter || 'all';
        renderFilterChips();
        applyFilters();
      });
    });
  }

  function renderLensSelect() {
    if (!lensSelectEl) return;
    const prev = beachMap.lens || 'rip';
    lensSelectEl.innerHTML = LENS_OPTIONS.map(
      (key) => `<option value="${key}" ${key === prev ? 'selected' : ''}>${escapeHtml(t(`lenses.${key}`))}</option>`
    ).join('');
  }

  function applyFilters() {
    const filtered = filterBeaches(allBeaches, searchQuery, activeFilter);
    beachMap.setFilteredBeaches(filtered);
    if (beachesCountEl) {
      beachesCountEl.textContent = t('app.beachesCount', {
        shown: filtered.length,
        total: allBeaches.length,
      });
    }
  }

  function renderSearchDropdown(query) {
    if (!searchResultsEl) return;
    const q = normalizeText(query);
    if (!q) {
      searchResultsEl.classList.remove('open');
      searchResultsEl.innerHTML = '';
      return;
    }

    const matches = allBeaches
      .filter((b) => {
        const hay = [b.name, b.ignName, ...(b.altNames || []), b.sector]
          .filter(Boolean)
          .map(normalizeText)
          .join(' ');
        return hay.includes(q);
      })
      .sort((a, b) => {
        const aStarts = normalizeText(a.name).startsWith(q) ? 0 : 1;
        const bStarts = normalizeText(b.name).startsWith(q) ? 0 : 1;
        if (aStarts !== bStarts) return aStarts - bStarts;
        return a.name.localeCompare(b.name);
      })
      .slice(0, 15);

    if (!matches.length) {
      searchResultsEl.classList.remove('open');
      searchResultsEl.innerHTML = '';
      return;
    }

    searchResultsEl.innerHTML = matches
      .map((b) => {
        const style = RIP_BADGE_COLORS[b.rip] || RIP_BADGE_COLORS.no_visitado;
        return `
          <button type="button" class="search-item" data-beach-id="${escapeHtml(b.id)}">
            <div>
              <div class="search-item-title">${escapeHtml(b.name)}</div>
              <div class="search-item-meta">${escapeHtml(t('drawer.sectorLabel', { sector: b.sector }))} · ${escapeHtml(t(`regions.${b.region}`))}</div>
            </div>
            <span class="search-item-badge" style="${style}">${escapeHtml(t(`rip.${b.rip}`))}</span>
          </button>
        `;
      })
      .join('');

    searchResultsEl.classList.add('open');
    searchResultsEl.querySelectorAll('.search-item').forEach((itemBtn) => {
      itemBtn.addEventListener('click', async () => {
        const beach = allBeaches.find((b) => b.id === itemBtn.dataset.beachId);
        if (!beach) return;
        searchResultsEl.classList.remove('open');
        // Ensure beach isn't hidden by an active restrictive chip when directly picked from search
        if (!filterBeaches([beach], '', activeFilter).length) {
          activeFilter = 'all';
          renderFilterChips();
        }
        searchQuery = '';
        if (searchInputEl) searchInputEl.value = '';
        clearSearchEl?.classList.remove('visible');
        applyFilters();
        const sectorData = await beachMap.focusBeach(beach, 15);
        openBeachPanel(beach, sectorData);
      });
    });
  }

  // Search events
  if (searchInputEl) {
    searchInputEl.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      clearSearchEl?.classList.toggle('visible', Boolean(searchQuery.trim()));
      applyFilters();
      renderSearchDropdown(searchQuery);
    });
    searchInputEl.addEventListener('focus', () => {
      if (searchQuery.trim()) renderSearchDropdown(searchQuery);
    });
  }

  clearSearchEl?.addEventListener('click', () => {
    searchQuery = '';
    if (searchInputEl) {
      searchInputEl.value = '';
      searchInputEl.focus();
    }
    clearSearchEl.classList.remove('visible');
    searchResultsEl?.classList.remove('open');
    applyFilters();
  });

  document.addEventListener('click', (e) => {
    if (searchResultsEl && !e.target.closest('.search-box')) {
      searchResultsEl.classList.remove('open');
    }
  });

  // Map lens selector
  lensSelectEl?.addEventListener('change', (e) => {
    beachMap.setLens(e.target.value);
  });

  // Basemap buttons
  document.querySelectorAll('.basemap-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.basemap;
      if (!mode) return;
      beachMap.setBasemap(mode);
      syncBasemapButtons(mode);
    });
  });

  // Zoom & GPS FAB controls
  document.getElementById('btn-zoom-in')?.addEventListener('click', () => beachMap.zoomIn());
  document.getElementById('btn-zoom-out')?.addEventListener('click', () => beachMap.zoomOut());
  document.getElementById('btn-locate')?.addEventListener('click', () => beachMap.locateUser());

  // Modals (Guide & About)
  function openModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'guide-modal') renderGuideModalContent();
    el.classList.add('open');
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove('open');
  }

  document.getElementById('btn-guide')?.addEventListener('click', () => openModal('guide-modal'));
  document.getElementById('btn-about')?.addEventListener('click', () => openModal('about-modal'));

  document.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
  });

  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove('open');
      }
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach((m) => m.classList.remove('open'));
    }
  });

  // Dynamic UI refresh on ES/EN toggle
  onLocaleChange(() => {
    renderLanguageSwitch();
    renderFilterChips();
    renderLensSelect();
    applyFilters();
    beachMap.refreshTranslations();
    drawer.rerenderIfOpen();
    updateThemeLabels();
    if (document.getElementById('guide-modal')?.classList.contains('open')) {
      renderGuideModalContent();
    }
  });

  // Initial render
  initTheme();
  renderLanguageSwitch();
  renderFilterChips();
  renderLensSelect();
  applyFilters();

  // Deep link handler (#playa=<id>)
  const handleHashNavigation = async () => {
    if (!window.location.hash.startsWith('#playa=')) return;
    const rawId = decodeURIComponent(window.location.hash.slice('#playa='.length));
    const target = allBeaches.find((b) => b.id === rawId);
    if (target) {
      const sectorData = await beachMap.focusBeach(target, 15);
      openBeachPanel(target, sectorData);
    }
  };
  window.addEventListener('hashchange', handleHashNavigation);
  await handleHashNavigation();

  // Register Service Worker for static caching
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
}

boot().catch((err) => {
  console.error('PlayasCR boot error:', err);
});
