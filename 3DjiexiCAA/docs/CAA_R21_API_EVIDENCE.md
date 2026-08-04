# CAA V5R21 API 证据

以下接口均在本机 `D:\CATIA` R21 安装中核对；项目没有使用 ProtectedInterfaces。

| API/类 | 头文件 / Framework | 项目位置 | 本机依据 | 访问级别 | 实际状态 |
|---|---|---|---|---|---|
| `Create_Session` / `Delete_Session` | `CATSessionServices.h` / ObjectModelerBase | `SessionGuard` | Public 头文件、`CAAAniExport` 示例 | Public L1 | 编译、样件运行通过 |
| `CATDocumentServices::OpenDocument(..., TRUE)` / `Remove` | `CATDocumentServices.h` / ObjectModelerBase | `DocumentGuard` | Public 头文件与本机示例 | Public L1 | 只读打开/关闭通过 |
| `CATInit::GetRootContainer` | `CATInit.h` / ObjectModelerBase | Crawler 根入口 | Public 头文件、`CAAAuiCreateFixConstraintInPart` | Public | 运行通过 |
| `CATIPrtContainer::GetPart` | `CATIPrtContainer.h` / MecModInterfaces | Part 入口 | Public 头文件/本机示例 | Public L1/U3 | 运行通过 |
| `CATIContainer::ListMembersHere` | `CATIContainer.h` / ObjectModelerBase | 补充容器入口 | Public 头文件/示例 | Public L1/U3 | 运行通过 |
| `CATISpecObject::ListComponents` | `CATISpecObject.h`、`CATLISTV_CATISpecObject.h` / ObjectSpecsModeler | 树遍历 | Public 头文件说明 delete 所有权且结果 unordered | Public L1/U3 | 编译、运行通过；保留返回顺序但记录跨环境限制 |
| `GetType` / `GetSuperType` / `GetName` / `GetDisplayName` | `CATISpecObject.h` / ObjectSpecsModeler | 类型指纹 | Public 头文件 | Public L1/U3 | 运行通过 |
| `GetFeatContainer` / `IsUpToDate` | `CATISpecObject.h` / ObjectSpecsModeler | Generic 基础状态、stale 汇总 | Public 头文件 | Public L1/U3 | 运行通过 |
| `CATUnicodeString::ConvertToUTF8` | `CATUnicodeString.h` / System | 全部 CAA 文本转 UTF-8 | Public 头文件 | Public L1 | 运行通过 |

## String 参数类型化读取

| 项目 | 已验证内容 |
|---|---|
| 参数接口 | `CATICkeParm` |
| 头文件 | `D:\CATIA\KnowledgeInterfaces\PublicInterfaces\CATICkeParm.h` |
| Framework / 模块 | `KnowledgeInterfaces` / `KnowledgeItf` |
| 访问级别 | Public，头文件标注 `@CAA2Level L1`、`@CAA2Usage U3` |
| 获取方式 | 对当前 `CATISpecObject` 调用 `QueryInterface(IID_CATICkeParm, ...)` |
| 类型判断 | `CATICkeParm::Type()` 得到 `CATICkeType_var`，调用 `CATICkeType::IsaString()`；头文件 `CATICkeType.h` |
| 真实值读取 | `CATICkeParm::Value()` 得到 `CATICkeInst_var`，调用 `CATICkeInst::AsString()`；头文件 `CATICkeInst.h` 明确 String 返回其 value |
| 展示文本 | `CATICkeParm::Show()` 只写入 `raw_display_text`，不标为真实类型值 |
| 其他状态 | `Name()`、`IsReadOnly()`、`IsHidden()`；限定 Name 只取叶名称，Owner 不靠路径猜测 |
| 本机示例 | `CAAElecHarnessItf.edu\CAAEhiFLEXImpl.m\src\CAAGetFLEXEquivalentModulusExt.cpp` 使用 `hTypeCkeParm->Value()->AsString()`；Encyclopedia `CAALifFormulas.htm` 也使用相同调用 |
| IdentityCard | `AddPrereqComponent("KnowledgeInterfaces", Public)` |
| 异常处理 | QueryInterface 正常不支持 → unsupported；QueryInterface 抛出 → query exception；Type/Value/AsString/Show/状态读取抛出 → value exception；均对象级隔离 |
| 值语义 | `value_text` 来源为 `typed_caa_value`；`raw_display_text` 是展示表示，两者不混淆 |
| 编译状态 | R21 mkmk + VS2008 Win32 编译/链接通过 |
| 样件状态 | `kuang.CATPart` 228 个 String 参数全部类型化读取成功，空值仍允许作为成功值 |

## Native Part Design Hole 类型化读取

