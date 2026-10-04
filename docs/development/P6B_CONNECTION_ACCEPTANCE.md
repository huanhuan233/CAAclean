# P6B 原生连接语义首批验收（2026-10-04）

## 已接通

- R21 CAA 从实际对象读取 `CATIAlias`，并通过 `CATIMmiGeometricalSet` / `CATIMfPoint` 记录对象类别。坐标定义点另外读取 `CATIGSMPointCoord` 的三维 MKS 参数及参考点/轴状态。显示名称不作为 Alias 证据。
- 规范化原生产物中的对象、树 occurrence、属性和产品 occurrence 在发布时投影为 `connection_semantics`；连接身份含文档、产品实例与集合 occurrence。`R_` PartNumber 与其他已知 PartNumber 分别保留 R/DM 来源规则。一次发布可以有同名连接集合，不按名称去重。
- `连接定义`、`K_密封定义`、`M_胶接定义` 需有真实几何图形集接口证据。紧固件 A 路径检查真实“紧固件”父集；点、编号项和统计参数分别计数，原始 `+` 编号、空片段与重复项保留。B 路径保留实际祖先链与缺口。密封/胶接保留 K001–K007、K010–K016、F017 原始参数及祖先 occurrence，区域与材料不按数组顺序猜配对。
- 严格 Alias 识别允许 CATIA 自动添加的正整数 `.N` 后缀，例如 `K_密封定义.2`，但保留原始 Alias。乱码和其他近似名称不会被模糊匹配升级为客户连接。
- PostgreSQL `CadNativeEvidence` 保存原生语义与来源状态；`GET /api/component-builds/{build_id}/assembly/connections` 支持分页、类别筛选，详情按 ID 查询。缺原生捕获渠道返回具体原因。

## 尚未完成的 P6B 验收

- 坐标定义点的原始局部 MKS 数值可以保留；有参考点/轴的点以及其他点类型没有可信绝对坐标。CATProduct 实例与定义级几何仍缺经过验证的对应映射，因此不输出装配世界点或四位小数业务标识。
- 路径 A 的标准件编号五项属性尚未由真实样件核对；B 路径中间引用链不完整时保持 partial。紧固件与配装孔、夹层、间隙、厚度均未计算。
- 密封/胶接区域几何、面积、周长、质心、材料集合三层归属以及参与零件仍未验证，保持 unresolved；不声称已确定材料或用量。
- 仓库已有 `business_fasteners.CATPart` 与 `business_seal_bond.CATPart`；R21 新采集成功，分别得到 94 个对象，但源样件里的中文客户 Alias 是乱码（例如 `K_�ܷⶨ��.1`），且独立 CATPart 没有产品 occurrence。严格原生规则因此得到 0 条连接，不把乱码按显示名猜回业务语义。非空 R/DM 客户 CATProduct 连接链与浏览器联动尚未通过。本阶段实现的是原生采集与可查询的部分语义链，不能视为 P6B 全项通过。
- 另尝试读取 `连接关系示例数据/500.000 A.CATProduct`：R21 进程持续运行超过五分钟而未写出 `capture_report.json`，为避免无限占用本机许可证与内存而终止；该样件状态是 not_run_to_completion，不记录为读取通过或连接为零。

## 运行记录

- R21 x86 `mkmk` 编译通过；`test_connection_semantics.py`、`test_feature_center_bundle.py`、`test_native_semantic_publishing.py` 共 20 passed。
- `P6_LIVE_DB=1` 的独立 PostgreSQL Revision 发布及分页/详情事务检查 1 passed。测试数据是显式构造的合成夹具，不是客户样件验收。
- 新增原生字段须对源 CATProduct 重新采集；已有完整 `object_entities`、`tree_occurrences`、`property_facts` 与 `product_occurrences` 的包可重新发布投影，但旧包不会凭回填产生缺失的 Alias、接口标记或坐标。
