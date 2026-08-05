# FTA/MBD 最小人工建模清单（CATIA V5R21）

仅当 `prepare_fta_scaffolds.vbs` 因许可证、工作台或 R21 Automation 签名限制不能完成全部语义类型时使用。必须在合法 FTA/MBD 工作台中完成，并让 `verify_real_fixtures.vbs` 重新打开验证；截图不能代替 CATPart 内的 TPS 对象。

## 1. `fta_all_semantic_types.CATPart`

以 `fta_all_semantic_types_scaffold.CATPart` 为载体，建立 `Annotation Set.1`（ISO），至少加入：

| 固定名称 | 类型 | 必填内容 |
|---|---|---|
| `DIM_LINEAR_FACE_FACE` | 线性尺寸 | 80 mm；关联两相对平面；单位 mm |
| `DIM_DIAMETER_CYLINDER` | 直径尺寸 | Ø30；关联圆柱面 |
| `DIM_LIMIT_DEVIATION` | 极限偏差 | 25 +0.10/-0.05 mm |
| `GDT_POSITION_DRF_ABC` | 位置度 | Ø0.20(M)；基准 A/B/C |
| `GDT_FLATNESS` | 平面度 | 0.08；关联顶面 |
| `DATUM_A` / `DATUM_B` / `DATUM_C` | 基准 | 三个不同基准要素 |
| `ROUGHNESS_RA32` | 表面粗糙度 | Ra 3.2 μm；关联侧面 |
| `TEXT_PROCESS_NOTE` | 文本 | `REMOVE BURRS`；关联面 |
| `FLAG_NOTE_1` | 旗标注释 | 标识 `1`，链接文本说明 |
| `NOA_GENERAL_NOTE` | NOA | 至少一条非语义注释 |
| `VIEW_FRONT` / `VIEW_TOP` | Annotation View | 两个不同方向 |
| `CAPTURE_MACHINING` | Capture | 包含至少五条标注和显隐状态 |

保存后关闭并重新打开，确认 Annotation Set、TPSView 和 Capture 数量不为 0。

## 2. `fta_geometry_references.CATPart`

以相应 scaffold 为载体，建立下列独立标注，并确保引用对象类型不同：

- `REF_FACE`：Face。
- `REF_EDGE`：Edge。
- `REF_VERTEX`：Vertex/Point。
- `REF_AXIS`：圆柱轴线或 Axis System 轴。
- `REF_DATUM_PLANE`：基准平面。
- `REF_TTRS_MULTI`：同一 TTRS 中含多几何对象。

不得只在显示文本中写对象名；必须通过 CATIA 原生关联建立引用。

## 3. `fta_orphan_invalid.CATPart`

先建立有效标注，再产生四种可合法保存的异常状态：

- 删除/替换被引用 Face 后保留的孤立标注；
- 抑制被引用 Feature；
- 语义校验失败的 GD&T；
- Annotation View/Capture 引用失效。

如果 CATIA 不允许保存某类非法状态，记录精确 UI/COM 错误，该行可成为真实 BLOCKED，但不能用普通文本冒充。

## 4. `version_fta_v1.CATPart` / `version_fta_v2.CATPart`

V1 复制 `fta_all_semantic_types.CATPart`。V2 必须从 V1 在 CATIA 内另存后修改：

- 一个尺寸值；
- 一个上下偏差；
- 一个 GD&T 数值或修饰符；
- 一个基准引用；
- 一个粗糙度值；
- 一个文本/旗标/NOA 内容；
- 一个 Annotation View/Capture；
- 保持一条标注内容不变但把关联 Face 改为另一 Face。

## 5. 验收证据

每个最终 CATPart 必须：

1. 在 V5R21 中关闭后重新打开；
2. `AnnotationSets.Count > 0`；
3. TPS 组件数量符合清单；
4. 每类固定名称可由 Automation/CAA 重新枚举；
5. 引用对象不是空字符串；
6. CAA 解析产生非空 `fta_semantics.jsonl` 和 `fta_topology_links.jsonl`；
7. `fta_topology_links` 的 `final_cell_id` 能在 `native_topology_cells.jsonl` 中解析；
8. 双跑 JSONL Hash 一致。

