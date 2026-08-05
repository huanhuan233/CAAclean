# CATIA V5R21 CAA 端完成度测试包

本包针对 `3DjiexiCAA` 当前提交中的真实实现制作，验收边界固定为：**Python 制造特征识别之前的 CAA/C++ 数据出口**。它不验收 Python 算法和 Web 前端，也不允许用 STEP、JSON fixture 或文件名猜测代替真实 CATIA 原生语义。

当前源码基线：

- Schema：`cad_parse_mvp_v9`
- Parser / Registry / Decoder Bundle：`1.9.0`
- 已注册专用 Decoder：`NativeHoleDecoder`、`NativePadDecoder`、`NativePocketDecoder`
- 已有 CAA 输出：`native_topology_*`、`native_feature_result_*`、候选 `native_feature_topology_links.jsonl`、`fta_sets.jsonl`、`fta_semantics.jsonl`、`native_mesh_face_map.jsonl`
- 当前明确缺口：权威 Feature–Topology 映射、FTA–Topology、完整解析几何、CATProduct 实例语义、更多原生 Decoder、真实 FTA/装配/复杂特征回归

## 包内内容

| 路径 | 用途 |
|---|---|
| `spec/fixture_catalog.json` | 全量样件矩阵；包括 Hole 复用、Part Design、GSD、FTA、属性/测量、连接定义、CATProduct、版本对和注册中心 |
| `spec/current_contract.json` | 从当前 `CadParseContracts.h` / `CadParseIR.cpp` 提取的 v9 字段契约 |
| `spec/completion_contract.json` | CAA 端可以宣布 complete 前必须满足的目标契约与门槛 |
| `generators/generate_core_fixtures.vbs` | 在 CATIA V5R21 中生成确定性基础/压力 CATPart、业务定义件和版本对；不生成 Hole |
| `generators/generate_product_fixtures.vbs` | 生成同 Part 多实例、变换和嵌套 CATProduct 样件 |
| `generators/prepare_fta_scaffolds.vbs` | 生成 FTA 载体并探测 FTA Automation；不能可靠自动创建的项写入阻塞账本，不伪造标注 |
| `generators/verify_real_fixtures.vbs` | 关闭后逐个重新打开 CATPart/CATProduct，记录原生类型、更新状态、FTA 数量和实例变换证据 |
| `manual/FTA_MBD最小人工建模清单.md` | V5R21 许可证或 Automation 限制下的最小人工建模步骤 |
| `tools/run_full_suite.ps1` | 生成/发现样件、构建、自测、双跑解析、逐件校验、汇总报告 |
| `tools/validate_caa_outputs.py` | 零第三方依赖的 JSON/JSONL、引用完整性、能力、映射、确定性和样件期望校验器 |
| `tools/lint_catalog.py` | 样件矩阵静态检查 |
| `tests/test_validator.py` | 校验器自身的离线回归测试 |
| `PROMPT_CAA端持续闭环.md` | 交给实现代理的持续闭环提示词 |

## 放入仓库

将整个 `CAA_R21_Completion_TestPack` 目录复制到：

```text
3DjiexiCAA\tests\caa_completion\
```

在已配置 `CAA_RADE_ROOT`、`CAA_PREREQ_ROOT` 且 CATIA V5R21 合法可用的 **32 位 CAA/VS2008 环境**中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\caa_completion\tools\run_full_suite.ps1 `
  -RepoRoot (Get-Location).Path `
  -Mode completion
```

只做离线静态检查：

```powershell
python .\tests\caa_completion\tools\lint_catalog.py `
  .\tests\caa_completion\spec\fixture_catalog.json

python -m unittest discover `
  -s .\tests\caa_completion\tests `
  -p "test_*.py"
```

只验当前 v9 基线，不要求所有 completion 门槛：

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\caa_completion\tools\run_full_suite.ps1 `
  -RepoRoot (Get-Location).Path `
  -Mode baseline `
  -SkipGenerate
```

## 结果语义

- `PASS`：该断言有真实 CATIA/CAA 输出证据并通过。
- `FAIL`：代码或输出违反契约，必须继续修。
- `BLOCKED`：缺少许可证、工作台、合法样件或已验证 Public API；必须写清证据，不能改成 PASS。
- `SKIP`：仅允许 baseline 模式跳过 completion-only 门槛；最终 completion 报告中不得用 SKIP 冒充完成。

`native_feature_topology_links.jsonl` 中当前的 `candidate` / `ambiguous` 只是几何指纹候选。只有可审计的 CATIA 原生持久命名、选取对象/TTRS 引用或等价权威链路才能进入 `confirmed`。测试器会专门阻止把候选映射计为 complete。

## 生成策略

样件矩阵采用五类来源：

- `reuse`：复用仓库现有 Hole CATPart，仍参加全量回归。
- `auto`：包内 VBS 在 CATIA V5R21 中自动生成并重新打开验证。
- `auto_probe`：脚本尝试公开 Automation；失败时记录真实 COM 错误和许可证信息。
- `manual_required`：必须在合法工作台中按最小清单建立，脚本只生成载体，不伪造原生历史/FTA。
- `derived_pair`：由真实 V1 复制后在 CATIA 中修改并保存 V2，用于跨版本/拓扑稳定性回归。

最终宣称完成前，`completion_required=true` 的每项都必须是 PASS，或仅因明确许可证/API 缺失而成为经批准的 BLOCKED；单独一个 Hole 或 `kuang.CATPart` 通过不能代表同族能力完成。
