# 专利附图标注 MVP 设计

## 目标与范围

新增顶层页面 `/patent-annotation`，提供 PDF 附图和 STEP 模型两种来源的手工引线标注能力。用户能够打开来源、创建一根三点折线、在右侧修改属性、拖动三个控制点，并通过本地草稿和 JSON 导入导出保存结果。

本次不接入 AI、专利文本解析、自动编号识别、引线避障、成品文档导出或新的后端数据表。PDF 仅在浏览器中处理；STEP 继续使用现有 CAD API 和 `CadViewer`。

## 方案选择

采用“共享标注内核 + 两个薄工作区”：

- `types.ts`、`geometry.ts` 和 `usePatentAnnotations.ts` 维护稳定数据结构及全部持久化规则。
- `LeaderOverlay.vue` 与 `AnnotationInspector.vue` 同时服务 PDF 和 STEP。
- `PdfAnnotationWorkspace.vue` 只负责 PDF 文件、分页及二维舞台。
- `StepAnnotationWorkspace.vue` 只负责模型列表、上传、解析轮询、Viewer 与视角锁定。
- `CadViewer.vue` 仅增加可选交互能力，保持现有 `/cad-model` 行为兼容。

未采用两套独立编辑器，因为会重复拖拽、校验、JSON 和属性表单逻辑。未抽象并重构 `cad-spec`，因为其回归风险和改动范围超过本次目标。

## 文件与模块边界

新增：

```text
frontend/src/views/patent-annotation/
├── index.vue
├── types.ts
├── geometry.ts
├── composables/
│   └── usePatentAnnotations.ts
└── modules/
    ├── LeaderOverlay.vue
    ├── AnnotationInspector.vue
    ├── PdfAnnotationWorkspace.vue
    └── StepAnnotationWorkspace.vue
```

职责：

- `index.vue`：模式切换、统一文档状态、当前来源/页、选择状态、JSON 导入导出、右侧面板及页面布局。
- `types.ts`：`SourceKind`、`Point2D`、`PatentSource`、`PatentAnnotation`、`PatentAnnotationDocument`。
- `geometry.ts`：`clamp01`、指针坐标归一化、归一化坐标转像素、默认标签/折点计算及点值修正。
- `usePatentAnnotations.ts`：来源与标注的唯一数据源，提供增删改、自动编号、按来源/页筛选、当前页清空、localStorage、JSON 校验导入和 `applySuggestedAnnotations`。
- `LeaderOverlay.vue`：无持久业务状态的 SVG 渲染和 Pointer Events 拖拽层。
- `AnnotationInspector.vue`：当前来源/页的列表及选中标注的双向属性编辑。
- `PdfAnnotationWorkspace.vue`：运行时 PDF 文件列表、Object URL 生命周期、分页、渲染尺寸、缩放、平移与落点创建。
- `StepAnnotationWorkspace.vue`：现有模型查询、STEP 上传、revision 轮询、Mesh 查询、视角锁定及面点击创建。

## 数据模型与持久化

数据文档固定为：

```ts
export type SourceKind = 'pdf' | 'step';

export interface Point2D {
  x: number;
  y: number;
}

export interface PatentSource {
  id: string;
  kind: SourceKind;
  fileKey: string;
  fileName: string;
  pageCount: number;
}

export interface PatentAnnotation {
  id: string;
  sourceId: string;
  sourceKind: SourceKind;
  page: number;
  refNo: string;
  partName: string;
  anchor: Point2D;
  elbow: Point2D;
  label: Point2D;
  visible: boolean;
  lineWidth: number;
  fontSize: number;
  entityId?: string;
  worldPoint?: [number, number, number];
}

export interface PatentAnnotationDocument {
  schemaVersion: '0.1';
  sources: PatentSource[];
  annotations: PatentAnnotation[];
}
```

所有二维坐标持久化为 `[0, 1]` 归一化值。`refNo` 始终是字符串。PDF 的 `fileKey` 为 `name:size:lastModified`；STEP 已有模型以 `cad-revision:{revisionId}` 为稳定键，文件名使用模型名称，新上传模型在获得 revision 后采用同一规则。

localStorage 使用固定草稿键保存整个文档，不保存 `File` 或 Object URL。刷新后重新上传相同 PDF 时，用 `fileKey` 将运行时文件绑定到已有 `PatentSource`。Object URL 在移除文件、替换运行时集合及组件卸载时回收。

导入 JSON 时要求 `schemaVersion === '0.1'`、`sources` 和 `annotations` 为数组；非法来源、缺失关联、非有限数值会被拒绝或修正。坐标用 `clamp01` 修正，`refNo` 转为字符串，线宽和字号限制在界面允许范围内。导入成功后立即替换草稿并显示。

## PDF 数据流与交互

1. 用户可一次选择多个 PDF，每个运行时文件创建 Object URL，并按 `fileKey` 复用或创建来源记录。
2. `VuePdfEmbed` 渲染当前文件和页。`rendered` 后读取 `doc.numPages`，并从实际 canvas 的 CSS 尺寸更新舞台尺寸。
3. PDF canvas 和 SVG 覆盖层位于同一 `stage`，共同承受 `translate + scale`，避免缩放漂移。
4. “添加引线”进入一次性创建状态。下一次普通左键点击以覆盖层 `getBoundingClientRect()` 换算归一化 anchor，自动生成 label、elbow 和下一个纯数字编号。
5. Space + 左键或中键用于平移；滚轮和按钮用于缩放；普通左键留给创建、选择与拖动。
6. 创建完成后退出创建状态并选中新标注。默认只绘制编号，不在图面显示部件名称。
7. 切换文件或页只改变过滤条件，不删除标注。清空当前页只删除当前 `sourceId + page`，并经过二次确认。

