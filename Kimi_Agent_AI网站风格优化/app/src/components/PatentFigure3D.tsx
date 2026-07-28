import type { EditRegion } from '@/types';

// ============ 三维（轴测）专利结构示意图 ============
// 白底黑墨线条，仿机械制图轴测图风格

const INK = '#1f2937';
const INK_SOFT = '#475569';
const DASH = '#94a3b8';

interface Leader { tx: number; ty: number; lx: number; ly: number }
interface Part { key: string; draw: React.ReactNode; leader: Leader }

const st = { stroke: INK, fill: 'none', strokeWidth: 1.4, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

// ---- 基础轴测件 ----
/** 水平圆柱段（左端椭圆 + 筒身） */
function HCylinder({ x, y, rx, ry, len }: { x: number; y: number; rx: number; ry: number; len: number }) {
  return (
    <g {...st}>
      <path d={`M${x} ${y - ry} h${len} a${rx} ${ry} 0 0 1 0 ${ry * 2} h${-len} a${rx} ${ry} 0 0 1 0 ${-ry * 2}`} />
      <ellipse cx={x + len} cy={y} rx={rx} ry={ry} />
      <ellipse cx={x + len} cy={y} rx={rx * 0.45} ry={ry * 0.45} />
    </g>
  );
}

/** 轴测长方体 */
function IsoBox({ x, y, w, h, d }: { x: number; y: number; w: number; h: number; d: number }) {
  const dx = d * 0.7, dy = -d * 0.45;
  return (
    <g {...st}>
      <rect x={x} y={y} width={w} height={h} />
      <path d={`M${x} ${y} l${dx} ${dy} h${w} l${-dx} ${-dy}`} />
      <path d={`M${x + w} ${y} l${dx} ${dy} v${h} l${-dx} ${-dy}`} />
      <path d={`M${x + w + dx} ${y + dy} v${h}`} />
    </g>
  );
}

/** 平板底座（轴测） */
function Slab({ x, y, w, d, t }: { x: number; y: number; w: number; d: number; t: number }) {
  const dx = d * 0.7, dy = -d * 0.45;
  return (
    <g {...st}>
      <path d={`M${x} ${y} h${w} l${dx} ${dy} h${-w} z`} />
      <path d={`M${x} ${y} v${t} h${w} v${-t}`} />
      <path d={`M${x + w} ${y} l${dx} ${dy} v${t} l${-dx} ${-dy}`} />
      <path d={`M${x} ${y + t} h${w}`} />
    </g>
  );
}

/** 顶部压力表 */
function Gauge({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  return (
    <g {...st}>
      <circle cx={cx} cy={cy} r={r} />
      <circle cx={cx} cy={cy} r={r * 0.72} />
      <path d={`M${cx} ${cy} l${r * 0.45} ${-r * 0.4}`} />
      <path d={`M${cx} ${cy + r} v8 h-6`} strokeWidth={1.2} />
    </g>
  );
}

/** 顶部立式阀 */
function TopValve({ x, y }: { x: number; y: number }) {
  return (
    <g {...st}>
      <rect x={x - 7} y={y - 26} width={14} height={26} rx={2} />
      <path d={`M${x - 12} ${y - 30} h24 M${x} ${y - 30} v-8 M${x - 6} ${y - 38} h12`} />
      <path d={`M${x} ${y} v10`} />
    </g>
  );
}

/** 螺旋弹簧 */
function Spring({ x, y, h }: { x: number; y: number; h: number }) {
  const n = 5, seg = h / n;
  let d = `M${x} ${y}`;
  for (let i = 0; i < n; i++) d += ` q10 ${seg / 2} 0 ${seg}`;
  return (
    <g {...st}>
      <path d={d} />
      <path d={`M${x - 9} ${y} h18 M${x - 9} ${y + h} h18`} />
    </g>
  );
}

/** 电机（轴测箱体 + 前端盖 + 散热筋） */
function Motor({ x, y }: { x: number; y: number }) {
  return (
    <g {...st}>
      <IsoBox x={x} y={y} w={86} h={58} d={22} />
      <ellipse cx={x} cy={y + 29} rx={12} ry={29} />
      <ellipse cx={x} cy={y + 29} rx={5} ry={12} />
      <path d={`M${x + 18} ${y - 6} v-8 h50 v8`} strokeWidth={1.1} />
      {[26, 40, 54, 68].map((k) => (
        <path key={k} d={`M${x + k} ${y} v-7`} strokeWidth={1} />
      ))}
      <path d={`M${x + 30} ${y + 58} v10 M${x + 70} ${y + 58} v10`} strokeWidth={1.2} />
    </g>
  );
}

/** 进料斗（梯形斗） */
function Hopper({ x, y }: { x: number; y: number }) {
  return (
    <g {...st}>
      <path d={`M${x - 46} ${y - 74} h92 l-24 44 h-44 z`} />
      <path d={`M${x - 40} ${y - 74} l20 44 M${x + 40} ${y - 74} l-20 44`} strokeWidth={1} opacity={0.6} />
      <rect x={x - 14} y={y - 30} width={28} height={30} />
    </g>
  );
}

/** 控制柜（轴测箱体 + 屏 + 按钮） */
function Cabinet({ x, y }: { x: number; y: number }) {
  return (
    <g {...st}>
      <IsoBox x={x} y={y} w={86} h={104} d={26} />
      <rect x={x + 12} y={y + 14} width={62} height={36} strokeWidth={1.1} />
      <path d={`M${x + 18} ${y + 26} h50 M${x + 18} ${y + 34} h34`} strokeWidth={0.9} opacity={0.6} />
      {[0, 1, 2].map((r) =>
        [0, 1, 2].map((c) => (
          <circle key={`${r}${c}`} cx={x + 22 + c * 21} cy={y + 66 + r * 15} r={3.4} strokeWidth={1} />
        )),
      )}
    </g>
  );
}

/** 六角螺栓头 */
function HexBolt({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 6;
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
  return (
    <g {...st}>
      <polygon points={pts} />
      <circle cx={cx} cy={cy} r={r * 0.4} strokeWidth={1} />
    </g>
  );
}

/** 法兰环（鼓端） */
function Flange({ cx, cy, rx, ry }: { cx: number; cy: number; rx: number; ry: number }) {
  return (
    <g {...st}>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} />
      <ellipse cx={cx} cy={cy} rx={rx * 0.6} ry={ry * 0.6} strokeWidth={1.1} />
    </g>
  );
}

interface Props {
  primitiveIds: string[];
  seedKey?: string;
  regions?: EditRegion[];
  activeRegionId?: string | null;
  changedRegionIds?: string[];
  title?: string;
}

export default function PatentFigure3D({ primitiveIds, regions = [], activeRegionId, changedRegionIds = [], title }: Props) {
  const ids = primitiveIds.length > 0 ? primitiveIds : ['prm-0604', 'prm-0201', 'prm-0202', 'prm-0701'];

  // 鼓主体几何
  const drum = { x: 300, y: 210, rx: 22, ry: 82, len: 400 };
  const parts: Part[] = [];

  const has = (id: string) => ids.includes(id);
  const hasCat = (prefix: string) => ids.some((i) => i.startsWith(prefix));

  ids.forEach((id) => {
    switch (id) {
      case 'prm-0604': // 壳体 → 主鼓筒 + 底座
        parts.push({
          key: id,
          draw: (
            <g>
              <HCylinder {...drum} />
              {/* 筒身环向加强圈 */}
              {[80, 180, 280].map((k) => (
                <ellipse key={k} cx={drum.x + k} cy={drum.y} rx={drum.rx * 0.82} ry={drum.ry} {...st} strokeWidth={1.1} />
              ))}
              {/* 左端法兰 */}
              <Flange cx={drum.x} cy={drum.y} rx={drum.rx + 7} ry={drum.ry + 6} />
              {/* 顶部阴影线 */}
              <path d={`M${drum.x + 30} ${drum.y - drum.ry + 8} q200 -14 340 4`} stroke={DASH} strokeWidth={0.9} fill="none" strokeDasharray="4 3" />
              <Slab x={drum.x - 40} y={drum.y + drum.ry + 46} w={drum.len + 120} d={40} t={12} />
              {/* 鞍座 */}
              <path {...st} d={`M${drum.x + 60} ${drum.y + drum.ry - 4} v50 h60 v-50 M${drum.x + 300} ${drum.y + drum.ry - 4} v50 h60 v-50`} />
            </g>
          ),
          leader: { tx: drum.x + 210, ty: drum.y - 40, lx: 520, ly: 60 },
        });
        break;
      case 'prm-0201': // 阶梯轴 → 贯穿主轴
        parts.push({
          key: id,
          draw: (
            <g {...st}>
              <path d={`M${drum.x - 90} ${drum.y} h${drum.len + 260}`} strokeWidth={2} />
              <path d={`M${drum.x - 90} ${drum.y - 5} h${drum.len + 260} M${drum.x - 90} ${drum.y + 5} h${drum.len + 260}`} strokeWidth={1.1} />
              <path d={`M${drum.x - 60} ${drum.y - 5} v10 M${drum.x + drum.len + 130} ${drum.y - 5} v10`} strokeWidth={1.1} />
            </g>
          ),
          leader: { tx: drum.x + 150, ty: drum.y + 5, lx: 440, ly: 430 },
        });
        break;
      case 'prm-0202': // 轴承 → 两端支承
        parts.push({
          key: id,
          draw: (
            <g>
              {[drum.x - 60, drum.x + drum.len + 100].map((cx) => (
                <g key={cx} {...st}>
                  <ellipse cx={cx} cy={drum.y} rx={12} ry={26} />
                  <ellipse cx={cx} cy={drum.y} rx={6} ry={13} strokeWidth={1.1} />
                  <path d={`M${cx - 4} ${drum.y + 26} v18 h8 v-18`} strokeWidth={1.1} />
                </g>
              ))}
            </g>
          ),
          leader: { tx: drum.x - 60, ty: drum.y - 22, lx: 150, ly: 90 },
        });
        break;
      case 'prm-0301': // 齿轮 → 轴端齿圈
      case 'prm-0306': // 联轴器 → 轴端联轴环
        parts.push({
          key: id,
          draw: (
            <g {...st}>
              <ellipse cx={drum.x + drum.len + 150} cy={drum.y} rx={14} ry={34} />
              <ellipse cx={drum.x + drum.len + 150} cy={drum.y} rx={8} ry={20} strokeWidth={1.1} />
              {id === 'prm-0301' &&
                [-28, -14, 0, 14, 28].map((k) => (
                  <path key={k} d={`M${drum.x + drum.len + 138} ${drum.y + k} l-7 ${k * 0.12}`} strokeWidth={1.1} />
                ))}
              <path d={`M${drum.x + drum.len + 136} ${drum.y} h28`} strokeWidth={2} />
            </g>
          ),
          leader: id === 'prm-0301'
            ? { tx: drum.x + drum.len + 150, ty: drum.y - 30, lx: 890, ly: 84 }
            : { tx: drum.x + drum.len + 150, ty: drum.y + 24, lx: 900, ly: 200 },
        });
        break;
      case 'prm-0701': // 电机
        parts.push({
          key: id,
          draw: <Motor x={770} y={300} />,
          leader: { tx: 800, ty: 330, lx: 850, ly: 420 },
        });
        break;
      case 'prm-0101': // 螺栓 → 法兰栓 + 顶部吊耳栓
        parts.push({
          key: id,
          draw: (
            <g>
              <HexBolt cx={drum.x - 2} cy={drum.y - drum.ry - 2} r={8} />
              <HexBolt cx={drum.x - 2} cy={drum.y + drum.ry + 2} r={8} />
              {[120, 260].map((k) => (
                <g key={k} {...st}>
                  <rect x={drum.x + k - 5} y={drum.y - drum.ry - 22} width={10} height={22} />
                  <HexBolt cx={drum.x + k} cy={drum.y - drum.ry - 27} r={6.5} />
                </g>
              ))}
            </g>
          ),
          leader: { tx: drum.x + 120, ty: drum.y - drum.ry - 24, lx: 340, ly: 66 },
        });
        break;
      case 'prm-0102': // 螺母
        parts.push({
          key: id,
          draw: <HexBolt cx={drum.x + 340} cy={drum.y - drum.ry - 24} r={7} />,
          leader: { tx: drum.x + 340, ty: drum.y - drum.ry - 27, lx: 660, ly: 72 },
        });
        break;
      case 'prm-0401': // 弹簧 → 顶部弹簧安全件
      case 'prm-0402':
        parts.push({
          key: id,
          draw: <Spring x={drum.x + 200} y={drum.y - drum.ry - 44} h={40} />,
          leader: { tx: drum.x + 200, ty: drum.y - drum.ry - 40, lx: 470, ly: 46 },
        });
        break;
      case 'prm-0501': // 密封 → 轴端密封环
      case 'prm-0502':
        parts.push({
          key: id,
          draw: (
            <g {...st}>
              <ellipse cx={drum.x + drum.len + 18} cy={drum.y} rx={8} ry={18} />
              <ellipse cx={drum.x + drum.len + 24} cy={drum.y} rx={4} ry={10} strokeWidth={1.1} />
            </g>
          ),
          leader: { tx: drum.x + drum.len + 22, ty: drum.y - 14, lx: 800, ly: 170 },
        });
        break;
      case 'prm-0702': // 液压缸 / 气缸 → 鼓下方执行器
      case 'prm-0703':
        parts.push({
          key: id,
          draw: <HCylinder x={430} y={352} rx={10} ry={17} len={110} />,
          leader: { tx: 480, ty: 369, lx: 380, ly: 420 },
        });
        break;
      case 'prm-0705': // 换向阀 → 顶部立阀
        parts.push({
          key: id,
          draw: <TopValve x={drum.x + 260} y={drum.y - drum.ry - 4} />,
          leader: { tx: drum.x + 260, ty: drum.y - drum.ry - 34, lx: 600, ly: 42 },
        });
        break;
      case 'prm-0704': // 油泵 → 电机旁小泵
        parts.push({
          key: id,
          draw: <HCylinder x={760} y={392} rx={9} ry={15} len={70} />,
          leader: { tx: 800, ty: 407, lx: 720, ly: 448 },
        });
        break;
      case 'prm-0602': // 导轨 → 底座侧边导轨条
      case 'prm-0603':
        parts.push({
          key: id,
          draw: (
            <g {...st}>
              <path d={`M${drum.x - 20} ${drum.y + drum.ry + 46} h${drum.len + 80}`} strokeWidth={2.4} />
              <rect x={drum.x + 160} y={drum.y + drum.ry + 38} width={70} height={9} />
            </g>
          ),
          leader: { tx: drum.x + 300, ty: drum.y + drum.ry + 48, lx: 620, ly: 430 },
        });
        break;
      default:
        // 其余图元 → 顶部仪表/传感器
        if (hasCat('prm-07') || id.startsWith('prm-0')) {
          parts.push({
            key: id,
            draw: <Gauge cx={drum.x + 320} cy={drum.y - drum.ry - 40} r={16} />,
            leader: { tx: drum.x + 320, ty: drum.y - drum.ry - 52, lx: 700, ly: 40 },
          });
        }
    }
  });

  // 进料斗（有壳体时默认带）
  const hopper = has('prm-0604') ? (
    <g>
      <Hopper x={drum.x - 60} y={drum.y} />
      <path {...st} d={`M${drum.x - 74} ${drum.y} h14`} strokeWidth={2} />
    </g>
  ) : null;

  // 控制柜（默认带，虚线连接）
  const cabinet = (
    <g>
      <Cabinet x={120} y={330} />
      <path d={`M206 380 C 300 380, 340 340, ${drum.x + 60} ${drum.y + drum.ry + 10}`} stroke={DASH} strokeWidth={1.1} fill="none" strokeDasharray="5 4" />
      <path d={`M206 420 C 420 460, 640 460, 780 372`} stroke={DASH} strokeWidth={1.1} fill="none" strokeDasharray="5 4" />
    </g>
  );

  // 引线标签：按 parts 顺序编号（与参数文档附图标记一致）
  const leaders = parts.map((p, i) => {
    const { tx, ty, lx, ly } = p.leader;
    const elbowX = lx + (lx < tx ? 16 : -16);
    return (
      <g key={`L${i}`}>
        <polyline points={`${lx},${ly} ${elbowX},${ly} ${tx},${ty}`} fill="none" stroke={INK_SOFT} strokeWidth={1} />
        <circle cx={tx} cy={ty} r={1.6} fill={INK_SOFT} />
        <text x={lx} y={ly - 6} textAnchor={lx < tx ? 'start' : 'end'} fontSize={15} fontWeight={600} fill={INK}>{i + 1}</text>
      </g>
    );
  });

  return (
    <svg viewBox="0 0 940 520" className="w-full h-full" style={{ background: '#ffffff' }}>
      {/* 图框 */}
      <rect x={10} y={10} width={920} height={500} fill="none" stroke="#94a3b8" strokeWidth={1} />
      <text x={922} y={30} textAnchor="end" fontSize={10} fill="#94a3b8">轴测示意图 · 符合专利附图规范</text>

      {hopper}
      {cabinet}
      {parts.map((p) => <g key={p.key}>{p.draw}</g>)}
      {leaders}

      {/* 框选/修改区域 */}
      {regions.map((r) => {
        const changed = changedRegionIds.includes(r.id);
        const active = activeRegionId === r.id;
        const color = changed ? '#059669' : '#d97706';
        return (
          <g key={r.id}>
            <rect
              x={(r.x / 100) * 940} y={(r.y / 100) * 520}
              width={(r.w / 100) * 940} height={(r.h / 100) * 520}
              fill={changed ? 'rgba(5,150,105,0.08)' : 'rgba(217,119,6,0.07)'}
              stroke={color} strokeWidth={active ? 2 : 1.4} strokeDasharray="6 4" rx={3}
            />
            <text x={(r.x / 100) * 940 + 6} y={(r.y / 100) * 520 + 15} fontSize={11} fill={color}>
              {changed ? '已修改' : '待修改区域'}
            </text>
          </g>
        );
      })}

      <text x={470} y={498} textAnchor="middle" fontSize={13} fill={INK_SOFT}>
        {title ?? `图1  机械结构三维示意图（共${parts.length}个构件）`}
      </text>
    </svg>
  );
}
