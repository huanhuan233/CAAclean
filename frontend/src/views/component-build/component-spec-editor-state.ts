import { stringify } from 'yaml'
import {
  createYamlWorkingDocument,
  updateYamlWorkingDocument,
  type TemplateSectionDefinition,
  type YamlFieldPath,
  type YamlWorkingDocument
} from './yaml-working-document'

export interface ComponentSpecDocumentLike {
  schema: {
    sections: TemplateSectionDefinition[]
  }
  data: Record<string, unknown>
  yaml?: string | null
  source_filename?: string | null
}

export interface ComponentSpecEditorState {
  systemYaml: string
  working: YamlWorkingDocument
  dirty: boolean
  source: 'system' | 'upload' | 'manual'
}

export interface CreateComponentSpecEditorStateOptions {
  generatedYaml?: string
}

export interface ComponentSpecSavePayload {
  data: Record<string, unknown>
  yaml: string
  source_filename: string | null
}

export function createComponentSpecEditorState(
  document: ComponentSpecDocumentLike,
  options: CreateComponentSpecEditorStateOptions = {}
): ComponentSpecEditorState {
  const yamlText = document.yaml || options.generatedYaml || stringify(document.data)
  const working = createYamlWorkingDocument(yamlText, {
    sourceFilename: document.source_filename ?? null,
    templateSections: document.schema.sections
  })
  return {
    systemYaml: yamlText,
    working,
    dirty: false,
    source: 'system'
  }
}

export function importComponentSpecYaml(
  state: ComponentSpecEditorState,
  yamlText: string,
  sourceFilename: string
): ComponentSpecEditorState {
  const working = createYamlWorkingDocument(yamlText, {
    sourceFilename,
    templateSections: state.working.templateSections
  })
  return {
    ...state,
    working,
    dirty: true,
    source: 'upload'
  }
}

export function applyComponentSpecFieldEdit(
  state: ComponentSpecEditorState,
  path: YamlFieldPath,
  value: unknown
): ComponentSpecEditorState {
  return {
    ...state,
    working: updateYamlWorkingDocument(state.working, path, value),
    dirty: true,
    source: state.source === 'system' ? 'manual' : state.source
  }
}

export function createComponentSpecSavePayload(
  state: ComponentSpecEditorState
): ComponentSpecSavePayload {
  return {
    data: state.working.data,
    yaml: state.working.yaml,
    source_filename: state.working.sourceFilename
  }
}
