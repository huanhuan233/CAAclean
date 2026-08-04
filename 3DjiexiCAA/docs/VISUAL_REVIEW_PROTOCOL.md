# 视觉审查协议

当前产品运行模式强制为 `disabled`，没有连接真实视觉服务，也没有把 Mock 结果写入生产 Bundle。`manifest.json` 中 `vision.call_count` 恒为 0。

`VisualReviewRouter` 的确定性结论包括：

- `not_needed`：B-Rep 已验证且模型状态不是 stale；
- `human_review_only`：stale 语义与导出几何必须由人审查；
- `blocked_by_missing_evidence`：缺少真实 Face，禁止只凭视觉定位；
- `disabled_by_policy`：存在候选，但当前策略不允许远程调用。

缓存键包含 Shape Hash、稳定排序后的候选 Face、证据配置版本、Prompt 版本和模型版本。离线响应校验要求 `[0,1]` 坐标、至少三点多边形、有限且范围正确的分类/定位置信度。视觉估算不会进入权威 `Measurement`。

本轮 updated 五项为 `not_needed`，stale 五项为 `human_review_only`。没有执行远程模型 Smoke Test，也没有生成多通道分析渲染包。
