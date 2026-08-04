# STEP 与 B-Rep 管线

## STEP 导出

`tools/export_catpart_step.ps1` 管理输入哈希、输出和清理；它调用 UTF-16 临时 VBScript，通过 CATIA Automation 的 `CATIADocument.ExportData(path, "stp")` 导出。该链路没有伪装成 CAA Public 接口，不执行 `Save` 或 `Part.Update`，关闭文档后退出 CATIA。

实际文件使用 `CONFIG_CONTROL_DESIGN`，长度实体为 `SI_UNIT(.MILLI.,.METRE.)`。Sidecar 明确记录源单位 `mm`、Kernel 单位 `mm`、比例 1.0 和单位矩阵，不做经验平移或补偿。

## B-Rep 提取

`backend/freecad_scripts/parse_step.py` 使用 FreeCAD 1.1.3 的 Part/TopoShape 能力读取 STEP，并输出 Solid、Shell、Face、Wire、Edge、Vertex、面邻接、曲面类型、面积、包围盒、法向和网格。实测内核为 OpenCascade 7.8.1。

稳定编号由 Shape Hash、规范化几何签名和完全对称实体的稳定 occurrence 构成，不使用运行期 UUID 或裸指针。它只保证同一几何、同一算法版本和同一 Kernel 提取语义下稳定；不声称跨模型修订天然稳定。

模型容差为 `max(0.01 mm, bbox_diagonal × 1e-5)`。非毫米或未知单位、非法 STEP Header、非有限几何数值都会在进入正式 Bundle 前失败。

## 本机导出证据

- updated STEP：32653 字节，SHA-256 `84d28010516b0830e1c61fdc16943c00879dc25d8fbbe030111822d8a504bf6a`
- stale STEP：32651 字节，SHA-256 `5ca33ca15593052ced53a51212254b1e85d9263c4123877823327a297b46f035`

两个 STEP 的形状哈希不同，stale 语义不会被导出几何覆盖。
