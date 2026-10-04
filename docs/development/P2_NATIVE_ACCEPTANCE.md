# P2 原生特征验收记录（2026-10-04）

本轮使用本机 CATIA V5R21 PublicGenerated 头文件、RADE `mkmk` 与 VS2008 x86 工具链编译。`CadCapture.exe` 构建成功；缺失 JDK 1.6 的初始化诊断未阻止当前 C++ 编译及运行。

| 能力 | 当前证据 | 限制 |
| --- | --- | --- |
| 普通定半径圆角 | `pd_fillet_constant.CATPart` 新采集读到 `CATIAConstRadEdgeFillet`、R=5 mm、输入引用显示名及传播/修剪枚举 | 输入引用尚未解析到稳定对象 ID；高级圆角不升级为 typed |
| 普通倒角 | `pd_chamfer_variants.CATPart` 新采集读到 `CATIAChamfer` 距离—角度模式，D1=5 mm、原始 45 deg 与规范化角度、输入引用及传播/方向 | 两距离模式代码存在但缺当前样件验证；输入对象 ID 未解析 |
| 草图 | 同一倒角样件中新采集 `PRTSketch`，读到正交局部轴和 13 个元素；四条实际轮廓线及端点、构造点均有三维显示点 | 第一个内核轴元素明确 `unsupported`；支撑对象关系、元素连接、非默认平面及圆弧样件未核验 |
| Hole/Pad/Pocket | 原有解码器及兼容载荷保持；本轮相关适配测试通过 | 尚未对全部对照 CATPart 重新逐项核验 |

规范 `semantic_facets.jsonl` 和兼容 `native_features.jsonl` 同时保留载荷，读者按对象/Facet 身份去重。前端在原有窄详情面板显示参数和草图元素，中央 Viewer 用采集的三维点画实际草图曲线；构造元素虚线显示。真实浏览器点选、数据库事务、两距离倒角及旋转草图为 `not_run`，不能视作验收通过。

旧采集包没有本轮字段时，必须重新执行 R21 采集；回填旧包不能生成圆角/倒角参数或草图几何。
