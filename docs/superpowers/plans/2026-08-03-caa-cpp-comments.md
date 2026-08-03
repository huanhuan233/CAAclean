# CAA C++ Teaching Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `3DjiexiCAA` 中每个 C++ 函数增加前置用途说明，并用分层中文注释讲清 C++03、STL、CAA 生命周期和解析框架控制流，同时保证程序行为不变。

**Architecture:** 注释按“文件职责 → 类型职责 → 函数用途 → 复杂实现原因”四层组织。头文件解释契约和所有权，源文件解释实现策略与失败路径；每组修改后运行现有无许可证测试并审查 diff，最终执行函数注释覆盖审计和可用的 R21 构建。

**Tech Stack:** C++03、Visual Studio 2008 SP1、CAA RADE V5R21、Win32/x86、PowerShell、Git。

## Global Constraints

- 只修改 `3DjiexiCAA` 下的 `.cpp` 和 `.h` 注释及必要空行，不改变程序行为。
- 每个函数声明或定义前必须有中文用途说明。
- 重要函数必须说明参数、返回值、副作用、对象所有权、失败路径和兜底行为。
- 保留 C++、STL、CAA、RAII、Decoder、Generic、Opaque 等可检索英文术语。
- 不修改函数签名、类布局、控制流、字符串常量、构建配置或输出 Schema。
- 不引入 C++11 及以后语法，不声称未经 R21 资料验证的 API 行为。

---

### Task 1: 建立验证基线并注释公共契约

**Files:**
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseContracts.h`
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.h`
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.h`
- Modify: `3DjiexiCAA/CadParseMvp.edu/IdentityCard/IdentityCard.h`

**Interfaces:**
- Consumes: 现有 `TypeFingerprint`、`FeatureRecord`、`ParseContext`、`INativeObjectView`、`IFeatureDecoder`、`DecoderRegistry`、`ArtifactWriter` 和 CAA 适配器声明。
- Produces: 不变的 C++ 接口，以及覆盖每个函数声明的用途、参数、返回值和所有权说明。

- [ ] **Step 1: 运行注释前测试并记录基线**

Run:

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\test_core_vs2008.bat
```

Expected: 测试进程返回 `0`；若 VS2008 环境缺失，完整记录脚本输出，后续使用同一环境复测。

- [ ] **Step 2: 为公共数据结构和抽象接口添加教学注释**

在每个文件顶部解释职责；在每个结构体、类和函数前使用以下层次：

```cpp
// 用途：根据当前统计值验证 enumerated_total 是否等于四种解析结果之和。
// 返回：守恒时为 true；不守恒表示遍历或结果分类发生遗漏。
bool IsConserved() const;
```

明确解释构造函数初始化、`const` 成员函数、纯虚函数 `= 0`、虚析构、引用参数、借用指针与 Decoder 所有权。`IdentityCard.h` 解释各 `AddPrereqComponent` 声明属于构建元数据，不是普通运行时函数。

- [ ] **Step 3: 审查头文件只发生注释变化**

Run:

```bash
git diff --check -- 3DjiexiCAA/CadParseMvp.edu/IdentityCard/IdentityCard.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseContracts.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.h
git diff --word-diff=porcelain -- 3DjiexiCAA/CadParseMvp.edu/IdentityCard/IdentityCard.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseContracts.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.h
```

Expected: `diff --check` 无输出；word diff 中仅新增注释文字和空行。

- [ ] **Step 4: 提交公共契约注释**

```bash
git add 3DjiexiCAA/CadParseMvp.edu/IdentityCard/IdentityCard.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseContracts.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.h 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.h
git commit -m "docs: explain CAA parser contracts"
```

### Task 2: 注释 Registry、Decoder 兜底和 Crawler 核心流程

