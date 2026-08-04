# CATIA V5R21 原生 Part Design Hole 回归样件

## 样件用途

本目录中的两个 CATPart 专用于后续原生 Part Design Hole 接口回归，不代表当前解析器已经实现 `NativeHoleDecoder`：

- `partdesign_holes_updated.CATPart`：包含已更新的原生 Pad、五个原生 Hole 和一个原生 Pocket；
- `partdesign_holes_stale.CATPart`：保留同一主要历史树，但在 Manual Update 模式下把 `Pad_Base` 长度从 25 mm 改为 27 mm 后不调用 `Part.Update`，用于验证真实未更新状态。

两个文件均由 CATIA V5R21 Automation 在本机实际创建，随后保存、关闭并重新打开验证。它们不是改名后的 GSMTool，也没有修改 CATPart 二进制内容。

## 实际历史树

验证器从 `PartBody.Shapes` 取得的稳定原生形状顺序为：

```text
Part
└─ PartBody
   ├─ Sketch_Base
   ├─ Pad_Base                     (Pad)
   ├─ Position_Hole_Blind
   ├─ Hole_Blind                   (Hole)
   ├─ Position_Hole_Through
   ├─ Hole_Through                 (Hole)
   ├─ Position_Hole_Counterbore
   ├─ Hole_Counterbore             (Hole)
   ├─ Position_Hole_Threaded
   ├─ Hole_Threaded                (Hole)
   ├─ Position_CoolingPort_A
   ├─ CoolingPort_A                (Hole)
   ├─ Sketch_Pocket
   └─ Pocket_Control               (Pocket)
```

`PartBody.Shapes` 的实际顺序是 `Pad_Base`、四个具名 Hole、`CoolingPort_A`、`Pocket_Control`，共 7 个。`PartBody.Sketches` 在 R21 Automation 中计数为 12；除脚本创建的基础、定位和 Pocket 草图外，还包含 Hole 创建过程管理的草图对象。

基体由 `Sketch_Base` 的 180 mm × 100 mm 矩形拉伸 25 mm 得到。所有 Hole 使用位于 XY 基准面的单点定位草图创建，孔轴沿草图法向进入实体。`Pocket_Control` 使用中心 `(0, 25)`、半径 10 mm 的圆形草图，深度 7 mm。

## Hole 类型、尺寸和位置

以下值由保存后重新打开的对象通过 Hole 专用 Automation 属性读取：

| 名称 | 原生类型 | 原点 (mm) | 直径 (mm) | 终止方式/深度 | 其他属性 |
| --- | --- | ---: | ---: | --- | --- |
| `Hole_Blind` | Simple Hole | `(-65, -25, 0)` | 10 | Offset，12 mm | Smooth |
| `Hole_Through` | Simple Hole | `(-30, -25, 0)` | 10 | Up To Last | Smooth |
| `Hole_Counterbore` | Counterbored Hole | `(5, -25, 0)` | 10 | Offset，15 mm | 沉孔直径 18 mm，沉孔深度 5 mm |
| `Hole_Threaded` | Simple Hole | `(40, -25, 0)` | 8.376（M10 底孔） | Offset，15 mm | 原生 ThreadingMode=Threaded；M10；螺纹直径 10 mm；螺纹深度 10 mm；螺距 1.5 mm |
| `CoolingPort_A` | Simple Hole | `(70, 20, 0)` | 9 | Offset，12 mm | Smooth；名称不含 `Hole` 或“孔”类词语 |

五个原点互不相同。保存后读取的五个 Hole 方向均为 `(0, 0, 1)`，`Pocket_Control.DirectionOrientation=catRegularOrientation`；它们从 XY 底面沿 Pad 的正 Z 方向真实切入材料。最终实体体积为 441247.239621105 mm³，小于未切削基体的 450000 mm³。`CoolingPort_A` 用于证明验证不能依赖显示名称：验证器先按该显式测试名取回对象，再成功读取 `Diameter`、`Type`、`BottomLimit`、`ThreadingMode`、`GetOrigin` 和 `GetDirection` 等 Hole 专用成员，才把它确认为原生 Hole。

