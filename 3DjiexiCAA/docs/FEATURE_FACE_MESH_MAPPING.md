# Feature、Face 与 Mesh 映射

当前轻量化策略是一面一个 GLB Primitive。每个 Primitive 在 GLB `extras` 中保存稳定 `face_id`，同时输出：

- `face_mesh_map.json`：Face 到 Primitive/三角形范围以及反向索引；
- `feature_mesh_map.json`：Canonical Feature 到 Face 和 Primitive；
- `feature_geometry_links.jsonl`：特征、面和面角色的权威链接。

Viewer 不通过材质颜色猜测实体。点击特征时按映射高亮全部真实面；点击 Mesh Primitive 时通过 Face 反查一个或多个特征。它支持恢复材质、透明、隔离、隐藏和局部剖切。

updated 样件生成 26 个 Primitive、820 个顶点、784 个三角形，GLB 为 32744 字节。五个 Hole 分别映射 3、2、6、3、3 个 Primitive。当前没有生成 LOD；将来若引入 LOD，每一级必须独立保存三角形映射。
