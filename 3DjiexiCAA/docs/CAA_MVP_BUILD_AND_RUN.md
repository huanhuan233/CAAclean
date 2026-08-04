# CATIA/CAA V5R21 构建与运行

## Feature Center Sidecar

先用现有 CAA Batch 生成原生 Bundle，再导出 STEP，最后在 `3dcad` Conda 环境构建：

```bat
conda run -n 3dcad python backend\scripts\feature_center.py build ^
  --step "模型.stp" ^
  --native-bundle "CAA输出目录" ^
  --output "FeatureCenter输出目录" ^
  --visual-review-mode disabled

conda run -n 3dcad python backend\scripts\feature_center.py validate ^
  --bundle "FeatureCenter输出目录"
```

本机 FreeCAD 路径从 `backend/.env` 的 `FREECAD_CMD_PATH` 读取；仓库根目录不再作为后端环境配置来源。默认不启用远程视觉服务。

要求 CATIA V5R21、CAA RADE V5R21、Visual Studio 2008 SP1、Win32/x86 和有效本机许可证设置。

```bat
cd /d D:\3Djiexi\3DjiexiCAA
set CAA_RADE_ROOT=D:\CATIA\Rade21
set CAA_PREREQ_ROOT=D:\CATIA
set RADECATSettingPath=C:\Users\pxy06\AppData\Roaming\DassaultSystemes\CATSettings\RADE
call tools\build_r21_x86.bat
```

构建脚本固定 32 位，执行 `mkGetPreq`/`mkmk`，检查日志和最终 exe；Git 可用时还会通过编译器宏嵌入当前 HEAD，否则 Manifest 如实写 `unknown`。

API 无关测试：

```bat
call tools\test_core_vs2008.bat
call tools\run_r21_x86.bat --self-test
```

解析样件（默认脱敏输入路径）：

```bat
call tools\run_r21_x86.bat --input "D:\3Djiexiother\kuang.CATPart" --output "D:\3Djiexiother\kuang_parse_v2" --read-only --pretty
```

Native Hole 回归样件：

```bat
call tools\run_r21_x86.bat --input "tests\fixtures\catia_r21\partdesign_holes_updated.CATPart" --output "%TEMP%\cadparse_native_hole_updated" --read-only
call tools\run_r21_x86.bat --input "tests\fixtures\catia_r21\partdesign_holes_stale.CATPart" --output "%TEMP%\cadparse_native_hole_stale" --read-only
```

只有调试时才显式加入 `--include-source-path`；默认 `manifest.json` 和 `parser.log` 只保留文件名。

输出包含：`manifest.json`、`features.jsonl`、`relations.jsonl`、`parameters.jsonl`、`business_features.jsonl`、`diagnostics.json`、`coverage.json`、`parser.log`。输入不存在、Session/Document 打开失败、守恒或来源引用失败、输出事务失败都返回非零码。

本机 mkmk 会提示缺少 JDK 1.6/Intel Fortran；当前纯 C++ 模块仍可成功构建，是否成功以 mkmk 错误扫描和 `intel_a\code\bin\CadParseMvp.exe` 是否生成共同判断。
# R21 构建与运行记录：cad_parse_mvp_v4

本轮新增 `GMModelInterfaces` Public 依赖，用于链接 `CATBody`、`CATTopology` 和 `CATCell`。
随后新增 `CATTPSInterfaces` Public 依赖，用于链接 `CATITPSDocument`、`CATITPSSet`、`CATITPSList` 和 `CATITPSGeometryList`。

构建命令：

```bat
set CAA_RADE_ROOT=D:\CATIA\Rade21
set CAA_PREREQ_ROOT=D:\CATIA
set RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE
call 3DjiexiCAA\tools\build_r21_x86.bat
```

自测命令：

```bat
call 3DjiexiCAA\tools\run_r21_x86.bat --self-test
```

kuang 回归命令：

```bat
call 3DjiexiCAA\tools\run_r21_x86.bat --input D:\3Djiexiother\kuang.CATPart --output %TEMP%\cadparse_topology_kuang_v1 --read-only
```

实测结果：

```text
R21 mkmk: 通过
self-test: 通过
kuang.CATPart: parsed 941 objects; parameters=228; declared_business_features=25
native_topology_body_count=1
native_topology_cell_count=1435
fta_extraction=complete
fta_set_count=0
```

构建日志仍会提示本机未在注册表中检测到 JDK 1.6 / Intel Fortran / VSTA，但当前 CAA C++ 编译、链接和运行均成功。
链接 CATTPSUUID 时还会出现 Dassault 预编译库缺少 `vc90.pdb` 的调试符号警告；该警告不影响 exe 生成和样件运行。
