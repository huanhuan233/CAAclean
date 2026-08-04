# 图元库存储管理统一 CAD 接入

## 1. 目录模型

目录接口返回两个同级系统根，而不是在前端拼接航空航天分类：

```text
机械工程图元库（MECHANICAL_COMPONENT_LIBRARY）
航空航天零件库（AEROSPACE_PART_LIBRARY）
```

航空航天零件库包含机体承力结构、壁板与蒙皮、发动机转子、发动机静子与机匣、起落架与作动、管路与连接附件、航天器结构与机构、通用航空航天零件八类。目录 ID 由既有 UUID 命名空间和稳定业务编码生成，多次启动不会重复插入；机械库原有分类编码和 ID 不变。根节点及任意中间节点的数量均为后代 `build` 叶子数量。

前端左侧目录完全读取 `/api/component-builds/tree`，两个根节点使用相同的图标、选中、展开和计数逻辑。首次进入时只展开两个系统根，分类可继续递归展开；前端没有航空航天分类常量。

## 2. 统一上传接口

机械库和航空航天库共用：

```http
POST /api/component-builds
PATCH /api/component-builds/{build_id}
```

源文件字段为 `source_file`，兼容旧调用方的 `step_file`，但两者不能同时提交。支持的真实扩展名为 `.step`、`.stp` 和 `.CATPart`，匹配不区分大小写；`.cart` 明确拒绝。处理路线只由后端检查过的文件名决定，客户端不能指定或伪造。

上传阶段会完成文件名安全检查、目录归属校验、SHA-256、源文件保存、零件记录和持久 Revision 任务创建。HTTP 请求只返回任务标识，不等待 CATIA 或 FreeCAD 完成。

响应中的关键字段为：

```json
{
  "part_id": "...",
  "task_id": "...",
  "source_format": "STEP",
  "processing_route": "step_cad_parse",
  "status": "queued"
}
```

## 3. 处理编排

统一编排器只负责识别格式、调用现有入口、保存阶段和校验产物，不复制几何算法。

```text
STEP/STP
→ 既有 CadService / FreeCAD 解析
→ 既有 Feature Center Sidecar
→ Bundle 与 GLB

CATPart
→ 既有 R21 CAA Batch
→ CATIADocument.ExportData(path, "stp")
→ 既有 Feature Center Sidecar
→ Bundle、GLB 与映射
```

任务阶段持久化在 `CadModelRevision.parse_manifest.ingest` 中，包含源格式、处理路线、当前阶段、进度、错误码、源 SHA-256 和 Viewer 资产定位。阶段至少区分 `queued`、`parsing`、`exporting_step`、`feature_center_processing`、`lightweighting`、`ready` 和 `failed`。

CATIA 路线使用单进程信号量，避免同一 Web 进程并发启动多个 R21 会话。CATIA、许可证或 Sidecar 不可用时保留原始 CATPart，并写入失败阶段和可读错误码；不会生成假 GLB，也不会把上传成功投影为解析成功。

当前轻量任务采用应用进程内后台协程和数据库持久状态，没有引入 Celery/Redis。服务重启时中断任务会由既有恢复逻辑标记为失败，用户可从同一记录重试；当前不承诺跨进程自动续跑。多 Web 进程部署时，CATIA 的全局单 Worker 约束仍需由部署层保证。

## 4. 统一 Viewer 契约

两条处理路线最终共用：

```http
GET /api/component-builds/{build_id}/viewer
GET /api/component-builds/{build_id}/viewer/assets/{asset_path}
```

契约提供 GLB、场景清单、Face–Mesh 和 Feature–Mesh 映射的受控 URL；前端不会接触服务器绝对路径。资产接口采用白名单并校验目录穿越。只有 Revision 为 `completed/ready` 且必要资产都存在时才返回可用 Viewer。

STEP 没有可信 Feature Center 特征时返回 `feature_center.available=false`，Viewer 仍正常显示几何。CATPart 具有可信 Canonical Feature 时继续使用既有 Feature → Face → Primitive 高亮和 Face → Feature 反查；没有可信特征时明确显示“暂无可信 Canonical Feature”，不伪造识别结果。

## 5. 本机真实验收

2026-08-04 使用同一统一接口处理了同一零件的两种来源。

### STEP

- 源文件：`KUANG (2).stp`
- part_id：`8b52fe82-3582-44cd-8a36-78bcfd3625e3`
- task_id：`e33145cf-8599-4734-a39a-5b34af467ee8`
- 源 SHA-256：`5bca06f897df4d5f0ca8aaed3325b84d3537ded833e780acff3283c040746402`
- 路线：`STEP / step_cad_parse`
- GLB：1,276,344 字节，SHA-256 `98f828ee2d05225d3c5bba8f7e07b796b29a1f6395e0842bad1b71de1eff2076`
- 结果：`ready`，受控 GLB 和两个映射 URL 均返回 HTTP 200，浏览器创建 1 个 WebGL Canvas。

