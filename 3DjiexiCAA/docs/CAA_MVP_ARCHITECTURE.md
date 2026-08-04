# CATIA V5R21 CAA Parser MVP v2 架构

## V1 通用扩展边界

`INativeObjectView` 现在只暴露 `FindCapability(capabilityId)`，不再为 Hole、Pad、Pocket 等逐类增加 Getter。`INativeHoleView` 是一个强类型 Capability；以后增加新原生特征只需提供独立 Capability 与 Decoder，无需修改 Crawler。

`FeatureRecord` 只拥有一个通用 `ITypedPayload`，通过 `Clone` 完成 C++03 所有权复制，Payload 自己负责 JSON 序列化。中央 Writer 不再含 Hole 类型分支。Registry 按优先级和稳定 Decoder ID 执行，明确处理 NotMatched、Unsupported、Success、Partial、Exception、Rejected 和 Conflict；失败后的继续策略由统一协议控制，Generic 回退不会继承失败 Decoder 的半成品。

Schema 为 `cad_parse_mvp_v2`，Parser/Registry/Decoder Bundle 为 `1.2.0`。工程仍保持一个 CAA Framework 和一个 LOAD MODULE；逻辑层通过纯 C++ 契约隔离，避免为名称创建空 Framework。

## 运行链路

```text
CadParseBatch
→ SessionGuard / DocumentGuard
→ UniversalFeatureCrawler（保留 CAA 枚举器原始顺序）
→ FeatureTypeRegistry
→ KnowledgewareStringParameterDecoder / NativeHoleDecoder / 基础 Typed Decoder
→ Generic / Opaque
→ ParameterRecordBuilder
→ DeclaredBusinessFeatureAggregator
→ JsonArtifactWriter staging
→ Coverage/引用守恒校验
→ 目录原子改名提交
```

`features.jsonl` 一行对应一个实际枚举到的 CAA 对象。String 参数也仍是原始 Feature；`parameters.jsonl` 只是用相同 `feature_id` 建立的消费索引。Native Hole 载荷是原始 Hole Feature 的可选 Typed Payload，不复制对象、不进入参数索引。`business_features.jsonl` 是从 GSMTool 声明节点和真实父子关系聚合出的派生记录，不混入 `enumerated_total`。

## 确定性和输出事务

Crawler 不再按显示名称排序，也不使用地址决胜，而是保留 `ListComponents`/`ListMembersHere` 的返回顺序，并记录 `native_enumeration_index`、`container_enumeration_index` 和 `traversal_index`。R21 文档把 `ListComponents` 结果描述为 unordered，所以跨机器/实现版本的绝对顺序不能作虚假保证；当前同一文件、同一 R21 环境连续两次运行的四个核心 JSONL 已做字节比较。

Writer 先在 `<output>.cadparse_stage` 完整写一次 features、relations、parameters、business_features，再写 diagnostics/log/coverage，计算文件大小与 SHA-256，最后写不包含自身哈希的 manifest，并通过目录改名提交。`output_ms` 覆盖核心/派生/诊断/log 的 staging 写入，不包含 Manifest 自身和最终目录改名。

## 边界

- CAA 指针只存在于 `CadParseCAA.cpp` 的 Session、Document、Crawler 和 Native View 内。
- 参数真实值通过 Public `CATICkeParm::Value()->AsString()` 读取；`Show()` 仅保存为 `raw_display_text`。
- `INativeFeatureDecoder`、`DecoderMatchStatus`、`DecoderContext` 和每类独立 Typed Payload 构成通用扩展边界；Crawler 不含 Hole 分支。
- Native Hole 由 `CATISpecObject → QueryInterface(IID_CATIAHole)` 确认；StartUp 只做候选预筛选。失败统一回到 Generic/Opaque。
- 当前 GSMTool“孔、槽、凸台”仍是 `declared_tree_parameter_aggregation`，不是 B-Rep 识别；只有真实 Part Design Hole 使用 `NativeHoleDecoder`。
- 已验证关系只有 `parent_of` 和 `contains`；悬空关系或派生来源会在写盘前被拒绝。
- 当前入口是 CATDocument、`CATIPrtContainer::GetPart`、`CATISpecObject::ListComponents` 和根 `CATIContainer::ListMembersHere`，不声称覆盖所有 CATPart 私有对象。
# CAA MVP 架构增量：原生拓扑出口

Schema `cad_parse_mvp_v4` 在既有 `features.jsonl` / `native_features.jsonl` 基础上新增两个 CAA 原生拓扑文件：

```text
native_topology_bodies.jsonl
native_topology_cells.jsonl
```

这两个文件来自 CATIA R21 Public `CATIPrtPart::GetSolid()` 和 `CATTopology`，用于证明最终实体的 Face/Edge/Vertex/Volume 已经能够在 CAA 端读取。

注意：它们不是新的规格树对象，不参与：

```text
enumerated_total = typed_count + generic_count + opaque_count + failed_count
```

当前仍未实现：

```text
Feature -> Face
Face -> Feature
FTA -> Face
Triangle -> Face
制造特征识别
```

因此前端或 Feature Center 只能把这些拓扑记录作为“真实 Face 拾取/几何详情”的基础数据，不能把它解释为“已完成特征关联面”。
