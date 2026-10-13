/** Presentation only; source dimensions and classification remain unchanged. */
export function tubeGeometryTitle(status: unknown): string {
  return status === 'confirmed_bent_hollow_tube' ? '弯管（空心）'
    : status === 'confirmed_straight_hollow_tube' ? '直管（空心）' : '几何候选';
}

export function tubeObjectStatus(status: unknown): string {
  const labels: Record<string, string> = {
    path_candidate_hollow_unverified: '中心线路径候选，空心状态未核验',
    confirmed_straight_hollow_tube: '已核验空心直管',
    confirmed_bent_hollow_tube: '已核验空心弯管',
    unsupported_geometry: '当前几何不支持', unsupported: '当前几何不支持',
    analysis_budget_exceeded: '超出本次计算范围', candidate: '待复核候选'
  };
  return labels[String(status)] || '状态待核实';
}

export function tubeSectionSamples(section: Record<string, unknown>, order?: number): Array<Record<string, unknown>> {
  const samples = Array.isArray(section.samples) ? section.samples as Array<Record<string, unknown>> : [];
  return samples.filter(sample => sample && typeof sample === 'object' &&
    (order === undefined || sample.segment_order === order));
}

export function tubeSectionRows(section: Record<string, unknown>): Array<[string, string]> {
  const rows: Array<[string, string]> = [];
  for (const [key, label] of [['outer_diameter_mm', '截面外径'], ['inner_diameter_mm', '截面内径'],
    ['wall_thickness_mm', '几何壁厚'], ['wall_thickness_min_mm', '已核验壁厚最小值'],
    ['wall_thickness_max_mm', '已核验壁厚最大值'], ['tolerance_mm', '核验容差']]) {
    const value = section[key];
    if (typeof value === 'number' && Number.isFinite(value)) rows.push([label, `${value.toFixed(3)} mm`]);
  }
  if (section.uniformity_status === 'verified_analytic_constant_section') {
    rows.push(['截面一致性', '解析内外壁与截面核验一致（当前 CAD 模型）']);
  }
  if (section.method === 'paired_cylindrical_toroidal_walls_and_normal_sections') {
    rows.push(['截面方法', '解析壁面配对、法向截面与材料侧核验']);
  } else if (section.method) rows.push(['截面方法', String(section.method)]);
  const samples = tubeSectionSamples(section);
  if (samples.length) rows.push(['核验截面', `${samples.filter(s => s.status === 'verified').length} / ${samples.length} 处通过`]);
  return rows;
}
