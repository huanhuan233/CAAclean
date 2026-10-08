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

test('CATDocument 使用自身 CATPart 文件名而不是上传 ZIP 包名', () => {
  const tree = buildNativeFeatureTree(
    [{ feature_id: 'doc', native_type: 'CATDocument', display_name: 'D:\\secret\\510.001 A.CATPart' }],
    '连接关系示例数据.zip'
  );

  assert.equal(tree[0].displayName, '510.001 A.CATPart');
});

test('CATProduct 装配直接作为树根而不是套一层上传 ZIP 文件名', () => {
  const tree = buildNativeFeatureTree(
    [{ feature_id: 'root', startup_type: 'CATProduct', display_name: '500.000' }],
    '连接关系示例数据.zip'
  );

  assert.equal(tree.length, 1);
  assert.equal(tree[0].id, 'root');
  assert.equal(tree[0].displayName, '500.000');
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
  const source = buildNativeFeatureTree(
    [
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
    ],
    'source.CATPart',
    {},
    { object_1: '16333', object_2: '开角' }
  );
  const nodes = flattenFeatureTree(source);
  assert.deepEqual(
    nodes.map(node => node.id),
    ['source:source.CATPart', 'F1', 'F2', 'G1', 'P1', 'P2']
  );
  assert.deepEqual(
    nodes.find(node => node.id === 'F2')?.children.map(node => node.id),
    ['G1']
  );
  assert.deepEqual(
    nodes.find(node => node.id === 'G1')?.children.map(node => node.id),
    ['P1', 'P2']
  );
  assert.equal(nodes.find(node => node.id === 'P1')?.parameterValue, '16333');
  assert.equal(nodes.find(node => node.id === 'P2')?.parameterValue, '开角');
});

test('PostgreSQL 树接口内联的参数值显示为黑体等号值', () => {
  const nodes = flattenFeatureTree(buildNativeFeatureTree([
    {
      feature_id: 'parameter',
      parent_id: 'group',
      traversal_index: 1,
      startup_type: 'String',
      display_name: '材料编号',
      parameter_value: 'M00001453'
    }
  ], 'source.CATPart'));

  assert.equal(nodes.find(node => node.id === 'parameter')?.parameterValue, 'M00001453');
});

test('默认原生树不把补充发现的铺层参数提升到 CATIA 顶层', () => {
  const source = buildNativeFeatureTree([
    { feature_id: 'doc', startup_type: 'CATDocument', display_name: 'source.CATPart' },
    { feature_id: 'container', parent_id: 'doc', startup_type: 'CATIPrtContainer', display_name: 'PartSpecContainer' },
    { feature_id: 'part', parent_id: 'container', startup_type: 'MechanicalPart', display_name: 'Part1' },
    { feature_id: 'plies', parent_id: 'part', startup_type: 'GSMTool', display_name: 'Plies Group.2_STLMeshData',
      attributes: { presentation_status: 'visible' } },
    { feature_id: 'sag', parent_id: 'container', startup_type: 'LENGTH', display_name: 'Sag',
      attributes: { presentation_status: 'non_primary' } },
    { feature_id: 'step', parent_id: 'sag', startup_type: 'LENGTH', display_name: 'Step',
      attributes: { presentation_status: 'visible' } }
  ], 'source.CATPart');
  const visible = flattenFeatureTree(projectFeatureTree(source, { showSystem: false }).nodes);
  assert.equal(visible.some(node => node.id === 'plies'), true);
  assert.equal(visible.some(node => node.id === 'sag' || node.id === 'step'), false);
});

test('同一容器下优先使用 CAA 原生枚举顺序而不是 occurrence 字符串顺序', () => {
  const source = buildNativeFeatureTree(
    [
      { feature_id: 'occurrence_1', traversal_index: 1, startup_type: 'MechanicalPart', display_name: 'Part2' },
      {
        feature_id: 'occurrence_19',
        parent_id: 'occurrence_1',
        traversal_index: 2,
        startup_type: 'GSMTool',
        display_name: '几何特征'
      },
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
    ],
    'source.CATPart'
  );

  const geometry = flattenFeatureTree(source).find(node => node.id === 'occurrence_19');
  assert.deepEqual(
    geometry?.children.map(node => node.displayName),
    ['槽.1', '槽.2', '槽.4']
  );
});

test('兼容 API 记录缺少 feature_id 但带 occurrence_id 的树节点', () => {
  const source = buildNativeFeatureTree(
    [
      { feature_id: 'root', traversal_index: 1, startup_type: 'MechanicalPart', display_name: 'Part2' },
      {
        occurrence_id: 'occurrence_missing_feature_id',
        parent_id: 'root',
        traversal_index: 2,
        startup_type: 'GSMTool',
        display_name: 'Surface.542'
      } as unknown as NativeFeatureRecord
    ],
    'source.CATPart'
  );

  const nodes = flattenFeatureTree(source);
  assert.equal(nodes.some(node => node.id === 'occurrence_missing_feature_id'), true);
  assert.equal(nodes.find(node => node.id === 'occurrence_missing_feature_id')?.displayName, 'Surface.542');
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
