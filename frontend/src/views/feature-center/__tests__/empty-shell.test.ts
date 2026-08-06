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
  assert.match(source, /v-if="showProcessingCard" class="processing-card"/);
  assert.match(source, /<ElProgress :percentage="viewerProgress"/);
  assert.match(source, /v-if="showErrorCard" class="error-card"/);
  assert.doesNotMatch(source, /v-if="errorText" class="error-card"/);
  assert.match(source, /class="geometry-toolbar"/);
  assert.match(source, /<ElTree[\s\S]*:data="geometryTreeNodes"/);
  assert.doesNotMatch(source, /class="geometry-tabs"/);
  assert.match(source, /contract\?\.summary\.part_number \|\| detailNode\?\.part_number/);
  assert.match(source, /contract\?\.summary\.part_name \|\| detailNode\?\.name/);
});
