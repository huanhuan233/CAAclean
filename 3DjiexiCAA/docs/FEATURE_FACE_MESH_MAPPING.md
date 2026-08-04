# Feature、Face 与 Mesh 映射

当前轻量化策略是一面一个 GLB Primitive。每个 Primitive 在 GLB `extras` 中保存稳定 `face_id`，同时输出：

- `face_mesh_map.json`：Face 到 Primitive/三角形范围以及反向索引；
- `feature_mesh_map.json`：Canonical Feature 到 Face 和 Primitive；
- `feature_geometry_links.jsonl`：特征、面和面角色的权威链接。

Viewer 不通过材质颜色猜测实体。只有 `feature_geometry_links.jsonl` 中存在真实链接时，点击特征才按映射高亮全部真实面；点击 Mesh Primitive 后也只在反向索引存在时反查一个或多个特征。没有链接时，Viewer 仍允许拾取真实 Face 并展示几何属性，但明确显示“未建立关联面”，不会构造假的 Feature ID、Face ID 或映射关系。

## 当前实现边界

CAA Worker 当前已实现并经 R21 接口确认的原生 Part Design `NativeHoleDecoder`；`Pad`、`Pocket` 等原生 Decoder 尚未实现。声明式 GSMTool 的“孔、槽、凸台”只属于 `declared_tree_parameter_aggregation`，其 `geometry_recognition_performed` 与 `native_part_design_feature_confirmed` 固定为 `false`，不能作为 Feature–Face 映射来源。

Face、稳定 `face_id`、Face–Mesh 对应表以及 Hole 的 Feature–Face 链接由 STEP/B-Rep Sidecar 生成：CAA 提供已确认的原生 Hole 设计语义，Sidecar 根据导出的 STEP 最终几何进行验证和定位。Bundle 可生成、GLB 可展示不等于映射存在；Web 任务清单中的 `mapping_available` 只有在 `feature_geometry_links.jsonl` 非空时才为 `true`。

因此，对于当前未产生已确认 Native Hole 的 `kuang.CATPart`，可以进行真实 Face 拾取，但不能高亮任何“特征对应面”。这反映当前解析范围，而不是把样件问题伪装成已有映射能力。

updated 样件生成 26 个 Primitive、820 个顶点、784 个三角形，GLB 为 32744 字节。五个 Hole 分别映射 3、2、6、3、3 个 Primitive。当前没有生成 LOD；将来若引入 LOD，每一级必须独立保存三角形映射。
