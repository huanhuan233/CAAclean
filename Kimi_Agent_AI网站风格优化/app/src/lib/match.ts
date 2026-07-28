// 自然语言 → 图元智能匹配（关键词向量检索的演示实现）
const KEYWORD_MAP: [string[], string][] = [
  [['锥齿轮', '伞齿轮'], 'prm-0302'],
  [['蜗轮', '蜗杆'], 'prm-0303'],
  [['齿轮'], 'prm-0301'],
  [['链轮'], 'prm-0305'],
  [['带轮', '皮带轮', '皮带'], 'prm-0304'],
  [['轴承', '滚动轴承'], 'prm-0202'],
  [['轴套', '衬套', '滑动轴承'], 'prm-0203'],
  [['曲轴'], 'prm-0204'],
  [['阶梯轴', '传动轴', '转轴', '主轴'], 'prm-0201'],
  [['法兰'], 'prm-0205'],
  [['碟簧', '碟形弹簧'], 'prm-0402'],
  [['弹簧'], 'prm-0401'],
  [['油封'], 'prm-0502'],
  [['密封', 'o形', 'o型'], 'prm-0501'],
  [['电机', '马达', '电动机'], 'prm-0701'],
  [['液压缸', '油缸', '液压'], 'prm-0702'],
  [['气缸', '气动'], 'prm-0703'],
  [['油泵', '齿轮泵', '泵'], 'prm-0704'],
  [['换向阀', '阀'], 'prm-0705'],
  [['凸轮'], 'prm-0706'],
  [['连杆'], 'prm-0707'],
  [['联轴器'], 'prm-0306'],
  [['导轨'], 'prm-0602'],
  [['滑块', '滑座'], 'prm-0603'],
  [['支架'], 'prm-0601'],
  [['箱体', '壳体', '基座', '机座'], 'prm-0604'],
  [['螺栓', '螺钉'], 'prm-0101'],
  [['螺母'], 'prm-0102'],
  [['弹簧垫圈'], 'prm-0104'],
  [['垫圈'], 'prm-0103'],
  [['平键', '键连接', '键'], 'prm-0105'],
  [['圆柱销', '销'], 'prm-0106'],
];

const FALLBACK = ['prm-0604', 'prm-0201', 'prm-0202', 'prm-0301', 'prm-0101', 'prm-0102'];

export function matchPrimitives(prompt: string): string[] {
  const text = prompt.toLowerCase();
  const hits: string[] = [];
  for (const [kws, id] of KEYWORD_MAP) {
    if (kws.some((k) => text.includes(k)) && !hits.includes(id)) hits.push(id);
  }
  if (hits.length === 0) return FALLBACK;
  // 自动补全关联件
  if (hits.includes('prm-0101') && !hits.includes('prm-0102')) hits.push('prm-0102');
  if (hits.includes('prm-0201') && !hits.includes('prm-0202')) hits.push('prm-0202');
  if (hits.includes('prm-0602') && !hits.includes('prm-0603')) hits.push('prm-0603');
  if (!hits.includes('prm-0604')) hits.unshift('prm-0604'); // 基体默认包含
  return hits.slice(0, 9);
}

export const PROMPT_TEMPLATES = [
  '一种齿轮减速传动装置，电机通过联轴器驱动小齿轮，小齿轮与安装于传动轴上的大齿轮啮合，传动轴两端由轴承支承于箱体',
  '一种液压夹紧机构，液压缸输出杆铰接连杆，连杆驱动压板绕支架支点转动，弹簧辅助复位',
  '一种直线进给滑台，滑块沿直线导轨往复移动，导轨由螺栓固定于基座，端部设弹簧缓冲',
  '一种带密封的轴系组件，阶梯轴由两端轴承支承于壳体，轴伸端设油封与法兰盘，通过平键连接齿轮',
];
