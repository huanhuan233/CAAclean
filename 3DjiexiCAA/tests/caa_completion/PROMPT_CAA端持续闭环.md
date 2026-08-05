# 给 Codex 的总提示词：持续实现与实机回归，直到 CAA 端闭环

你现在位于 `D:\3Djiexi\3DjiexiCAA`（若实际路径不同，以当前仓库根目录为准）。用户要求你继续实现 **Python 制造特征识别之前的 CATIA V5R21 CAA/C++ 数据出口**，并持续运行真实样件，直到 CAA 端满足完成门槛。

测试包已放在：

```text
tests\caa_completion\
```

先完整读取以下文件，不要只读摘要：

```text
tests\caa_completion\README_CN.md
tests\caa_completion\spec\CODE_AUDIT.md
tests\caa_completion\spec\CAA_COMPLETION_GATES.md
tests\caa_completion\spec\fixture_catalog.json
tests\caa_completion\spec\current_contract.json
tests\caa_completion\spec\completion_contract.json
tests\caa_completion\tools\validate_caa_outputs.py
tests\caa_completion\tools\run_full_suite.ps1
```

然后完整检查当前源码和真实输出，尤其是：

```text
CadParseMvp.edu\CadParseMvp.m\src\CadParseContracts.h
CadParseMvp.edu\CadParseMvp.m\src\CadParseCAA.h
CadParseMvp.edu\CadParseMvp.m\src\CadParseCAA.cpp
CadParseMvp.edu\CadParseMvp.m\src\CadParseCore.cpp
CadParseMvp.edu\CadParseMvp.m\src\CadParseIR.cpp
CadParseMvp.edu\CadParseMvp.m\src\CadParseSelfTests.cpp
CadParseMvp.edu\CadParseMvp.m\src\CadParseBatch.cpp
CadParseMvp.edu\CadParseMvp.m\Imakefile.mk
CadParseMvp.edu\IdentityCard\IdentityCard.h
docs\CAA_SCOPE_STATUS.md
```

## 一、范围固定

本任务包括：

- CATPart/CATProduct 原生规格树、容器、Reference/Instance、属性和更新状态；
- 专用 Native Feature Decoder 与新特征注册中心；
- ResultOUT、完整 B-Rep/解析几何和拓扑邻接；
- Feature↔Face/Edge/Vertex 权威正反向关系；
- FTA/MBD 逐类语义、TTRS/几何引用和 FTA↔Topology；
- Face↔Triangle range 的 CAA sidecar；
- 属性/测量、声明式紧固/密封/胶接数据保真；
- 给后续版本比对提供稳定且足够的 CAA 证据；
- 真实 V5R21 样件生成、重新打开验证、解析、双跑确定性和能力矩阵。

本任务不包括：

- Python 制造特征识别、AAG/eAAG 最终推断算法；
- 前端、Web 高亮和交互；
- GLB Writer 本身（但 CAA 必须输出无猜测可消费的 Face→Triangle 契约）；
- STEP 识别结果冒充 CATIA 原生设计语义。

`manufacturing_feature_recognition` 必须继续为 `not_performed`。不要再把“Python 未完成”或“前端未联动”列为这次 CAA 范围的未完成项。

## 二、当前基线事实

当前提交是 `cad_parse_mvp_v9 / 1.9.0`，已经有：

- Hole/Pad/Pocket 专用 Decoder；
- 最终主实体 Cell/Wire 基础输出；
- ResultOUT summary 和 per-cell 输出；
- 中心+面积的 Feature Result→最终 Face 候选匹配；
- TPS Set 和组件通用接口观测；
- Face→Triangle range 前置数据。

但以下仍不是 complete：

- 其它原生 Feature Decoder；
- 完整曲面/曲线/UV/法向/材料侧/曲率/凹凸/连续性；
- 权威 Feature↔Topology；
- FTA 逐类语义和 FTA↔Topology；
- CATProduct 多实例；
- 注册中心可审计导出；
- 全矩阵真实样件验证。

不要删除或弱化测试来维持 `partial`。目标是把能力真正做到 complete。

## 三、持续循环规则

从现在开始执行下面的循环，**不要在某个小阶段完成后停下来问用户是否继续**：

1. 运行 baseline，记录当前失败；
2. 选择当前最高优先级的最小失败集合；
3. 先补自测/契约断言，再实现；
4. R21 `mkmk` 编译；
5. `--self-test`；
6. 生成或更新真实 CATPart/CATProduct；
7. 关闭并重新打开样件做 Automation 独立验证；
8. 每件解析两次；
9. 运行 completion validator；
10. 修复本轮失败并再次执行；
11. 小里程碑通过后提交本地 Git；
12. 继续下一失败集合，直到总门槛通过。

基础命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\caa_completion\tools\run_full_suite.ps1 `
  -RepoRoot (Get-Location).Path `
  -Mode baseline

