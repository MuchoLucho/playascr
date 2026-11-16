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
  AlertTriangle,
  Car,
  Check,
  Eye,
  Fish,
  Info,
  LifeBuoy,
  LocateFixed,
  Map,
  MapPin,
  Navigation,
  Palmtree,
  Satellite,
  Search,
  Share2,
  ShieldCheck,
  Waves,
  Wind,
  X,
} from 'lucide';

const ICON_REGISTRY = {
  map: Map,
  family: ShieldCheck,
  swim: Fish,
  surf: Wind,
  snorkel: Eye,
  car: Car,
  beach: Palmtree,
  hazard: AlertTriangle,
  guide: LifeBuoy,
  waves: Waves,
  info: Info,
  search: Search,
  close: X,
  satellite: Satellite,
  googleMaps: MapPin,
  waze: Navigation,
  share: Share2,
  check: Check,
  locate: LocateFixed,
};

/**
 * Render a Lucide icon as an inline SVG string with currentColor styling.
 * @param {keyof typeof ICON_REGISTRY} name
 * @param {{ size?: number, className?: string, strokeWidth?: number }} [options]
 * @returns {string}
 */
export function iconSvg(name, { size = 16, className = '', strokeWidth = 2 } = {}) {
  const iconDef = ICON_REGISTRY[name];
  if (!iconDef) return '';

  const children = iconDef
    .map(([tag, attrs]) => {
      const attrStr = Object.entries(attrs)
        .map(([k, v]) => `${k}="${v}"`)
        .join(' ');
      return `<${tag} ${attrStr}/>`;
    })
    .join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" class="lucide-icon lucide-${name} ${className}" aria-hidden="true">${children}</svg>`;
}

export { ICON_REGISTRY };
