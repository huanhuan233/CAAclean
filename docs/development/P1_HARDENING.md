# P1 几何查询前置修正（2026-10-04）

本记录对应 `fix(p1): harden geometry queries for feature recognition`。旧 `interactive.p1.v1` 结果继续可读；新结果使用 `interactive.p1.v2` 和 `geometry_query_v2`，避免把旧 `intersects` 布尔值误解为已证实相交。

| 问题 | 修正与当前边界 |
| --- | --- |
| 面点与显示精度 | 前端保留原始命中坐标，四位小数只用于输入框显示。`seed_point` 明确是显示网格种子；内核仅投影到所选裁剪 Face/Edge，返回输入点、投影点、残差与接受上限。显式输入用 `point` 且只允许计算容差内残差。种子上限由 Bundle 记录的显示网格弦差计算并封顶，不因用户参数任意放宽。多最近点返回 `unsupported`。 |
| 曲线/曲面角度 | 曲线点在有限 Edge 上求最近点，并验证曲线参数处于修剪区间；曲面点在所选 Face 上核验。角度结果含实际求值位置、方向与定义。无向角、有向向量角分开；缺材料侧/参考法向的有向线面角仍 `unsupported`，不输出所谓内角。右侧面板提供 A/B 求值点，未填曲线/曲面点由后端返回 `invalid_input`。 |
| 距离状态 | `within_tolerance` 仅表示距离在容差内；`intersection_status=not_evaluated`。旧结果若含 `intersects`，前端显示兼容提示，不把它当相交事实。 |
| 校验与版本 | `null`、非有限数、零法向、裁剪范围外点返回业务状态。FreeCAD 版本与 OpenCascade 版本分字段记录；内核版本取不到为 `unknown`。相切且无面积的截面为 `contact_only`；截线显示采样截断时写 `display_complete=false`，面积仍来自 B-Rep。 |
| 单任务批量 | `GeometryKernelContext` 在一个隔离 FreeCAD 进程内按资产路径与类型缓存 B-Rep，最多 256 个资产、500 个查询、512 MiB 资产文件；沿用服务超时，输出加载数、查询数与耗时。交互和批量调用同一 `execute_query`。本轮不设跨请求常驻缓存。 |

自动验证：`3dcad` FreeCAD 合成件检查圆柱显示种子投影、有限圆弧面外点、微小正间隙、相切截面及单任务重复查询；后端定向套件 16 项通过。前端测量会话的高精度种子测试通过，类型检查通过。单零件真实数据库写入和浏览器测量冒烟仍为 `not_run`，不能用模拟仓储测试代替。真实 CATIA 模型及装配实例路径也未据此验收。
