# CAA 端能力状态盘点（Python 制造特征识别之前）

本文只盘点 CATIA V5R21 CAA / C++ 批处理解析器侧能力，不包含 Python STEP/B-Rep 算法、Web 前端联动和制造特征识别结果。

当前 Schema：`cad_parse_mvp_v9`  
当前 Parser / Registry / Decoder Bundle：`1.9.0`

## 能力状态

| 能力 | 状态 | 实际依据 |
|---|---|---|
| 专用 Native Feature Decoder | `partial` | 已实现并实测 `NativeHoleDecoder`、`NativePadDecoder`、`NativePocketDecoder`。Hole 样件中 5 个原生 Hole 均为 Typed，Pad/Pocket 棱柱载荷可读；其它 Part Design 特征尚未逐类实现。 |
| 完整 Face / Edge / Vertex / Wire 几何拓扑 | `partial` | `native_topology_cells.jsonl` 输出最终主实体 Face/Edge/Vertex/Volume，含中心、面积/长度、边界 cell、相邻 cell；`native_topology_wires.jsonl` 输出 Face 边界 Loop/Wire。尚未输出曲面精确类型、曲率、UV 边界等完整几何细节。 |
| Feature Result cell 明细 | `partial` | `native_feature_result_cells.jsonl` 从 `CATIShapeFeatureBody::GetResultOUT()` 和 `CATIGeometricalElement::GetBodyResult()` 读取 ResultOUT body 的 cell 明细，不再只是数量摘要。 |
| Feature Result cell 到最终 Face 正反向映射 | `partial` | `native_feature_topology_links.jsonl` 输出 ResultOUT face 到最终主实体 face 的几何指纹候选、歧义或未匹配状态。该文件是候选映射证据，不是 CATIA Generic Naming 权威映射；不能作为“关联面已完全可用”的最终结论。 |
| FTA 语义提取 | `partial` | `fta_sets.jsonl` 输出 TPS Set；`fta_semantics.jsonl` 对 Set 内 TPS 组件尝试 `CATITPS`、`CATITPSSemanticValidity`、`CATITPSText`、`CATITPSTextContent` 观测。当前验证样件无 TPS Set，因此运行结果为 0 条，不代表代码路径不可编译。 |
| FTA–Topology 映射 | `not_available` | 当前没有从 TPS/TTRS 解析到最终 Face 的可靠 Public 链路输出，`topology_mapping_status` 保持 `not_available`。 |
| GLB Triangle–Face 映射前置数据 | `partial` | CAA 端通过 `CATICGMBodyTessellator` 输出 `native_mesh_face_map.jsonl`，记录 Face 到三角范围的 revision-local 映射。CAA 端本身不生成 GLB；GLB 写出仍属于后续轻量化阶段。 |
| CATProduct 多实例统一 ID | `not_available` | 当前 CAA Batch 主链路仍以 CATPart 文档为主，没有实现 CATProduct 装配实例路径、Reference/Instance 拆分和多实例统一 ID。 |
| 真实特征样件验证 | `partial` | 已用 `partdesign_holes_updated.CATPart` 验证原生 Hole/Pad/Pocket 与 ResultOUT/Topology 输出；已用 `D:\3Djiexiother\kuang.CATPart` 验证 941 对象回归和拓扑输出。缺少真实 FTA、CATProduct 多实例、更多 Part Design 特征样件。 |

## 本轮新增 CAA 输出文件

```text
native_feature_result_cells.jsonl
native_feature_topology_links.jsonl
fta_semantics.jsonl
```

说明：

- `native_feature_result_cells.jsonl`：保存每个原生形状特征 ResultOUT body 内部 cell 的明细，包含中心、面积/长度、边界 Result cell。
- `native_feature_topology_links.jsonl`：保存 ResultOUT face 与最终主实体 face 的几何指纹候选关系。状态可能为 `candidate`、`ambiguous`、`unmatched` 或 `insufficient_result_fingerprint`。
- `fta_semantics.jsonl`：保存 TPS 组件级公开语义观测。没有 TPS Set 时为空文件是正常事实，不是失败。

## 本轮 R21 接口证据

