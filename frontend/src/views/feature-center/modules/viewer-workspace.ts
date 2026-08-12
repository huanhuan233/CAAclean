export type ViewerTab = 'bom' | 'native' | 'recognized' | 'geometry';
export type ViewerSourceFormat = 'STEP' | 'CATPART' | 'CATPRODUCT';

export function isCatiaNativeSource(sourceFormat: string | null | undefined) {
  return sourceFormat === 'CATPART' || sourceFormat === 'CATPRODUCT';
}

// 用途：遵循后端装配契约决定初始 BOM 状态；用户切换后由页面本地响应式状态维护。
export function defaultBomVisible(bom: { assembly_mode: string; default_visible: boolean } | null | undefined) {
  return Boolean(bom?.default_visible && bom.assembly_mode === 'assembly');
}

// 用途：在共享 Viewer 中区分 STEP 推理语义与 CATIA 原生语义，不复制页面实现。
export function tabsForSource(sourceFormat: ViewerSourceFormat): ViewerTab[] {
  void sourceFormat;
  return ['bom', 'recognized', 'geometry'];
}

// 用途：把内部稳定排序投影成面向用户的一基编号，长拓扑 ID 仍留在高级信息中。
export function geometryDisplayId(entityType: 'face' | 'edge' | 'vertex', index: number) {
  const prefix = entityType === 'face' ? 'F' : entityType === 'edge' ? 'E' : 'V';
  return `${prefix}-${String(index + 1).padStart(3, '0')}`;
}

const STAGE_LABELS: Record<string, string> = {
  queued: '等待处理',
  dispatching_caa: '连接 CATIA Worker',
  queued_caa: '等待 CAA Worker',
  running_caa: 'CAA 原生解析',
  exporting_step: 'CATIA 导出 STEP',
  processing_exported_step: '处理 CATIA 导出的 STEP',
  feature_center_processing: 'Feature Center 处理',
  validating_bundle: '校验 Feature Center Bundle',
  lightweighting: '生成轻量化模型',
  publishing_assets: '发布 Viewer 资产',
  running_freecad: 'STEP 几何解析',
  ready: '解析完成',
  failed: '处理失败'
};

// 用途：将持久化阶段翻译为可诊断中文，不在 UI 中泄露命令或本机路径。
export function workerStageLabel(stage: string | null | undefined) {
  if (!stage) return '—';
  return STAGE_LABELS[stage] ?? stage;
}
