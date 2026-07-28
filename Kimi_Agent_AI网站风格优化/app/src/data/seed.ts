import type { DatasetRecord, ModelInfo, Pipeline, TokenLog, FeedbackRecord } from '@/types';

export const DATASET_LABELS: Record<string, string> = {
  'text-patent': '自然语言描述 → 专利图库',
  'text-primitive': '自然语言描述 → 图元库',
  'image-edit': '图改图库（图-文-图）',
  'param-primitive': '制图参数文档 → 图元库',
};

export const seedDatasets: DatasetRecord[] = [
  { id: 'DS-1001', type: 'text-patent', title: '减速器箱体装配示意图', input: '一种二级圆柱齿轮减速器，包括箱体、输入轴、输出轴、两级齿轮副与轴承支承……', output: 'PAT-FIG-0231（装配示意图，含附图标记1-12）', quality: 4.6, source: '脱敏专利 CN114xxxxxxA', createdAt: '2026-06-18' },
  { id: 'DS-1002', type: 'text-patent', title: '液压夹紧装置结构图', input: '夹紧装置由液压缸驱动连杆机构，连杆与压板铰接实现对工件的夹紧与松开……', output: 'PAT-FIG-0187（结构示意图，含剖视）', quality: 4.4, source: '脱敏专利 CN115xxxxxxA', createdAt: '2026-06-20' },
  { id: 'DS-1003', type: 'text-patent', title: '带式输送机传动滚筒', input: '传动滚筒包括筒体、轮辐、轮毂与传动轴，轮毂通过平键与传动轴连接……', output: 'PAT-FIG-0264（剖视结构图）', quality: 4.8, source: '脱敏专利 CN116xxxxxxB', createdAt: '2026-07-02' },
  { id: 'DS-1004', type: 'text-patent', title: '弹簧复位安全阀', input: '阀体内设阀芯，阀芯顶部抵接压缩弹簧，弹簧预紧力决定开启压力……', output: 'PAT-FIG-0302', quality: 4.2, source: '脱敏专利 CN113xxxxxxA', createdAt: '2026-07-09' },
  { id: 'DS-2001', type: 'text-primitive', title: '螺栓-螺母-垫圈紧固组', input: '六角头螺栓穿过法兰连接孔，依次套入平垫圈与弹簧垫圈后与六角螺母旋合', output: 'PRM-0101 / PRM-0102 / PRM-0103 / PRM-0104', quality: 4.9, source: '标注批次 B-0721', createdAt: '2026-07-11' },
  { id: 'DS-2002', type: 'text-primitive', title: '轴系支承组件', input: '阶梯轴两端由深沟球轴承支承，轴段间以轴套轴向定位，端部法兰盘输出动力', output: 'PRM-0201 / PRM-0202 / PRM-0203 / PRM-0205', quality: 4.7, source: '标注批次 B-0721', createdAt: '2026-07-12' },
  { id: 'DS-2003', type: 'text-primitive', title: '齿轮传动匹配', input: '电机输出轴经联轴器驱动小齿轮，小齿轮与大齿轮啮合减速后输出', output: 'PRM-0701 / PRM-0306 / PRM-0301×2', quality: 4.5, source: '标注批次 B-0723', createdAt: '2026-07-15' },
  { id: 'DS-2004', type: 'text-primitive', title: '直线导向运动副', input: '滑块沿直线导轨往复移动，导轨螺栓固定于基座平面', output: 'PRM-0602 / PRM-0603 / PRM-0604 / PRM-0101', quality: 4.3, source: '标注批次 B-0724', createdAt: '2026-07-18' },
  { id: 'DS-3001', type: 'image-edit', title: '联轴器替换为弹性联轴器', input: '源图：刚性凸缘联轴器局部', output: '目标图：弹性套柱销联轴器', pairs: '原图区域(联轴器) → “改为带弹性元件的挠性联轴器” → 修改后区域图', quality: 4.6, source: '用户会话 U-3391', createdAt: '2026-07-14' },
  { id: 'DS-3002', type: 'image-edit', title: '增加密封结构', input: '源图：轴承端盖区域', output: '目标图：端盖内增加骨架油封', pairs: '原图区域(端盖) → “端盖内侧增加旋转油封” → 修改后区域图', quality: 4.4, source: '用户会话 U-3417', createdAt: '2026-07-16' },
  { id: 'DS-3003', type: 'image-edit', title: '支承方式修改', input: '源图：滑动轴承支承段', output: '目标图：改为深沟球轴承支承', pairs: '原图区域(支承段) → “滑动轴承改为滚动轴承支承” → 修改后区域图', quality: 4.1, source: '用户会话 U-3488', createdAt: '2026-07-19' },
  { id: 'DS-4001', type: 'param-primitive', title: '齿轮参数文档-直齿轮', input: '模数2.5、齿数24、压力角20°、齿宽25mm、40Cr调质……', output: 'PRM-0301（参数映射完整率100%）', quality: 5.0, source: '参数文档库 P-118', createdAt: '2026-07-08' },
  { id: 'DS-4002', type: 'param-primitive', title: '液压缸参数文档', input: '缸径50mm、杆径28mm、行程200mm、额定压力16MPa……', output: 'PRM-0702（参数映射完整率96%）', quality: 4.7, source: '参数文档库 P-121', createdAt: '2026-07-13' },
  { id: 'DS-4003', type: 'param-primitive', title: '弹簧参数文档', input: '丝径3mm、中径20mm、有效圈数6、自由高度42mm……', output: 'PRM-0401（参数映射完整率100%）', quality: 4.8, source: '参数文档库 P-125', createdAt: '2026-07-17' },
];

