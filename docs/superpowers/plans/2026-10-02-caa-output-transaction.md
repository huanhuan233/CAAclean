# CAA Output Transaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使 CAA 写出事务仅替换已证明属于解析器的产物，绝不删除未知目录，同时保持后端预创建空目录与旧采集包兼容。

**Architecture:** `ArtifactRepository` 负责唯一暂存/备份路径、所有权验证、提交及故障恢复；Windows 路径检查置于同一模块的私有帮助函数。Worker 仍只传入输出目录，不直接清理原生临时目录。

**Tech Stack:** VS2008 C++、Win32 文件 API、现有 `CaptureCoreTestMain.cpp`、Python pytest。

## Global Constraints

- 不修改 CATPart/CATProduct 原文件，不触碰 `main` 的未提交内容。
- 本机只实编 x86；实现避免依赖 C++11，x64 调用器目标契约保留。
- C++ 所有新增或修改函数写中文职责注释。
- 前端不直接读取 JSONL；本项不改变 JSONL/manifest schema。

---

### Task 1: 暴露并修复既有事务基线失败

**Files:**
- Modify: `caa_new/tests/CaptureCoreTestMain.cpp:507-550`
- Modify: `caa_new/CadCapture.edu/CadCapture.m/src/output/ArtifactRepository.cpp:262-318`

**Interfaces:**
- Consumes: `ArtifactRepository::Commit(package, report, output_dir, pretty, error)`。
- Produces: 失败时清晰的 `error` 文本，既有合法包正常写出。

- [x] **Step 1: 在失败的 `Commit` 断言中输出 `error`，并新增“预创建空目录正常提交”的断言。**

```cpp
const bool committed = repository.Commit(package, output_report, output_dir, true, error);
if (!committed) std::cerr << "transaction error: " << error << "\n";
Check(committed, "ArtifactRepository transactional commit");
```

- [x] **Step 2: 在 `caa_new` 目录运行 `cmd /c tools\\test_core_vs2008.bat`；发现固定暂存目录导致运行状态不稳定。**
- [x] **Step 3: 以每次独占暂存目录替换固定暂存名，不改变 JSONL/manifest 结构。**
- [x] **Step 4: 重跑同一命令，合法 CATPart/CATProduct 测试通过。**

### Task 2: 拒绝危险与未知目录

**Files:**
- Modify: `caa_new/CadCapture.edu/CadCapture.m/src/output/ArtifactRepository.cpp`
- Modify: `caa_new/tests/CaptureCoreTestMain.cpp`

**Interfaces:**
- Produces: `ValidateOutputTarget(path, error)` 私有函数，解析绝对路径并拒绝卷根、重解析点、非目录目标、未知非空目录；旧 `manifest.json` 且 schema 为 `caa_capture_*` 的目录可替换；空目录可写。

- [x] **Step 1: 加入拒绝未知非空目录、混入未知文件和同名未知暂存/备份的失败测试；验证哨兵文件保留。卷根通过路径规范化函数的早期分支拒绝，未对真实卷根运行破坏性测试。**

```cpp
Check(!repository.Commit(package, output_report, "build_core\\foreign_output", true, error),
      "unknown nonempty output is rejected");
Check(ReadableFileExists("build_core\\foreign_output\\sentinel.txt"),
      "unknown output remains untouched");
```

- [x] **Step 2: 运行核心测试，确认新断言红。**
- [x] **Step 3: 在仓储模块实现路径规范化、所有权校验和拒绝逻辑；任何失败不得调用递归清理。**
- [x] **Step 4: 重跑核心测试，确认新断言绿，且旧 bundle 可替换。**

### Task 3: 事务路径独占与故障恢复

**Files:**
- Modify: `caa_new/CadCapture.edu/CadCapture.m/src/output/ArtifactRepository.cpp`
- Modify: `caa_new/tests/CaptureCoreTestMain.cpp`
- Test: `backend/tests/test_catia_worker_server.py`

**Interfaces:**
- Produces: `CreateOwnedStaging` 生成唯一同级目录并写所有权标记；`CommitStaging` 在旧输出属于本解析器时用唯一备份替换，失败时恢复；`RemoveOwnedTree` 仅清理本次创建、无重解析点的路径。

- [x] **Step 1: 加入提交中途失败及预存旧 `.cadcapture_stage`/`.cadcapture_backup` 哨兵测试。**
- [x] **Step 2: 运行哨兵测试确认红；故障注入测试验证恢复分支。**
- [x] **Step 3: 实现唯一目录名、标记和非跟随重解析点的清理；若恢复失败，保留备份并返回完整路径。**
- [x] **Step 4: 重跑 C++ 核心与 Worker 测试，确认空目录、旧 bundle、未知目录、失败恢复均通过。**
- [x] **Step 5: 提交本项代码并记录测试命令、结果。**

## 自检

- 三个任务覆盖旧失败诊断、目录安全、事务恢复，并保持 Worker 预建目录契约。
- 所有写出都经 `ArtifactRepository::Commit`；没有向前端引入文件回退路径。
- 后续 2–8 项另立执行计划，按设计文档的原顺序推进。

## 执行记录

- `cmd /c tools\\test_core_vs2008.bat`：通过（含旧目录哨兵与备份后故障恢复）。
- `python -m pytest tests/test_catia_worker_server.py -q`：11 通过。
- `CAA_RADE_ROOT=D:\\CATIA\\Rade21`、`CAA_PREREQ_ROOT=D:\\CATIA` 下执行 `tools\\build_r21_x86.bat`：通过；x64 未在本机实编。
