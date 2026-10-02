import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

// 执行页面中的真实属性处理函数，避免测试复制一份实现后产生假通过。
function pageFunctions(names: string[], bindings: Record<string, unknown> = {}, path = '../index.vue') {
  const text = readFileSync(new URL(path, import.meta.url), 'utf8');
  const script = path.endsWith('.vue') ? text.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1] : text;
  const source = ts.createSourceFile('page.ts', script, ts.ScriptTarget.Latest, true);
  const declarations = source.statements.filter(statement => {
    if (ts.isFunctionDeclaration(statement)) return names.includes(statement.name?.text || '');
    return ts.isVariableStatement(statement) && statement.declarationList.declarations.some(
      declaration => ts.isIdentifier(declaration.name) && names.includes(declaration.name.text)
    );
  });
  const code = declarations.map(statement => statement.getText(source).replace(/^export /, '')).join('\n');
  const js = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return vm.runInNewContext(`${js}\n({${names.join(',')}})`, bindings);
}

test('数据库铺层分组不被 CATIA 旧属性页声明隐藏，零度角仍显示', () => {
  const { apiTabsToCatiaTabs } = pageFunctions([
    'apiTabsToCatiaTabs', 'normalizeCatiaToken', 'normalizeCatiaTabId', 'catiaDisplayLabel',
    'catiaFieldLabel', 'apiPropertyValueText', 'isHiddenCatiaApiField', 'mergeCatiaGroups',
    'catiaTabLabelMap', 'catiaGroupLabelMap', 'catiaFieldLabelMap', 'hiddenCatiaPropertyKeys'
  ]);
  const result = apiTabsToCatiaTabs([
    { tab_id: 'mechanical', groups: [{ group_id: 'native', fields: [
      { key: '__catia_property_tab__mechanical', display_name: '机械属性页声明', raw_value: 'declared' }
    ] }] },
    { tab_id: 'composites', groups: [{ group_id: 'composites', fields: [
      { key: 'composite_orientation', display_name: '铺层角度', raw_value: 0, raw_unit: 'rad' },
      { key: 'composite_material_name', display_name: '材料', raw_value: 'S1454_G803' }
    ] }] }
  ]);
  const composite = result.find((tab: { name: string }) => tab.name === 'composites');
  assert.ok(composite, '数据库返回的铺层分组必须可见');
  assert.equal(composite.groups[0].rows[0].value, '0');
  assert.equal(composite.groups[0].rows[0].unit, 'rad');
  assert.equal(composite.groups[0].rows[1].value, 'S1454_G803');
  assert.ok(result.every((tab: { groups: { rows: { key: string }[] }[] }) =>
    tab.groups.every(group => group.rows.every(row => !row.key.startsWith('__catia_property_tab__')))),
  '属性页声明是内部元数据，不应混入业务字段');
});

test('接口返回错误时不能伪装成数据库没有属性', async () => {
  const { loadCaaNewNodeProperties } = pageFunctions(['loadCaaNewNodeProperties'], {
    fetchComponentBuildNativeNodeProperties: async () => ({ data: null, error: new Error('database offline') })
  }, '../modules/caa-new-loader.ts');
  await assert.rejects(() => loadCaaNewNodeProperties('build-1', 'occurrence_800'));
});

test('数据库属性请求失败不能打开由本地数据拼出的属性弹窗', async () => {
  const dialog = { value: false };
  const messages: string[] = [];
  const { showNativeTreeNodeProperties } = pageFunctions(['showNativeTreeNodeProperties'], {
    selectNativeTreeNode: () => {}, catiaPropertyNode: { value: null }, catiaPropertyApiTabs: { value: null },
    contract: { value: { part_id: 'build-1' } }, assetRequestController: { signal: undefined },
    loadCaaNewNodeProperties: async () => { throw new Error('database unavailable'); },
    buildMechanicalRows: () => ({ characteristic: ['stale'], center: [], inertia: [] }),
    catiaPropertyTab: { value: '' }, catiaPropertyDialogOpen: dialog,
    window: { $message: { info: (s: string) => messages.push(s), error: (s: string) => messages.push(s) } }
  });
  await showNativeTreeNodeProperties({ id: 'occurrence_800', kind: 'part', raw: {} });
  assert.equal(dialog.value, false, '数据库失败时不得显示本地兜底属性');
  assert.ok(messages.length > 0, '应明确显示数据库属性读取失败');
});
