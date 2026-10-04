# 三维语义端到端状态与验收（2026-10-03）

> 2026-10-04 P6A 首批：新解析的多导入对象 STEP 可按已放置 Solid 计算距离、正间隙、受限平面接触和实体干涉；原生 CATProduct occurrence→定义 B-Rep 映射仍缺失，不能声称装配实例精确分析，详见 [P6A 验收](development/P6A_ASSEMBLY_GEOMETRY_ACCEPTANCE.md)。

> 2026-10-04 P5 修复：文档归属改用采集会话的原生对象身份，文本/TPS 分类、尺寸单位、公差带字段和 PMI 产物完整性已修正；真实非空 R21 FT&A 样件与 TTRS 到几何的目标映射仍未验收，详见 [P5 验收记录](development/P5_MBD_ACCEPTANCE.md)。P6 对这些未核实引用保持限制。

> 2026-10-04 P5 产品属性/MBD：R21 CAA 采集、类型字段、PostgreSQL/API 和窄侧栏详情的实际支持范围与 `not_run` 项见 [P5 验收记录](development/P5_MBD_ACCEPTANCE.md)。几何识别确认选区为主题色，候选/待复核为警告黄色；未建立 TTRS 到 GLB 面的映射时不伪造 MBD 精确定位。旧包缺少新增字段时需要重新只读采集。

> 2026-10-04 识别特征浏览器 UI：左侧“特征 → 识别特征”使用当前 PostgreSQL API 的 Canonical Feature 分页结果，按 family/subtype 显示中文名称和有证据的短标签；`feature_center_id`、原始枚举与复核状态不改写。`auto_verified` 显示“自动核验”，`needs_review` 显示“待复核”；子类型或结构角色仍为候选却与自动核验矛盾时显示“状态需核实”。搜索仅覆盖已加载记录，底部分别显示服务端总量与已加载量；当前版本有实际映射的候选范围可随选择高亮和三维预览，界面标为“候选范围预览”。2026-10-04 实际浏览器用 build `35a05c3a-8983-4f7b-93c0-caca3b587025` 的 221 条结果核查了约 320px 左栏、分页追加、筛选弹层、ID 搜索、圆角与薄板候选的选择及右侧标题联动。380/440px 与暗色主题的视觉复核 `not_run`；该样件未覆盖所有 P4 类别和长名称。此次仅改变展示，旧识别结果无需重新采集或补算。

> 2026-10-04 P3/P4 判定收口：正间隙、孔端局部边界、真实裁剪面、薄壁配对和组合测量预算的修正与验收范围见 [几何正确性修复记录](development/P3_P4_CORRECTNESS_HARDENING.md)。旧算法结果可查看；发布新版状态前需从保存的 STEP 几何重新解析并重新识别、计算组合测量。此修复不需要重新采集 CATIA 原生参数。

> 2026-10-04 P4 增量：P3 方向/角向/材料区间与默认高亮修正见 [P3 验收](development/P3_GEOMETRY_ACCEPTANCE.md)；P4A 四个标准子类见 [P4A 验收](development/P4A_STANDARD_STRUCTURES_ACCEPTANCE.md)；P4B 薄壁和结构角色候选见 [P4B 验收](development/P4B_THIN_STRUCTURES_ACCEPTANCE.md)；P4C 凹圆角和组合距离见 [P4C 验收](development/P4C_COMBINED_ACCEPTANCE.md)。以下早期矩阵是历史基线，不代表 P4 当前执行。P4 合成 STEP、实时 PostgreSQL 入库/查询、浏览器单个合成件的识别列表/筋条详情及连线、前端类型检查/构建已执行；真实业务件与其余子类的浏览器视觉定位仍待验收。

> 2026-10-04 第二开发包更新：P1 几何查询修正见 [P1 修正](development/P1_HARDENING.md)；R21 原生圆角/倒角/草图的新采集证据见 [P2 验收](development/P2_NATIVE_ACCEPTANCE.md)；纯 STEP 孔、直边圆角/倒角的范围与限制见 [P3 验收](development/P3_GEOMETRY_ACCEPTANCE.md)。下方早期矩阵保留历史记录，不能覆盖上述较新验收状态。

