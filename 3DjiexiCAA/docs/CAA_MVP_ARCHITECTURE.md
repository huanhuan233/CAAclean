# CATIA V5R21 CAA Parser MVP v1 架构

Schema 为 `cad_parse_mvp_v1`。工程仍保持一个 CAA Framework 和一个 LOAD MODULE；逻辑层通过纯 C++ 契约隔离，避免为名称创建空 Framework。

## 运行链路

```text
CadParseBatch
→ SessionGuard / DocumentGuard
→ UniversalFeatureCrawler（保留 CAA 枚举器原始顺序）
→ FeatureTypeRegistry
→ KnowledgewareStringParameterDecoder 或基础 Typed Decoder
→ Generic / Opaque
→ ParameterRecordBuilder
→ DeclaredBusinessFeatureAggregator
→ JsonArtifactWriter staging
→ Coverage/引用守恒校验
→ 目录原子改名提交
```

`features.jsonl` 一行对应一个实际枚举到的 CAA 对象。String 参数也仍是原始 Feature；`parameters.jsonl` 只是用相同 `feature_id` 建立的消费索引。`business_features.jsonl` 是从 GSMTool 声明节点和真实父子关系聚合出的派生记录，不混入 `enumerated_total`。

## 确定性和输出事务

Crawler 不再按显示名称排序，也不使用地址决胜，而是保留 `ListComponents`/`ListMembersHere` 的返回顺序，并记录 `native_enumeration_index`、`container_enumeration_index` 和 `traversal_index`。R21 文档把 `ListComponents` 结果描述为 unordered，所以跨机器/实现版本的绝对顺序不能作虚假保证；当前同一文件、同一 R21 环境连续两次运行的四个核心 JSONL 已做字节比较。

Writer 先在 `<output>.cadparse_stage` 完整写一次 features、relations、parameters、business_features，再写 diagnostics/log/coverage，计算文件大小与 SHA-256，最后写不包含自身哈希的 manifest，并通过目录改名提交。`output_ms` 覆盖核心/派生/诊断/log 的 staging 写入，不包含 Manifest 自身和最终目录改名。

## 边界

- CAA 指针只存在于 `CadParseCAA.cpp` 的 Session、Document、Crawler 和 Native View 内。
- 参数真实值通过 Public `CATICkeParm::Value()->AsString()` 读取；`Show()` 仅保存为 `raw_display_text`。
- 当前“孔、槽、凸台”是 `declared_tree_parameter_aggregation`，不是 B-Rep 识别，也不是原生 Pad/Hole/Pocket Decoder。
- 已验证关系只有 `parent_of` 和 `contains`；悬空关系或派生来源会在写盘前被拒绝。
- 当前入口是 CATDocument、`CATIPrtContainer::GetPart`、`CATISpecObject::ListComponents` 和根 `CATIContainer::ListMembersHere`，不声称覆盖所有 CATPart 私有对象。
