export type ComponentSpecFieldPath = Array<string | number>

export function appendFieldPath(
  path: ComponentSpecFieldPath,
  ...segments: Array<string | number>
): ComponentSpecFieldPath {
  return [...path, ...segments]
}

export function updateValueAtPath<T>(
  source: T,
  path: ComponentSpecFieldPath,
  value: unknown
): T {
  if (path.length === 0) return value as T

  const [head, ...tail] = path
  if (typeof head === 'number') {
    const array = Array.isArray(source) ? [...source] : []
    array[head] = updateValueAtPath(array[head], tail, value)
    return array as T
  }

  const record = source !== null && typeof source === 'object' && !Array.isArray(source)
    ? { ...(source as Record<string, unknown>) }
    : {}
  record[head] = updateValueAtPath(record[head], tail, value)
  return record as T
}