export const seedModels: ModelInfo[] = [
  { id: 'm-kimi-k2', name: 'Kimi K2', provider: 'Moonshot AI', type: 'LLM', status: '已接入', latency: '1.2s', costPer1k: '¥0.012' },
  { id: 'm-kimi-vl', name: 'Kimi-VL 多模态', provider: 'Moonshot AI', type: '多模态', status: '已接入', latency: '1.8s', costPer1k: '¥0.018' },
  { id: 'm-gpt4o', name: 'GPT-4o', provider: 'OpenAI', type: '多模态', status: '已接入', latency: '1.5s', costPer1k: '¥0.036' },
  { id: 'm-claude', name: 'Claude Sonnet 4', provider: 'Anthropic', type: 'LLM', status: '已接入', latency: '1.4s', costPer1k: '¥0.022' },
  { id: 'm-qwen', name: 'Qwen2.5-72B', provider: '阿里云', type: 'LLM', status: '已接入', latency: '1.1s', costPer1k: '¥0.009' },
  { id: 'm-deepseek', name: 'DeepSeek-V3', provider: '深度求索', type: 'LLM', status: '已接入', latency: '1.0s', costPer1k: '¥0.008' },
  { id: 'm-bge', name: 'BGE-M3 Embedding', provider: '智源研究院', type: '向量化', status: '已接入', latency: '0.3s', costPer1k: '¥0.002' },
  { id: 'm-sd', name: 'Stable Diffusion XL', provider: 'Stability AI', type: '图像生成', status: '已接入', latency: '4.5s', costPer1k: '¥0.050' },
  { id: 'm-doubao', name: '豆包 Seedream', provider: '字节跳动', type: '图像生成', status: '未接入', latency: '-', costPer1k: '¥0.042' },
];

export const seedPipelines: Pipeline[] = [
  {
    id: 'pl-data',
    name: '数据处理流程',
    desc: '图元/专利文档入库前的解析与向量化',
    nodes: [
      { id: 'n-upload', label: '文件接入', desc: 'DOCX/PDF/XML/SVG 多格式接入与完整性校验', modelId: '', avgTokens: 0 },
      { id: 'n-parse', label: '文件解析', desc: '段落级语义解析，抽取构件名称、参数、连接关系', modelId: 'm-kimi-k2', avgTokens: 3200 },
      { id: 'n-struct', label: '结构化抽取', desc: '生成图元元数据 Schema 与参数表', modelId: 'm-deepseek', avgTokens: 2100 },
      { id: 'n-embed', label: '向量化', desc: '语义向量嵌入，写入向量索引库', modelId: 'm-bge', avgTokens: 800 },
      { id: 'n-store', label: '入库', desc: '元数据入图元库，向量入检索库，双向索引', modelId: '', avgTokens: 0 },
    ],
  },
  {
    id: 'pl-t2i',
    name: '文生图流程',
    desc: '自然语言描述 + 图元选择 → 专利附图与参数文档',
    nodes: [
      { id: 'n-understand', label: '语义理解', desc: '解析自然语言中的构件、方位与装配关系', modelId: 'm-kimi-k2', avgTokens: 1800 },
      { id: 'n-match', label: '图元匹配', desc: '向量检索匹配图元库，返回候选图元集', modelId: 'm-bge', avgTokens: 600 },
      { id: 'n-frame', label: '形成框架', desc: '规划布局骨架：基准、相对位置、附图标记编号', modelId: 'm-claude', avgTokens: 2600 },
      { id: 'n-assemble', label: '组装成图', desc: '参数化实例化图元并按框架装配，输出线条图', modelId: 'm-sd', avgTokens: 1500 },
      { id: 'n-doc', label: '生成参数文档', desc: '输出构件参数文档（尺寸/材料/装配关系）', modelId: 'm-qwen', avgTokens: 1200 },
    ],
  },
  {
    id: 'pl-i2i',
    name: '图改图流程',
    desc: '框选区域 + 修改指令 → 局部重绘与合成',
    nodes: [
      { id: 'n-region', label: '区域解析', desc: '解析框选区域坐标与区域内构件识别', modelId: 'm-kimi-vl', avgTokens: 1400 },
      { id: 'n-instruct', label: '指令理解', desc: '自然语言修改指令 + 替换图元语义融合', modelId: 'm-gpt4o', avgTokens: 1600 },
      { id: 'n-rematch', label: '图元重匹配', desc: '按修改指令检索替换图元', modelId: 'm-bge', avgTokens: 500 },
      { id: 'n-redraw', label: '局部修改', desc: '区域内构件替换/参数重绘，保持风格一致', modelId: 'm-sd', avgTokens: 1800 },
      { id: 'n-merge', label: '组装合成', desc: '修改区域与全图合成，更新参数文档版本', modelId: 'm-kimi-k2', avgTokens: 900 },
    ],
  },
];

