
import { primitiveIcons, getPrimitive } from '@/data/primitives';
import type { EditRegion, ParamDocRow } from '@/types';

// 简单确定性哈希，用于布局微偏移
function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

const RELATION_BY_CAT: Record<string, string> = {
  '01 连接紧固件': '贯穿连接孔与相邻构件紧固连接',
  '02 轴系与支承': '支承于壳体轴承孔内，传递转矩',
  '03 传动件': '与轴键连接，啮合/挠性传递动力',
  '04 弹性元件': '预压缩安装于两构件之间提供回复力',
  '05 密封元件': '过盈装配于密封腔，防止介质泄漏',
  '06 支撑与结构': '作为安装基体，螺栓固定于基础面',
  '07 动力与执行': '固定于基座，输出机械动力',
};

export function buildParamDoc(primitiveIds: string[]): ParamDocRow[] {
  return primitiveIds.map((id, i) => {
    const p = getPrimitive(id);
    if (!p) return { refNo: String(i + 1), name: id, code: '-', keyParams: '-', material: '-', relation: '-' };
    return {
      refNo: String(i + 1),
      name: p.name,
      code: p.code,
      keyParams: p.params.map((x) => `${x.label} ${x.value}${x.unit && x.unit !== '-' ? x.unit : ''}`).join('；'),
      material: p.material,
      relation: RELATION_BY_CAT[p.category] ?? '按装配图位置连接',
    };
  });
}

interface Props {
  primitiveIds: string[];
  seedKey?: string;
  regions?: EditRegion[];
  activeRegionId?: string | null;
  changedRegionIds?: string[];
  title?: string;
}

/** 专利风格线条装配图（平面版三维视图） */
export default function PatentFigure({ primitiveIds, seedKey = '', regions = [], activeRegionId, changedRegionIds = [], title }: Props) {
  const h = hash(seedKey + primitiveIds.join(','));
  const n = primitiveIds.length;
  const cols = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(n + 1))));
  const rows = Math.max(1, Math.ceil(n / cols));

  // 装配体内部布局区域
  const bx = 120, by = 96, bw = 400, bh = 280;
  const cellW = bw / cols, cellH = bh / rows;

  const items = primitiveIds.map((id, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const jx = ((h >> (i % 16)) % 17) - 8;
    const jy = ((h >> ((i + 5) % 16)) % 13) - 6;
    const cx = bx + cellW * (col + 0.5) + jx;
    const cy = by + cellH * (row + 0.5) + jy;
    const size = Math.min(cellW, cellH) * 0.62;
    return { id, i, cx, cy, size };
  });

  // 引线标号：交替放在左/右侧
  const leaders = items.map((it, k) => {
    const left = k % 2 === 0;
    const lx = left ? 64 : 576;
    const ly = 70 + k * (340 / Math.max(1, items.length)) + 12;
    return { ...it, lx, ly, left };
  });

  return (
    <svg viewBox="0 0 640 460" className="w-full h-full text-slate-800" style={{ background: '#ffffff' }}>
      <defs>
        <pattern id="hatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="7" stroke="#cbd5e1" strokeWidth="1" />
        </pattern>
        <pattern id="hatch2" width="6" height="6" patternTransform="rotate(-45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="6" stroke="#cbd5e1" strokeWidth="1" />
        </pattern>
      </defs>

      {/* 图框 */}
      <rect x="16" y="16" width="608" height="428" fill="none" stroke="#94a3b8" strokeWidth="1" />
      <rect x="22" y="22" width="596" height="416" fill="none" stroke="#cbd5e1" strokeWidth="0.6" />

      {/* 基座剖面（壳体） */}
      <rect x={bx} y={by + bh} width={bw} height="26" fill="url(#hatch)" stroke="#64748b" strokeWidth="1.2" />
      <rect x={bx - 22} y={by + bh + 26} width={bw + 44} height="16" fill="url(#hatch2)" stroke="#64748b" strokeWidth="1.2" />
      <rect x={bx} y={by} width={bw} height={bh} fill="rgba(100,116,139,0.08)" stroke="#64748b" strokeWidth="1.2" strokeDasharray="8 4" />
      {/* 中心线 */}
      <line x1={bx - 16} y1={by + bh / 2} x2={bx + bw + 16} y2={by + bh / 2} stroke="#7c3aed" strokeWidth="0.7" strokeDasharray="14 4 2 4" opacity="0.55" />

      {/* 图元实例 */}
      {items.map((it) => (
        <g key={it.i} transform={`translate(${it.cx - it.size / 2},${it.cy - it.size / 2}) scale(${it.size / 64})`} opacity="0.95" color="#334155">
          {primitiveIcons[it.id] ?? <circle cx="32" cy="32" r="16" fill="none" stroke="currentColor" />}
        </g>
      ))}

      {/* 引线与附图标记 */}
      {leaders.map((l) => (
        <g key={`L${l.i}`}>
          <polyline
            points={`${l.lx},${l.ly} ${l.left ? l.lx + 22 : l.lx - 22},${l.ly} ${l.cx},${l.cy}`}
            fill="none" stroke="#94a3b8" strokeWidth="0.9"
          />
          <circle cx={l.cx} cy={l.cy} r="1.8" fill="#94a3b8" />
          <circle cx={l.lx} cy={l.ly} r="11" fill="#ffffff" stroke="#94a3b8" strokeWidth="1" />
          <text x={l.lx} y={l.ly + 4} textAnchor="middle" fontSize="11" fill="#334155">{l.i + 1}</text>
        </g>
      ))}

      {/* 框选/修改区域 */}
      {regions.map((r) => {
        const changed = changedRegionIds.includes(r.id);
        const active = activeRegionId === r.id;
        const color = changed ? '#34d399' : active ? '#f59e0b' : '#fbbf24';
        return (
          <g key={r.id}>
            <rect
              x={(r.x / 100) * 640} y={(r.y / 100) * 460}
              width={(r.w / 100) * 640} height={(r.h / 100) * 460}
              fill={changed ? 'rgba(52,211,153,0.10)' : 'rgba(251,191,36,0.08)'}
              stroke={color} strokeWidth={active ? 2 : 1.4} strokeDasharray="6 4" rx="3"
            />
            <text x={(r.x / 100) * 640 + 5} y={(r.y / 100) * 460 + 14} fontSize="11" fill={color}>
              {changed ? '已修改' : '待修改区域'}
            </text>
          </g>
        );
      })}

      {/* 图题 */}
      <text x="320" y="436" textAnchor="middle" fontSize="13" fill="#64748b">
        {title ?? `图1  机械结构装配示意图（平面版三维视图，共${n}个构件）`}
      </text>
      <text x="608" y="40" textAnchor="end" fontSize="10" fill="#94a3b8">SCALE 1:1 · 符合GB/T 专利附图规范</text>
    </svg>
  );
}

/** 导出 SVG 为 PNG */
export function exportFigureAsPng(svgEl: SVGSVGElement, filename: string) {
  const xml = new XMLSerializer().serializeToString(svgEl);
  const svg64 = btoa(unescape(encodeURIComponent(xml)));
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 1280; canvas.height = 920;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const a = document.createElement('a');
    a.download = filename;
    a.href = canvas.toDataURL('image/png');
    a.click();
  };
  img.src = 'data:image/svg+xml;base64,' + svg64;
}
