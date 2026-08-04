import assert from 'node:assert/strict';
import test from 'node:test';
import { buildDetailPanelLayout } from '../modules/detail-panel';

test('独立 CATPart 只显示零件、来源、操作和拓扑分组', () => {
  const layout = buildDetailPanelLayout({
    assemblyMode: 'single_part',
    nodeType: 'part',
    hasParent: false,
    sourceFormat: 'CATPART',
    nativeFeatureAvailable: true,
    featureFaceMappingAvailable: true
  });

  assert.deepEqual(layout.groups, ['part', 'source', 'operations', 'topology']);
  assert.equal(layout.featureLinkLabel, '查看原生特征与关联面');
  assert.equal(layout.featureLinkEnabled, true);
});

test('BOM 中的零件实例增加装配实例和定位分组', () => {
  const layout = buildDetailPanelLayout({
    assemblyMode: 'assembly',
    nodeType: 'part',
    hasParent: true,
    sourceFormat: 'STEP',
    nativeFeatureAvailable: false,
    featureFaceMappingAvailable: true
  });

  assert.deepEqual(layout.groups, ['part', 'assembly_instance', 'source', 'positioning', 'operations', 'topology']);
  assert.equal(layout.featureLinkLabel, '查看识别特征与关联面');
});

test('总装和子装配使用装配属性而不是零件属性', () => {
  for (const nodeType of ['assembly', 'subassembly', 'root'] as const) {
    const layout = buildDetailPanelLayout({
      assemblyMode: 'assembly',
      nodeType,
      hasParent: nodeType === 'subassembly',
      sourceFormat: 'CATPART',
      nativeFeatureAvailable: true,
      featureFaceMappingAvailable: true
    });
    assert.deepEqual(layout.groups, ['assembly', 'assembly_statistics', ...(nodeType === 'subassembly' ? ['positioning'] as const : []), 'operations', 'topology']);
  }
});

test('设计特征和几何对象拥有各自属性分组', () => {
  assert.deepEqual(buildDetailPanelLayout({ selectionKind: 'feature', assemblyMode: 'assembly', sourceFormat: 'CATPART' }).groups,
    ['feature', 'operations', 'topology']);
  assert.deepEqual(buildDetailPanelLayout({ selectionKind: 'geometry', assemblyMode: 'assembly', sourceFormat: 'STEP' }).groups,
    ['geometry', 'operations', 'topology']);
});

test('Feature 关联入口必须由真实数据能力决定', () => {
  const layout = buildDetailPanelLayout({
    assemblyMode: 'single_part',
    nodeType: 'part',
    sourceFormat: 'CATPART',
    nativeFeatureAvailable: false,
    featureFaceMappingAvailable: true
  });
  assert.equal(layout.featureLinkEnabled, false);
});