## STEP 数据流与交互

1. 页面查询现有模型列表，也允许上传 `.step/.stp`。
2. 选择或上传后查询 revision 状态；`queued/processing` 状态按固定间隔轮询，完成后加载最多 5000 个 Face Mesh。
3. `CadViewer` 新增默认值为 `false` 的 `interactionLocked`，并新增 `sceneClick`：

```ts
{
  entityId: string;
  worldPoint: [number, number, number];
  screen: { x: number; y: number };
}
```

4. raycaster 命中后仍发送原有 `faceClick(entityId)`，同时发送 `sceneClick`。`screen` 通过 renderer canvas 的 bounding rect 归一化，`worldPoint` 使用 intersection point。
5. “锁定视角并添加引线”设置 `interactionLocked=true`。此时禁用 OrbitControls，但保留面点击。
6. 点击面后创建标注，保存 `entityId`、`worldPoint` 和 screen anchor。标签、折点和所有属性继续通过共享覆盖层及属性面板编辑。
7. 当前 STEP 来源存在标注时默认保持锁定。用户解锁需确认；确认后删除该 STEP 来源的全部标注，避免屏幕锚点与模型视角错位。
8. 本次不实现旋转后的 `worldPoint` 动态重投影。

## SVG 覆盖层

- 使用 `polyline` 绘制 `anchor -> elbow -> label`，无箭头。
- 默认线宽 `1.2`，颜色使用 `var(--el-text-color-primary)`，并设置 `vector-effect="non-scaling-stroke"`。
- anchor 始终有小圆点；未选中时仅显示线、圆点和编号。
- 选中时显示 anchor、elbow、label 三个控制柄。
- 线、编号及控制柄均可选择标注。
- 控制柄使用 Pointer Events 和 pointer capture。拖动时按覆盖层当前 bounding rect 实时计算归一化坐标，并直接更新共享状态。
- label 点既是折线终点也是文字位置；文字使用非缩放线宽策略，字号跟随舞台缩放，属性中的 `fontSize` 表示舞台坐标字号。

## 属性面板

上半部分显示当前来源和当前页的标注列表，列表项为“编号 + 部件名称”。点击列表项选择并高亮对应引线。

下半部分编辑：

- `refNo`
- `partName`
- anchor X/Y
- elbow X/Y
- label X/Y
- `lineWidth`
- `fontSize`
- `visible`
- 删除

坐标在界面中显示为百分比，写回时转换为 `[0, 1]`。所有字段直接更新共享响应式对象，因此舞台实时变化。

## 页面、路由与响应式布局

新增自定义顶层路由 `patent-annotation`，路径 `/patent-annotation`，图标 `carbon:draw`，菜单顺序为 4。更新 elegant-router 生成文件和中英文路由文案，但不重排前三个业务菜单。

页面使用 Element Plus 风格，不使用渐变。桌面布局为主舞台和 360px 属性栏：

```css
grid-template-columns: minmax(620px, 1fr) 360px;
height: calc(100vh - 118px);
```

窄窗口切换为上下布局。无来源或无 Mesh 时显示 `ElEmpty`。每个异步按钮具有 loading/disabled 状态。

## 错误处理与资源清理

- 拒绝错误扩展名并显示消息。
- PDF 加载或页渲染失败时保留其他来源，不创建无效标注。
- STEP API 错误停止轮询并显示后端错误；模型切换会取消旧轮询状态。
- JSON 解析和结构错误不会覆盖当前草稿。
- localStorage 写入失败只提示一次，不阻断当前编辑。
- Object URL、轮询 timer、pointer capture 和 Viewer 事件监听在退出路径上清理。
- 异步调用全部捕获错误，避免未处理 Promise。

## 验证

自动验证：

- `pnpm gen-route` 后检查只产生本任务相关路由变更。
- `pnpm typecheck`
- `pnpm build`
- 若项目现有测试设施适合，给纯几何与 JSON 修正逻辑增加单元测试；否则由 typecheck 和人工步骤覆盖。

PDF 人工验收：

1. 一次上传至少四个 PDF 并切换。
2. 验证分页、适应窗口、缩放和平移。
3. 创建引线，修改编号为 `61`，编辑三个点并拖动三个控制柄。
4. 切换文件和页后返回，确认标注保留。
5. 导出、清空、导入 JSON，确认恢复。
6. 刷新后重新上传同一 PDF，确认通过 `fileKey` 找回草稿。
7. 缩放后确认引线与落点对齐。

STEP 人工验收：

1. 选择现有模型和上传新 STEP 各一次。
2. 完成解析后显示 Mesh。
3. 锁定视角，点击面创建引线。
4. 修改编号、名称和三个点。
5. 回到 `/cad-model` 验证面点击及 OrbitControls 行为未变。

## 提交拆分与已知限制

实现提交拆为：

1. `feat: add pdf patent annotation editor`
2. `feat: add minimal step annotation mode`

已知限制：

- 尚未接入自动识别或自动标注。
- STEP 模型旋转后尚未根据 `worldPoint` 动态重投影。
- PDF 二进制和 STEP 标注文档不上传后端，跨设备需通过 JSON 传递。