> P1 公共几何查询的本轮执行与限制见 [P1 验收记录](development/P1_ACCEPTANCE.md)。本页下方保留此前基线记录；其中的历史执行数不代表 P1 本轮重新运行。

本页记录本轮代码的能力边界。CAA 源码/历史样件证明“采到了”不等于当前工作树已重新编译、已入库、已在浏览器验收。`caa_new/docs/legacy_migration_matrix.json` 是 CAA 迁移审计的机器可读来源；本页补充后端、数据库、Feature Center 与前端的接通状态，不改写旧审计结论。

## 实际链路与深模块边界

| 边界 | 输入 → 输出 | 隐藏的复杂性 |
| --- | --- | --- |
| `caa_new` C++ 采集 | 只读 CATPart/CATProduct → `caa_capture_v1` 包 | CAA 生命周期、定义/出现位置、属性、拓扑、专用 Decoder、32 位 ABI |
| `CaaNewBundleReader` | 新/旧采集包 → 定义级原生语义与规范拓扑 | Schema 选择、旧字段别名、语义投影去重、实例上下文、坏文件诊断；CLI/入库共用 |
| `native_persistence` + `CadRepository` | 统一记录 + Revision → PostgreSQL 快照和发布标记 | 批量写入、旧证据保留、事务回滚、类别计数；不在 Vue 读取 JSONL 语义兜底 |
| Feature Center | 规范 Hole + 保存的 STEP/FreeCAD 结果 → Canonical、测量、面链接、GLB | 几何核验、STEP 面 ID 与原生面 ID 区分、局部/全局坐标安全规则 |
| `ComponentBuildService` | Build/Revision/选中节点 → 数据库详情和选择候选 | 对象、树出现位置、实例、属性与定义级语义对应；按选中节点查询 |
| Feature Center 前端模块 | API DTO + 受控 GLB/映射资产 → 树、详情、选择与高亮 | 请求取消/版本缓存、主选择、可信映射、主题色及材质恢复 |

依赖方向是采集包适配 → CLI/持久化/服务 → HTTP/页面。`features.jsonl` 是旧树投影，不是 Hole/Pad/Pocket 专用参数的权威来源；新包的定义级专用参数以 `native_features.jsonl` 为规范投影，`semantic_facets.jsonl` 不再重复计数。树 occurrence、对象 definition、产品 instance、原生 topology face、STEP render face 均保留不同身份。

## 能力矩阵

状态术语：`implemented` 是代码已接通；`automated_tested` 是本轮隔离测试通过；`fixture_verified` 是本轮读取真实已保存样件；`frontend_verified` 需真实浏览器操作；`not_run` 不得解释为通过。

| 能力 | CAA 采集与参数 | 入库/详情 | 前端与映射 | 本轮证据/剩余限制 |
| --- | --- | --- | --- | --- |
| 原生树、定义/实例 | 既有 CAA 输出；定义与出现位置分离 | 树、属性和原生证据同一事务发布；按节点查详情 | 懒加载树；Revision+节点缓存 | `automated_tested`；复杂重复装配真实浏览器 `not_run` |
| Hole | 专用类型、直径、原点/方向、限制、头/螺纹按实际采到的字段保留 | 规范 `native_features` JSONB；设计值与 B-Rep 测量分开 | 参数可读；仅同 shape hash 且核验通过的 Canonical 映射可确定高亮 | 真实保存的 `holes_typed_payload_migration` 包读到 5 条带载荷 Hole，属 `fixture_verified`；本轮 CAA 未重编 |
| Pad/Pocket | 已有专用 Prism 载荷 | 同一规范输入、入库和按节点详情 | 真值、false、null、缺失状态分别呈现 | `automated_tested`；不伪造新的 Canonical 识别器 |
| 其他原生类型 | CAA 泛型/type-only/generic 状态 | 类型及属性可读；不把泛型当专用解码成功 | type-only 有缺口提示 | `automated_tested`；专用参数缺失如实说明 |
| 导管、复材、公式、可用标注 | 既有 `property_facts` 通道 | 同原生属性表和详情分组 | 沿现有属性面板显示；不生成机床程序或有序铺层边界 | 历史复材样件记录见 `SEMANTIC_CAPTURE.md`；本轮非空 FTA `not_run` |
| 拓扑/几何 | body/solid/face/edge/vertex、wire/coedge 等已有通道 | `topology_kind` 在适配边界规范为 `kind`，原始类型保留 | 统一类别；未知不默认归面/体 | `automated_tested`；NURBS 大载荷仍按需取，不在树节点塞满 |
| 选择与显示面 | ResultOUT/最终面候选仍是证据，不是历史归属 | 候选保留原状态；跨原生/STEP ID 不按字符串猜测 | 面为主选择；候选范围点击后预览高亮，右侧明确提示误选风险；单零件无定位映射时可预览整件但不宣称精确；主题色 | 单元测试 `automated_tested`，真实浏览器 `not_run` |
| Hole 几何核验 | 原生设计参数 + STEP B-Rep | 单零件可用既有 verifier；装配局部坐标无实例变换时 `needs_review` | 未定位参数仍可看，不会假亮 | `automated_tested`；没有实施装配实例坐标变换 |
| 纯 STEP | 无 CAA 原生语义 | 不造 NativeHoleDecoder | 保留原有 GLB 和可用识别范围 | 原有链路保留；本轮真实纯 STEP `not_run` |

