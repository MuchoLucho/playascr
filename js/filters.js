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

import { t } from './i18n.js';

export const FILTER_DEFS = [
  { id: 'all', iconName: 'map', key: 'filters.all', predicate: () => true },
  {
    id: 'familySafe',
    iconName: 'family',
    key: 'filters.familySafe',
    predicate: (b) => b.family === 'adecuada'
  },
  {
    id: 'swimSafe',
    iconName: 'swim',
    key: 'filters.swimSafe',
    predicate: (b) => b.swim === 'favorable'
  },
  {
    id: 'surf',
    iconName: 'surf',
    key: 'filters.surf',
    predicate: (b) => b.surf === 'favorable' || (b.uses && b.uses.includes('surf'))
  },
  {
    id: 'snorkel',
    iconName: 'snorkel',
    key: 'filters.snorkel',
    predicate: (b) => b.uses && b.uses.includes('snorquel')
  },
  {
    id: 'vehicle',
    iconName: 'car',
    key: 'filters.vehicle',
    predicate: (b) => b.accessMode === 'vehiculo' && b.accessType !== 'restringido'
  },
  {
    id: 'whiteSand',
    iconName: 'beach',
    key: 'filters.whiteSand',
    predicate: (b) => b.sand === 'blanca' || b.sand === 'blanca_negra'
  },
  {
    id: 'highHazard',
    iconName: 'hazard',
    key: 'filters.highHazard',
    predicate: (b) =>
      b.rip === 'alto' ||
      b.rip === 'muy_alto' ||
      (b.hazards && b.hazards.includes('bloqueo_marea_alta'))
  }
];

export function normalizeText(str) {
  return (str || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

export function filterBeaches(beaches, query, activeFilterId) {
  const filterDef = FILTER_DEFS.find((f) => f.id === activeFilterId) || FILTER_DEFS[0];
  const q = normalizeText(query);

  return beaches.filter((b) => {
    if (!filterDef.predicate(b)) return false;
    if (!q) return true;
    const haystack = [
      b.name,
      b.ignName,
      ...(b.altNames || []),
      b.sector,
      t(`regions.${b.region}`)
    ]
      .filter(Boolean)
      .map(normalizeText)
      .join(' ');
    return haystack.includes(q);
  });
}
