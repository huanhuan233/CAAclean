# Native Hole 到 B-Rep Face 映射

`HoleGeometryVerifier` 只消费 `NativeHoleDecoder` 已经由真实 CATIA Hole 接口确认的对象。Pocket、GSMTool 和普通圆柱面不会进入该融合链路。匹配不使用显示名称、内部名、Face 序号或样件固定坐标。

验证证据包括原生 Hole 原点、轴向、主体直径、终止方式、沉孔参数，以及 STEP 圆柱半径、轴线距离、轴向包围范围、邻接关系和底面。Up To Last 只映射贯穿壁与开口上下文，不伪造底面深度。

updated 样件实测：

| CAA Feature | Canonical Feature | 面数 | 状态 |
|---|---|---:|---|
| F000049 / Hole.1 | FCC7013210674BC78A | 3 | verified |
| F000082 / Hole.2 | FC1953C2BFC02F6E72 | 2 | verified |
| F000113 / Hole.3 | FC3A032B4DEFA56D5D | 6 | verified |
| F000155 / Hole.4 | FC313C4A79AB3B934A | 3 | verified |
| F000190 / Hole.5 | FCCC01238FD0779986 | 3 | verified |

`CoolingPort_A` 在 CAA 内部仍显示 `Hole.5`；它依靠专用 Hole 载荷和几何参数完成映射，不依赖别名文字。

stale 样件的五个 Hole 仍能完成几何匹配，但 Canonical Feature 全部为 `needs_review`，并记录 `stale_requires_review`。