| 项目 | 已验证内容 |
|---|---|
| 专用接口 | `CATIAHole`，IID 为本机生成头声明的 `IID_CATIAHole`（IDL DCE：`a6ae2c93-64f9-11d1-a27f0000f87546fd`） |
| 头文件 | `PartInterfaces/PublicGenerated/intel_a/CATIAHole.h`；原始契约为 `PartInterfaces/PublicInterfaces/CATIAHole.idl` |
| Framework / 链接 | `PartInterfaces`；`CATPartInterfaces`、`PartInterfacesUUID` |
| 访问级别 | Public，`CATIAHole.idl` 标注 `@CAA2Level L1`、`@CAA2Usage U3`；未使用 ProtectedInterfaces |
| 准确获取链路 | Crawler 当前 `CATISpecObject*` → `QueryInterface(IID_CATIAHole, ...)` → `CATIAHole*`；成功引用由 `CaaInterfaceGuard` 在对象级 Decode 结束时 `Release()` |
| 候选与确认 | `startup_type == "Hole"` 只预筛选；仅 QueryInterface 成功且必需属性读取完成才输出 Typed |
| 孔型 | `CATIAHole::get_Type` + `CATHoleDefs.h` 的 `CatHoleType`：Simple、Tapered、Counterbored、Countersunk、Counterdrilled；保留 raw 枚举 |
| 直径/头部 | `get_Diameter`；头部严格按 IDL 适用矩阵读取：Tapered=Angle、Counterbored=Diameter+Depth、Counterdrilled=三者、Countersunk=Depth+Angle；R21 文档明确 Length 为 mm、Angle 为 decimal degrees |
| 原点/方向 | `GetOrigin`、`GetDirection`，使用三元素 `SAFEARRAY(VARIANT)`；输出 number 数组 |
| BottomLimit | `get_BottomLimit` → `CATIALimit::get_LimitMode/get_Dimension`；`CATLimitDefs.h` 定义 Offset、Up To Last 等。非 Offset 深度为 `null/not_applicable` |
| 螺纹 | `get_ThreadingMode`、`get_ThreadDiameter`、`get_ThreadDepth`、`get_ThreadPitch`、`get_HoleThreadDescription`；描述来自 `CATIAStrParam::get_Value`，不自行拼接 |
| Automation 别名 | 同一个 `CATIAHole` 继承 Public `CATIABase::get_Name`；可得到 `Hole_Blind` 至 `CoolingPort_A`，与 CAA 规格内部名 `Hole.1` 至 `Hole.5` 分开保存 |
| 异常策略 | E_NOINTERFACE → unsupported；QueryInterface 抛出 → exception；接口已确认但必需值失败 → partial 并 Generic 回退；不适用可选字段不计 partial |
| 构建状态 | 2026-08-04，R21 mkmk 5.21 + VS2008 Win32 编译、链接通过 |
| 运行状态 | updated/stale 两个合法样件均 275 对象；5 个 Hole 全部 `NativeHoleDecoder` Typed；Pocket 保持 Generic；updated Hole up-to-date，stale Hole not-up-to-date |

## 证据缺口

- `TODO(R21_API_VERIFY)`：没有确认 Public R21 原生实现类名 getter，`native_type` 不猜测，使用 Late Type 写入 `startup_type`。
- `TODO(R21_API_VERIFY)`：没有确认 CATIA 安装 SP/HF 的 Public 运行时 API；Runtime SP/HF 写 `unknown`。文件头 `V5R21SP0HF0` 只进入低置信 `source_file_hint`。
- `TODO(R21_API_VERIFY)`：没有 Public 持久 Feature ID；ID 是同入口/同实现下 revision-local。
- `ListComponents` 文档说明结果 unordered。当前保留原始枚举次序且同机双跑字节稳定，但不声称跨 CATIA 实现或版本完全稳定。
- 当前没有验证原生 Pad/Pocket 专用 Decoder，也没有执行 B-Rep、Feature–Face 或制造特征识别；Native Hole 结果是保存的 Part Design 设计语义读取。
# 2026-08-05：CAA 原生拓扑出口证据

| 接口/类 | 头文件 | Framework | Public/Protected | 使用位置 | 验证状态 |
| --- | --- | --- | --- | --- | --- |
| `CATIPrtPart` / `IID_CATIPrtPart` | `MecModInterfaces/PublicInterfaces/CATIPrtPart.h` | `MecModInterfaces` | Public L1/U3 | `CadParseCAA.cpp::CollectPartMainSolidTopology` | R21 mkmk 通过，`kuang.CATPart` 实测成功 |
| `CATIPrtPart::GetSolid()` | `MecModInterfaces/PublicInterfaces/CATIPrtPart.h` | `MecModInterfaces` | Public L1/U3 | 获取 Part 主实体 `CATBody` | R21 mkmk 通过，输出 `TB000001` |
| `CATBody` | `GMModelInterfaces/PublicInterfaces/CATBody.h` | `GMModelInterfaces` | Public L1/U3 | 主实体拓扑对象 | 已新增 `IdentityCard` 依赖和 `CATGMModelInterfaces` 链接 |
| `CATTopology::GetCellNumbers()` | `GMModelInterfaces/PublicInterfaces/CATTopology.h` | `GMModelInterfaces` | Public L1/U3 | 输出 vertex/edge/face/volume 数量 | `kuang.CATPart` 实测 442/711/281/1 |
| `CATTopology::GetAllCells()` | `GMModelInterfaces/PublicInterfaces/CATTopology.h` | `GMModelInterfaces` | Public L1/U3 | 枚举 Face/Edge/Vertex/Volume 单元 | `kuang.CATPart` 实测输出 1435 条 cell |
| `CATCell::GetDimension()` / `GetNbDomains()` / `GetNbInternalDomains()` | `GMModelInterfaces/PublicInterfaces/CATCell.h` | `GMModelInterfaces` | Public L1/U3 | 输出单元维度和 domain 摘要 | R21 mkmk 通过，样件运行成功 |

当前只输出最终实体拓扑摘要和 revision-local cell ID；尚未通过 R21 Public 接口建立 `Feature -> Face` 或 `FTA -> Face` 映射，因此相关能力仍标记为 `not_available`。
