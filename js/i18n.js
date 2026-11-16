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

/**
 * Extensible Internationalization (i18n) Module
 *
 * To add a new language in the future:
 * 1. Create `locales/<lang_code>.json` matching the structure of `locales/en.json`.
 * 2. Append `{ code: '<lang_code>', label: '<SHORT_LABEL>' }` to SUPPORTED_LOCALES below.
 */

export const SUPPORTED_LOCALES = [
  { code: 'es', label: 'ES' },
  { code: 'en', label: 'EN' }
];

const STORAGE_KEY = 'playascr_locale';
const FALLBACK_LOCALE = 'es';

let currentLocale = FALLBACK_LOCALE;
const dictionaries = new Map();
const listeners = new Set();

function resolveNested(obj, path) {
  return path.split('.').reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), obj);
}

export async function loadLocale(code) {
  const validCode = SUPPORTED_LOCALES.some((l) => l.code === code) ? code : FALLBACK_LOCALE;
  if (!dictionaries.has(validCode)) {
    const res = await fetch(`./locales/${validCode}.json`);
    if (!res.ok) throw new Error(`Failed to load locale ${validCode}`);
    dictionaries.set(validCode, await res.json());
  }
  currentLocale = validCode;
  document.documentElement.lang = validCode;
  try {
    localStorage.setItem(STORAGE_KEY, validCode);
  } catch {
    // ignore storage restrictions
  }
  applyStaticTranslations();
  listeners.forEach((cb) => cb(validCode));
  return validCode;
}

export async function initI18n() {
  let initial = FALLBACK_LOCALE;
  try {
    const urlLang = new URLSearchParams(window.location.search).get('lang');
    const saved = localStorage.getItem(STORAGE_KEY);
    const nav = (navigator.language || '').slice(0, 2).toLowerCase();
    const candidate = urlLang || saved || nav;
    if (SUPPORTED_LOCALES.some((l) => l.code === candidate)) {
      initial = candidate;
    }
  } catch {
    initial = FALLBACK_LOCALE;
  }

  // Always preload fallback Spanish dictionary too for graceful missing-key fallback
  if (!dictionaries.has(FALLBACK_LOCALE)) {
    try {
      const res = await fetch(`./locales/${FALLBACK_LOCALE}.json`);
      if (res.ok) dictionaries.set(FALLBACK_LOCALE, await res.json());
    } catch {
      // handled below
    }
  }

  return loadLocale(initial);
}

export function getLocale() {
  return currentLocale;
}

export function onLocaleChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function t(key, params = {}) {
  const dict = dictionaries.get(currentLocale) || dictionaries.get(FALLBACK_LOCALE) || {};
  let val = resolveNested(dict, key);
  if (val === undefined) {
    const fallbackDict = dictionaries.get(FALLBACK_LOCALE) || {};
    val = resolveNested(fallbackDict, key);
  }
  if (val === undefined) return key;
  if (typeof val === 'string') {
    return val.replace(/\{(\w+)\}/g, (_, k) => (params[k] !== undefined ? String(params[k]) : `{${k}}`));
  }
  return val;
}

export function applyStaticTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    const translated = t(key);
    if (typeof translated === 'string') {
      el.textContent = translated;
    }
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    const key = el.getAttribute('data-i18n-placeholder');
    const translated = t(key);
    if (typeof translated === 'string') {
      el.setAttribute('placeholder', translated);
    }
  });
  document.querySelectorAll('[data-i18n-aria]').forEach((el) => {
    const key = el.getAttribute('data-i18n-aria');
    const translated = t(key);
    if (typeof translated === 'string') {
      el.setAttribute('aria-label', translated);
    }
  });
  document.querySelectorAll('[data-i18n-title]').forEach((el) => {
    const key = el.getAttribute('data-i18n-title');
    const translated = t(key);
    if (typeof translated === 'string') {
      el.setAttribute('title', translated);
    }
  });
}
