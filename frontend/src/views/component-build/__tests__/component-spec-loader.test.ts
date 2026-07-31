import assert from 'node:assert/strict'
import test from 'node:test'
import { loadComponentSpecWithFallback } from '../component-spec-loader'
import {
  applyComponentSpecFieldEdit,
  createComponentSpecEditorState,
  createComponentSpecSavePayload,
  importComponentSpecYaml
} from '../component-spec-editor-state'

type TestComponentSpecDocument = {
  build_id: string
  schema: { sections: never[] }
  data: { identity: { name: string } }
  yaml?: string | null
  source_filename?: string | null
  saved: boolean
  updated_at: string | null
}

const serverDocument: TestComponentSpecDocument = {
  build_id: 'build-1',
  schema: { sections: [] },
  data: { identity: { name: 'server' } },
  yaml: '# server\nidentity:\n  name: server\n',
  source_filename: 'server.yaml',
  saved: true,
  updated_at: '2026-07-31T00:00:00Z'
}

const localDocument: TestComponentSpecDocument = {
  build_id: 'build-1',
  schema: { sections: [] },
  data: { identity: { name: 'local' } },
  yaml: null,
  source_filename: null,
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

test('creates editor state from a persisted YAML document', () => {
  const state = createComponentSpecEditorState(serverDocument)

  assert.equal(state.systemYaml, serverDocument.yaml)
  assert.equal(state.working.yaml, serverDocument.yaml)
  assert.equal(state.working.sourceFilename, 'server.yaml')
  assert.equal(state.dirty, false)
})

test('uses generated YAML when loading a legacy data-only document', () => {
  const state = createComponentSpecEditorState(localDocument, {
    generatedYaml: 'identity:\n  name: local\n'
  })

  assert.equal(state.systemYaml, 'identity:\n  name: local\n')
  assert.equal(state.working.data.identity.name, 'local')
})

test('imports YAML only after successful parsing', () => {
  const initial = createComponentSpecEditorState(serverDocument)
  const imported = importComponentSpecYaml(
    initial,
    '# upload\nidentity:\n  name: uploaded\nextra: true\n',
    'upload-v1.3.yml'
  )

  assert.equal(imported.working.data.identity.name, 'uploaded')
  assert.equal(imported.working.data.extra, true)
  assert.equal(imported.working.sourceFilename, 'upload-v1.3.yml')
  assert.equal(imported.dirty, true)
  assert.equal(initial.working.data.identity.name, 'server')

  assert.throws(
    () => importComponentSpecYaml(imported, 'identity: [\n', 'broken.yaml'),
    /Flow sequence/
  )
  assert.equal(imported.working.data.identity.name, 'uploaded')
})

test('field edits update current YAML and produce the complete save payload', () => {
  const initial = createComponentSpecEditorState(serverDocument)
  const edited = applyComponentSpecFieldEdit(initial, ['identity', 'name'], 'edited')
  const payload = createComponentSpecSavePayload(edited)

  assert.match(edited.working.yaml, /name: edited/)
  assert.equal(edited.dirty, true)
  assert.deepEqual(payload.data, { identity: { name: 'edited' } })
  assert.equal(payload.yaml, edited.working.yaml)
  assert.equal(payload.source_filename, 'server.yaml')
})

test('a fused document becomes a fresh system baseline', () => {
  const fused = createComponentSpecEditorState({
    ...serverDocument,
    data: { identity: { name: 'fused' } },
    yaml: '# fused\nidentity:\n  name: fused\n',
    source_filename: null
  })

  assert.equal(fused.systemYaml, '# fused\nidentity:\n  name: fused\n')
  assert.equal(fused.working.data.identity.name, 'fused')
  assert.equal(fused.dirty, false)
})
