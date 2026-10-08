import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { getIconData } from '@iconify/utils';

const root = resolve(import.meta.dirname, '..');
const source = join(root, 'src/views/feature-center');
const output = join(root, 'src/assets/iconify/feature-center-icons.ts');
const required = [
  'mdi:layers-triple-outline', 'mdi:folder-multiple-outline',
  'mdi:format-list-numbered', 'mdi:rhombus-outline',
  'mdi:magnify', 'mdi:content-copy', 'mdi:chevron-right',
  'mdi:alert-circle-outline', 'mdi:refresh', 'mdi:crosshairs-gps',
  'mdi:information-outline', 'mdi:close', 'mdi:chevron-down',
  'mdi:vector-polyline'
];

function sources(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sources(path);
    return /\.(vue|ts)$/.test(entry.name) && path !== output ? [path] : [];
  });
}

function iconNames() {
  const names = new Set(required);
  for (const path of sources(source)) {
    const text = readFileSync(path, 'utf8');
    for (const match of text.matchAll(/\b(?:mdi|lucide):[a-z0-9-]+\b/g)) names.add(match[0]);
  }
  return [...names].sort();
}

function generatedSource() {
  const collections = new Map();
  const icons = {};
  for (const name of iconNames()) {
    const [prefix, iconName] = name.split(':');
    if (!collections.has(prefix)) {
      collections.set(prefix, JSON.parse(readFileSync(
        join(root, 'node_modules/@iconify/json/json', `${prefix}.json`), 'utf8')));
    }
    const data = getIconData(collections.get(prefix), iconName);
    if (!data) throw new Error(`Iconify snapshot does not contain ${name}`);
    icons[name] = data;
  }
  return `// Generated from @iconify/json ${JSON.parse(readFileSync(join(root, 'node_modules/@iconify/json/package.json'), 'utf8')).version}.\n` +
    `// Run pnpm icons:generate; do not edit by hand.\n` +
    `import type { IconifyIcon } from '@iconify/vue';\n\n` +
    `export const featureCenterIcons = ${JSON.stringify(icons, null, 2)} as Record<string, IconifyIcon>;\n`;
}

const command = process.argv[2] || 'check';
if (command === 'search') {
  const prefix = process.argv[3] || 'mdi';
  const keyword = (process.argv[4] || '').toLowerCase();
  if (!/^[a-z0-9-]+$/.test(prefix)) throw new Error('invalid icon collection prefix');
  const collection = JSON.parse(readFileSync(join(root, 'node_modules/@iconify/json/json', `${prefix}.json`), 'utf8'));
  const names = [...Object.keys(collection.icons || {}), ...Object.keys(collection.aliases || {})]
    .filter(name => name.includes(keyword)).sort().slice(0, 100);
  process.stdout.write(names.map(name => `${prefix}:${name}`).join('\n') + '\n');
} else if (command === 'generate') {
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, generatedSource());
  process.stdout.write(`Generated ${relative(root, output)} with ${iconNames().length} icons\n`);
} else if (command === 'check') {
  if (readFileSync(output, 'utf8') !== generatedSource()) throw new Error('Feature Center icon subset is stale; run pnpm icons:generate');
  process.stdout.write(`Verified ${iconNames().length} local Feature Center icons\n`);
} else {
  throw new Error('usage: feature-center-icons.mjs generate|check|search [prefix] [keyword]');
}