`Pocket_Control` 是原生 Pocket 反例。验证器确认其 Automation 类型为 `Pocket`，能够读取 `FirstLimit`，同时 Hole 专用属性探测失败，因此不会被计入五个 Hole。

## stale 状态制造与验证

生成器通过 `CATIA.SettingControllers.Item("CATMmuPartInfrastructureSettingCtrl")` 读取并暂存用户原来的更新模式，然后：

1. 把 `UpdateMode` 设置为 `catManualUpdate`；
2. 重新打开 updated 文件；
3. 将 `Pad_Base.FirstLimit.Dimension.Value` 从 25 mm 改为 27 mm；
4. 不调用 `Part.Update`，另存为 stale 文件；
5. 关闭并重新打开 stale 文件；
6. 使用 `Part.IsUpToDate(object)` 验证状态；
7. 关闭文档并恢复原更新模式。

重新打开后的实际未更新形状共 7 个：`Pad_Base|Pad`、五个 `Hole` 和 `Pocket_Control|Pocket`。文件仍能正常打开，主要历史树和有效实体都存在；该状态不是文件名、Manifest 或损坏文件伪造的。

## 本机 R21 生成接口证据

本轮使用的接口都能在本机 `D:\CATIA` 安装中的 PublicInterfaces IDL 找到：

| Automation 接口/成员 | 本机头文件或 IDL | 用途 |
| --- | --- | --- |
| `CATIAApplication.Documents`、`SystemConfiguration`、`SettingControllers` | `InfInterfaces/PublicInterfaces/CATIAApplication.idl` | 文档、运行时版本和设置入口 |
| `CATIASystemConfiguration.Version/Release/ServicePack` | `InfInterfaces/PublicInterfaces/CATIASystemConfiguration.idl` | 运行时版本来源 |
| `CATIAPart.Bodies/ShapeFactory/OriginElements/CreateReferenceFromObject/Update/UpdateObject/IsUpToDate` | `MecModInterfaces/PublicInterfaces/CATIAPart.idl` | Part 建模、更新和状态验证 |
| `CATIAPartInfrastructureSettingAtt.UpdateMode` | `MecModInterfaces/PublicInterfaces/CATIAPartInfrastructureSettingAtt.idl` | Manual Update 状态制造 |
| `CatPartUpdateMode` | `MecModInterfaces/PublicInterfaces/CatPartUpdateMode.idl` | `catManualUpdate=0` |
| `CATIASketches.Add`、`CATIASketch.OpenEdition`、`CATIAFactory2D.CreateLine/CreatePoint/CreateClosedCircle` | `SketcherInterfaces/PublicInterfaces` | 基础、孔定位和 Pocket 草图 |
| `CATIAShapeFactory.AddNewPad/AddNewHoleFromSketch/AddNewPocket` | `PartInterfaces/PublicInterfaces/CATIAShapeFactory.idl` | 原生 Part Design 特征生成 |
| `CATIAHole` 的类型、直径、终止、沉孔、螺纹、`Reverse`、`GetOrigin` 和 `GetDirection` | `PartInterfaces/PublicInterfaces/CATIAHole.idl` | Hole 配置、切削方向和真实性验证 |
| `CatHoleType`、`CatHoleThreadingMode` 等枚举 | `PartInterfaces/PublicInterfaces/CATHoleDefs.idl` | R21 枚举值依据 |
| `CATIALimit.LimitMode/Dimension`、`CatLimitMode` | `PartInterfaces/PublicInterfaces/CATIALimit.idl`、`CATLimitDefs.idl` | Blind 与 Up To Last 区分 |
| `CATIAProduct.Analyze`、`CATIAAnalyze.Volume` | `ProductStructureInterfaces/PublicInterfaces` | 保存后最终实体体积及真实减料验证 |

本轮没有使用 ProtectedInterfaces，也没有使用名称匹配来替代 Hole 专用接口探测。

