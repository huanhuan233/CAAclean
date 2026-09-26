# CAA ZIP ASCII 工作路径 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让带中文共同顶层目录的 CATProduct ZIP 在交给 R21 CAA_NEW 前获得 ASCII 工作路径，同时保持装配依赖层级和根 Product 选择规则。

**Architecture:** 在 Worker 的 ZIP 解包边界计算所有非目录条目的唯一共同顶层目录；若存在，则仅剥离这一段后逐项安全解包。根 Product 仍交给 `_select_entry_catproduct` 选择，路径越界保护在归一化后的目标路径上执行。

**Tech Stack:** Python 3.11、FastAPI Worker、`zipfile`、pytest、CATIA V5R21 CAA_NEW x86

## Global Constraints

- 不修改原始 ZIP 或 CATIA 文件内容。
- 不重命名 CATProduct/CATPart 文件，保持内部相对引用。
- 没有唯一共同顶层目录时维持原布局。
- 继续拒绝绝对路径、父目录穿越和越出 `source-bundle` 的 ZIP 条目。
- 根 Product 继续采用现有规则，本现场包选择 `500.000 A.CATProduct`。

---

### Task 1: ASCII-safe ZIP extraction

**Files:**
- Modify: `backend/tests/test_catia_worker_server.py`
- Modify: `backend/app/catia_worker/server.py:205-225`

**Interfaces:**
- Consumes: `_resolve_job_source(job_root: Path) -> Path`
- Produces: `_zip_entry_relative_path(entry_name: str, common_root: str | None) -> Path`，供 `_resolve_job_source` 安全计算解包目标。

- [ ] **Step 1: Write the failing regression test**

新增测试，ZIP 内容为：

```python
with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
    archive.writestr("连接关系示例数据/510.000 A.CATProduct", b"child")
    archive.writestr("连接关系示例数据/500.000 A.CATProduct", b"root references 510.000 A.CATProduct")
    archive.writestr("连接关系示例数据/510.001 A.CATPart", b"part")

source = _resolve_job_source(job_root)

assert source == job_root / "source-bundle" / "500.000 A.CATProduct"
assert source.parent.as_posix().isascii()
assert (source.parent / "510.001 A.CATPart").read_bytes() == b"part"
```

同时保留并运行现有 ZIP 越界测试；若不存在，则新增 `../outside.CATPart` 用例并断言 `WorkerExecutionError.code == "catia_source_bundle_invalid"`。

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
conda run -n 3dcad pytest backend/tests/test_catia_worker_server.py -k "unicode_common_root or traversal" -q
```

Expected: 中文共同目录用例 FAIL，实际入口仍含 `连接关系示例数据`；越界用例 PASS。

- [ ] **Step 3: Implement minimal safe extraction**

在读取 `archive.infolist()` 后：

```python
entry_paths = [PurePosixPath(item.filename) for item in entries]
first_parts = {path.parts[0] for path in entry_paths if len(path.parts) > 1}
common_root = next(iter(first_parts)) if len(first_parts) == 1 and all(len(path.parts) > 1 for path in entry_paths) else None
```

逐项取 `path.parts[1:]` 或原始 `path.parts`，拒绝绝对路径、空路径、`.`、`..`，以 `archive.open(entry)` 复制到经 `relative_to(resolved_root)` 验证的目标文件。不得继续使用 `extractall`。

- [ ] **Step 4: Update existing layout expectations**

把已有单共同顶层目录用例的预期从：

```python
job_root / "source-bundle" / "assembly" / "top.CATProduct"
```

改为：

```python
job_root / "source-bundle" / "top.CATProduct"
```

根 Product 选择用例同样移除 `bundle` 路径段，但保持 `RootAssembly.CATProduct` 断言。

- [ ] **Step 5: Run focused and full Worker tests**

Run:

```powershell
conda run -n 3dcad pytest backend/tests/test_catia_worker_server.py -q
```

Expected: 全部 PASS。

- [ ] **Step 6: Restart Worker and replay the original uploaded ZIP**

重启端口 5182 的 Worker，使用原文件 `D:\CAAclean\.runtime\catia-worker\98e6a006-79d9-4303-8aac-4692c4eac491\source.zip` 创建新任务并轮询状态。断言新任务不再以 `CATIA document open failed` / `caa_parse_failed` 在打开阶段结束；若完整解析耗时较长，至少验证 CAA 已越过原 3 秒失败点且 ASCII 工作路径存在。

- [ ] **Step 7: Commit production change and regression test**

```powershell
git add -- backend/app/catia_worker/server.py backend/tests/test_catia_worker_server.py docs/superpowers/plans/2026-09-16-caa-zip-ascii-path.md
git commit -m "fix: use ASCII-safe paths for CATIA ZIP bundles"
```