export const seedTokenLogs: TokenLog[] = [
  { date: '07-18', 数据解析: 42000, 向量化: 8600, 文生图: 61500, 图改图: 23800, 参数文档: 12400 },
  { date: '07-19', 数据解析: 38500, 向量化: 7900, 文生图: 58200, 图改图: 26100, 参数文档: 11800 },
  { date: '07-20', 数据解析: 51200, 向量化: 10400, 文生图: 66800, 图改图: 30500, 参数文档: 13900 },
  { date: '07-21', 数据解析: 47800, 向量化: 9200, 文生图: 71400, 图改图: 28900, 参数文档: 15200 },
  { date: '07-22', 数据解析: 44600, 向量化: 8800, 文生图: 69300, 图改图: 33200, 参数文档: 14600 },
  { date: '07-23', 数据解析: 53900, 向量化: 11200, 文生图: 76800, 图改图: 35700, 参数文档: 16100 },
  { date: '07-24', 数据解析: 32500, 向量化: 6400, 文生图: 45200, 图改图: 19800, 参数文档: 9600 },
];

export const seedFeedback: FeedbackRecord[] = [
  { id: 'FB-0921', feature: '文生图', contentTitle: '减速器装配示意图 V1', contentSnapshot: '描述：“二级齿轮减速器，含箱体、输入输出轴”｜匹配图元6个｜附图标记1-9', feedbackType: '点赞', feedbackText: '装配关系正确，附图标记规范', user: 'user_2204', createdAt: '2026-07-23 14:22', status: '已闭环' },
  { id: 'FB-0922', feature: '文生图', contentTitle: '液压夹紧装置图 V1', contentSnapshot: '描述：“液压缸驱动连杆夹紧”｜匹配图元5个', feedbackType: '点踩', feedbackText: '连杆与压板的铰接位置画反了，应在压板中部', user: 'user_2204', createdAt: '2026-07-23 15:07', status: '已采纳' },
  { id: 'FB-0923', feature: '图改图', contentTitle: '联轴器区域修改 V2→V3', contentSnapshot: '框选区域：联轴器(32%,41%,18%,14%)｜指令：“改为弹性联轴器”', feedbackType: '点赞', feedbackText: '局部替换风格一致，未影响周边构件', user: 'user_2317', createdAt: '2026-07-24 09:41', status: '已闭环' },
  { id: 'FB-0924', feature: '图元解析', contentTitle: 'CN116xxxxxxB 解析结果', contentSnapshot: '解析出构件14个、参数32项、连接关系11条', feedbackType: '文字', feedbackText: '“轮辐”被误识别为“法兰”，建议增加轮辐图元', user: 'admin_li', createdAt: '2026-07-24 10:15', status: '待处理' },
  { id: 'FB-0925', feature: '文生图', contentTitle: '弹簧复位安全阀 V1', contentSnapshot: '描述：“阀芯顶部抵接压缩弹簧”｜匹配图元4个', feedbackType: '点踩', feedbackText: '弹簧旋向与常规示意不符，建议左旋改右旋', user: 'user_2452', createdAt: '2026-07-24 11:02', status: '待处理' },
];

export const seedParseOutput = {
  fileName: 'CN116xxxxxxB_传动滚筒.pdf',
  meta: { 文献类型: '发明专利说明书', 段落数: 87, 解析耗时: '6.4s', 解析模型: 'Kimi K2' },
  components: [
    { name: '筒体', refNo: '1', params: ['外径 φ320mm', '壁厚 12mm'], confidence: 0.98 },
    { name: '轮辐', refNo: '2', params: ['数量 2', '板厚 10mm'], confidence: 0.91 },
    { name: '轮毂', refNo: '3', params: ['内孔 φ90mm'], confidence: 0.96 },
    { name: '传动轴', refNo: '4', params: ['轴径 φ85mm', '材料 45钢'], confidence: 0.99 },
    { name: '平键', refNo: '5', params: ['键宽 22mm', 'GB/T 1096'], confidence: 0.97 },
    { name: '深沟球轴承', refNo: '6', params: ['型号 6217'], confidence: 0.95 },
  ],
  relations: [
    '轮毂(3) 通过 平键(5) 与 传动轴(4) 周向固定',
    '轮辐(2) 焊接于 筒体(1) 与 轮毂(3) 之间',
    '传动轴(4) 两端由 深沟球轴承(6) 支承',
  ],
  suggestedPrimitives: ['prm-0604', 'prm-0201', 'prm-0105', 'prm-0202'],
};
