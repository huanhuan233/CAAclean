# 图元建库工作台设计

## 目标

新增“图元建库”统一入口，把 STEP 和二维参数图作为同一图元建库版本的两项输入。用户在文件树中上传、查看解析状态；解析完成后分别进入现有 CAD 模型解析页和二维图纸解析页查看证据。最终输出严格遵循 ComponentSpec v1.2 YAML。

第一期不重写现有解析器，不把两个专业查看页嵌入工作台，也不实现尚未存在的 YAML 导出能力。

## 现有能力

- STEP 上传创建 `CadModel` 和 `CadModelRevision`，通过 `revision_id` 查询解析状态、结构、网格、几何对象、尺寸和特征。
- 二维参数图创建 `CadSpecTask`，其 `revision_id` 必须引用一个 STEP revision；通过 `task_id` 查询版面状态、抽取状态、区域和 Drawing Facts。
- CAD 页面目前自行加载模型列表，尚未按路由 `revision_id` 精确选中模型。
- 图纸页面已经读取路由 `revision_id`，尚未读取路由 `task_id` 精确选中抽取任务。
- `CadSpecField` 和 `CadSpecFieldEvidence` 已能保存图纸值、几何测量值和来源证据，但当前没有完整的工作台查询与审核界面。
- `/api/cad/revisions/{revision_id}/exports/v2` 当前返回 501，ComponentSpec YAML 生成属于后续阶段。

## 产品结构

侧边菜单新增“图元建库”，作为默认业务入口。现有“CAD 模型解析”和“组件规范”保留为专业查看页；“组件规范”在界面文案中改称“二维图纸解析”，避免与最终 ComponentSpec YAML 混淆。

工作台采用两栏布局：

- 左侧：图元、版本和文件组成的业务文件树。
- 右侧：当前节点详情，包括任务摘要、解析阶段、错误信息、文件元数据和可执行操作。

CAD 页内部的产品结构树仍只表示 STEP 内部的 Solid、Face、Edge 等几何结构，不与工作台业务文件树合并。

## 业务文件树

```text
图元库
└─ 管路连接件
   └─ 法兰
      └─ 带颈对焊法兰
         └─ XMS06 / HG/T 20592-2009
            └─ 建库版本 v1.0.0
               ├─ 输入资料
               │  ├─ XMS06-DN80.stp
               │  └─ XMS06参数图.png
               ├─ 数据融合
               │  └─ 图纸与几何字段对齐
               ├─ ComponentSpec
               │  ├─ component-spec.yaml
               │  ├─ generator.py
               │  ├─ preview.glb
               │  └─ thumbnail.png
               └─ 发布校验
```

分类层映射 `identity.family/type/subtype`，图元层映射 `identity.id/name/standard`，建库版本映射 `identity.version`。DN、PN 等规格进入 YAML 的 `presets[]`，默认不作为独立图元节点。

STEP 既是解析输入，也是 `artifacts.reference_step` 指向的交付文件。二维参数图是内部解析证据，通过 `provenance` 记录来源，不增加模板中不存在的 artifact 类型。

## 工作台记录

现有 `CadModelRevision` 和 `CadSpecTask` 只能表达各自任务，不能稳定表达“这两个文件共同生成一个 ComponentSpec 版本”。第一期增加聚合记录 `ComponentBuild`：

- `id`
- `catalog_node_id`
- `component_id`
- `component_name`
- `component_type`
- `component_subtype`
- `standard_number`
- `version`
- `default_dn`
- `default_pn`
- `cad_model_id`
- `cad_revision_id`
- `drawing_task_id`
- `status`
- `status_message`
- `created_by`
- `created_at`
- `updated_at`

第一期每个 build 只关联一个活动 STEP revision 和一个活动 drawing task。替换文件时创建新的解析记录并更新活动引用，旧记录保留用于审计。

分类目录使用独立的 `ComponentCatalogNode`，至少包含 `id`、`parent_id`、`name`、`code`、`node_type`、`sort_order` 和 `status`。业务文件节点由 build 和关联任务动态投影，不为每个虚拟文件夹单独建表。

## 上传流程

1. 用户在树上选择分类节点，点击“新建图元”或“上传资料”。
2. 抽屉要求确认图元 ID、名称、类型、默认 DN/PN，并选择 STEP 和二维参数图。
3. 系统创建 `ComponentBuild`，状态为 `uploading`。
4. 系统上传 STEP，获得 `model_id` 和 `revision_id`，立即写回 build。
5. 获得 `revision_id` 后创建 drawing task，获得 `task_id`，写回 build。
6. 两项解析任务分别运行，工作台通过一个聚合状态接口轮询。
7. STEP 完成且图纸达到 `review_ready` 后，build 进入 `sources_ready`。
8. 后续阶段执行字段对齐、YAML 草稿生成、人工审核和发布。

