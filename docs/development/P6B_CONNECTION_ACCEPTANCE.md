# P6B 原生连接语义首批验收（2026-10-04）

## 已接通

- R21 CAA 从实际对象读取 `CATIAlias`，并通过 `CATIMmiGeometricalSet` / `CATIMfPoint` 记录对象类别。坐标定义点另外读取 `CATIGSMPointCoord` 的三维 MKS 参数及参考点/轴状态。显示名称不作为 Alias 证据。
- 规范化原生产物中的对象、树 occurrence、属性和产品 occurrence 在发布时投影为 `connection_semantics`；连接身份含文档、产品实例与集合 occurrence。`R_` PartNumber 与其他已知 PartNumber 分别保留 R/DM 来源规则。一次发布可以有同名连接集合，不按名称去重。
- `连接定义`、`K_密封定义`、`M_胶接定义` 需有真实几何图形集接口证据。紧固件 A 路径检查真实“紧固件”父集；点、编号项和统计参数分别计数，原始 `+` 编号、空片段与重复项保留。B 路径保留实际祖先链与缺口。密封/胶接保留 K001–K007、K010–K016、F017 原始参数及祖先 occurrence，区域与材料不按数组顺序猜配对。
- PostgreSQL `CadNativeEvidence` 保存原生语义与来源状态；`GET /api/component-builds/{build_id}/assembly/connections` 支持分页、类别筛选，详情按 ID 查询。缺原生捕获渠道返回具体原因。

## 尚未完成的 P6B 验收

- 坐标定义点的原始局部 MKS 数值可以保留；有参考点/轴的点以及其他点类型没有可信绝对坐标。CATProduct 实例与定义级几何仍缺经过验证的对应映射，因此不输出装配世界点或四位小数业务标识。
- 路径 A 的标准件编号五项属性尚未由真实样件核对；B 路径中间引用链不完整时保持 partial。紧固件与配装孔、夹层、间隙、厚度均未计算。
- 密封/胶接区域几何、面积、周长、质心、材料集合三层归属以及参与零件仍未验证，保持 unresolved；不声称已确定材料或用量。
- 真实 R/DM 客户 CATProduct 样件、许可证环境中的非空连接数据和浏览器联动均为 not_run。本阶段实现的是原生采集与可查询的部分语义链，不能视为 P6B 全项通过。

## 运行记录

- R21 x86 `mkmk` 编译通过；`test_connection_semantics.py`、`test_feature_center_bundle.py`、`test_native_semantic_publishing.py` 共 20 passed。
- `P6_LIVE_DB=1` 的独立 PostgreSQL Revision 发布及分页/详情事务检查 1 passed。测试数据是显式构造的合成夹具，不是客户样件验收。
- 新增原生字段须对源 CATProduct 重新采集；已有完整 `object_entities`、`tree_occurrences`、`property_facts` 与 `product_occurrences` 的包可重新发布投影，但旧包不会凭回填产生缺失的 Alias、接口标记或坐标。