**Files:**
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCore.cpp`

**Interfaces:**
- Consumes: `CadParseContracts.h` 中全部核心契约。
- Produces: 不变的统计、诊断、Decoder 匹配、Generic/Opaque 兜底和树遍历实现。

- [ ] **Step 1: 为每个函数定义增加用途说明**

注释必须覆盖 `ParseStatistics`、`ParseContext::AddDiagnostic`、`GenericFeatureDecoder`、`OpaqueObjectRecorder`、`DecoderRegistry`、`FeatureTypeFingerprintBuilder`、`FeatureTypeCatalog`、`InterfaceProbeService`、`UnknownTypeCollector`、`CoverageTracker` 和 `UniversalFeatureCrawler` 的所有函数。短函数至少写用途；核心函数采用：

```cpp
// 用途：按确定性规则从所有匹配项中选出唯一 Decoder。
// 规则：先比较 priority，再以稳定 decoder ID 决胜；同优先级冲突会写入 warning。
// 返回：Registry 不拥有返回指针；调用者不得 delete。
```

- [ ] **Step 2: 在复杂代码块解释实现原因**

解释稳定指纹分隔符、`std::vector` 迭代器、按 priority/ID 决胜、先建基础记录再 Decode、对象级失败为何继续遍历、Generic 失败为何进入 Opaque，以及 Coverage 守恒如何更新。

- [ ] **Step 3: 运行核心测试并检查 diff**

Run:

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\test_core_vs2008.bat
```

Run:

```bash
git diff --check -- 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCore.cpp
git diff --word-diff=porcelain -- 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCore.cpp
```

Expected: 测试与基线一致；diff 仅新增注释和空行。

- [ ] **Step 4: 提交核心流程注释**

```bash
git add 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCore.cpp
git commit -m "docs: explain decoder and crawler flow"
```

### Task 3: 注释结构化 IR 输出实现

**Files:**
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.cpp`

**Interfaces:**
- Consumes: `ParseContext`、`FeatureRecord`、`RelationRecord`、`DiagnosticRecord` 和 `ArtifactWriter`。
- Produces: 不变的 JSON 转义、JSONL 记录与六类产物文件写出行为。

- [ ] **Step 1: 为每个函数定义增加用途说明**

说明 JSON 字符串转义、数组/对象写入、Feature/Relation/Diagnostic 序列化和 `ArtifactWriter::WriteAll`。强调 JSONL 每行一个完整对象、输出记录不得包含 CAA 指针。

- [ ] **Step 2: 注释边界处理和输出失败路径**

解释控制字符为何写成 `\u00XX`、`std::map` 为何带来稳定属性顺序、文件流状态如何传播错误，以及 Coverage 不守恒为何不能静默成功。

- [ ] **Step 3: 测试并审查**

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\test_core_vs2008.bat
```

```bash
git diff --check -- 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.cpp
git diff --word-diff=porcelain -- 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.cpp
```

Expected: JSON 转义和 Golden Output 测试通过；diff 仅新增注释和空行。

- [ ] **Step 4: 提交 IR 注释**

```bash
git add 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseIR.cpp
git commit -m "docs: explain structured IR output"
```

### Task 4: 注释 CATIA R21 运行时和对象适配层

**Files:**
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.cpp`

**Interfaces:**
- Consumes: 已验证的 R21 PublicInterfaces、`NativeObjectView`、`SessionGuard`、`DocumentGuard` 和 `UniversalFeatureCrawler`。
- Produces: 不变的 Session 创建、CATPart 打开、公开接口遍历、类型指纹和清理行为。

- [ ] **Step 1: 为匿名命名空间辅助函数逐个增加用途说明**

说明 UTF-8 转换、HRESULT/错误文本处理、接口探测、对象名读取、树路径构造和 CAA 引用释放。每个函数明确输入指针是否允许为空、是否借用、是否增加引用计数。

- [ ] **Step 2: 为运行时类和适配器全部函数增加用途说明**

覆盖 `NativeObjectView`、Typed Decoder、`SessionGuard`、`DocumentGuard`、Decoder 工厂/销毁和 `RunCaaParse`。重点解释 C++03 RAII、构造/析构配对、CAA `AddRef/Release`、对象级错误隔离和已验证遍历入口的边界。

- [ ] **Step 3: 检查 API 表述与证据文档一致**

Run:

```bash
rg -n "CATCreateSession|CATDeleteSession|CATDocumentServices|CATIDocRoots|CATIContainer|CATISpecObject|CATIMmiPrtContainer|CATIPrtContainer" 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.cpp 3DjiexiCAA/docs/CAA_R21_API_EVIDENCE.md
git diff --check -- 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.cpp
```

Expected: 注释不超出证据文档确认范围；无空白错误。

- [ ] **Step 4: 构建 R21 x86 模块**

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\build_r21_x86.bat
```