## 运行生成和验证

在 `3DjiexiCAA` 目录的普通 `cmd.exe` 中执行：

```bat
tools\generate_partdesign_hole_fixtures.bat
```

该命令生成两个 CATPart，关闭并重新打开它们，随后调用独立验证器并重建 `fixtures_manifest.json`。只重新验证现有文件时执行：

```bat
tools\verify_partdesign_hole_fixtures.bat
```

两个脚本也可以把目标目录作为第一个参数传入；默认目录为 `tests\fixtures\catia_r21`。失败时返回非零退出码，Manifest 只会在独立验证成功后写出。

## 使用现有 CadParseBatch 回归

本机验证使用以下命令形式：

```bat
set CAA_RADE_ROOT=D:\CATIA\Rade21
set CAA_PREREQ_ROOT=D:\CATIA
set RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE

call tools\run_r21_x86.bat --input "tests\fixtures\catia_r21\partdesign_holes_updated.CATPart" --output "%TEMP%\cadparse_fixture_updated" --read-only
call tools\run_r21_x86.bat --input "tests\fixtures\catia_r21\partdesign_holes_stale.CATPart" --output "%TEMP%\cadparse_fixture_stale" --read-only
```

在 Schema v2 / Parser 1.2.0 的实际结果中，两个文件均解析 275 个对象，`typed=14`、`generic=261`、`opaque=0`、`failed=0`、关系 548 条，且无悬空关系。五个原生 Hole 均由 `NativeHoleDecoder` 通过同一对象的 Public `CATIAHole` 接口确认并产生 Typed 载荷；`Pocket_Control` 保持 Generic 且没有 `native_hole` 字段。`business_features.jsonl` 为空，现有声明式业务特征语义未被修改。

updated 文件连续解析两次后，`features.jsonl`、`relations.jsonl`、`parameters.jsonl` 和 `business_features.jsonl` 的 SHA-256 均分别一致。updated 的五个顶层 Hole 在解析记录中均为 `up_to_date`；stale 的五个顶层 Hole 均为 `not_up_to_date`。

当前 CAA crawler 还会枚举低层 `MFparameter`、二维草图元素和关系等内部规格对象。即使九个具名设计节点已由 Automation 确认为 up-to-date，updated 的 Coverage 仍把其中 74 个内部规格对象报告为 `not_up_to_date`；stale 为 90 个。本文只据 `Part.IsUpToDate` 对具名 Part Design 历史节点声明 updated/stale 状态，不把内部规格统计混同为顶层设计特征状态。

## 运行时版本与已知限制

实际生成和验证环境由 `CATIA.SystemConfiguration` 返回：CATIA V5R21 SP0。该公开 Automation 接口未提供 Hotfix，因此 Manifest 如实记录 `hotfix=unknown`，没有使用 CATPart 文件头冒充运行时版本。

本机 R21 对隐藏 Automation 会话中的 `Selection.Search("Topology.Face,...")` 未返回 Pad 拓扑面，因此生成器采用本机 IDL 明确支持的 `AddNewHoleFromSketch`：在 XY 基准面创建单点定位草图，再建立原生 Hole。Hole 创建后调用 `Reverse` 指向正 Z，Pocket 显式设置为 regular orientation；保存后验证器再次读取方向，并以最终实体体积小于基体体积证明减料真实发生。这种方式会产生比“直接选择顶面”更多的草图对象，但不影响 Hole 的原生 Part Design 类型、专有属性或实体结果。

Automation 的显式测试名称可由 `Part.FindObjectByName` 取回。当前 CAA 规格名称仍是 `Hole.1` 至 `Hole.5`，而 `NativeHoleDecoder` 可从同一 `CATIAHole` 的 Public `CATIABase::get_Name` 取得 `Hole_Blind` 至 `CoolingPort_A` 别名；两者分别保存。这正是 Decoder 必须依赖 Hole 专用接口、不能依赖显示名称的原因之一。
