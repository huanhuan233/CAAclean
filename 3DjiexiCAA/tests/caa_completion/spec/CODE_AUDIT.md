# 当前提交代码审查摘要

本摘要直接来自随包提供的 `3DjiexiCAA.zip`，用于约束测试适配，不代替真实 V5R21 运行。

## 已确认实现

1. `CadParseBatch.cpp`
   - CLI：`--input`、`--output`、`--read-only`、`--pretty`、`--include-source-path`、`--self-test`。
   - 非 self-test 仍按 CATPart 入口准备元数据，尚无 CATProduct 专用参数或装配遍历模式。
2. `CadParseCAA.cpp`
   - 已注册 `KnowledgewareStringParameterDecoder`、Hole/Pad/Pocket Decoder 和基础容器 Decoder。
   - 通过 `CATIPrtPart::GetSolid()` 枚举最终主实体。
   - 通过 `CATIShapeFeatureBody::GetResultOUT()` / `CATIGeometricalElement::GetBodyResult()` 取特征结果体。
   - 当前 Result Face→最终 Face 使用中心+面积几何指纹，输出候选、歧义、未匹配，不是权威 Generic Naming。
   - FTA 当前扫描 TPS Set 和组件的通用接口观测，未逐类提取尺寸/GD&T/基准/粗糙度，也未建立 TTRS/几何引用到最终拓扑。
3. `CadParseContracts.h`
   - `NativeTopologyCellRecord` 现有字段只覆盖 cell 基础、中心、面积/长度、边界和邻接。
   - 缺 surface/curve 解析类型与参数、UV/参数域、周期/闭合、法向/材料侧、曲率采样、连续性和二面角/凹凸关系。
   - `NativeFeatureTopologyLinkRecord` 缺生成/修改/消耗语义、权威命名证据、跨版本持久键和完整反向来源集合。
4. `CadParseIR.cpp`
   - 实际写出 14 个有 Hash 的核心 artifact 及 `manifest.json`、`coverage.json`、`diagnostics.json`、`parser.log`。
   - `capabilities.json` 将拓扑、Feature 映射、Mesh 映射保持为 `partial`，FTA–Topology 为 `not_available`，这一点是诚实的。
   - `native_features.jsonl` 的 `part_id`、`body_id` 为空，`instance_id=null`，`references` / `result_topology_refs` 为空。
5. 已有自测
   - Registry 选择、冲突、异常隔离、Generic/Opaque 回退、Hole/Pad/Pocket 合成读取和输出确定性已有覆盖。
   - 真实环境仅有 Hole 样件与 `kuang.CATPart` 报告，不能覆盖新增目标。

## 测试包必须揭露的缺口

- 其它原生类型落到 Generic/Opaque，而非逐类 Typed Decoder。
- 最终 Face 只有几何候选 link，后续特征修改/消耗、Face 分裂/合并和一对多/多对一无法权威表达。
- Face/Edge/Wire 没有足够的 AAG/几何证据。
- FTA “Set 非空”不等于八类标注语义完成；`validation_text` 也不能代替标准字段。
- 当前 CATPart 主链路不能证明同一 Reference 的多实例路径与 4×4 变换。
- `native_mesh_face_map` 必须检查范围连续性、无重叠、计数一致和统一 `face_id`，仅文件非空不够。
- 注册中心需要输出可审计 Decoder 目录、Payload Schema/version、优先级/冲突和类型继承命中证据；仅 C++ 中 `Register()` 不够。

## 不能接受的“修复”

- 用 display name、文件名、树路径或几何类型猜原生 Feature 类型。
- 把 STEP 导入体当成 Pad/Fillet/Pattern 等原生 Decoder 样件。
- 把 geometry-fingerprint `candidate` 政名为 `confirmed`。
- 在 fixture/manifest 中手写期望后直接回填解析输出。
- FTA 无 TPS Set 时把 `fta_extraction=complete`解释成 FTA 能力完成。
- 用单一组合件代替每类最小正例、变体、拓扑消耗压力件和反例。
- 只编译/只跑 self-test，不重新打开真实 CATPart/CATProduct。