用户只执行一次提交，不直接接触 `revision_id` 和 `task_id`。如果 STEP 上传失败，图纸任务不创建；已上传文件和错误信息保留，允许重试。

## 节点交互

- 分类、图元和版本节点：展开树，并在右侧展示摘要。
- 解析中的 STEP：右侧展示 STEP 阶段、真实进度和错误；不进入 3D 页。
- 已完成的 STEP：点击“查看解析结果”，进入 `/cad-model?revision_id={revision_id}&build_id={build_id}`。
- 解析中的图纸：右侧展示版面检测或字段抽取阶段；不进入图纸页。
- `review_ready` 的图纸：点击“查看解析结果”，进入 `/cad-spec?revision_id={revision_id}&task_id={task_id}&build_id={build_id}`。
- 数据融合节点：后续展示图纸值、STEP 测量值、采用值、置信度和冲突。
- YAML 节点：未生成时展示缺失条件；生成后展示严格按模板十个章节组织的 YAML。
- 发布校验节点：展示必填字段、参数约束、拓扑、几何、端口和 STEP 往返校验。

两个专业页面增加“返回图元建库”，使用 `build_id` 恢复原树节点。直接从菜单进入专业页面时，继续兼容现有列表选择方式。

## 状态模型

Build 状态使用稳定的业务状态，不直接暴露两个解析器全部内部状态：

- `draft`
- `uploading`
- `parsing_sources`
- `source_failed`
- `sources_ready`
- `aligning`
- `review_required`
- `yaml_ready`
- `released`

文件节点保留各自原始状态。父节点聚合优先级为：失败 > 待人工处理 > 解析中 > 已完成 > 未开始。

STEP 已有真实百分比。图纸状态接口当前未完整返回数据库中的 `progress`，第一期以阶段文本为主；只有后端返回真实进度后才显示百分比，不在前端制造模拟进度。

## 路由兼容

CAD 页面启动时：

- 路由存在 `revision_id`：加载模型列表后精确选择对应 revision。
- 路由没有 `revision_id`：保持当前默认选择第一个模型的行为。

图纸页面启动时：

- 路由存在 `task_id`：直接加载该任务及其图像、区域、状态和抽取结果。
- 只有 `revision_id`：保持当前列出该 revision 下 drawing tasks 的行为。

返回工作台时携带 `build_id`，工作台根据该 ID 展开并选中对应版本或文件节点。

## 聚合接口

第一期工作台只依赖少量聚合接口，隐藏底层任务拼装细节：

- `GET /api/component-builds/tree`
- `POST /api/component-builds`
- `GET /api/component-builds/{build_id}`
- `GET /api/component-builds/{build_id}/status`
- `POST /api/component-builds/{build_id}/retry`，请求体必须指定 `role=reference_step|drawing`

创建接口接收业务字段、STEP 和二维参数图，在服务端负责调用现有 CAD 与 drawing 模块。工作台不分别调用两个上传接口，避免出现 build 已创建但前端丢失关联的情况。

## 错误处理

- 文件类型不合法：提交前阻止并指出具体文件。
- STEP 失败：保留 build 和错误，允许仅替换或重试 STEP；图纸保持等待。
- 图纸失败：STEP 结果保持可查看，允许仅重试图纸。
- 图纸需要手工版面：build 显示“待人工处理”，跳转图纸页修正。
- 文件替换：创建新解析记录，旧记录不可被静默覆盖。
- 用户刷新或离开页面：状态由数据库恢复，不依赖前端内存中的轮询状态。
- 聚合状态接口异常：保留最后成功状态，并显示“状态暂时不可用”，不将任务判为失败。

## 第一阶段范围

第一阶段实现：

- ComponentBuild 与目录树所需的最小数据结构。
- 成套上传和聚合状态接口。
- 图元建库工作台及业务文件树。
- STEP、图纸解析状态展示和失败重试入口。
- 精确跳转现有两个专业页面及返回工作台。
- 现有页面继续支持直接使用。

第一阶段不实现：

- ComponentSpec YAML 实际生成和下载。
- generator.py 自动生成。
- GLB、缩略图生成。
- 字段融合审核页面。
- 发布流程和版本差异。
- 多图纸、多 STEP 共同组成一个 build。

这些节点可在树中以禁用状态展示，并明确标记“待生成”或“后续能力”，不能显示虚假的完成状态。

## 验收

- 用户可一次提交一份 STEP 和一份二维参数图，系统建立稳定关联。
- 工作台刷新后仍能恢复树和任务状态。
- STEP 与图纸分别失败时不会污染对方结果，并可独立重试。
- STEP 完成后可精确进入对应 3D 结果，不会误选模型列表第一项。
- 图纸待审核后可精确进入对应 task，不会要求用户重新选择任务。
- 从两个专业页面返回后，工作台恢复原 build。
- 现有单独上传 STEP、从 CAD 页创建图纸任务的流程不回归。
- YAML 和发布节点在未实现时保持禁用，不给出成功假象。
