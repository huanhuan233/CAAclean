# Feature Center V1 验收矩阵

| 范围 | 实际结果 |
|---|---|
| Feature Center/STEP/融合单测 | 54 passed |
| Viewer 映射单测 | 3 passed |
| Vue 类型检查 | passed |
| Viewer 生产构建 | passed |
| VS2008 C++03 Core | self-test passed |
| R21 mkmk Win32 | 编译链接成功；仅保留已有 JDK 1.6 缺失警告 |
| R21 Batch 自测 | passed |
| updated CAA | 275 = 14 typed + 261 generic；5 个 Native Hole；548 关系 |
| stale CAA | 275 = 14 typed + 261 generic；5 个 stale Native Hole；548 关系 |
| kuang 回归 | 941；228 参数；25 声明式业务特征；3/8/14；Native Hole 0 |
| STEP/B-Rep | 每份 154 实体、507 关系、26 面 Primitive、784 三角形 |
| Hole→Face | 五个 Hole 全部 verified；Pocket 未进入链路 |
| stale 融合 | 五项均 `needs_review`，设计/几何冲突保留 |
| 视觉 | disabled，调用 0；协议与非法响应测试通过 |
| 双跑确定性 | CAA 四个核心 JSONL、Feature Center 十个 JSONL、GLB 和两份映射均字节稳定 |
| CATIA 残留 | 无 CNEXT/CATSTART |

本轮没有生产级 Rib/Web、Cavity/Island、Freeform Recognizer，没有分析渲染包，也没有真实 VLM 调用。对应输出仅是能力就绪度，不能解释为复杂特征识别成功。