### CATPart

- 源文件：`kuang.CATPart`
- part_id：`97ef202b-e87c-45bb-9714-13886c6467eb`
- task_id：`ee13d500-59e5-4b69-abea-e5eb6f9bbb32`
- 源 SHA-256：`41f07f1f51b6cc6330f0f7385edc3ba2bdae93a71973e058679fd9db2269bc94`
- 路线：`CATPART / catia_feature_center`
- CAA：941 个 Feature、1880 条关系、228 个参数、25 个声明式业务特征；Typed 233、Generic 708、Opaque 0、Failed 0。
- 导出 STEP：3,612,502 字节，SHA-256 `1c1521fb81902442ddf6ccc50ebe4bde6567014981d7d2c3560bd8fe453719b2`。
- GLB：1,943,464 字节，SHA-256 `23a30e45e2130c0ef0cbbbef820f4aa6844d7be4f2434de9c6a9bc581a6f0698`。
- 结果：`ready`，受控 GLB 和两个映射 URL 均返回 HTTP 200，浏览器创建 1 个 WebGL Canvas。
- 本样件实际 Canonical Feature 数为 0，页面仍显示真实轻量化模型并如实提示无可信特征。

同一 Revision 的重复重试会由进程内任务登记表去重，避免两个 Sidecar 同时争用事务式输出目录。Windows 子进程错误输出同时兼容 UTF-8 和本机代码页，页面不会再把“Feature Center 输出目录已存在”显示成乱码。任务只有在 Bundle、GLB 和映射文件全部校验后才进入 `ready`。

### 同件几何对照

对照容差为 0.01 mm。两条路线的唯一实体数量均为 4，GLB 头可加载；包围盒最大差约 0.000189 mm，尺寸、中心和实体体积均在容差内，结果为 `match`。该检查用于发现单位错误、空模型和严重几何丢失，不是完整的模型版本比对。

## 6. Feature Center 页面状态

Feature Center 仅展示 CATPart/CATIA 处理结果，STEP 始终进入 CAD 模型解析页。顶层菜单只保存“上一次真实成功 CATPart”的 `build_id`，不缓存或构造模型数据；没有成功记录时仍保留页面头部、三项导航栏、Viewer 外壳和右侧详情外壳，只不填充对象数据。独立 CATPart 的右侧详情由真实对象类型驱动，不显示数量、所属组件、装配层级或定位状态等装配实例字段。

一级菜单继续保留图元建库、CAD 模型解析、Feature Center、二维图纸解析和专利附图标注。CAD 模型解析页只移除左侧“模型列表”，上传、刷新、装配/BOM、特征和几何拓扑入口仍保留。Feature Center 左侧折叠栏也固定保留装配结构、特征、几何拓扑三个入口和展开按钮。

### 右侧详情分组

详情面板只看“当前对象类型”和“是否存在真实装配上下文”，与 BOM 树当前是否展开无关。

| 当前对象 | 详情分组 |
| --- | --- |
| 独立 CATPart | 零件属性、来源与特征、操作、高级拓扑信息 |
| 独立 STEP | 零件属性、来源与识别结果、操作、高级拓扑信息 |
| 装配中的 CATPart/STEP 实例 | 零件属性、装配实例属性、来源、装配定位、操作、高级拓扑信息 |
| 总装或子装配 | 装配属性、装配统计、定位信息（有真实数据时）、操作 |
| 设计特征 | 特征属性、参数、关联面、操作 |
| Face、Edge、Vertex | 几何属性、拓扑归属、关联特征、操作 |

独立零件不补 `数量=1`、所属组件、层级或“已定位”。CATPart 只有在原生特征和 Feature–Face 映射都真实可用时才启用“查看原生特征与关联面”；STEP 使用“查看识别特征与关联面”，没有映射时禁用。

## 7. 本机配置

后端从 `backend/.env` 读取已有 FreeCAD 和工作目录配置，并使用：

```text
CAA_RADE_ROOT
CAA_PREREQ_ROOT
CATIA_WORKER_MODE
CATIA_WORKER_URL
CATIA_WORKER_JOB_TIMEOUT
```

Python 依赖运行在 Conda 环境 `3dcad`。密钥、账号、本机绝对工作路径和上传源路径不进入业务响应或本文档。

本机启动顺序如下，端口按部署配置调整：

```bat
conda activate 3dcad
call 3DjiexiCAA\tools\start_catia_worker.bat
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 5180
```

Worker 健康检查：

```bat
call 3DjiexiCAA\tools\check_catia_worker.bat
```

当前后台任务运行在 Web 进程内。服务重启会中断正在运行的 Sidecar，任务会进入可重试失败状态；多 Web 进程部署还需要外部的单 Worker 调度约束。
