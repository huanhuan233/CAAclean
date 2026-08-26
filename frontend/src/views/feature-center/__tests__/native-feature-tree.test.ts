import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildNativeFeatureTree,
  flattenFeatureTree,
  projectFeatureTree,
  splitHighlight
} from '../modules/native-feature-tree';
import type { NativeFeatureRecord } from '../modules/native-feature-tree';

const records: NativeFeatureRecord[] = [
  { feature_id: 'F1', traversal_index: 1, native_type: 'CATDocument', display_name: 'D:\\secret\\source.CATPart' },
  {
    feature_id: 'F2',
    parent_id: 'F1',
    traversal_index: 2,
    native_type: 'CATIPrtContainer',
    display_name: 'PartSpecContainer'
  },
  { feature_id: 'F3', parent_id: 'F2', traversal_index: 3, startup_type: 'MechanicalPart', display_name: 'Part2' },
  { feature_id: 'F4', parent_id: 'F3', traversal_index: 4, startup_type: 'GSMPlane', display_name: 'xy 平面' },
  { feature_id: 'F5', parent_id: 'F4', traversal_index: 5, startup_type: 'GSMInternal', display_name: 'GSMInternal.1' },
  { feature_id: 'F6', parent_id: 'F3', traversal_index: 6, startup_type: 'PartBody', display_name: 'PartBody' },
  { feature_id: 'F7', parent_id: 'F6', traversal_index: 7, startup_type: 'Sketch', display_name: '草图.1' },
  { feature_id: 'F8', parent_id: 'F6', traversal_index: 8, startup_type: 'Pocket', display_name: '凹槽.1' }
];

test('语义树隐藏技术容器、归组基准元素并保持真实建模顺序', () => {
  const tree = projectFeatureTree(buildNativeFeatureTree(records, 'source.CATPart'), { showSystem: false });
  const nodes = flattenFeatureTree(tree.nodes);

  assert.equal(tree.nodes[0].displayName, 'source.CATPart');
  assert.equal(
    nodes.some(node => node.displayName.includes('D:\\')),
    false
  );
  assert.equal(
    nodes.some(node => node.nativeType === 'CATIPrtContainer'),
    false
  );
  assert.deepEqual(
    nodes.find(node => node.kind === 'datum_group')?.children.map(node => node.displayName),
    ['xy 平面']
  );
  assert.deepEqual(
    nodes.find(node => node.kind === 'body')?.children.map(node => node.displayName),
    ['草图.1', '凹槽.1']
  );
});

test('开启系统节点后保留原始类型且不改变业务节点顺序', () => {
  const tree = projectFeatureTree(buildNativeFeatureTree(records, 'source.CATPart'), { showSystem: true });
  const nodes = flattenFeatureTree(tree.nodes);

  assert.equal(nodes.find(node => node.id === 'F2')?.isSystem, true);
  assert.equal(nodes.find(node => node.id === 'F5')?.nativeType, 'GSMInternal');
  assert.deepEqual(
    nodes.find(node => node.kind === 'body')?.children.map(node => node.id),
    ['F7', 'F8']
  );
});

test('参数记录保留 CATIA 原始分组层级并显示真实参数值', () => {
  const source = buildNativeFeatureTree([
    { feature_id: 'F1', traversal_index: 1, startup_type: 'MechanicalPart', display_name: 'Part1' },
    { feature_id: 'F2', parent_id: 'F1', traversal_index: 2, startup_type: 'Pocket', display_name: 'Pocket.1' },
    { feature_id: 'G1', parent_id: 'F2', traversal_index: 3, startup_type: 'GSMTool', display_name: '特征属性' },
    {
      feature_id: 'P1',
      parent_id: 'G1',
      traversal_index: 4,
      source_object_id: 'object_1',
      startup_type: 'String',
      display_name: '底面标识'
    },
    {
      feature_id: 'P2',
      parent_id: 'G1',
      traversal_index: 5,
      source_object_id: 'object_2',
      startup_type: 'String',
      display_name: '侧壁类型'
    }
  ], 'source.CATPart', {}, { object_1: '16333', object_2: '开角' });
  const nodes = flattenFeatureTree(source);
  assert.deepEqual(nodes.map(node => node.id), ['source:source.CATPart', 'F1', 'F2', 'G1', 'P1', 'P2']);
  assert.deepEqual(nodes.find(node => node.id === 'F2')?.children.map(node => node.id), ['G1']);
  assert.deepEqual(nodes.find(node => node.id === 'G1')?.children.map(node => node.id), ['P1', 'P2']);
  assert.equal(nodes.find(node => node.id === 'P1')?.parameterValue, '16333');
  assert.equal(nodes.find(node => node.id === 'P2')?.parameterValue, '开角');
});

