# MinerU PDF 专利自动标注设计

日期：2026-07-24  
状态：已批准（需求源为 `codex_prompt_patent_pdf_auto_annotation_phase2_mineru.md`，用户要求直接实施且不设置中途确认）

## 目标

在现有 `/patent-annotation` 手动标注页面中加入一个最小但真实可用的 PDF 自动标注闭环：

1. 上传带文字层或 MinerU 可识别的专利说明书 PDF；
2. 优先用现有 MinerU 配置解析，失败时回退 pypdf；
3. 提取部件编号、附图说明、图号上下文和局部放大标记；
4. 将已上传的无引线 PDF 映射为图 1、图 2 等；
5. 把当前 PDF 页渲染为清晰 PNG，调用现有视觉模型定位候选部件；
6. 生成经过墨迹吸附和左右分栏布局的可编辑引线；
7. 显示置信度与审核状态，重跑只替换当前页自动结果，保留人工结果。

本阶段不实现 DOC/DOCX、服务端持久化、任务队列、Word 导出、STEP 自动标注、OCR、GPU 检测模型或全局引线避障。

## 方案取舍

### 采用：共享基础客户端 + 独立专利领域包

- 将 MinerU 的 HTTP/命令调用抽成无业务含义的共享客户端，现有 Drawing layout provider 与专利文档解析器共同使用。
- 将视觉客户端构建函数移到共享模块，Drawing 与专利定位共同使用现有 `VisionJsonClient`。
- 专利文本抽取、定位规则、图片预处理和 API 保持在 `app.patent_annotation` 内。
- 前端继续使用第一阶段 store、PDF 舞台、属性面板和 `LeaderOverlay`。

优点是复用真实配置和重试逻辑，同时让纯文本规则、定位合并与前端布局可以独立测试。风险集中在共享客户端抽取，必须用现有 Drawing 测试做回归。

### 不采用：路由内直接实现

把正则、临时文件、视觉调用和响应整理都写在 FastAPI 路由中虽然改动少，但无法可靠注入 fake client，也会让错误处理与批处理难以测试。

### 不采用：异步任务与数据库

解析和当前页定位都按单请求同步完成。任务队列和数据库会扩大部署面，不属于本阶段验收范围。

## 后端架构

### 共享基础设施

`app.core.mineru`

- `MineruClient` 接受现有 `MINERU_LAYOUT_MODE/URL/COMMAND/TIMEOUT`。
- `fetch_payload(path)` 支持 disabled、HTTP、command 和测试 transport。
- 统一将未配置、超时、连接失败、非法 JSON 转为带 code/message 的错误。
- `MineruLayoutProvider` 改为调用该客户端，外部行为和构造参数保持兼容。

`app.core.vision`

- `build_vision_client(settings)` 复用现有 vision 环境变量。
- 校验 model、host 和 key；未配置时由专利 API 返回 `patent_vision_not_configured`。
- 继续复用 `VisionJsonClient.complete_json(...)`，不实现新的 HTTP 客户端。

### 专利领域包

`app.patent_annotation.schemas`

- 定义统一文档页、解析结果、部件、附图、局部标记；
- 定义模型 0～1000 坐标 schema 与接口 0～1 归一化 schema；
- 所有列表使用 `Field(default_factory=list)`；
- 编号始终为字符串。

`app.patent_annotation.document_parser`

- `PatentDocumentParser` 先调用 MinerU；快速模式、未配置、超时、连接失败或无有效文本时尝试 pypdf。
- MinerU 原始 JSON 先适配为 `PatentDocumentContent`，领域抽取不读取 MinerU 私有结构。
- 适配常见 `pages`、`content_list`、`markdown`、`text/full_text` 及嵌套 `data/result` 形态；每页保留页码、文本、Markdown 和图片引用。
- pypdf 逐页提取文字并保留页边界；页面无文字产生 warning，全文无文字抛出 `patent_document_no_text`。
- 规范化仅用于匹配：空白压缩、中文断行拼接、全角括号兼容；返回描述和上下文保留可读标点。
- 先解析“图中：”编号表，再用“名称（编号）”补全；按编号去重且保持原顺序。
- 从“附图说明”提取图号和描述；从正文聚合图号上下文、显式编号和稳定候选列表。
- 识别“图 N 中 A 处放大”并生成 detail marker，但不加入普通部件表。

`app.patent_annotation.image_utils`

- 验证 PNG/JPG/WEBP 和 20 MB 限制；
- Pillow EXIF 转正、RGBA 白底合成、RGB、最长边 2048、轻度 autocontrast；
- 输出干净图与同尺寸浅色 10×10 坐标参考图；
- 所有文件位于请求级 `TemporaryDirectory`。

`app.patent_annotation.localization`

- 接收候选部件和图号上下文，每 16 个一批调用 `VisionJsonClient.complete_json(...)`；
- 每批同时传干净图和网格图；
- 只保留请求候选，重复编号取最高置信度；
- 可见但无 anchor 的项降级，bbox 排序并 clamp，anchor 明显位于 bbox 外时进入 review；
- 0～1000 转 0～1；
- `>=0.72` accepted，`0.45～0.72` review，低于 0.45 或 invisible 为 rejected；
- 模型错误转换为稳定业务错误，不泄露临时路径。

`app.patent_annotation.router`

