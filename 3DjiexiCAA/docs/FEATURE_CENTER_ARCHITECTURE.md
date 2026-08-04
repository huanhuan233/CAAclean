# Feature Center V1 架构

## 已实现边界

Feature Center 采用进程隔离：CATIA R21 的 CAA Worker 继续使用 VS2008、C++03、Win32；现代 Python Sidecar 使用 FreeCAD/OpenCascade 读取 STEP。两者只通过结构化文件交换，不把 Python、OpenCascade 或视觉 SDK 装进 CAA 进程。

当前真实链路为：

```text
NativeHoleDecoder
→ CATIA ExportData 导出的 STEP
→ FreeCAD/OpenCascade B-Rep
→ 稳定拓扑与 eAAG
→ HoleGeometryVerifier
→ Observation 与 Canonical Feature
→ 一面一 Primitive 的 GLB
→ Feature/Face/Mesh 双向映射
→ Web Viewer 高亮
```

CAA 原生语义说明设计意图，B-Rep 是几何定位和毫米测量的权威。stale 文件同时保留原生设计参数与导出几何，统一特征进入 `needs_review`，两者不会互相覆盖。

## 数据分层

- `Observation`：保留 `native_caa` 或 `brep_deterministic` 单一来源事实。
- `CanonicalFeature`：融合来源引用、真实面、强类型载荷和审查状态。
- `Measurement`：只接受 B-Rep 计算值，记录单位、容差、方法和输入面。
- `review_requests.jsonl`：离线视觉审查路由；当前视觉调用数固定为零。
- `readiness_probes.jsonl`：只报告复杂识别所缺证据，不生成 Rib/Cavity/Freeform 生产特征。

Feature Center 使用独立 Schema `cad_feature_center_v1`，不会混入 CAA 的 275/941 对象守恒统计。

## 本机实测

本机 FreeCAD 1.1.3、OpenCascade 7.8.1 对 updated 与 stale STEP 均得到 154 个拓扑实体、507 条拓扑关系、26 个可渲染面和 784 个三角形。五个原生 Hole 均关联真实面；updated 自动验证，stale 全部进入人工审查。

小样件通过只证明当前链路和样件事实，不代表工业模型上的通用识别准确率。
