# NativePadDecoder 与 NativePocketDecoder（CATIA V5R21）

本页记录本轮新增的原生 Part Design Prism 家族读取能力。这里的 Prism 指 CATIA Public `CATIAPrism` 基类，当前只注册 `NativePadDecoder` 和 `NativePocketDecoder`。它们读取设计历史语义，不执行 B-Rep 制造特征识别，也不输出 Feature-Face 拓扑映射。

## 接口链路

`UniversalFeatureCrawler` 仍只枚举 `CATISpecObject`。对于候选对象，Decoder 先用 `startup_type` 做低成本预筛选，然后通过统一 Capability 查询：

```text
CATISpecObject*
→ FindCapability("NativePad" / "NativePocket")
→ QueryInterface(IID_CATIAPad / IID_CATIAPocket)
→ QueryInterface(IID_CATIAPrism)
→ NativePrismData
→ NativePrismPayload
→ features.jsonl/native_features.jsonl
```

`startup_type == "Pad"` 或 `startup_type == "Pocket"` 只表示候选，不代表 Typed 成功。只有对应 Public 接口查询成功，并且 `CATIAPrism` 必需字段读取成功，才会输出 `decode_level=typed`。

## R21 证据

| 项目 | 内容 |
|---|---|
| Pad 接口 | `CATIAPad`，IID 为 `IID_CATIAPad` |
| Pocket 接口 | `CATIAPocket`，IID 为 `IID_CATIAPocket` |
| Prism 公共基类 | `CATIAPrism`，IID 为 `IID_CATIAPrism` |
| 生成头 | `D:\CATIA\PartInterfaces\PublicGenerated\intel_a\CATIAPad.h`、`CATIAPocket.h`、`CATIAPrism.h` |
| 原始 IDL | `D:\CATIA\PartInterfaces\PublicInterfaces\CATIAPad.idl`、`CATIAPocket.idl`、`CATIAPrism.idl`、`CATPrismDefs.idl` |
| Framework | `PartInterfaces` |
| IdentityCard | 继续使用 `AddPrereqComponent("PartInterfaces", Public)` |
| 链接 | 现有 `CATPartInterfaces`、`PartInterfacesUUID` 满足 Win32/x86 mkmk 链接 |
| 访问级别 | Public；未使用 ProtectedInterfaces |

## 读取字段

`NativePrismData` 读取并输出以下字段：

- `semantic_kind`：`part_design_pad` 或 `part_design_pocket`；
- `material_operation`：Pad 为 `add_material`，Pocket 为 `remove_material`；
- `direction_type/raw`：来自 `CATIAPrism::get_DirectionType` 与 `CatPrismExtrusionDirection`；
- `direction_orientation/raw`：来自 `CATIAPrism::get_DirectionOrientation` 与 `CatPrismOrientation`；
- `direction`：来自 `CATIAPrism::GetDirection` 的三元数值数组；
- `is_symmetric`、`is_thin`、`neutral_fiber`、`merge_end`；
- `first_limit` 和 `second_limit`：来自 `CATIALimit::get_LimitMode`；仅 Offset 终止读取 `CATIALength::get_Value`，其他终止尺寸写 `null/not_applicable`。

所有数值都写 JSON number 或 null，不把缺失字段伪造成 0。接口不支持是正常 unsupported，查询异常和必需字段失败才进入对象级诊断。

## 当前验证状态

2026-08-05 已在本机 R21 mkmk 5.21、VS2008、Win32/x86 下完成编译链接。API 无关自测覆盖：

- Pad 成功确认后输出 `NativePadDecoder` 和 `native_prism`；
- Pocket 成功确认后输出 `NativePocketDecoder` 和 `native_prism`；
- 只有 StartUp 但接口不支持时回退 Generic；
- Pocket 不会被 `NativePadDecoder` 误接管；
- `native_prism` 通过通用 Payload 写出，不需要修改中央 Writer 分支。

当前仓库缺少包含原生 Pad/Pocket 的回归 CATPart 二进制样件，因此真实运行回归只在 `kuang.CATPart` 上验证“不误伤”：941 个对象、228 个字符串参数、25 个声明式业务特征保持不变，`NativeHoleDecoder/NativePadDecoder/NativePocketDecoder` 均未命中。等含原生 Pad/Pocket 的 CATPart 样件重新放回仓库后，需要补跑真实 Typed 命中验证。