- `POST /api/patent-annotations/parse-document`
- `POST /api/patent-annotations/localize-page`
- 解析接口只接受 30 MB 内 PDF；定位接口只接受 20 MB 内 PNG/JPG/WEBP。
- multipart 中 `components_json` 做 Pydantic 强校验。
- 依赖函数可在 router 测试中替换 fake parser/service。
- 错误 detail 统一为 `{code, message}`。

## 前端架构

### 数据兼容

- `PatentAnnotationDocument` 升级为 `schemaVersion: '0.2'`。
- 导入和 localStorage 读取同时接受 0.1、0.2；0.1 标注默认视为人工标注。
- `PatentSource.figureNo?` 保存 PDF 到图号的映射。
- `PatentAnnotation` 增加可选 `origin/confidence/bbox/reviewState/reviewed/modelReason/modelName`。
- 继续使用原 localStorage key，使旧草稿自动迁移而不是丢失。

### Store 语义

- 手动创建的标注设置 `origin='manual'`。
- 自动应用建议时，只处理当前 `sourceId + page`：
  - 删除旧 `origin='auto'`；
  - 保留所有人工标注；
  - 人工标注已使用的 refNo 跳过自动结果；
  - 新自动结果写入模型元数据。
- 用户拖动或编辑自动标注后设置 `reviewed=true`、`reviewState='accepted'`。
- 支持“接受当前页全部”。

### 自动标注工作流

新增紧凑的 `AutoAnnotationPanel`，只在 PDF 模式显示：

- 选择并解析专利说明书；
- 显示解析器来源、标题、部件数、图数和 warnings；
- 折叠查看/编辑部件名称，勾选参与定位的部件；
- 为当前无引线 PDF 选择图号并查看图描述；
- 触发“自动标注当前图”和“接受当前页全部”。

默认映射规则：

1. 文件名包含 `图N` 或 `figureN` 时匹配 N；
2. 否则按 PDF 来源上传顺序映射解析出的图号；
3. 用户修改后写入 `PatentSource.figureNo`。

`PdfAnnotationWorkspace` 通过 `defineExpose` 暴露当前页 PNG Blob 和 ImageData：

- 直接读取 VuePdfEmbed 的 PDF canvas，不包含 SVG 标注层；
- 白底输出；
- 最长边目标为 1600～2048；
- 未渲染时抛可读错误。

自动标注 composable 按顺序执行：

1. 验证说明书、当前来源和图号映射；
2. 组合用户勾选候选与 detail marker；
3. 若存在旧自动结果，先确认是否替换；
4. 获取当前页 PNG 与 ImageData；
5. 调定位 API；
6. 过滤 invisible/rejected/无 anchor 项；
7. 用 `snapPointToInk` 吸附最近暗像素；
8. 用 `autoLayoutAnnotations` 生成左右分栏的 elbow/label；
9. 调 store 的建议应用方法；
10. 显示新增数和待审核数。

## 纯前端算法

`snapPointToInk`

- 默认半径 28 px，RGB 平均值低于 190 且 alpha 非零视为墨迹；
- 搜索欧氏距离最近的暗像素；
- 无结果保留原点；输出 clamp 后归一化坐标。

`autoLayoutAnnotations`

- 以画布中心分左右组，组内按 anchor.y 稳定排序；
- 标签 x 固定在 0.06/0.94；
- 标签 y 保持至少 0.055 间距并限制在 0.06～0.94；
- elbow 放在 0.18/0.82 附近并连接 anchor 与 label；
- SVG 根据 `label.x < anchor.x` 选择 `text-anchor=start/end`。

## 错误与安全

- 上传文件只在请求级临时目录存在，请求结束即清理。
- 不记录 PDF 内容、模型图片 data URL、API key 或绝对临时路径。
- MinerU 失败但 pypdf 成功时返回 warning 和 `parser='pypdf'`。
- 两种解析器都无文本时返回 422。
- 视觉模型未配置返回 503。
- 模型返回部分非法项时过滤并给 warning，不让整个页面失败。
- 无可见部件时不修改现有人工标注。

## 测试

后端：

- 文本规则：编号表、括号补全、附图说明、跨页内容、图号上下文、A marker、稳定候选顺序；
- 双解析器：MinerU 成功、未配置/超时回退、无文字错误、warning 透传；
- 定位：坐标归一化、未知/重复编号、空 anchor、bbox 排序、置信度、16 项分批、模型错误；
- router：文件类型、大小、components JSON、未配置 vision、fake parser/client；
- 回归现有 Drawing provider 与 extraction client 测试。

前端：

- 0.1 到 0.2 迁移；
- 自动结果替换且人工结果保留；
- 自动编辑后审核状态更新；
- 墨迹吸附；
- 标签间距与边界；
- 文件名/上传顺序图号映射。

验证：

- Node 20 运行 patent tests、typecheck、test build；
- `conda activate 3dcad` 运行新增后端测试与相关 Drawing 测试；
- 用本地说明书和资源 527～530 做解析、映射、当前页定位和可编辑性烟测；
- 样例文件和渲染中间产物不进入 Git。

## 验收边界

- 第一版 UI 只上传 PDF；
- MinerU OCR 能力取决于现有部署；
- 一次只自动定位当前 PDF 页；
- VLM 定位为辅助结果，低置信度必须人工复核；
- 没有可用视觉模型配置时，文档解析仍可单独完成并给出明确定位错误。
