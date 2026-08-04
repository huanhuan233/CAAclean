import assert from 'node:assert/strict';
import test from 'node:test';
import {
  defaultBomVisible,
  geometryDisplayId,
  tabsForSource,
  workerStageLabel
} from '../modules/viewer-workspace';

// 用途：单零件默认收起 BOM，真实装配体默认展开。
test('bom visibility follows assembly contract', () => {
  assert.equal(defaultBomVisible({ assembly_mode: 'single_part', default_visible: false }), false);
  assert.equal(defaultBomVisible({ assembly_mode: 'assembly', default_visible: true }), true);
});

// 用途：STEP 与 CATPart 在同一个 Viewer 中显示不同语义页签。
test('折叠导航始终提供装配、特征和几何三个入口', () => {
  assert.deepEqual(tabsForSource('STEP'), ['bom', 'recognized', 'geometry']);
  assert.deepEqual(tabsForSource('CATPART'), ['bom', 'recognized', 'geometry']);
});

// 用途：几何列表使用稳定、易读的编号，而不是向用户暴露长 UUID。
test('geometry display id is stable and one based', () => {
  assert.equal(geometryDisplayId('face', 0), 'F-001');
  assert.equal(geometryDisplayId('edge', 11), 'E-012');
  assert.equal(geometryDisplayId('vertex', 2), 'V-003');
});

// 用途：CATPart 阶段不得误导为正在用 FreeCAD 打开源文件。
test('catia stages use explicit worker labels', () => {
  assert.equal(workerStageLabel('running_caa'), 'CAA 原生解析');
  assert.equal(workerStageLabel('running_freecad'), 'STEP 几何解析');
  assert.notEqual(workerStageLabel('exporting_step'), 'STEP 几何解析');
});
