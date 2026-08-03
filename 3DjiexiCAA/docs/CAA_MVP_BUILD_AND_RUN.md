# CATIA/CAA V5R21 构建与运行

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
call tools\run_r21_x86.bat --input "D:\3Djiexiother\kuang.CATPart" --output "D:\3Djiexiother\kuang_parse_v1" --read-only --pretty
```

只有调试时才显式加入 `--include-source-path`；默认 `manifest.json` 和 `parser.log` 只保留文件名。

输出包含：`manifest.json`、`features.jsonl`、`relations.jsonl`、`parameters.jsonl`、`business_features.jsonl`、`diagnostics.json`、`coverage.json`、`parser.log`。输入不存在、Session/Document 打开失败、守恒或来源引用失败、输出事务失败都返回非零码。

本机 mkmk 会提示缺少 JDK 1.6/Intel Fortran；当前纯 C++ 模块仍可成功构建，是否成功以 mkmk 错误扫描和 `intel_a\code\bin\CadParseMvp.exe` 是否生成共同判断。
