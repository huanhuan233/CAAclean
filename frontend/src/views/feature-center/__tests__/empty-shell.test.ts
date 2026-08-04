import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

test('没有历史结果时仍保留 Feature Center 工作区框架', () => {
  const componentPath = fileURLToPath(new URL('../index.vue', import.meta.url));
  const source = readFileSync(componentPath, 'utf-8');

  assert.match(source, /<main\s+v-loading="loading"\s+class="workspace"/);
  assert.match(source, /v-if="!contract"\s+class="viewer-empty"/);
  assert.doesNotMatch(source, /<main\s+v-else-if="contract"/);
  assert.match(source, /<span v-if="contract">\{\{ contract\.summary\.recognized_feature_count/);
  assert.match(source, /<span v-if="contract" :class="mappingAvailable/);
  assert.match(source, /<span v-if="contract" class="stage-badge"/);
  assert.match(source, /contract\?\.summary\.part_number \|\| detailNode\?\.part_number/);
  assert.match(source, /contract\?\.summary\.part_name \|\| detailNode\?\.name/);
});
