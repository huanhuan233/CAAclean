import assert from 'node:assert/strict'
import test from 'node:test'
import { buildCatalogNavigation } from '../catalog-navigation'
import { isSupportedPartSourceFile } from '../source-file'

/**
 * 用途：构造最小双库树，验证两个系统库保持同级且统计互不污染。
 */
function makeLibrary(id: string, label: string, category: string, buildCount: number) {
  return {
    id,
    label,
    node_type: 'library',
    library_code: id,
    children: [{
      id: `${id}-family`,
      label: `${label}分类`,
      label_en: 'Family',
      node_type: 'family',
      category_code: category,
      children: [{
        id: `${id}-type`,
        label: '零件类型',
        node_type: 'type',
        category_code: category,
        part_type_code: `${category}-type`,
        children: Array.from({ length: buildCount }, (_, index) => ({
          id: `${id}-build-${index}`,
          label: '版本',
          node_type: 'build',
          children: []
        }))
      }]
    }]
  }
}

test('机械库与航空航天库是两个同级系统根', () => {
  const items = buildCatalogNavigation([
    makeLibrary('MECHANICAL_COMPONENT_LIBRARY', '机械工程图元库', 'mechanical', 2),
    makeLibrary('AEROSPACE_PART_LIBRARY', '航空航天零件库', 'aerospace', 1)
  ])
  const roots = items.filter(item => item.nodeType === 'library')
  assert.deepEqual(roots.map(item => item.parentId), [undefined, undefined])
  assert.deepEqual(roots.map(item => item.count), [2, 1])
  assert.deepEqual(roots.map(item => item.label), ['机械工程图元库', '航空航天零件库'])
})

test('上传提示接受 STEP、STP、CATPart、CATProduct 和依赖 ZIP，且大小写不敏感', () => {
  assert.equal(isSupportedPartSourceFile('零件 (1).STEP'), true)
  assert.equal(isSupportedPartSourceFile('零件.stp'), true)
  assert.equal(isSupportedPartSourceFile('框体.CATPart'), true)
  assert.equal(isSupportedPartSourceFile('装配.CATProduct'), true)
  assert.equal(isSupportedPartSourceFile('装配依赖.ZIP'), true)
  assert.equal(isSupportedPartSourceFile('错误.cart'), false)
})
