/** Display names for geometry classifications; persisted API values remain unchanged. */
const GEOMETRY_LABELS: Record<string, string> = {
  plane: '平面',
  cylinder: '圆柱面',
  cone: '圆锥面',
  sphere: '球面',
  torus: '圆环面',
  toroid: '圆环面',
  bspline_surface: 'B 样条曲面',
  line: '直线',
  circle: '圆',
  ellipse: '椭圆',
  hyperbola: '双曲线',
  parabola: '抛物线',
  bezier_curve: '贝塞尔曲线',
  bspline_curve: 'B 样条曲线',
  offset_curve: '偏移曲线',
  other_curve: '其他曲线'
};

export function topologyGeometryLabel(value: string): string {
  return GEOMETRY_LABELS[value.trim().toLowerCase()] || value;
}
