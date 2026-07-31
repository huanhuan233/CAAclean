# STEP 边曲线完整分类设计

## 目标

STEP 模型导入 FreeCAD/OpenCASCADE 后，每条 B-Rep 边必须得到确定、互斥且可查询的几何类型。解析器不得根据 Python 类名片段或判断顺序猜测类型，也不得把合法的退化边错误标记为未知曲线。

本设计只定义边的有效几何分类。STEP 源文件中的 `TRIMMED_CURVE`、`COMPOSITE_CURVE`、`SURFACE_CURVE`、`PCURVE`、`SEAM_CURVE`、`INTERSECTION_CURVE` 等表示实体，会在导入阶段归一化为 B-Rep 的基础 3D 曲线、参数区间及面上的 2D 参数曲线；它们不作为互斥的最终 3D 几何类型。

## 确定性分类

解析器以 FreeCAD 几何对象的完整 `TypeId` 为唯一分派键：

| FreeCAD `TypeId` | `geometry_type` |
| --- | --- |
| `Part::GeomLine` | `line` |
| `Part::GeomCircle` | `circle` |
| `Part::GeomEllipse` | `ellipse` |
| `Part::GeomHyperbola` | `hyperbola` |
| `Part::GeomParabola` | `parabola` |
| `Part::GeomBezierCurve` | `bezier_curve` |
| `Part::GeomBSplineCurve` | `bspline_curve` |
| `Part::GeomOffsetCurve` | `offset_curve` |

OpenCASCADE 明确定义但不能归入上述解析曲线族的有效曲线使用 `other_curve`，并强制保留其原始 `TypeId`、参数区间和采样点，确保几何证据不丢失。

当边没有可用的 3D 曲线，并同时满足长度在容差内、只有一个几何顶点时，类型为 `degenerate_edge`。这类边保存退化点、参数区间以及可取得的面上 2D p-curve；它不是错误，也不是 `unknown_curve`。

若边既不是合法退化边，又无法取得 3D 曲线，类型为 `invalid_curve`，保存结构化错误信息。单条坏边不得导致整个 STEP 解析任务无结果。

## 通用字段

每条非退化边保存：

- `curve_type_id`
- `parameter_range`
- `start_point`、`end_point`
- `closed`
- `periodic`
- `trimmed`

各解析曲线另外保存：

- `line`：位置、方向。
- `circle`：圆心、轴、半径。
- `ellipse`：圆心、轴、长半径、短半径、长轴方向。
- `hyperbola`：中心、轴、长半径、短半径、焦距。
- `parabola`：位置、轴、焦距。
- `bezier_curve`：次数、极点、权重、有理性。
- `bspline_curve`：次数、极点、权重、节点、节点重数、有理性、周期性、连续性。
- `offset_curve`：偏移量、偏移方向，以及递归提取的基曲线类型和参数。
- `other_curve`：确定的原始 `TypeId` 和有限数量采样点。

`trimmed` 根据边的参数范围与基础曲线的自然参数范围确定。圆弧、椭圆弧、双曲线弧和抛物线弧因此保留基础类型，同时明确标记裁剪区间。

## 退化边与 2D 参数曲线

`degenerate_edge` 保存：

- `point`
- `parameter_range`
- `pcurves`

每条 p-curve 保存所在曲面的类型、曲面放置、参数范围，以及按 2D `TypeId` 确定的 `line_2d / circle_2d / ellipse_2d / hyperbola_2d / parabola_2d / bezier_curve_2d / bspline_curve_2d / offset_curve_2d / other_curve_2d`。

第一阶段至少从 `edge.curveOnSurface(index)` 读取 FreeCAD 已暴露的全部 p-curve，直到返回空值。任何一个 p-curve 提取失败只记录该项错误，不影响边和模型解析。

## 错误处理

- 属性读取采用逐字段安全读取；缺少可选属性时省略该字段。
- 类型判断只允许精确 `TypeId` 查表，不允许类名包含匹配。
- 数组和向量统一转为 JSON 数值数组。
- 不以 NURBS 转换结果覆盖原始解析曲线类型；NURBS 或采样仅作为 `other_curve` 的保底几何证据。

## 验证

自动测试必须覆盖八种明确 3D 曲线、裁剪曲线、退化边和 `other_curve`。测试先观察旧实现失败，再实现映射。

真实验证使用 `D:\anaconda\envs\3dcad`：

1. 重跑用户上传的 revision `5bd7d8a5-2e0f-4abb-aafd-53ca4e3d15a0`。
2. 确认原有 18 条 `unknown_curve` 全部成为 `degenerate_edge`。
3. 确认其 p-curve 为 `line_2d`，并保留球面类型与参数范围。
4. 确认解析任务完成、API 返回 `completed`，且没有因单边异常丢失整个 `result.json`。
