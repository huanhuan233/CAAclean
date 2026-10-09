import assert from 'node:assert/strict';
import test from 'node:test';
import { filterStepImportTree, mapStepImportTree, stepImportSelection } from '../modules/step-import-tree';

const imported: Api.Cad.TreeNode[] = [{
  id: 'document-id', parent_entity_id: null, entity_type: 'root', label: 'duoyimian234.stp',
  source_ref: null, geometry_type: null, children: [
    { id: 'face-object-id', parent_entity_id: 'document-id', entity_type: 'imported_object',
      label: 'FACE055', source_ref: 'Face055', geometry_type: null, children: [] },
    { id: 'axis-object-id', parent_entity_id: 'document-id', entity_type: 'imported_object',
      label: 'X-axis', source_ref: 'XAxis', geometry_type: null, children: [] },
    { id: 'body-id', parent_entity_id: 'document-id', entity_type: 'body',
      label: 'Body001', source_ref: 'Body001', geometry_type: null, children: [
        { id: 'solid-id', parent_entity_id: 'body-id', entity_type: 'solid',
          label: 'Solid001', source_ref: 'Solid001', geometry_type: null, children: [] }
      ] }
  ]
}];

test('STEP 导入树保留数据库身份与父子关系，不伪造 CATIA 原生特征', () => {
  const tree = mapStepImportTree(imported);
  assert.equal(tree[0].id, 'document-id');
  assert.deepEqual(tree[0].children.map(node => node.id), ['face-object-id', 'axis-object-id', 'body-id']);
  assert.equal(tree[0].children[2].children[0].id, 'solid-id');
  assert.equal(stepImportSelection(tree[0].children[0]).kind, 'step_import_object');
  assert.equal(stepImportSelection(tree[0].children[0]).namespace, 'step_render');
});

test('STEP 搜索保留原始 ID 和祖先，不按筛选结果重新编号', () => {
  const tree = mapStepImportTree(imported);
  const filtered = filterStepImportTree(tree, 'solid001');
  assert.equal(filtered[0].id, 'document-id');
  assert.equal(filtered[0].children[0].id, 'body-id');
  assert.equal(filtered[0].children[0].children[0].id, 'solid-id');
  assert.equal(stepImportSelection(filtered[0].children[0].children[0]).kind, 'solid');
});

test('STEP 同级对象按原始导入序号排列，不按文本树路径排列', () => {
  const tree = mapStepImportTree([{
    ...imported[0],
    children: [
      { ...imported[0].children[1], sort_order: 10 },
      { ...imported[0].children[0], sort_order: 2 }
    ]
  }]);
  assert.deepEqual(tree[0].children.map(node => node.id), ['face-object-id', 'axis-object-id']);
});
