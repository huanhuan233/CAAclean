import {
  isMap,
  parseDocument,
  type Document,
  type ParsedNode
} from 'yaml'

export type YamlFieldPath = Array<string | number>
export type YamlFieldKind =
  | 'object'
  | 'object_array'
  | 'scalar_array'
  | 'text'
  | 'number'
  | 'boolean'
  | 'null'
  | 'generic'

export interface YamlFieldDefinition {
  key: string
  path: string
  label: string
  required: boolean
  read_only: boolean
  source: string
  comment: string
  kind: YamlFieldKind
  repeatable?: boolean
  value_type?: 'text' | 'number' | 'boolean'
  fixed_value?: unknown
  children?: YamlFieldDefinition[]
  item?: {
    kind: 'object'
    children: YamlFieldDefinition[]
  }
}

export interface TemplateFieldDefinition extends Omit<YamlFieldDefinition, 'kind' | 'children' | 'item'> {
  kind: string
  children?: TemplateFieldDefinition[]
  item?: {
    kind: 'object'
    children: TemplateFieldDefinition[]
  }
}

export interface TemplateSectionDefinition {
  key: string
  label: string
  description: string
  fields: TemplateFieldDefinition[]
}

export interface YamlWorkingDocument {
  ast: Document.Parsed<ParsedNode>
  data: Record<string, unknown>
  yaml: string
  fields: YamlFieldDefinition[]
  sourceFilename: string | null
  templateSections: TemplateSectionDefinition[]
}

export interface CreateYamlWorkingDocumentOptions {
  sourceFilename?: string | null
  templateSections?: TemplateSectionDefinition[]
}

export class YamlWorkingDocumentError extends Error {
  line: number | null
  column: number | null