| 接口 | 头文件 | Framework | 用途 | 验证 |
|---|---|---|---|---|
| `CATIShapeFeatureBody::GetResultOUT()` | `MecModInterfaces/PublicInterfaces/CATIShapeFeatureBody.h` | MecModInterfaces | 获取形状特征 ResultOUT 对象 | R21 mkmk 通过；Hole 样件和 kuang 样件运行成功 |
| `CATIGeometricalElement::GetBodyResult()` | `MecModInterfaces/PublicInterfaces/CATIGeometricalElement.h` | MecModInterfaces | 获取 ResultOUT 对应 `CATBody` | R21 mkmk 通过；输出 Result cell 明细 |
| `CATTopology::GetAllCells()` | `GMModelInterfaces/PublicInterfaces/CATTopology.h` | GMModelInterfaces | 枚举 Face/Edge/Vertex/Volume | R21 mkmk 通过；kuang 输出 1435 个最终 cell |
| `CATCell::EstimateCenter()` | `GMModelInterfaces/PublicInterfaces/CATCell.h` | GMModelInterfaces | 输出 cell 中心点 | R21 mkmk 通过；输出 `center_mm` |
| `CATFace::CalcArea()` | `GMModelInterfaces/PublicInterfaces/CATFace.h` | GMModelInterfaces | 输出 Face 面积 | R21 mkmk 通过；输出 `area_mm2` |
| `CATEdge::CalcLength()` | `GMModelInterfaces/PublicInterfaces/CATEdge.h` | GMModelInterfaces | 输出 Edge 长度 | R21 mkmk 通过；输出 `length_mm` |
| `CATBoundaryIterator` | `GMModelInterfaces/PublicInterfaces/CATBoundaryIterator.h` | GMModelInterfaces | 输出 Face/Result cell 边界关系 | R21 mkmk 通过 |
| `CATCell::CellNeighbours()` | `GMModelInterfaces/PublicInterfaces/CATCell.h` | GMModelInterfaces | 输出最终 cell 邻接关系 | R21 mkmk 通过 |
| `CATICGMBodyTessellator` | `GMModelInterfaces/PublicInterfaces/CATICGMBodyTessellator.h` | GMModelInterfaces | 输出 Face 到三角范围的映射前置数据 | R21 mkmk 通过 |
| `CATITPSSemanticValidity` | `CATTPSInterfaces/PublicInterfaces/CATITPSSemanticValidity.h` | CATTPSInterfaces | TPS 组件级语义接口观测 | R21 mkmk 通过；当前样件无 TPS Set |
| `CATITPSTextContent` | `CATTPSInterfaces/PublicInterfaces/CATITPSTextContent.h` | CATTPSInterfaces | TPS 文本校验串读取 | R21 mkmk 通过；当前样件无 TPS Set |

## 本轮实测结果

### Hole 样件

输入：

```text
3DjiexiCAA\tests\fixtures\catia_r21\partdesign_holes_updated.CATPart
```

输出摘要：

```text
enumerated_total = 275
parameters = 5
declared_business_features = 0
native_hole_decoded_count = 5
native_prism_decoded_count = 2
native_topology_cell_count = 117
native_topology_wire_count = 34
native_mesh_face_map_count = 26
native_feature_result_count = 14
native_feature_result_cell_count = 1018
native_feature_topology_link_count = 224
native_feature_topology_candidate_link_count = 208
fta_set_count = 0
fta_semantic_count = 0
```

### kuang 样件

输入：

```text
D:\3Djiexiother\kuang.CATPart
```

输出摘要：

```text
enumerated_total = 941
parameters = 228
declared_business_features = 25
native_topology_body_count = 1
native_topology_cell_count = 1435
native_topology_wire_count = 299
native_mesh_face_map_count = 281
native_feature_result_count = 2
native_feature_result_cell_count = 2592
native_feature_topology_link_count = 498
native_feature_topology_candidate_link_count = 281
fta_set_count = 0
fta_semantic_count = 0
```

kuang 双跑核心文件 SHA-256 全部一致，包括新增的：

```text
native_feature_result_cells.jsonl = 69DD2E00641628CB204A06475FAC0817A7AEA286E67057774B570D0E92AC94EA
native_feature_topology_links.jsonl = 3FA2C85FB76D57ABEF542B7F4D399E96192A04D090EAF0ACC8103055C03039E4
fta_semantics.jsonl = E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855
```

## 不能误读的边界

- `native_feature_topology_mapping = partial` 表示已经输出候选 link，不表示权威 Feature–Face 映射完成。
- `geometry-fingerprint candidate` 不能替代 CATIA Generic Naming 或专用 Result/Selecting object 追踪。
- `fta_extraction = complete` 在当前 kuang/Hole 样件中表示 TPS Set 扫描完成且数量为 0，不表示 FTA 语义和拓扑映射完成。
- CAA 端输出 `native_mesh_face_map.jsonl` 是 GLB Triangle–Face 映射的前置契约；真正 GLB 文件仍由轻量化阶段生成。
- 当前没有 CATProduct 多实例统一 ID；不能把 CATPart 的 revision-local feature_id 当作装配实例 ID。