Expected: 与基线相同环境下构建成功并生成 Batch 可执行文件；若许可证或 RADE 环境失败，保留完整错误并继续执行 API 无关测试。

- [ ] **Step 5: 提交 CAA 适配层注释**

```bash
git add 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseCAA.cpp
git commit -m "docs: explain CATIA R21 runtime lifecycle"
```

### Task 5: 注释 Batch 入口和无许可证测试

**Files:**
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseBatch.cpp`
- Modify: `3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseSelfTests.cpp`
- Modify: `3DjiexiCAA/tests/CadParseCoreTestMain.cpp`

**Interfaces:**
- Consumes: `RunCaaParse`、`RunCadParseSelfTests`、命令行参数和核心契约。
- Produces: 不变的 Batch 退出码、参数校验和十类自测结果。

- [ ] **Step 1: 注释 Batch 的每个函数和阶段**

解释参数查找、扩展名校验、输出目录准备、`--self-test` 分支、解析阶段计时和退出码传播。指出 `main(int, char**)` 的 `argv` 生命周期由 C 运行库管理。

- [ ] **Step 2: 注释测试夹具和每个测试函数**

每个伪对象、伪 Decoder 和测试函数前说明被验证的不变量，例如确定匹配、Generic/Opaque 兜底、同优先级冲突、异常隔离、JSON 转义、ID 唯一性、输出顺序和 Coverage 守恒。

- [ ] **Step 3: 运行全部无许可证测试**

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\test_core_vs2008.bat
call tools\run_r21_x86.bat --self-test
```

Expected: 两个入口在各自可用环境中返回 `0`；测试结果与基线一致。

- [ ] **Step 4: 提交入口和测试注释**

```bash
git add 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseBatch.cpp 3DjiexiCAA/CadParseMvp.edu/CadParseMvp.m/src/CadParseSelfTests.cpp 3DjiexiCAA/tests/CadParseCoreTestMain.cpp
git commit -m "docs: explain batch entry and self tests"
```

### Task 6: 全量覆盖审计与最终验证

**Files:**
- Verify: `3DjiexiCAA/**/*.cpp`
- Verify: `3DjiexiCAA/**/*.h`

**Interfaces:**
- Consumes: 前五个任务的全部注释变更。
- Produces: 每个函数均有用途说明、行为未变、测试与构建结果可复核的最终状态。

- [ ] **Step 1: 逐文件审计函数前置注释**

Run:

```powershell
rg -n "^[A-Za-z_~][A-Za-z0-9_:<> ,*&]*\(" D:\3Djiexi\3DjiexiCAA -g '*.cpp' -g '*.h'
```

逐个核对搜索结果的紧邻上方存在 `用途：` 注释；宏式 `AddPrereqComponent` 单独按 IdentityCard 构建语义核对。对多行函数签名使用人工复核，避免正则漏报。

- [ ] **Step 2: 审查本轮所有源码差异**

Run:

```bash
git diff 5a5380c..HEAD -- 3DjiexiCAA
git diff --check 5a5380c..HEAD -- 3DjiexiCAA
```

Expected: 仅有注释和必要空行，没有 token、常量、签名或控制流变化；`diff --check` 无输出。

- [ ] **Step 3: 执行最终测试与构建**

```bat
cd /d D:\3Djiexi\3DjiexiCAA
call tools\test_core_vs2008.bat
call tools\build_r21_x86.bat
call tools\run_r21_x86.bat --self-test
```

Expected: 可用环境中的全部命令返回 `0`。任何无法执行的命令必须记录具体原因，不得报告为通过。

- [ ] **Step 4: 检查工作区和提交历史**

```bash
git status --short
git log --oneline -8
```

Expected: 没有未提交的 C++ 注释修改；提交按公共契约、核心流程、IR、CAA 运行时、Batch/测试分组。