  constructor(message: string, line: number | null = null, column: number | null = null) {
    super(message)
    this.name = 'YamlWorkingDocumentError'
    this.line = line
    this.column = column
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function formatPath(segments: Array<string | '[]'>): string {
  return segments.reduce(
    (result, segment) => segment === '[]' ? `${result}[]` : result ? `${result}.${segment}` : segment,
    ''
  )
}

function collectTemplateFields(
  sections: TemplateSectionDefinition[]
): Map<string, TemplateFieldDefinition> {
  const fieldsByPath = new Map<string, TemplateFieldDefinition>()

  function visit(field: TemplateFieldDefinition) {
    fieldsByPath.set(field.path, field)
    field.children?.forEach(visit)
    field.item?.children.forEach(visit)
  }

  sections.forEach(section => section.fields.forEach(visit))
  return fieldsByPath
}

function scalarKind(value: unknown): YamlFieldKind {
  if (value === null) return 'null'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  return 'text'
}

function scalarValueType(value: unknown): 'text' | 'number' | 'boolean' {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  return 'text'
}

function templateKind(kind: string): YamlFieldKind {
  const supported: YamlFieldKind[] = [
    'object',
    'object_array',
    'scalar_array',
    'text',
    'number',
    'boolean',
    'null',
    'generic'
  ]
  return supported.includes(kind as YamlFieldKind) ? kind as YamlFieldKind : 'generic'
}

function materializeTemplateField(field: TemplateFieldDefinition): YamlFieldDefinition {
  return {
    ...field,
    kind: templateKind(field.kind),
    children: field.children?.map(materializeTemplateField),
    item: field.item
      ? {
          kind: 'object',
          children: field.item.children.map(materializeTemplateField)
        }
      : undefined
  }
}

function orderedObjectArrayKeys(items: Record<string, unknown>[]): string[] {
  const keys = new Set<string>()
  items.forEach(item => Object.keys(item).forEach(key => keys.add(key)))
  return [...keys]
}

function mergeRepresentativeValues(values: unknown[]): unknown {
  const present = values.filter(value => value !== undefined)
  if (present.length === 0) return undefined
  if (present.every(isRecord)) {
    const records = present as Record<string, unknown>[]
    return Object.fromEntries(
      orderedObjectArrayKeys(records).map(key => [
        key,
        mergeRepresentativeValues(records.map(record => record[key]))
      ])
    )
  }
  if (present.every(Array.isArray)) {
    return present.flatMap(value => value as unknown[])
  }
  return present.find(value => value !== null) ?? null
}

function inferField(
  key: string,
  value: unknown,
  pathSegments: Array<string | '[]'>,
  metadataByPath: Map<string, TemplateFieldDefinition>
): YamlFieldDefinition {
  const path = formatPath(pathSegments)
  const metadata = metadataByPath.get(path)
  const common = {
    key,
    path,
    label: metadata?.label || key,
    required: metadata?.required || false,
    read_only: metadata?.read_only || false,
    source: metadata?.source || '',
    comment: metadata?.comment || '',
    fixed_value: metadata?.fixed_value
  }

  if (isRecord(value)) {
    return {
      ...common,
      kind: 'object',
      children: Object.entries(value).map(([childKey, childValue]) =>
        inferField(childKey, childValue, [...pathSegments, childKey], metadataByPath)
      )
    }
  }

  if (Array.isArray(value)) {
    const objectItems = value.filter(isRecord)
    if (value.length > 0 && objectItems.length === value.length) {
      const children = orderedObjectArrayKeys(objectItems).map(childKey => {
        const representative = mergeRepresentativeValues(
          objectItems.map(item => item[childKey])
        )
        return inferField(childKey, representative, [...pathSegments, '[]', childKey], metadataByPath)
      })
      return {
        ...common,
        kind: 'object_array',
        repeatable: true,
        item: { kind: 'object', children }
      }
    }

    const scalarTypes = new Set(
      value
        .filter(item => item !== null)
        .map(item => typeof item)
    )
    const allScalars = value.every(item => item === null || ['string', 'number', 'boolean'].includes(typeof item))
    if (allScalars && scalarTypes.size <= 1 && (value.length > 0 || metadata?.kind === 'scalar_array')) {
      const representative = value.find(item => item !== null)
      return {
        ...common,
        kind: 'scalar_array',
        value_type: metadata?.value_type || scalarValueType(representative)
      }
    }

    if (value.length === 0 && metadata?.kind === 'object_array') {
      return {
        ...common,
        kind: 'object_array',
        repeatable: true,
        item: {
          kind: 'object',
          children: (metadata.item?.children || []).map(materializeTemplateField)
        }
      }
    }

    return { ...common, kind: 'generic' }
  }

  return {
    ...common,
    kind: scalarKind(value),
    value_type: metadata?.value_type || scalarValueType(value)
  }
}

function snapshot(
  ast: Document.Parsed<ParsedNode>,
  options: Required<CreateYamlWorkingDocumentOptions>
): YamlWorkingDocument {
  const data = ast.toJS({ mapAsMap: false }) as unknown
  if (!isRecord(data)) {
    throw new YamlWorkingDocumentError('ComponentSpec YAML root must be a mapping')
  }
  const metadataByPath = collectTemplateFields(options.templateSections)
  return {
    ast,
    data,
    yaml: ast.toString({ lineWidth: 0 }),
    fields: Object.entries(data).map(([key, value]) =>
      inferField(key, value, [key], metadataByPath)
    ),
    sourceFilename: options.sourceFilename,
    templateSections: options.templateSections
  }
}

export function createYamlWorkingDocument(
  yamlText: string,
  options: CreateYamlWorkingDocumentOptions = {}
): YamlWorkingDocument {
  const ast = parseDocument(yamlText, {
    keepSourceTokens: true,
    prettyErrors: true,
    strict: true
  })
  const firstError = ast.errors[0]
  if (firstError) {
    const start = firstError.linePos?.[0]
    throw new YamlWorkingDocumentError(
      firstError.message,
      start?.line ?? null,
      start?.col ?? null
    )
  }
  if (!isMap(ast.contents)) {
    throw new YamlWorkingDocumentError('ComponentSpec YAML root must be a mapping')
  }
  return snapshot(ast, {
    sourceFilename: options.sourceFilename ?? null,
    templateSections: options.templateSections ?? []
  })
}

export function updateYamlWorkingDocument(
  working: YamlWorkingDocument,
  path: YamlFieldPath,
  value: unknown
): YamlWorkingDocument {
  if (path.length === 0) {
    if (!isRecord(value)) {
      throw new YamlWorkingDocumentError('ComponentSpec YAML root must be a mapping')
    }
    working.ast.contents = working.ast.createNode(value) as unknown as ParsedNode
  } else {
    working.ast.setIn(path, value)
  }
  return snapshot(working.ast, {
    sourceFilename: working.sourceFilename,
    templateSections: working.templateSections
  })
}
