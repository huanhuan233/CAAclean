# P0 需求、样件与能力基线（2026-10-03）

## 证据与版本

- 开始时基线分支 `main`，HEAD `92824eb788c60df56522581ae4bc53ddb1316dbb`，暂存区为空；用户工作区已有 `caa_new.zip` 和 `cad-spec-work-acceptance` 下若干图片删除，以及未跟踪的 `分析报告.md`。本轮不触碰这些路径。P0 基线单独提交为 `9449d8acbe8d525da52520ea04f6e823e2830850`；本表随后按 P1 实际运行结果更新。
- 原技术方案《三维数模解析与模型比对系统 V1.0 技术方案(2).docx》和《三维数模解析-功能性人天评估表V5.xlsx》在本次附件及仓库中未找到。两份原文的版本、章节、单元格、内容指纹均为 `source_unavailable`。`requirements.json` 的对应摘要来自本次用户粘贴的需求，不冒充原文摘录。
- 用户补充场景来自本次消息：导管、复材铺层、自动铺丝、超塑成形。随后的孔详情截图是界面参考，图中所有数值和时间都不是验收真值。
- 当前实现证据以本地代码为准。既有 `docs/END_TO_END_STATUS.md` 记录历史执行，但其中的历史通过结果不视为本次执行。

## 架构与交付口径

| 职责 | 当前边界 | P1 复用方向 |
| --- | --- | --- |
| 原生采集 | `caa_new` C++03、CAA R21 采集包 | 保留 native 来源与定义/实例身份 |
| 采集适配/持久化 | `CaaNewBundleReader`、`native_persistence`、CadRepository | 复用 Schema 与原生证据通道 |
| 几何辅助计算 | 已保存 STEP、FreeCAD 进程、Feature Center Bundle | 快照绑定资产指纹；不能从 GLB 反推 B-Rep |
| 测量业务 | `app.measurement` 的事实构建、替换与查询 | 交互结果与自动事实分离，复用 `CadMeasurement` |
| 前端 | 现有 Feature Center Viewer/对象详情 | 保留主选择身份，窄面板展示和 Viewer 标注 |

原技术方案提出纯 CAA R21、服务端批处理、原生结果保真；现有 FreeCAD/OpenCascade 是辅助几何处理。`native_only` 无原生算法时必须返回 `unsupported`。CAA R21 与另一处 CATIA V5-6R2021、所谓“10 种几何类型”的实际枚举数、原生非近似与网格/近似计算的关系，都需要原文到手后核对；本轮不猜测客户真实版本。

## 能力矩阵（代码证据，不是生产验收）

`implemented` 表示可定位到代码；`automated_tested`、`fixture_verified`、`frontend_verified` 仅在本轮实际执行后追加。`not_run`、`missing_input`、`unsupported` 分别表示未运行、缺输入、明确不支持。下表的“真实产物/运行”只描述本轮。

| 能力 | 采集/计算 | 写出/DB | API | 前端/定位 | 自动测试 | 真实产物/运行 |
| --- | --- | --- | --- | --- | --- | --- |
| BOM、定义/实例、变换 | `implemented`: `caa_new`、`native_tree_store` | `implemented`: 原生发布 | `implemented`: build viewer/tree | `implemented`: BOM；实例精确几何定位待核 | `not_run` | `not_run` |
| 原生属性、知识参数、标注 | `implemented`: 原生属性/FTA 采集 | `implemented`: property/evidence 表 | `implemented`: 节点详情 | `implemented`: 详情；标注定位需映射 | `not_run` | `not_run` |
| 几何、拓扑、GLB | `implemented`: CAA 拓扑、STEP/FreeCAD | `implemented`: Bundle/部分 DB 证据 | `implemented`: 受控资产 | `implemented`: 映射视具体快照而定 | `automated_tested`: STEP→B-Rep/Bundle | `fixture_verified`: 仓库 STEP 生成新 Bundle；CATIA 未运行 |
| 自动测量、候选特征 | `implemented`: `fact_builder`、Feature Center | `implemented`: `CadMeasurement`、候选表 | `implemented`: CAD 路由 | `implemented`: 旧测量列表 | `not_run` | `not_run` |
| 交互 B-Rep 距离/角度/截面/厚度 | `implemented`: FreeCAD 精确 B-Rep 查询 | `implemented`: 独立交互结果；真实 DB 写入未验收 | `implemented`: 快照/查询/结果 | `implemented`: A/B 会话、窄面板及 Viewer 标注；浏览器实测未运行 | `automated_tested`: 合成有限拓扑/孔洞/空腔 | `fixture_verified`: 3dcad 合成件；真实 CATIA/装配实例未运行 |
| 孔、R、筋、腹板等制造语义 | 部分类别 `implemented`，不代表全部识别 | 因类型而异 | 因类型而异 | 候选高亮不等于原生历史归属 | `not_run` | `not_run` |
| 版本比对、连接关系、部署 | 存量模块需按需求逐项验收 | 因模块而异 | 因模块而异 | 因模块而异 | `not_run` | `not_run` |

## 样件与验收

`fixtures.json` 对现有真实文件只记录来源、类型、指纹和可用性；未核验的预期值为 `null`。仓库内真实 CATPart 与导出的 STEP 不自动视为相同快照。P1 已用 FreeCAD 脚本生成合成参数化件，孔洞、板厚、空腔反例的预期值由生成脚本与测试共同记录；它们不能替代业务样件验收。不同单位等价输入和可信实例映射仍为 `missing_input`。

## 阶段边界

本轮仅执行 P0/P1。F05 专门识别、导管/复材/铺丝/超塑、关系和版本比对保留 P2–P11 追踪；P1 只建立公共几何、查询、测量、持久化和定位能力。详见 `P1_CONTRACT.md`。