类型识别、专用参数解码、B-Rep 测量、几何核验、渲染映射、建模历史归属、参数化重建是七个不同结论。当前没有把 Pad/Pocket 自动识别、ResultOUT 存续关系或候选映射升级成历史归属。

## 旧结果恢复

从 `backend` 目录执行，默认只读且必须限定范围：

```powershell
python -m scripts.backfill_native_evidence --revision <Revision-UUID>
python -m scripts.backfill_native_evidence --revision <Revision-UUID> --apply
python -m scripts.backfill_native_evidence --revision <Revision-UUID> --apply --recompute
python -m scripts.backfill_native_evidence --all
```

`--apply --all` 是显式全量写入，不是默认行为。检查输出会区分 `backfill`、`recompute`、`insufficient_source`。仅回填使用已保存的原生和 Feature Center 包，不运行 CATIA；树、属性、原生证据和 Feature Center 结果按实际存在的通道分别入库，缺少可选通道不阻止其他通道，失败通道会单独报告。旧包有 Hole 专用载荷但识别文件为空时，仅回填仍会保存可用证据并标明识别待补算；有 `exported.stp` 时可显式 `--recompute`。补算调用现有 Feature Center/FreeCAD 管线写入新的暂存目录，验证后切换固定资产目录并发布数据库；旧目录保留为 `feature-center-previous-*`，失败时回滚目录及数据库发布。不会删除源 CATIA、STEP 或旧结果；空识别结果不记为已修复。

## 本轮验证与未验证

- 已保存真实采集包读取：`caa_new/test-output/holes_typed_payload_migration`，Schema `caa_capture_v1`，275 个定义，其中 NativePadDecoder 1、NativeHoleDecoder 5、NativePocketDecoder 1；5 个 Hole 均带 `native_hole`。这是 `fixture_verified`，不是本轮 CATIA 重跑。
- 隔离自动测试：适配、原生发布、详情、Feature Center CLI、Hole 融合、恢复计划、前端选择/详情/缓存均有新增测试；最终命令与完整结果以本轮交付回复为准。
- 本轮全后端套件曾得 306 passed、15 failed、5 skipped。失败涉及未改的图纸 API/视觉凭据及工作树缺少的 XMS06 STEP/脚本等；不能记为全套通过。相关后端 83 项、前端 Feature Center 66 项测试及 TypeScript 类型检查通过。
- 已在本机 PostgreSQL 对保存有完整/部分采集包的 11 个 Revision 实施幂等回填，均无通道错误；最大一份为 34,191 条原始特征、16,706 条规范原生定义。其余 31 个 UUID 工作目录没有可发布保存包，已跳过。旧 Feature Center 包的规范识别数确为零，此次没有伪称识别成功，也没有自动补算。
- 当前机器本轮没有重新编译/运行 CAA x86 或 x64，也没有真实浏览器逐项验收；这些状态均为 `not_run`。x64 调用配置有代码和 PE 测试，但本机只有 x86 CAA 编译/运行条件，不能称 x64 已验收。
