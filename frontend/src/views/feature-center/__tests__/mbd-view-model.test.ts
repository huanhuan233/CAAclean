import assert from 'node:assert/strict';
import test from 'node:test';
import { mbdAnnotationTitle, mbdFieldName, mbdReadStatus, mbdSafeExternalUrl, mbdSemanticValue, mbdTypeName } from '../modules/mbd-view-model';

test('MBD types and raw roughness indexes remain distinct', () => {
  assert.equal(mbdTypeName('dimension'), '尺寸');
  assert.equal(mbdTypeName('gdt'), '形位公差');
  assert.equal(mbdTypeName('roughness'), '表面粗糙度');
  assert.equal(mbdTypeName('datum_simple'), '基准');
  assert.equal(mbdTypeName('text'), '文本注解');
  assert.equal(mbdTypeName('flag_note'), '旗标注释');
  assert.equal(mbdTypeName('noa'), 'NOA 注释');
  assert.equal(mbdFieldName('field_9'), '粗糙度原始字段 9');
  assert.equal(mbdTypeName('future_type'), '未分类标注');
});

test('native text is kept verbatim and unavailable status is not a success', () => {
  const record = { fta_semantic_id: 'T1', fta_set_id: 'P1', component_kind: 'text', read_status: 'partial',
    annotation_text: '第一行\n第二行 <script>', annotation_text_status: 'available' };
  assert.equal(mbdAnnotationTitle(record), '第一行');
  assert.equal(record.annotation_text, '第一行\n第二行 <script>');
  assert.equal(mbdReadStatus('partial').tone, 'warning');
  assert.equal(mbdReadStatus('failed').tone, 'danger');
});

test('external annotation references only expose ordinary web protocols', () => {
  assert.equal(mbdSafeExternalUrl('javascript:alert(1)'), null);
  assert.equal(mbdSafeExternalUrl('file:///c:/secret'), null);
  assert.equal(mbdSafeExternalUrl('https://example.org/drawing'), 'https://example.org/drawing');
});

test('nested native alias and TTRS evidence remain visible for old stored payloads', () => {
  const record = { fta_semantic_id: 'A1', fta_set_id: 'P1', component_kind: 'dimension', read_status: 'partial',
    semantic_payload: { native_alias: '孔径', annotation_ttrs_count: 2,
      native_geometry_link_status: 'native_ttrs_unmapped' } };
  assert.equal(mbdAnnotationTitle(record), '孔径');
  assert.equal(mbdSemanticValue(record, 'annotation_ttrs_count'), 2);
  assert.equal(mbdSemanticValue(record, 'native_geometry_link_status'), 'native_ttrs_unmapped');
});
