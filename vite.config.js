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

import { cpSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const rootDir = dirname(fileURLToPath(import.meta.url));

function copyStaticAtlasAssets() {
  const staticEntries = ['data', 'locales', 'assets', 'manifest.json', 'sw.js'];
  return {
    name: 'copy-static-atlas-assets',
    closeBundle() {
      const outDir = resolve(rootDir, 'dist');
      for (const entry of staticEntries) {
        const src = resolve(rootDir, entry);
        const dest = resolve(outDir, entry);
        if (existsSync(src)) {
          cpSync(src, dest, { recursive: true });
        }
      }
    },
  };
}

export default defineConfig({
  base: './',
  envPrefix: ['VITE_', 'CARTO_'],
  plugins: [copyStaticAtlasAssets()],
});
