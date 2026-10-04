# P3/P4 几何判定与组合测量正确性收口（2026-10-04）

本轮修复不扩展 P4 类别。所有新增判定来自同一 FreeCAD/OCCT B-Rep 解析任务及现有 Feature Center 发布链路；原生设计参数与几何识别仍分别保存。

## 规则、状态与版本

| 范围 | 修正后的证据与状态 | 限制 |
| --- | --- | --- |
| 圆凸台至矩形筋 | `distance_mm` 保留正间隙原值，`within_tolerance` 单独表达接近阈值，`intersection_status=not_evaluated` 不声称接触；解析范围重叠时 `proxy_overlap_unverified` 和有符号代理间隔独立记录，见证点仅在两个明确的主体范围内输出 | 解析代理未验证真实实体交叠深度；无共同高度时不产生距离 |
| 圆柱孔端 | `centerline_end_states` 和 `end_scan` 保留精确中心线材料区间、最近偏移与所有区间；最终 `end_states` 由局部共享端环核验，远端材料不能充当局部孔底；平底轴点需位于有限裁剪面内部；闭合空腔维持候选 | 复杂相交空域若缺可靠局部边界，保留候选，不宣称贯通 |
| 裁剪面 | 内核有限 Face 距离与边界距离区分 `inside`、`boundary`、`outside`，包含内环孔洞；包围盒只可筛选，不能确认底面 | 退化或多义边界不确认平底 |
| 薄壁 | 两面规范排序、双向有限裁剪投影和真实材料线段核验；配对 ID 基于同一几何快照的稳定 Face ID；`representative_local_sample` 只证明一个位置的局部厚度 | 不代表整张面的全局最小厚度；候选点耗尽为 `local_projection_unverified` |
| 组合预算 | 先按 Solid 与支撑面过滤，再按空间距离及特征 ID 确定顺序，每筋最多评估 128 个相关圆凸台；记录候选、已评估、未评估、失败数及原因 | `budget_exceeded` 不能解释为剩余候选不存在关系 |

组合距离测量算法升为 `p4c_combined.v2`，孔端与薄壁证据方法分别为 `exact_centerline_solid_intersection_local_end_v3`、`trimmed_plane_projection_and_exact_solid_segment_intersection_v2`，识别规则升为 `geometry_p3_p4_boundary_and_pair_correctness.v5`。旧版 `overlap_or_contact` 保留“旧算法未区分正小间隙”的历史语义；前端不把它翻译成新版的接触确认。旧结果继续可查，不被静默改写。

## 数据与重算

新孔端 `end_boundary` 引用同一快照的真实 Face/Edge，薄壁 `pair_id` 使用映射后的稳定 ID，组合测量与其特征、输入面、数值、状态和算法版本一同发布。现有 Revision、几何快照、CanonicalFeature、Measurement 和详情 API 未新增平行表。详情显示预算状态、未评估数、接近阈值和相交未判定；0.0005 mm 显示与复制保留原值。

旧 P3/P4 几何结果要获得新孔端和薄壁证据，须从**保存的 STEP** 重新执行 Feature Center build/发布；仅对旧识别 JSON 补算不能产生旧解析包没有的真实端环与裁剪面证据。含新版解析结果的包可沿现有发布流程发布。此过程不要求重新运行 CATIA CAA 原生采集；缺 STEP、过期显示映射或损坏包时不得把旧结果冒充新版。生产 Revision 未由本轮自动重算或覆盖。发布失败沿现有暂存/事务回滚保留上一可用结果。

## 验收证据与保留范围

真实 FreeCAD/OCCT 反例包含：0.0005 mm 正间隙与旋转等价、解析代理重叠、U 形连通 Solid 的远端材料、平底/锥底/阶梯/双盲孔隔板与闭合空腔、环形/偏孔/内凹平面及边界点、大/小有限面反向配对与质心落孔洞、超过 128 个相关与不相关圆凸台。合成件尺寸由生成脚本给定，测试断言不从识别器反推。实际运行命令与结果见本轮交付报告；未运行的真实业务件、浏览器验收不能算通过。

复杂/带岛/圆角型腔、内侧竖向转角、相交筋缘条处 R、内形闭角、全局最小厚度及严格最大高度仍未实现。本轮局部样点与解析代理不能证明这些能力。
