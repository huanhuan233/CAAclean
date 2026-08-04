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
fta_extraction = not_available
fta_topology_mapping = not_available
mesh_face_mapping = not_available
manufacturing_feature_recognition = not_performed
```

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
face_count = 281
edge_count = 711
vertex_count = 442
volume_count = 1
```

