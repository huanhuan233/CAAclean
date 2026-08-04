# NativeHoleDecoder（CATIA V5R21）

## 语义边界

`NativeHoleDecoder` 读取 CATPart 历史树中已经存在的原生 Part Design Hole 设计语义。它不是 B-Rep 圆柱面识别、制造特征推理或 Feature–Face 映射，也不会把 GSMTool 声明式“孔”提升为原生 Hole。

`startup_type == "Hole"` 只用于候选预筛选。Typed 成功的必要链路是：

```text
CATISpecObject*
→ QueryInterface(IID_CATIAHole)
→ CATIAHole*（Public）
→ 必需字段成功读取
→ NativeHoleData
→ FeatureRecord.native_hole
```

接口不支持时回到 Generic；QueryInterface 异常、必需字段异常只影响当前对象。可选字段对当前孔型不适用时写 `null/not_applicable`，不计 partial。

## R21 接口与依赖

| 项目 | 实际值 |
|---|---|
| 接口 | `CATIAHole` |
| IID | `IID_CATIAHole`；IDL DCE `a6ae2c93-64f9-11d1-a27f0000f87546fd` |
| 生成头 | `D:\CATIA\PartInterfaces\PublicGenerated\intel_a\CATIAHole.h` |
| 原始 IDL | `D:\CATIA\PartInterfaces\PublicInterfaces\CATIAHole.idl` |
| Framework | `PartInterfaces` |
| 级别 | Public L1/U3；未使用 ProtectedInterfaces |
| IdentityCard | `AddPrereqComponent("PartInterfaces", Public)` |
| LINK_WITH | `CATPartInterfaces`、`PartInterfacesUUID`；既有 `KnowledgeItf` 提供参数基类实现 |
| 引用管理 | QueryInterface 及属性返回的 `CATIAHole`、`CATIALimit`、`CATIALength`、`CATIAAngle`、`CATIAStrParam` 均由对象级 `CaaInterfaceGuard` 精确 `Release()` |

## 字段读取

| 输出字段 | R21 Public 方法 | 单位/处理 |
|---|---|---|
| `hole_type/raw` | `CATIAHole::get_Type` + `CATHoleDefs.h` | 保留规范名和原始枚举 |
| `diameter_mm` | `get_Diameter` → `CATIALength::get_Value` | mm |
| `origin_mm` | `GetOrigin(SAFEARRAY(VARIANT))` | mm，三元素 number 数组 |
| `direction` | `GetDirection(SAFEARRAY(VARIANT))` | 无量纲，三元素 number 数组 |
| `bottom_limit.mode/raw` | `get_BottomLimit` → `CATIALimit::get_LimitMode` + `CATLimitDefs.h` | Offset/Up To Last 等 |
| `bottom_limit.depth_mm` | `CATIALimit::get_Dimension` → `CATIALength::get_Value` | 仅 Offset 有意义；其余 null |
| Head | `get_HeadDiameter/get_HeadDepth/get_HeadAngle` | R21 IDL 矩阵：Tapered=Angle；Counterbored=Diameter+Depth；Counterdrilled=三者；Countersunk=Depth+Angle。mm；角度为 decimal degrees |
| ThreadingMode | `get_ThreadingMode` | `catThreadedHoleThreading=0`、`catSmoothHoleThreading=1` |
| Thread 数值 | `get_ThreadDiameter/get_ThreadDepth/get_ThreadPitch` | mm |
| Thread 描述 | `get_HoleThreadDescription` → `CATIAStrParam::get_Value` | 接口原文，例如样件为 `M10`，不拼接 |
| Automation 别名 | 同一 `CATIAHole` 的 `CATIABase::get_Name` | 与规格内部名分别保存；不可用时为 null |

`CATIARealParam` 本机 Encyclopedia 明确：Length 的 `Value` 为毫米，Angle 为十进制度。未知 Hole/Limit 枚举保留 raw 数值并产生 `NATIVE_HOLE_ENUM_UNKNOWN`。

## 通用扩展协议

Core 只依赖 `INativeObjectView`、`INativeHoleView`、`INativeFeatureDecoder`、`DecoderMatchStatus`、`DecodeResult`、`ParseContext` 和纯数据 Typed Payload。`DecoderRegistry` 按 priority 和稳定 Decoder ID 确定选择；多个候选产生冲突诊断。专用 Decoder 失败后统一恢复基础记录并进入 Generic/Opaque，半成品 Typed Payload 不会泄漏。

新增其他 Part Design 特征时，应增加独立 View 和独立 Typed Payload，再通过 `RegisterCoreDecoders` 注册；不得向 `UniversalFeatureCrawler` 添加特征类型 if/else。本版本没有空的 Pad/Pocket/Fillet Decoder。

## 实际验证（2026-08-04）

R21 mkmk 5.21、VS2008 SP1、Win32/x86 编译链接成功。updated 和 stale 样件各枚举 275 对象，五个 Hole 均由 `NativeHoleDecoder` Typed，Pocket 保持 Generic；Hole 专项统计为 candidate=5、success=5、partial=0、unsupported=0、exception=0。实际 CATPart 集成覆盖 Simple、Counterbored、Offset、Up To Last、Smooth 和 Threaded；Tapered、Countersunk、Counterdrilled 的字段矩阵来自本机 Public IDL 和编译验证，本轮没有声称已用对应 CATPart 做运行验证。

updated 中五孔均 `up_to_date`；stale 中五孔均 `not_up_to_date`，且仍能读取相同设计参数。`CoolingPort_A` 的 CAA 规格内部/显示名是 `Hole.5`，同一 `CATIAHole` 的 Automation 别名为 `CoolingPort_A`，专用接口给出直径 9 mm、原点 `(70,20,0)`、方向 `(0,0,1)`、Offset 深度 12 mm，证明解码不依赖名称。

updated 双跑的四个核心 JSONL 字节一致。旧 `kuang.CATPart` 仍为 941 对象、228 参数、25 个声明式业务特征（3 boss、8 hole、14 slot），`NativeHoleDecoder` 命中 0。
