# 声明式业务特征聚合

当前模型中的“凸台、孔、槽”是 GSMTool 与子 String 参数表达的模型内声明信息。本模块输出 `declared_business_feature`，识别方法固定为 `declared_tree_parameter_aggregation`；每条记录都明确：

```text
geometry_recognition_performed = false
native_part_design_feature_confirmed = false
```

聚合流程：按原始遍历顺序找候选 GSMTool，去除末尾完整 `.数字` 实例后缀，根据真实 parent_of 图收集参数，组合规范化名称与“特征类型”参数证据，再分类为 `declared_boss`、`declared_hole`、`declared_slot` 或 `declared_unknown`。名称和参数证据一致才可给 high；只有名称为 medium；冲突为 ambiguous/low。

每个 `business_feature_id` 按聚合顺序稳定生成，`source_feature_id` 反查 GSMTool，所有 `parameter_ids` 反查原始 Feature。缺值不会删除业务特征；悬空来源会使 Writer 校验失败。业务记录是派生数据，不进入 941 个原始对象的守恒式。

增加新声明类别时，在 `BusinessFeatureRuleCatalog` 增加通用别名/参数签名规则并补成功、冲突、歧义、Golden 和守恒测试；禁止写实例 ID、固定树路径或固定样件数量。

将来接入真正 Pad/Pocket/Hole Decoder 时，应在 Registry 中使用已验证 R21 原生接口生成原生业务语义；它和本声明聚合并存，不能用名称聚合结果冒充几何或 Part Design 识别。
