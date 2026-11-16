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

export function getSystemPreference() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function getStoredTheme() {
  try {
    const val = localStorage.getItem('color-scheme');
    if (val === 'light' || val === 'dark') return val;
  } catch (e) {}
  return null;
}

export function getEffectiveTheme() {
  const meta = document.querySelector('meta[name="color-scheme"]');
  const content = meta?.getAttribute('content');
  if (content === 'dark' || content === 'light') return content;
  return getSystemPreference();
}

export function updateThemeLabels() {
  const toggleBtn = document.getElementById('theme-toggle');
  if (!toggleBtn) return;
  const current = getEffectiveTheme();
  const nextTheme = current === 'dark' ? 'light' : 'dark';
  const labelKey = nextTheme === 'dark' ? 'app.themeDark' : 'app.themeLight';
  const text = t(labelKey);
  toggleBtn.setAttribute('aria-label', text);
  toggleBtn.setAttribute('title', text);
}

export function initTheme() {
  const meta = document.querySelector('meta[name="color-scheme"]');
  const toggleBtn = document.getElementById('theme-toggle');

  function applyScheme(target) {
    if (!meta) return;
    const system = getSystemPreference();

    if (target === 'system' || target === system) {
      try {
        localStorage.removeItem('color-scheme');
      } catch (e) {}
      meta.setAttribute('content', 'light dark');
      document.documentElement.removeAttribute('data-theme');
    } else {
      try {
        localStorage.setItem('color-scheme', target);
      } catch (e) {}
      meta.setAttribute('content', target);
      document.documentElement.setAttribute('data-theme', target);
    }
    updateThemeLabels();
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const current = getEffectiveTheme();
      const target = current === 'dark' ? 'light' : 'dark';
      applyScheme(target);
    });
  }

  // Cross-tab synchronization via storage event
  window.addEventListener('storage', (e) => {
    if (e.key === 'color-scheme') {
      const val = e.newValue;
      if (val === 'dark' || val === 'light') {
        meta?.setAttribute('content', val);
        document.documentElement.setAttribute('data-theme', val);
      } else {
        meta?.setAttribute('content', 'light dark');
        document.documentElement.removeAttribute('data-theme');
      }
      updateThemeLabels();
    }
  });

  // Handle system preference changes
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  mql.addEventListener('change', () => {
    updateThemeLabels();
  });

  updateThemeLabels();
}
