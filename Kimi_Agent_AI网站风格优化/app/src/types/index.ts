export interface ParamField {
  key: string;
  label: string;
  unit?: string;
  value: string;
}

export interface Primitive {
  id: string;
  code: string; // 图元编码 PRM-XXXX
  name: string;
  category: string; // 一级目录
  standard: string; // 国标号
  description: string;
  material: string;
  params: ParamField[];
  version: string;
  status: '已入库' | '待审核' | '解析中';
  updatedAt: string;
  usageCount: number;
}

export interface CategoryNode {
  id: string;
  name: string;
  children?: CategoryNode[];
}

export type DatasetType = 'text-patent' | 'text-primitive' | 'image-edit' | 'param-primitive';

export interface DatasetRecord {
  id: string;
  type: DatasetType;
  title: string;
  input: string; // 自然语言描述 / 源图说明
  output: string; // 目标：专利图 / 图元编码 / 参数文档
  pairs?: string; // 图改图：图-文-图 三元组说明
  quality: number; // 质量分
  source: string;
  createdAt: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  type: 'LLM' | '多模态' | '向量化' | '图像生成';
  status: '已接入' | '未接入';
  latency: string;
  costPer1k: string;
}

export interface PipelineNode {
  id: string;
  label: string;
  desc: string;
  modelId: string;
  avgTokens: number;
}

export interface Pipeline {
  id: string;
  name: string;
  desc: string;
  nodes: PipelineNode[];
}

export interface TokenLog {
  date: string;
  数据解析: number;
  向量化: number;
  文生图: number;
  图改图: number;
  参数文档: number;
}

export interface FeedbackRecord {
  id: string;
  feature: '文生图' | '图改图' | '图元解析';
  contentTitle: string;
  contentSnapshot: string; // 对应内容摘要
  feedbackType: '点赞' | '点踩' | '文字';
  feedbackText: string;
  user: string;
  createdAt: string;
  status: '待处理' | '已采纳' | '已闭环';
}

export interface ParamDocRow {
  refNo: string; // 附图标记
  name: string;
  code: string; // 图元编码
  keyParams: string;
  material: string;
  relation: string; // 装配关系
}

export interface GeneratedResult {
  id: string;
  version: number;
  prompt: string;
  primitiveIds: string[];
  docRows: ParamDocRow[];
  createdAt: string;
  regions?: EditRegion[];
  feedback?: 'up' | 'down' | null;
}

export interface EditRegion {
  id: string;
  x: number; // percent
  y: number;
  w: number;
  h: number;
  instruction: string;
  primitiveIds: string[];
}

export interface ParseTask {
  id: string;
  fileName: string;
  fileType: string;
  size: string;
  stage: number; // 0-4
  status: '解析中' | '已完成' | '失败';
  createdAt: string;
}
