# P1 实施与验收记录（2026-10-03）

## 实际接口与模块

| 模块 | 输入 → 输出 | 隐藏的处理 |
| --- | --- | --- |
| `parse_step.py` + Feature Center Bundle | 保存的 STEP → `geometry/*.brep`、`geometry/index.json`、原有 GLB/拓扑 | 在同一次 FreeCAD 导入中导出 Solid/Face/Edge/Vertex 子形状，稳定 ID 绑定 B-Rep 文件 SHA-256；写入同一事务式 Bundle 与 Manifest |
| `GeometrySnapshot` | Revision、快照 ID、稳定几何 ID → 已验证的 B-Rep 路径 | 限制目录、索引 Manifest 哈希、资产哈希、过期引用、坐标变换校验 |
| `measure_geometry.py` | 受控 B-Rep 路径及操作参数 → 数值和定位几何 | FreeCAD/OCCT 调用、有限拓扑、材料侧检查、几何/显示参数分离 |
| `MeasurementService/Repository` | Build、引用、参数 → `CadMeasurement` 与 API 结果 | Build→Revision 归属、真实根实体 FK、交互算法版本、重复请求 ID、事务；自动重算仍只替换自己的算法版本 |
| 前端会话与标注 | 主选择/快照 → A/B 引用、请求、结果与 Viewer 叠加 | 请求代际取消、旧响应隔离、资源释放，标注不加入模型拾取列表 |

`GET /api/component-builds/{build_id}/geometry/snapshot` 返回当前 Revision 和快照 ID。`POST .../geometry/query` 接收 `operation`、`references`、受控 `parameters`、`source_policy=auxiliary_brep`。`GET .../geometry/results` 和 `GET .../geometry/results/{result_id}` 查询该 Build/Revision 的交互结果。引用至少含 Revision、快照和稳定实体 ID，可选资产 SHA-256。客户端路径、脚本或表达式不可传入。`native_only` 返回 `unsupported`，绝不改用 FreeCAD。

## 定义、来源与可定位条件

- 距离：FreeCAD `distToShape` 针对有限 B-Rep，保留最近点对；多对等距解在内核返回多对时标为 `multiple`。相交零距离带 `intersects=true`，缺几何不会伪造 0。
- 夹角：直线切向/平面法向；无向定义取两方向的最小夹角。有向线面角缺参考法向时 `unsupported`。曲面需要指定在裁剪面上的点。没有材料侧不输出“内角”。
- 截面：闭合 Solid 与指定平面求 `common`，返回各区域、孔洞边界数和净面积；截线按 0.1 mm 弦差离散显示，面积来自 B-Rep。当前不接受 Compound 多实体截面，也不把 Viewer 剖切按钮当真实截面。
- 局部厚度：选中真实 Face 和面内点，读取其所属 Solid，依据实体内外判定材料侧，取紧邻起点的第一个连续材料区间；不跨空腔相加。当前只返回一个位置的局部法向厚度，不宣称全局最小值。开放壳体/材料侧不明返回 `unsupported`。
- 详情：Vertex 坐标；有限 Edge 端点、长度、曲线类型、适用半径；Face 裁剪边数、面积、周长、曲面类型；Solid 体积、面积和包围盒。已有原生设计参数仍由原通道呈现，B-Rep 辅助计算另列来源。

快照的 `geometry_snapshot_id` 由 STEP SHA、Shape Hash、内核版本和本次保存的子形状哈希组成。GLB primitive 与计算对象只通过同一次 Bundle 的 `face_mesh_map`/稳定 Face ID 对应；原生 Face、STEP Face、DB UUID 和 Three.js UUID 不互换。画布命中点只作为候选位置，精确操作由后端验证点是否位于真实面上。旧 Bundle 无 `geometry/index.json` 时仍可查看原有数据，但交互查询返回 `geometry_unavailable`；可对已有源 STEP 明确重建新派生 Bundle，不自动重采 CATIA 或覆盖旧快照。

内部单位为 mm、mm²、mm³、deg，STEP 输入的 mm/m/in 转换仍在 `step_input.py` 边界完成。查询使用 Bundle 尺寸容差并在配置的 `geometry_tolerance_min_mm` 与 `geometry_tolerance_max_mm` 之间钳制，结果记录实际容差；弦差与显示位数不当作测量误差。矩阵函数只接受右手刚体变换，拒绝反射、缩放和奇异矩阵。**当前 HTTP 查询只支持零件局部坐标**：没有可核验的实例 B-Rep/变换映射时，装配实例精确测量仍未开放，不会把同定义不同姿态混为一谈。

## 右侧窄面板

顶部“测量”进入距离模式，右侧对象详情中可切换距离、夹角、截面、局部厚度。当前真实面/边/点/实体可作为 A，继续选 B；夹角选择有向/无向，截面输入原点/法向，厚度输入面内点。画布点击有可信 Face 映射时，命中点预填为位置种子；后端仍验证。计算后显示状态、数值、结果 ID；Viewer 中叠加实际测量点/线或截线显示离散曲线。清除/取消释放叠加层，不重载 GLB，不重置相机、透明和 Viewer 剖切。爆炸视图下入口禁用。截图中的孔参数和时间均未作为产品数据。

## 本轮已执行

- `python tools/validate_p0.py`：通过。
- `3dcad` Python + FreeCADCmd：真实仓库 STEP `partdesign_holes_updated.stp` 完成 Feature Center 构建与 Bundle 校验，154 个稳定拓扑实体、117 个保存的 Solid/Face/Edge/Vertex B-Rep 子形状；未运行 CATIA。
- `3dcad` FreeCAD 合成件集成测试：点距 5 mm、有限边端点最短距离 √5 mm、有限面距离 10 mm、直角 90°、带孔截面净面积 `200−4π` mm²、板厚 4 mm、空腔上壁 2 mm，均通过。合成件不替代业务模型验收。
- 后端定向测试：`tests/test_freecad_geometry_query.py tests/test_parser_runner.py tests/test_geometry_snapshot.py tests/test_feature_center_geometry_assets.py tests/test_interactive_measurement_service.py`，10 passed。相关更广定向套件 51 passed。
- 前端 Feature Center `tsx --test` 69 passed；`pnpm build` 生产构建通过；最后一次 `pnpm typecheck` 通过。
- 全后端套件：323 passed、14 failed、5 skipped。失败涉及未改的 CATIA STEP 导出脚本断言、规格融合、图纸/视觉接口及缺少 `XMS06-DN80.stp`；本轮不通过删测、skip 或放宽断言掩盖。数据库仅做过只读根实体抽查，没有向用户生产 Revision 写入测试测量。

## 尚未验收的边界

真实 CATIA R21 重新采集、重复装配实例的世界坐标测量、不同单位等价 STEP 对照、曲面局部角度、截面相切/共面/多独立区域、平行面多解、厚度孔边界和多点采样、真实数据库交互写入、浏览器 360/400/440px 操作验收均为 `not_run` 或 `unsupported`。当前每次 HTTP 查询启动受控 FreeCAD 子进程并读取所需 B-Rep；尚无跨请求内存缓存或批量任务队列。超时终止进程，服务请求取消会通知进程终止；浏览器停止等待不能代替服务端对所有断连场景的取消保障。

P2/P3 可复用稳定几何引用、`GeometrySnapshot`、`MeasurementService.query_geometry`、FreeCAD B-Rep 子形状和已保存的距离/角度/局部厚度结果；专用孔、筋、腹板、R 识别器尚未实现。
