# P6A 装配空间关系首批验收（2026-10-04）

## 实际可用范围

- 本轮可计算新解析 STEP 中**不同导入对象**的已放置 Solid。`geometry/index.json` 保存导入对象来源与 `world_placed_step` 坐标约定；旧快照没有此证据时返回 `instance_geometry_mapping_unavailable`，不把合并网格拆成虚构 CATProduct 实例。
- CATProduct occurrence 的 `CATIMovable.GetAbsPosition` 是绝对矩阵；上下文验证刚性、可逆性和手性，不重复乘父矩阵。定义级 B-Rep 到原生 occurrence 的可信映射尚无采集资产，因此本轮不对 CATProduct 发布精确实例关系。
- 一个 FreeCAD 任务加载最多 64 个 Solid，AABB 只筛候选，对最多 128 个实例 Solid 对计算有限 B-Rep 最短距离和见证点。正间隙保留原值与 `within_tolerance`；零距离再检查闭合有效实体的布尔交集。普通共面裁剪面和已验证的正交长方体面接触输出实际接触面积；无法判定的点/线/复杂曲面接触保留未知。布尔失败不会报告无干涉。
- 计算结果绑定 Revision、几何快照、资产哈希、算法与容差配置；`assembly_run` 与 `assembly_relations` 在同一 PostgreSQL 事务替换。失败保留上一可用结果。API 为 `POST /api/component-builds/{build_id}/assembly/analyze`、`GET /assembly/relations` 和 `GET /assembly/relations/{id}`。

## 验收与限制

- R21 核心能力未声称提供装配空间内核；`native_only` 明确返回 unsupported。实例几何无可靠映射、超预算和旧快照均明确拒绝。
- 合成盒子构造参数独立于算法：10 mm 立方体与另一个立方体形成 0.001 mm 正间隙、100 mm² 平面接触和正体积交集；真实 FreeCAD 任务分别核验。
- 2026-10-04 验证：纯 Python 上下文/几何资产测试 6 passed；`P6_LIVE_FREECAD=1` 的实际 FreeCAD B-Rep 测试及 `P6_LIVE_DB=1` 的临时 PostgreSQL Revision 发布、分页/详情、失败保留旧结果测试 2 passed。测试构造件只证明受限子类，不代表 CATProduct 样件。
- 真实 CATProduct 重复实例、两层装配变换、单位变化、曲面接触、线/点接触和真实业务装配样件尚需验证。不能用这个 STEP 受限子类替代 F01 全部验收。