powershell -ExecutionPolicy Bypass -File .\tests\caa_completion\tools\run_full_suite.ps1 `
  -RepoRoot (Get-Location).Path `
  -Mode completion `
  -SkipGenerate
```

生成器中的 `auto_probe` 若因 R21 方法签名不同失败，必须以本机已安装的：

- PublicInterfaces / PublicGenerated 头文件；
- CAA Encyclopedia 示例；
- V5 Automation 类型库/帮助；
- 合法录制宏；

为证据修正脚本并重新生成。不要因为一次 COM 错误就删除该样件行。若确实受许可证阻塞，继续完成其它门槛，并在 `generation_ledger.tsv` 和最终矩阵中记录运行时版本、许可证/Workbench、方法、HRESULT 和复现步骤。

## 四、实现优先级

### P0：测试基础和真实入口

1. 让测试包的离线 lint/unit tests 全过。
2. 修正生成器在本机 R21 的真实 Automation 差异；保持“失败不冒充生成”的语义。
3. 扩展 Batch 输入识别：CATPart 和 CATProduct 分流；不再把 CATProduct 当 CATPart 静默部分解析。
4. Schema 至少升级到 completion contract 要求的代次；Manifest 对全部新增 artifact 计 Hash/size。
5. 所有新增记录必须是 C++03/VS2008 可复制的纯数据，CAA 指针不得越过会话边界。

### P1：新特征注册中心与专用 Decoder

实现并导出 `decoder_registry.json`，每个条目至少包含：

```text
decoder_id
decoder_version
priority
candidate_startup_types
candidate_super_types
required_interface_keys
payload_type
payload_schema_version
r21_support_status
parameter_fields
failure_policy
```

实际 `native_features.jsonl` 必须引用 `decoder_version/payload_type/payload_schema_version`。

按 `completion_contract.json.native_decoder_families` 逐类实现，不得把同族整组一次性标 complete。每类都要：

- 专用 Public R21 接口证据；
- Typed Payload；
- 参数适用性/单位/原始枚举；
- renamed 正例；
- 几何相似反例；
- unsupported/query exception/required read exception；
- output Golden；
- 真实 CATPart 重新打开验证。

Generic/Opaque 必须保留完整 TypeFingerprint、StartUp/SuperType/接口键和诊断；不得丢对象。

### P2：完整 B-Rep 与解析几何

扩展现有 `NativeTopologyCellRecord` 或引入规范化子记录，达到 completion contract。至少包括：

```text
Solid/Shell/Body/Face/Loop/Wire/Edge/Vertex 归属
surface_type / surface_parameters
curve_type / curve_parameters
parameter_domain / UV bounds
periodic / closed
orientation / material_side
outer_wire / inner_wires
center / centroid / bounding_box
area / length
normal_samples / controlled curvature samples
shared-edge adjacency
dihedral_angle
convex / concave / tangent / unknown
G0 / G1 / G2 / unknown
```

凹凸关系必须结合法向、材料侧和二面角，不能由 Mesh 法向猜测。无法可靠取得 G1/G2 时写 unknown 和证据，不得伪造。

处理全部 Body/Shell/Solid，不得只取 `CATIPrtPart::GetSolid()` 后丢弃其它实体或曲面。空 Part、无实体、仅曲面、多 Body、退化/小面反例必须稳定输出。

### P3：权威 Feature↔Topology

当前 `center+area` 只能保留为候选辅助证据。继续查证并使用 R21 Public 的 Generic Naming、Selection Reference、Result/历史追踪或等价权威链路，输出：

```text
mapping_status = confirmed|candidate|ambiguous|unmatched|...
authority
persistent_reference
relation_kind = generated|modified|consumed|split|merged
mapping_direction
```

要求：

- Feature→最终 Face/Edge/Vertex；
- Face/Edge/Vertex→一个或多个 Feature；
- 一对多、多对一；
- 后续圆角/倒角/Boolean/Pattern 修改；
- 前序 Face 消失和 Edge 被消耗；
- rebuild 后枚举编号变化仍可审计；
- candidate 不进入 complete 计数。

任何无法确认的映射必须保留为 candidate/ambiguous，不允许改状态字符串骗过 validator。

### P4：FTA/MBD

不要停在 `CATITPS`、`CATITPSSemanticValidity`、`CATITPSTextContent` 的通用观测。按真实 R21 Public 接口逐类支持：

```text
dimension
limit_deviation
geometric_tolerance
datum / datum_reference_frame / datum_target
surface_roughness
text
flag_note
NOA
annotation_view
capture
```

`fta_semantics.jsonl` 输出规范 Payload；`fta_topology_links.jsonl` 输出 TPS/TTRS/UserSurface/Geometry reference 到最终 Face/Edge/Vertex/轴线/基准平面的权威链路。

