# CAA 原生拓扑出口

本页记录当前 CAA R21 解析器已经实际编译并在 `kuang.CATPart` 上运行通过的原生拓扑出口。

## 当前能力

解析器在访问到 `CATIPrtPart` 对应的 Part 节点后，使用 R21 Public 接口读取主实体结果：

```text
CATISpecObject
→ QueryInterface(IID_CATIPrtPart)
→ CATIPrtPart::GetSolid()
→ CATBody / CATTopology
→ GetCellNumbers()
→ GetAllCells(face/edge/vertex/volume)
```

输出文件：

```text
native_topology_bodies.jsonl
native_topology_cells.jsonl
capabilities.json
```

`native_topology_bodies.jsonl` 保存主实体拓扑数量和来源 Feature：

```json
{
  "body_id": "TB000001",
  "source_feature_id": "F000003",
  "source_kind": "catiprtpart_main_solid",
  "vertex_count": 442,
  "edge_count": 711,
  "face_count": 281,
  "volume_count": 1
}
```

`native_topology_cells.jsonl` 保存每个拓扑单元的本轮编号、维度、domain 数和来源：

```json
{
  "cell_id": "TB000001_F000001",
  "body_id": "TB000001",
  "cell_kind": "face",
  "topology_index": 1,
  "dimension": 2
}
```

## ID 语义

`cell_id` 是 revision-local ID，只承诺在以下条件不变时保持稳定：

```text
同一输入文件
同一 CATIA R21 / CAA 运行环境
同一解析器版本
同一 CATTopology 原生枚举顺序
```

它不是 CATIA 指针、内存地址或跨模型版本稳定 ID。跨版本拓扑匹配仍需要几何指纹和邻接指纹，本轮没有声称完成。

## 明确未完成

当前拓扑出口只证明最终实体的 Face/Edge/Vertex 可以被 CAA 读取，不等于已经建立设计特征到拓扑面的映射。

以下能力仍在 `capabilities.json` 中如实标记为未可用：

```text
native_feature_topology_mapping = not_available
fta_topology_mapping = not_available
mesh_face_mapping = not_available
manufacturing_feature_recognition = not_performed
```

## FTA/TPS 集合级出口

Schema `cad_parse_mvp_v5` 新增：

```text
fta_sets.jsonl
```

它使用 R21 Public `CATITPSDocument`、`CATITPSSet`、`CATITPSList` 和 `CATITPSGeometryList` 读取文档内 FTA/TPS Set 数量，以及每个 Set 的 TPS 数和几何引用数。

当前只输出集合级摘要，不输出具体公差语义，不输出 FTA 到 Face 的映射：

```json
{
  "fta_set_id": "FTA000001",
  "set_index": 1,
  "tps_count": 0,
  "geometry_count": 0,
  "semantic_detail_status": "not_implemented",
  "topology_mapping_status": "not_available"
}
```

如果文档公开 `CATITPSDocument` 且扫描完成但没有 TPS Set，`fta_extraction` 写为 `complete`，`fta_set_count` 写为 `0`，`fta_sets.jsonl` 为空文件。这表示“没有集合”，不是“解析失败”。

## 原生特征 ResultOUT 出口

Schema `cad_parse_mvp_v6` 新增：

```text
native_feature_results.jsonl
```

它使用 R21 Public：

```text
CATISpecObject
→ CATIShapeFeatureBody
→ GetResultOUT()
→ CATIGeometricalElement
→ GetBodyResult()
→ CATTopology::GetCellNumbers()
```

该文件说明某个原生设计特征是否具有可读取的 ResultOUT 拓扑结果体。它不是最终主实体 Face 归属，因此每条记录都必须保留：

```text
final_body_mapping_status = not_available
```

kuang 样件实测读取到 2 条 ResultOUT 摘要：

```text
NFR000001 source_feature_id=F000011 face_count=281 edge_count=711 vertex_count=442 volume_count=1
NFR000002 source_feature_id=F000018 face_count=217 edge_count=575 vertex_count=364 volume_count=1
```

这一步只是为后续 Feature→Face 对齐提供真实 CAA 输入，不得把它描述为 Feature–Face 映射完成。

## Schema v9：Result cell 明细、候选映射和 TPS 语义观测

本轮新增三个 CAA 端输出：

```text
native_feature_result_cells.jsonl
native_feature_topology_links.jsonl
fta_semantics.jsonl
```

`native_feature_result_cells.jsonl` 来自：

```text
CATISpecObject
→ CATIShapeFeatureBody::GetResultOUT()
→ CATIGeometricalElement::GetBodyResult()
→ CATTopology::GetAllCells()
→ CATCell / CATFace / CATEdge / CATBoundaryIterator
```

它逐条输出 ResultOUT 内部 Face/Edge/Vertex/Volume 的中心、面积/长度和边界 Result cell。它不是最终主实体 Face，也不参与 `enumerated_total`。

`native_feature_topology_links.jsonl` 当前采用几何指纹候选匹配：

```text
ResultOUT Face 中心 + 面积
→ 与最终主实体 Face 中心 + 面积比较
→ 输出 candidate / ambiguous / unmatched / insufficient_result_fingerprint
```

这只是可审计候选，不是 CATIA Generic Naming 的权威映射。只有候选存在时，`capabilities.json` 中的 `native_feature_topology_mapping` 才写为 `partial`，绝不写成 `complete`。

`fta_semantics.jsonl` 来自 R21 Public `CATITPSList::Item` 后对每个 `CATITPSComponent` 进行接口探测：

```text
CATITPS
CATITPSSemanticValidity
CATITPSText
CATITPSTextContent
```

当前 Hole 和 kuang 验证样件没有 TPS Set，因此 `fta_semantics.jsonl` 为空文件；这表示样件中没有可枚举 TPS 组件，不表示代码路径编译失败。

## R21 实测结果

命令：

```bat
call 3DjiexiCAA\tools\run_r21_x86.bat --input D:\3Djiexiother\kuang.CATPart --output %TEMP%\cadparse_topology_kuang_v1 --read-only
```

结果：

```text
enumerated_total = 941
parameters = 228
declared_business_features = 25
native_topology_body_count = 1
native_topology_cell_count = 1435
fta_extraction = complete
fta_set_count = 0
native_feature_result_count = 2
face_count = 281
edge_count = 711
vertex_count = 442
volume_count = 1
```
