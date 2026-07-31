import assert from 'node:assert/strict'
import test from 'node:test'
import {
  YamlWorkingDocumentError,
  createYamlWorkingDocument,
  updateYamlWorkingDocument
} from '../yaml-working-document'

test('parses a mapping-root YAML document and preserves its presentation', () => {
  const source = '# component comment\nidentity:\n  name: \"Quoted flange\"\nenabled: true\n'

  const working = createYamlWorkingDocument(source, { sourceFilename: 'flange.yaml' })

  assert.deepEqual(working.data, {
    identity: { name: 'Quoted flange' },
    enabled: true
  })
  assert.equal(working.sourceFilename, 'flange.yaml')
  assert.match(working.yaml, /# component comment/)
  assert.match(working.yaml, /name: "Quoted flange"/)
})

test('reports line and column for malformed YAML', () => {
  assert.throws(
    () => createYamlWorkingDocument('identity:\n  name: [\n'),
    (error: unknown) => {
      assert.ok(error instanceof YamlWorkingDocumentError)
      assert.equal(error.line, 3)
      assert.equal(error.column, 1)
      return true
    }
  )
})

test('rejects sequence and scalar roots', () => {
  assert.throws(() => createYamlWorkingDocument('- one\n- two\n'), /root must be a mapping/)
  assert.throws(() => createYamlWorkingDocument('plain scalar\n'), /root must be a mapping/)
})

test('infers editors for objects, arrays, scalars, nulls, and mixed arrays', () => {
  const working = createYamlWorkingDocument(`
identity:
  name: Flange
count: 4
enabled: false
empty_value: null
tags: [steel, forged]
dimensions:
  - name: DN
    value: 80
mixed: [one, { value: 2 }]
`)
  const byKey = Object.fromEntries(working.fields.map(field => [field.key, field]))

  assert.equal(byKey.identity.kind, 'object')
  assert.equal(byKey.identity.children?.find(field => field.key === 'name')?.kind, 'text')
  assert.equal(byKey.count.kind, 'number')
  assert.equal(byKey.enabled.kind, 'boolean')
  assert.equal(byKey.empty_value.kind, 'null')
  assert.equal(byKey.tags.kind, 'scalar_array')
  assert.equal(byKey.dimensions.kind, 'object_array')
  assert.deepEqual(byKey.dimensions.item?.children.map(field => field.key), ['name', 'value'])
  assert.equal(byKey.mixed.kind, 'generic')
})

test('merges known template metadata by exact field path', () => {
  const working = createYamlWorkingDocument(
    'identity:\n  name: Uploaded flange\n  vendor_field: kept\n',
    {
      templateSections: [
        {
          key: 'identity',
          label: '身份',
          description: '身份信息',
          fields: [
            {
              key: 'identity',
              path: 'identity',
              label: '图元身份',
              required: false,
              read_only: false,
              source: '',
              comment: '',
              kind: 'object',
              children: [
                {
                  key: 'name',
                  path: 'identity.name',
                  label: '当前对象名称',
                  required: true,
                  read_only: false,
                  source: '人工',
                  comment: '必填名称',
                  kind: 'text'
                }
              ]
            }
          ]
        }
      ]
    }
  )
  const identity = working.fields.find(field => field.key === 'identity')
  const name = identity?.children?.find(field => field.key === 'name')
  const unknown = identity?.children?.find(field => field.key === 'vendor_field')

  assert.equal(identity?.label, '图元身份')
  assert.equal(name?.label, '当前对象名称')
  assert.equal(name?.required, true)
  assert.equal(name?.source, '人工')
  assert.equal(unknown?.label, 'vendor_field')
})

test('updates a scalar by path while preserving comments, order, and unrelated quoting', () => {
  const working = createYamlWorkingDocument(
    '# keep top\nidentity:\n  name: Old\nuntouched: \'keep quotes\' # keep eol\nlast: 3\n'
  )

  const updated = updateYamlWorkingDocument(working, ['identity', 'name'], 'New flange')

  assert.equal(updated.data.identity.name, 'New flange')
  assert.match(updated.yaml, /# keep top/)
  assert.match(updated.yaml, /untouched: 'keep quotes' # keep eol/)
  assert.ok(updated.yaml.indexOf('identity:') < updated.yaml.indexOf('untouched:'))
  assert.ok(updated.yaml.indexOf('untouched:') < updated.yaml.indexOf('last:'))
})

test('replaces object and array nodes and exports matching data', () => {
  const working = createYamlWorkingDocument(
    '# outside\nsettings:\n  mode: old\nitems:\n  - name: first\ntail: kept\n'
  )
  const withObject = updateYamlWorkingDocument(working, ['settings'], { mode: 'new', enabled: true })
  const withArray = updateYamlWorkingDocument(withObject, ['items'], [{ name: 'second' }, { name: 'third' }])

  assert.deepEqual(withArray.data.settings, { mode: 'new', enabled: true })
  assert.deepEqual(withArray.data.items, [{ name: 'second' }, { name: 'third' }])
  assert.match(withArray.yaml, /# outside/)
  assert.match(withArray.yaml, /tail: kept/)
})
