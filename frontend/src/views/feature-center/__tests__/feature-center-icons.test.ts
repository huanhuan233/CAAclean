import assert from 'node:assert/strict';
import test from 'node:test';
import { featureCenterIcons } from '../../../assets/iconify/feature-center-icons';

test('all four composite object icons and the offline fallback are bundled', () => {
  for (const name of [
    'mdi:layers-triple-outline', 'mdi:folder-multiple-outline',
    'mdi:format-list-numbered', 'mdi:rhombus-outline',
    'mdi:information-outline', 'mdi:magnify', 'mdi:content-copy',
    'carbon:tree-view-alt', 'carbon:3d-mpr-toggle',
    'material-symbols:sunny', 'heroicons:language'
  ]) {
    const icon = featureCenterIcons[name];
    assert.ok(icon?.body, name);
    assert.ok((icon.width || 0) > 0 && (icon.height || 0) > 0, name);
  }
});
