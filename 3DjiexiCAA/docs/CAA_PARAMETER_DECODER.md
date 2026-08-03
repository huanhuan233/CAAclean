# Knowledgeware String 参数 Decoder

String 参数首先仍作为一个原始 `FeatureRecord` 参与 `enumerated_total`。`KnowledgewareStringParameterDecoder` 的 Match 只说明它是 String 候选；只有 `CATICkeParm::Type()->IsaString()` 和 `Value()->AsString()` 都成功，才标记 `typed/success`。

`parameters.jsonl` 不复制对象，只用同一个 `feature_id` 作为 `parameter_id` 建立便于消费的索引。Owner 通过 `parent_of` 图向上寻找最近的声明式业务 GSMTool 节点，不解析 tree_path；无 Owner 写空串并诊断，多 Owner 写 ambiguous，不能静默选择。

值来源：

- `typed_caa_value`：已验证类型接口的真实 String 值。
- `display_representation`：仅 CAA 格式化/展示文本。
- `parsed_from_display`：从展示文本二次解析，必须保留原文。
- `unavailable`：接口或值不可访问。

规范化永远不覆盖 `value_text`。只有整个字符串匹配数值加可选明确单位（当前 mm/cm/m/deg/rad）才填写数值字段；复杂包围盒、向量、ID 列表只保留原文。空字符串可以是合法的 typed 成功值。

新增参数类型时应先扩展 Native Adapter 和纯数据契约，明确真实类型值来源，再增加 Fake View、异常隔离、空值、中文、规范化和 Golden 测试；不可从显示名或参数名称中的数字伪造值。
