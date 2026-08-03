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

## 证据缺口

- `TODO(R21_API_VERIFY)`：没有确认 Public R21 原生实现类名 getter，`native_type` 不猜测，使用 Late Type 写入 `startup_type`。
- `TODO(R21_API_VERIFY)`：没有确认 CATIA 安装 SP/HF 的 Public 运行时 API；Runtime SP/HF 写 `unknown`。文件头 `V5R21SP0HF0` 只进入低置信 `source_file_hint`。
- `TODO(R21_API_VERIFY)`：没有 Public 持久 Feature ID；ID 是同入口/同实现下 revision-local。
- `ListComponents` 文档说明结果 unordered。当前保留原始枚举次序且同机双跑字节稳定，但不声称跨 CATIA 实现或版本完全稳定。
- 当前没有验证原生 Pad/Pocket/Hole 接口，也没有执行 B-Rep、Feature–Face 或制造特征识别。
