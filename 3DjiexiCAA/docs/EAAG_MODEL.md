# eAAG 模型

`EaagGraph` 在稳定拓扑之上提供曲面分类、面邻接、共享边、Wire 归属和引用校验。正式关系两端必须存在，悬空引用不会静默写入 Bundle。

当前 Hole 映射实际使用圆柱半径、轴线、轴距、轴向范围、邻接面和边界环。复杂结构就绪度探针还会统计平面数量、邻接对、Wire、自由曲面类型和曲率样本。

当前尚未提取可靠的边凹凸、外部可达性、连续性等级和局部厚度场，因此：

- Rib/Web 只报告基础邻接证据，并明确为 `verifier_prerequisites_incomplete`；
- Cavity/Island 只报告 Wire 与邻接证据，并明确为 `verifier_prerequisites_incomplete`；
- Freeform 即使存在真实 Bezier/BSpline/Offset 面，在连续性验证缺失时也只报告前置条件不完整；本次 Hole 样件为证据不足。

这些状态用于阻止系统把“不够证据”包装成高置信特征。