test('同一容器下优先使用 CAA 原生枚举顺序而不是 occurrence 字符串顺序', () => {
  const source = buildNativeFeatureTree([
    { feature_id: 'occurrence_1', traversal_index: 1, startup_type: 'MechanicalPart', display_name: 'Part2' },
    { feature_id: 'occurrence_19', parent_id: 'occurrence_1', traversal_index: 2, startup_type: 'GSMTool', display_name: '几何特征' },
    {
      feature_id: 'occurrence_122',
      parent_id: 'occurrence_19',
      container_enumeration_index: 1,
      native_enumeration_index: 4,
      startup_type: 'GSMTool',
      display_name: '槽.4'
    },
    {
      feature_id: 'occurrence_20',
      parent_id: 'occurrence_19',
      container_enumeration_index: 1,
      native_enumeration_index: 1,
      startup_type: 'GSMTool',
      display_name: '槽.1'
    },
    {
      feature_id: 'occurrence_65',
      parent_id: 'occurrence_19',
      container_enumeration_index: 1,
      native_enumeration_index: 2,
      startup_type: 'GSMTool',
      display_name: '槽.2'
    }
  ], 'source.CATPart');

  const geometry = flattenFeatureTree(source).find(node => node.id === 'occurrence_19');
  assert.deepEqual(geometry?.children.map(node => node.displayName), ['槽.1', '槽.2', '槽.4']);
});

test('搜索名称、类型和稳定编号时保留祖先并返回自动展开键', () => {
  const source = buildNativeFeatureTree(records, 'source.CATPart');
  const byName = projectFeatureTree(source, { showSystem: false, query: '凹槽' });
  const byType = projectFeatureTree(source, { showSystem: false, query: 'Pocket' });
  const byId = projectFeatureTree(source, { showSystem: false, query: 'F8' });

  for (const result of [byName, byType, byId]) {
    assert.equal(flattenFeatureTree(result.nodes).at(-1)?.id, 'F8');
    assert.equal(result.expandedKeys.includes('F6'), true);
  }
});

test('过滤条件只保留真实类别及其祖先', () => {
  const result = projectFeatureTree(buildNativeFeatureTree(records, 'source.CATPart'), {
    showSystem: false,
    category: 'sketch'
  });
  const ids = flattenFeatureTree(result.nodes).map(node => node.id);

  assert.equal(ids.includes('F7'), true);
  assert.equal(ids.includes('F8'), false);
});

test('搜索高亮保持原文本且不使用 HTML 拼接', () => {
  assert.deepEqual(splitHighlight('凹槽 Pocket.1', 'pocket'), [
    { text: '凹槽 ', matched: false },
    { text: 'Pocket', matched: true },
    { text: '.1', matched: false }
  ]);
});

test('命中父节点时不会把默认隐藏的技术后代重新带回结果', () => {
  const result = projectFeatureTree(buildNativeFeatureTree(records, 'source.CATPart'), {
    showSystem: false,
    query: 'xy 平面'
  });
  assert.equal(
    flattenFeatureTree(result.nodes).some(node => node.id === 'F5'),
    false
  );
});
