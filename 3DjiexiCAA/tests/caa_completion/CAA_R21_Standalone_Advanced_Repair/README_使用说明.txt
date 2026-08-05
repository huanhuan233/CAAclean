CATIA V5R21 高级样件独立修复脚本
===================================

修订说明（v1.0.3）
------------------
- 根据 V5R21SP0 的 v1.0.2 实机日志，仅修复 6 个失败件；已通过的 Rib/Slot、Pattern、GSD 不再重跑；
- 修正 CATIA 枚举数值：catTangencyChamfer=0、catLengthAngleChamfer=1；旧版把两者写反，实际生成了无效的 5/45 mm 双长度倒角；
- Fillet/Chamfer/Shell/Thickness 直接使用 Selection.Item(...).Value 返回的 TriDimFeatEdge/Face Boundary；不再错误读取 SelectedElement.Reference；
- Boundary 在 ShapeFactory 消费前保持在 Selection 中，避免 R21 的短生命周期拓扑对象因 Selection.Clear 提前失效；
- Shaft/Groove 的 Sketch 现在真实包含 CenterLine，满足 AddNewShaft/AddNewGroove 对“轮廓 + 旋转轴”的要求；
- Boolean 改成 4 个独立结果 Body，避免四种布尔连续串联后最终 Intersect 把整件更新为空；每个结果 Body 单独做 SPA 体积断言；
- Shell 与 Thickness 使用两个独立原生 Body，降低 R21 拓扑顺序对 Thickness 成败的影响；
- 保存前增加内存中特征树硬校验；不会再把“创建调用返回了对象、实际树里却没有特征”的文件拿去关闭重开；
- 日志增加 [TOPOLOGY]、[FEATURE]、[HISTORY-OK]、[BODY-VOLUME] 证据；
- 新增 run_repair_failed_only.bat，只运行 fillet、chamfer、shaft_groove、shell_thickness、boolean、pressure；
- 修复 VBScript 不支持 VBA Double 字面量后缀（例如 5#）导致的“缺少 ')'”编译错误；
- 批处理新增启动前语法预检；若脚本无法编译，只报一次并停止，不再重复运行 9 个案例；
- 可单独执行以下命令验证脚本语法，且不会启动 CATIA：

  C:\Windows\SysWOW64\cscript.exe //nologo generate_one_advanced_fixture.vbs --syntax-check

用途
----
不用再运行原来的 generate_advanced_fixtures.vbs，也不用手工重画九个零件。
本包针对原脚本的即时失败修复：

1. Fillet/Chamfer/Shell：使用 Selection.Item(...).Value 返回的原生 Boundary；
   自动搜索失败时可改用交互选边/选面。
2. Chamfer：补齐 V5 Automation 要求的 6 个参数。
3. Shaft/Groove：显式绑定 Profile 和 RevoluteAxis。
4. RectPattern：补齐第二方向反转参数和 RotationAngle，共 12 个参数。
5. GSD：允许纯点/线/面样件体积为 0。
6. Pressure：真实创建 Pad -> Pocket -> Fillet -> Chamfer。
7. Rib/Slot、Boolean：补上旧脚本没有生成的 Slot、Remove、Assemble、Intersect。

最快运行方式
------------
把本文件夹复制到：

  D:\3Djiexi\3DjiexiCAA\tests\caa_completion\CAA_R21_Standalone_Advanced_Repair

然后在该文件夹地址栏输入 cmd，运行：

  run_repair_all.bat "..\fixtures_manual"

已经运行过 v1.0.1 且 rib_slot、pattern、gsd_analytic 通过时，请优先运行：

  run_repair_failed_only.bat "..\fixtures_manual"

也可以直接双击 run_repair_all.bat；默认输出目录是 ..\fixtures_manual。

脚本会按顺序单独生成 9 个文件。一件失败不会中断其他件。

如果仍有 0x1A8
----------------
仅对失败件使用引导模式。CATIA 会让你点一条边或一个面，不需要重新建模：

  run_one_guided.bat fillet "..\fixtures_manual"
  run_one_guided.bat chamfer "..\fixtures_manual"
  run_one_guided.bat shell_thickness "..\fixtures_manual"
  run_one_guided.bat pressure "..\fixtures_manual"

安全规则
--------
- 先保存为 __repair_tmp_*.CATPart；
- 关闭并重新打开；
- 检查必需的原生特征名；
- 检查实体体积（GSD 除外）；
- 全部通过后才替换正式文件；
- 原文件复制到 fixtures_manual\repair_backups\时间戳\；
- 失败时原文件保持不变。

结果
----
- advanced_repair_ledger.tsv：本修复脚本的逐次结果；
- generation_ledger.tsv：同时追加到原测试包总账；
- generated：完成关闭重开与最小原生历史检查；
- blocked：该件未替换，查看错误步骤即可。

范围说明
--------
这些脚本生成的是“每类至少一个真实原生特征”的 CAA Decoder 最小验收件，
用于尽快把 CAA 解析能力跑通。它不会冒充完整工程变体库：例如变半径圆角、
三切圆角、User Pattern、全部 GSD 曲面变体等仍属于后续压力回归样件。
