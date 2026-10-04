export function parseGeometryPoint(text: string): number[] | null {
  const values = text.split(/[，,\s]+/u).filter(Boolean).map(Number);
  return values.length === 3 && values.every(Number.isFinite) ? values : null;
}

export function anglePointParameters(
  orientation: 'directed' | 'unoriented',
  fields: { text: string; seed: number[] | null | undefined; edited: boolean }[]
): Record<string, unknown> | null {
  const parameters: Record<string, unknown> = { orientation };
  for (const [index, field] of fields.entries()) {
    if (!field.text.trim()) continue;
    const point = field.edited ? parseGeometryPoint(field.text) : field.seed;
    if (!point) return null;
    const suffix = index === 0 ? 'a' : 'b';
    parameters[field.edited ? `point_${suffix}` : `seed_point_${suffix}`] = [...point];
  }
  return parameters;
}
