import assert from 'node:assert/strict'
import test from 'node:test'
import {
  appendFieldPath,
  parseScalarArrayInput,
  updateValueAtPath
} from '../component-spec-field-events'

test('appends object keys and array indices to an editor path', () => {
  const path = appendFieldPath(['parameters'], 1, 'default')

  assert.deepEqual(path, ['parameters', 1, 'default'])
})

test('updates a nested object value without mutating the source', () => {
  const source = { identity: { name: 'Old', type: 'flange' } }

  const updated = updateValueAtPath(source, ['identity', 'name'], 'New')

  assert.deepEqual(updated, { identity: { name: 'New', type: 'flange' } })
  assert.deepEqual(source, { identity: { name: 'Old', type: 'flange' } })
  assert.notEqual(updated.identity, source.identity)
})

test('updates an object-array item without mutating sibling items', () => {
  const source = {
    parameters: [
      { name: 'DN', default: 80 },
      { name: 'PN', default: 16 }
    ]
  }

  const updated = updateValueAtPath(source, ['parameters', 1, 'default'], 25)

  assert.equal(updated.parameters[1].default, 25)
  assert.equal(source.parameters[1].default, 16)
  assert.equal(updated.parameters[0], source.parameters[0])
})

test('replaces scalar arrays and the root document', () => {
  const source = { tags: ['steel'] }

  assert.deepEqual(updateValueAtPath(source, ['tags'], ['steel', 'forged']), {
    tags: ['steel', 'forged']
  })
  assert.deepEqual(updateValueAtPath(source, [], { replaced: true }), { replaced: true })
})

test('parses scalar arrays without changing boolean and number types', () => {
  assert.deepEqual(parseScalarArrayInput('true, false', 'boolean'), [true, false])
  assert.deepEqual(parseScalarArrayInput('1, 2.5', 'number'), [1, 2.5])
  assert.deepEqual(parseScalarArrayInput('steel, forged', 'text'), ['steel', 'forged'])
  assert.throws(() => parseScalarArrayInput('true, maybe', 'boolean'), /boolean/)
  assert.throws(() => parseScalarArrayInput('1, nope', 'number'), /number/)
})
