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

import { getLocale, t } from './i18n.js';

const SAND_SWATCHES = {
  blanca: '#f8fafc',
  negra: '#334155',
  blanca_negra: 'linear-gradient(135deg, #f8fafc 50%, #334155 50%)',
  parda_clara: '#e6cfa8',
  parda: '#b89463',
  parda_oscura: '#705232',
  parda_rojiza: '#9d5336',
  sin_datos: '#cbd5e1'
};

function ripTone(rip) {
  switch (rip) {
    case 'bajo':
      return 'tone-low';
    case 'medio':
      return 'tone-med';
    case 'alto':
      return 'tone-high';
    case 'muy_alto':
      return 'tone-vhigh';
    default:
      return 'tone-na';
  }
}

function swimTone(swim) {
  switch (swim) {
    case 'favorable':
      return 'tone-low';
    case 'precaucion':
      return 'tone-med';
    case 'peligrosa':
      return 'tone-high';
    default:
      return 'tone-na';
  }
}

function familyTone(fam) {
  switch (fam) {
    case 'adecuada':
      return 'tone-low';
    case 'supervision':
      return 'tone-med';
    case 'no_recomendada':
      return 'tone-high';
    default:
      return 'tone-na';
  }
}

function surfTone(surf) {
  switch (surf) {
    case 'favorable':
      return 'tone-low';
    case 'posible':
      return 'tone-med';
    default:
      return 'tone-na';
  }
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export class BeachDrawer {
  constructor({ onInspectSatellite }) {
    this.el = document.getElementById('beach-drawer');
    this.titleEl = document.getElementById('drawer-title');
    this.badgesEl = document.getElementById('drawer-badges');
    this.bodyEl = document.getElementById('drawer-body');
    this.closeBtn = document.getElementById('drawer-close');
    this.handleEl = document.getElementById('drawer-handle');
    this.onInspectSatellite = onInspectSatellite;
    this.currentBeach = null;
    this.currentSector = null;

    this.closeBtn.addEventListener('click', () => this.close());
    this.initTouchDrag();
  }

  initTouchDrag() {
    if (!this.handleEl) return;
    let startY = 0;
    let isDragging = false;
    this.handleEl.addEventListener(
      'touchstart',
      (e) => {
        if (!this.el.classList.contains('open')) return;
        startY = e.touches[0].clientY;
        isDragging = true;
      },
      { passive: true }
    );
    this.handleEl.addEventListener(
      'touchend',
      (e) => {
        if (!isDragging) return;
        isDragging = false;
        const deltaY = e.changedTouches[0].clientY - startY;
        if (deltaY > 90) {
          if (this.el.classList.contains('peek')) {
            this.close();
          } else {
            this.el.classList.add('peek');
          }
        } else if (deltaY < -50) {
          this.el.classList.remove('peek');
        }
      },
      { passive: true }
    );
    this.handleEl.addEventListener('click', () => {
      if (window.innerWidth < 768) {
        this.el.classList.toggle('peek');
      }
    });
  }

  open(beach, sectorFeature = null) {
    this.currentBeach = beach;
    this.currentSector = sectorFeature;
    this.el.classList.add('open');
    this.el.classList.remove('peek');
    this.render();
  }

  close() {
    this.el.classList.remove('open', 'peek');
    this.currentBeach = null;
    if (window.location.hash.startsWith('#playa=')) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }

  rerenderIfOpen() {
    if (this.currentBeach && this.el.classList.contains('open')) {
      this.render();
    }
  }

  render() {
    const b = this.currentBeach;
    if (!b) return;
    const locale = getLocale();

    this.titleEl.textContent = b.name;

    const badges = [
      `<span class="tag sector">${escapeHtml(t('drawer.sectorLabel', { sector: b.sector }))}</span>`,
      `<span class="tag">${escapeHtml(t(`regions.${b.region}`))}</span>`,
      `<span class="tag">${b.visited ? '✓ ' + escapeHtml(t('drawer.visited')) : '• ' + escapeHtml(t('drawer.notVisited'))}</span>`
    ];
    this.badgesEl.innerHTML = badges.join('');

    const hazardsList = (b.hazards && b.hazards.length ? b.hazards : ['ninguno_conocido'])
      .map((h) => escapeHtml(t(`hazards.${h}`)))
      .join(' · ');

    const usesList = (b.uses && b.uses.length ? b.uses : ['ocio'])
      .map((u) => escapeHtml(t(`uses.${u}`)))
      .join(' · ');

    const tideAlerts = [];
    if (b.hazards && b.hazards.includes('bloqueo_marea_alta')) {
      tideAlerts.push(t('drawer.tideCutoffWarn'));
    }
    if (b.hazards && b.hazards.includes('desembocadura')) {
      tideAlerts.push(t('drawer.riverMouthWarn'));
    }
    if (b.hazards && b.hazards.includes('rocas_intermareales')) {
      tideAlerts.push(t('drawer.intertidalRocksWarn'));
    }

    const sandSwatchStyle = SAND_SWATCHES[b.sand] || SAND_SWATCHES.sin_datos;
    const accessParts = [
      t(`accessType.${b.accessType || 'publico'}`),
      b.accessMode ? t(`accessMode.${b.accessMode}`) : null,
      b.accessState ? t(`accessState.${b.accessState}`) : null
    ].filter(Boolean);

    const sectorSummary =
      (this.currentSector && this.currentSector.summary && this.currentSector.summary[locale]) ||
      (this.currentSector && this.currentSector.summary && this.currentSector.summary.es) ||
      '';

    const beachNote =
      (b.note && (b.note[locale] || b.note.es)) ||
      (this.currentSector && this.currentSector.beachNotes && this.currentSector.beachNotes[b.id] && (this.currentSector.beachNotes[b.id][locale] || this.currentSector.beachNotes[b.id].es)) ||
      '';

    const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${b.lat},${b.lng}`;
    const wazeUrl = `https://waze.com/ul?ll=${b.lat},${b.lng}&navigate=yes`;

    this.bodyEl.innerHTML = `
      ${
        b.altNames && b.altNames.length
          ? `<div style="font-size:0.82rem;color:var(--text-muted)"><strong>${escapeHtml(t('drawer.altNames'))}:</strong> ${escapeHtml(b.altNames.join(', '))}</div>`
          : ''
      }
      ${
        b.ignName && b.ignName !== 'No tiene'
          ? `<div style="font-size:0.82rem;color:var(--text-muted)"><strong>${escapeHtml(t('drawer.ignName'))}:</strong> ${escapeHtml(b.ignName)}</div>`
          : ''
      }

      <div>
        <h3 class="section-heading">${escapeHtml(t('drawer.behaviorHeading'))}</h3>
        <div class="behavior-grid">
          <div class="behavior-card ${ripTone(b.rip)}">
            <span class="behavior-card-label">🌊 ${escapeHtml(t('drawer.tideCard'))}</span>
            <span class="behavior-card-val">${escapeHtml(t(`rip.${b.rip}`))}</span>
          </div>
          <div class="behavior-card ${swimTone(b.swim)}">
            <span class="behavior-card-label">🏊 ${escapeHtml(t('drawer.swimCard'))}</span>
            <span class="behavior-card-val">${escapeHtml(t(`swim.${b.swim}`))}</span>
          </div>
          <div class="behavior-card ${familyTone(b.family)}">
            <span class="behavior-card-label">👨‍👩‍👧 ${escapeHtml(t('drawer.familyCard'))}</span>
            <span class="behavior-card-val">${escapeHtml(t(`family.${b.family}`))}</span>
          </div>
          <div class="behavior-card ${surfTone(b.surf)}">
            <span class="behavior-card-label">🏄 ${escapeHtml(t('drawer.surfCard'))}</span>
            <span class="behavior-card-val">${escapeHtml(t(`surf.${b.surf}`))}</span>
          </div>
        </div>
        <p class="behavior-note">${escapeHtml(t(`ripDesc.${b.rip}`))} ${escapeHtml(t(`familyDesc.${b.family}`))}</p>
        ${tideAlerts.map((a) => `<div class="alert-box">${escapeHtml(a)}</div>`).join('')}
      </div>

      <div>
        <h3 class="section-heading">${escapeHtml(t('drawer.techHeading'))}</h3>
        <div class="tech-list">
          <div class="tech-row">
            <span class="tech-key">${escapeHtml(t('drawer.accessLabel'))}</span>
            <span class="tech-val">${escapeHtml(accessParts.join(' · '))}</span>
          </div>
          <div class="tech-row">
            <span class="tech-key">${escapeHtml(t('drawer.sandGeoLabel'))}</span>
            <span class="tech-val">
              <span class="sand-swatch" style="background:${sandSwatchStyle}"></span>
              ${escapeHtml(t(`sand.${b.sand || 'sin_datos'}`))} · ${escapeHtml(t(`geo.${b.geo || 'recta_abierta'}`))}
            </span>
          </div>
          <div class="tech-row">
            <span class="tech-key">${escapeHtml(t('drawer.infraLabel'))}</span>
            <span class="tech-val">${escapeHtml(t(`infra.${b.infra || 'sin_datos'}`))}</span>
          </div>
          <div class="tech-row">
            <span class="tech-key">${escapeHtml(t('drawer.otherHazardsLabel'))}</span>
            <span class="tech-val">${hazardsList}</span>
          </div>
          <div class="tech-row">
            <span class="tech-key">${escapeHtml(t('drawer.usesLabel'))}</span>
            <span class="tech-val">${usesList}</span>
          </div>
          ${
            b.sinac
              ? `<div class="tech-row"><span class="tech-key">${escapeHtml(t('drawer.protectedLabel'))}</span><span class="tech-val">${escapeHtml(b.sinac)}</span></div>`
              : ''
          }
        </div>
      </div>

      ${
        beachNote || sectorSummary
          ? `<div>
              <h3 class="section-heading">${escapeHtml(t('drawer.sectorNotesHeading'))}</h3>
              <div class="narrative-box">
                ${beachNote ? `<p style="margin:0 0 8px">${escapeHtml(beachNote)}</p>` : ''}
                ${sectorSummary ? `<p style="margin:0;color:var(--text-muted)">${escapeHtml(sectorSummary)}</p>` : ''}
              </div>
            </div>`
          : ''
      }

      <button type="button" class="action-btn primary" id="btn-inspect-sat" style="width:100%">
        🛰️ ${escapeHtml(t('drawer.viewSatellite'))}
      </button>

      <div class="action-row">
        <a class="action-btn" href="${googleMapsUrl}" target="_blank" rel="noopener">📍 ${escapeHtml(t('drawer.openGoogleMaps'))}</a>
        <a class="action-btn" href="${wazeUrl}" target="_blank" rel="noopener">🚗 ${escapeHtml(t('drawer.openWaze'))}</a>
        <button type="button" class="action-btn" id="btn-share-beach">🔗 ${escapeHtml(t('drawer.shareBeach'))}</button>
      </div>
    `;

    const satBtn = document.getElementById('btn-inspect-sat');
    if (satBtn) {
      satBtn.addEventListener('click', () => {
        if (this.onInspectSatellite) this.onInspectSatellite(b);
      });
    }

    const shareBtn = document.getElementById('btn-share-beach');
    if (shareBtn) {
      shareBtn.addEventListener('click', async () => {
        const url = `${window.location.origin}${window.location.pathname}#playa=${encodeURIComponent(b.id)}`;
        try {
          await navigator.clipboard.writeText(url);
          shareBtn.textContent = '✓ ' + t('drawer.linkCopied');
          setTimeout(() => {
            shareBtn.textContent = '🔗 ' + t('drawer.shareBeach');
          }, 1800);
        } catch {
          window.location.hash = `playa=${encodeURIComponent(b.id)}`;
        }
      });
    }
  }
}

export function renderGuideModalContent() {
  const container = document.getElementById('guide-modal-body');
  if (!container) return;
  const rules = t('guide.rules');
  const rulesHtml = Array.isArray(rules)
    ? rules.map((r) => `<li>${escapeHtml(r)}</li>`).join('')
    : '';

  container.innerHTML = `
    <p style="margin:0">${escapeHtml(t('guide.intro'))}</p>
    <div>
      <h3 class="section-heading">${escapeHtml(t('guide.visualTitle'))}</h3>
      <div class="svg-diagram-grid">
        <div class="diagram-card">
          <svg viewBox="0 0 220 110" style="width:100%;border-radius:8px;background:#e0f2fe">
            <rect y="78" width="220" height="32" fill="#fde68a"/>
            <path d="M0 68 Q55 62 110 68 T220 68" stroke="#ffffff" stroke-width="5" fill="none"/>
            <path d="M0 50 Q45 45 90 50 M130 50 Q175 45 220 50" stroke="#ffffff" stroke-width="4" fill="none"/>
            <ellipse cx="110" cy="28" rx="22" ry="18" fill="#b45309" opacity="0.55"/>
            <path d="M110 76 L110 18 M103 28 L110 16 L117 28" stroke="#dc2626" stroke-width="3" fill="none"/>
          </svg>
          <h4>${escapeHtml(t('guide.plumeTitle'))}</h4>
          <p>${escapeHtml(t('guide.plumeDesc'))}</p>
        </div>
        <div class="diagram-card">
          <svg viewBox="0 0 220 110" style="width:100%;border-radius:8px;background:#bae6fd">
            <rect y="78" width="220" height="32" fill="#fde68a"/>
            <path d="M10 64 L82 64 M138 64 L210 64" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>
            <path d="M10 46 L84 46 M136 46 L210 46" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
            <rect x="88" y="16" width="44" height="62" fill="#0369a1" opacity="0.35" rx="6"/>
            <path d="M110 74 L110 22 M103 32 L110 20 L117 32" stroke="#dc2626" stroke-width="3" fill="none"/>
          </svg>
          <h4>${escapeHtml(t('guide.sandyChannelTitle'))}</h4>
          <p>${escapeHtml(t('guide.sandyChannelDesc'))}</p>
        </div>
        <div class="diagram-card">
          <svg viewBox="0 0 220 110" style="width:100%;border-radius:8px;background:#bae6fd">
            <rect y="78" width="220" height="32" fill="#fde68a"/>
            <path d="M12 80 L48 48 L88 55 L86 80 Z" fill="#64748b"/>
            <path d="M134 80 L132 52 L175 46 L208 80 Z" fill="#64748b"/>
            <path d="M110 76 L110 18 M103 28 L110 16 L117 28" stroke="#dc2626" stroke-width="3" fill="none"/>
            <path d="M15 36 L85 36 M135 36 L205 36" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
          </svg>
          <h4>${escapeHtml(t('guide.rockyChannelTitle'))}</h4>
          <p>${escapeHtml(t('guide.rockyChannelDesc'))}</p>
        </div>
        <div class="diagram-card">
          <svg viewBox="0 0 220 110" style="width:100%;border-radius:8px;background:#bae6fd">
            <path d="M0 72 Q28 90 55 72 T110 72 T165 72 T220 72 L220 110 L0 110 Z" fill="#fde68a"/>
            <path d="M55 70 L55 24 M49 33 L55 22 L61 33" stroke="#dc2626" stroke-width="2.5" fill="none"/>
            <path d="M165 70 L165 24 M159 33 L165 22 L171 33" stroke="#dc2626" stroke-width="2.5" fill="none"/>
            <path d="M10 48 L40 48 M75 48 L145 48 M180 48 L210 48" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
          </svg>
          <h4>${escapeHtml(t('guide.cuspTitle'))}</h4>
          <p>${escapeHtml(t('guide.cuspDesc'))}</p>
        </div>
      </div>
    </div>
    <div>
      <h3 class="section-heading">${escapeHtml(t('guide.rulesTitle'))}</h3>
      <ol class="rules-list">${rulesHtml}</ol>
    </div>
    <div class="escape-banner">${escapeHtml(t('guide.escapeTip'))}</div>
  `;
}
