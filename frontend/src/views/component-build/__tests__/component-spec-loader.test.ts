import assert from 'node:assert/strict'
import test from 'node:test'
import { loadComponentSpecWithFallback } from '../component-spec-loader'

type TestComponentSpecDocument = {
  build_id: string
  schema: { sections: never[] }
  data: { identity: { name: string } }
  saved: boolean
  updated_at: string | null
}

const serverDocument: TestComponentSpecDocument = {
  build_id: 'build-1',
  schema: { sections: [] },
  data: { identity: { name: 'server' } },
  saved: true,
  updated_at: '2026-07-31T00:00:00Z'
}

const localDocument: TestComponentSpecDocument = {
  build_id: 'build-1',
  schema: { sections: [] },
  data: { identity: { name: 'local' } },
  saved: false,
  updated_at: null
}

test('uses the server ComponentSpec when the request succeeds', async () => {
  const result = await loadComponentSpecWithFallback(
    'build-1',
    async () => ({ data: serverDocument, error: null }),
    () => localDocument
  )

  assert.equal(result.document, serverDocument)
  assert.equal(result.offline, false)
})

test('uses the local ComponentSpec when the server returns no document', async () => {
  const result = await loadComponentSpecWithFallback(
    'build-1',
    async () => ({ data: null, error: new Error('unavailable') }),
    () => localDocument
  )

  assert.equal(result.document, localDocument)
  assert.equal(result.offline, true)
})

test('uses the local ComponentSpec when the request throws', async () => {
  const result = await loadComponentSpecWithFallback(
    'build-1',
    async () => {
      throw new Error('network error')
    },
    () => localDocument
  )

  assert.equal(result.document, localDocument)
  assert.equal(result.offline, true)
})