验证：有效关联、同一 TTRS 多几何、孤立/失效引用、Feature 被抑制、内容不变但关联面变化。真实 FTA 样件为空时不能把能力写 complete。

### P5：CATProduct 多实例

输出 `product_references.jsonl` 和 `product_instances.jsonl`：

```text
Reference/Instance 分离
reference_id / instance_id / parent_instance_id
instance_path
PartNumber / Revision
suppressed / load_status / broken reference
4×4 transform
同一 CATPart 多实例
嵌套装配
同 PartNumber 不同 Revision
DM 与 R_ 节点
```

全局引用必须以 `instance_id + part-local id` 消除不同实例之间冲突。CATPart 本地 `F000001` 或 `TB000001_F000001` 不能直接冒充装配全局 ID。

### P6：Mesh sidecar、属性与业务连接

`native_mesh_face_map.jsonl` 必须做到：

- range 非负、连续、无重叠；
- triangle count 自洽；
- 每个 primitive/range 只指向一个最终 Face；
- orientation 可审计；
- GLB Writer 不需要几何猜测即可使用。

补齐体积/面积/质量/密度/重心/惯性/包围盒、单位和值来源。

声明式业务层继续和原生制造特征分离。扩展紧固两条路径、多个紧固点、`K_密封定义`、`M_胶接定义`、嵌套和缺失字段反例；字段必须来自真实树/参数，不可从 fixture 文件名回填。

### P7：版本证据和全矩阵

V1/V2 比对算法不属于 CAA，但 CAA 必须让这些变化在稳定 IR 中可见：

- BOM 增删/数量；
- 实例移动/旋转；
- PartNumber/Revision/属性；
- Feature 增删/参数；
- 几何/拓扑；
- FTA 内容及关联；
- 紧固/密封/胶接。

对 `fixture_catalog.json` 每一行生成报告。不能把缺样件的行从 Catalog 删除，也不能把多种类合并后用一个 count 代表全部通过。

## 五、强制真实性规则

1. Native Feature 样件必须是 CATIA 原生历史；STEP 只能作为无原生历史反例。
2. 类型确认必须来自专用接口 QueryInterface/等价公开语义，不得依赖 display name。
3. FTA 必须是真 TPS/Annotation 对象；普通 String 参数不算 FTA。
4. CATProduct 必须是真装配实例；复制两个 CATPart 文件不算同 Reference 多实例。
5. 每个生成脚本保存后必须关闭并重新打开验证。
6. Fixture verifier 的期望只能用于断言，不能注入 parser 输出。
7. 不得硬编码样件对象数量、固定 feature_id、固定 face_id、固定坐标来让产品代码通过。
8. Public API 未验证时使用 `TODO(R21_API_VERIFY)` 和 partial/unsupported；禁止使用 ProtectedInterfaces。
9. 对象级异常必须隔离；单个 Decoder/TPS/Body 失败不应使整个文档无输出，但必须有诊断和失败计数。
10. 保持只读打开，不保存或更新用户输入模型。

## 六、Git 与报告规则

- 先检查工作区；保留用户已有改动，不覆盖无关文件。
- 每个里程碑只提交与该里程碑相关文件；提交信息示例：

```text
feat(catia): export decoder registry metadata
feat(catia): extract analytic brep geometry
feat(catia): map native feature history to final topology
feat(catia): extract fta semantics and topology links
feat(catia): traverse catproduct instances
test(catia): complete r21 native fixture matrix
```

- 不推送远端，除非用户明确要求。
- 不把 `selftest_output_*`、生成 CATPart、结果目录、构建对象提交到源码；只提交生成器、验证器、必要小型合法 fixture（若仓库策略允许）、契约和文档。
- 每轮更新 `docs/CAA_SCOPE_STATUS.md`，但状态只能由 suite 结果支持。

## 七、允许停止的条件

只有两种：

### A. 真正完成

```text
tests\caa_completion\results\suite_summary.json
overall_status = PASS
missing_reports = []
FAIL = 0
BLOCKED = 0
```

且 R21 build、自测、所有真实样件、双跑 Hash、无残留进程全部通过。此时按类别给出能力矩阵和提交列表。

### B. 真正外部阻塞

仅限缺失许可证/Workbench、合法样件无法建立、已安装 R21 Public API 确实不提供所需链路或受保护权限阻断。停止前必须：

- 已完成所有不受该阻塞影响的门槛；
- 给出精确 API/头文件/Framework/访问级别或 HRESULT；
- 给出复现命令和最小样件；
- 在 suite 中保持 BLOCKED；
- 明确说明因此 **CAA 端尚未 complete**。

普通编译错误、脚本错误、一次 API 调用失败、测试失败、样件尚未生成，都不是停止理由。继续修复并重复循环。

现在开始：先跑 baseline，给出首轮失败分组，然后直接进入实现和实机回归，不要只写计划或重新汇报现状。

