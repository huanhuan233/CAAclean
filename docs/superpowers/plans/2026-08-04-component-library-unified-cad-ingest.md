# 图元库存储管理统一 CAD 接入实施计划

## 目标

在不复制现有页面、STEP 解析器、Feature Center 或 Viewer 的前提下，为机械工程图元库与航空航天零件库提供同一个 STEP/STP/CATPart 上传入口，并把两条处理路线收敛到同一 Viewer 资产契约。

## 已确认基线

- 起始提交：`8095d344c0a9bd02c5983d708f731c75648b59d0`。
- 用户改动：`backend/app/core/config.py`；用户文件：`3DjiexiCAA/总阶段提示词.md`，本轮不暂存。
- 后端相关基线：68 项测试通过。
- 前端类型检查在 120 秒内未结束，未产生诊断，作为超时基线记录。
- 现有 STEP 路线：`CadService -> FreeCAD parser -> CadModelRevision/CadMesh`。
- 现有 CATPart 路线：CAA Batch -> `ExportData` STEP -> Feature Center CLI。
- 现有 Viewer：Feature Center 页面已经支持 GLB、Face/Feature 映射和高亮，但当前只支持本地目录载入。

## M1：审计与边界

1. 保留现有机械分类、部件 UUID 和 `ComponentBuild` 数据。
2. 将目录数据源扩展为“库根 -> 分类 -> 部件类型”，前端只消费接口。
3. 新建最小的持久化导入任务表，避免把 CATPart 阶段状态硬塞入 STEP Revision。
4. 新建编排服务，只调用已有 CAD、CAA、STEP 导出和 Feature Center 能力。
5. 通过受控资产接口发布 Bundle，不向浏览器泄露磁盘路径。

## M2：航空航天目录

1. 先增加目录稳定 ID、根计数和幂等性的失败测试。
2. 增加机械与航空航天两个稳定根节点，机械既有分类 ID 保持不变。
3. 增加八个航空航天分类及可选叶子类型。
4. 将前端目录组件改为递归消费后端树，文案按库类型显示“新增零件”。

## M3：统一上传与任务分流

1. 先测试大小写格式、`.cart` 拒绝、中文/空格/括号文件名、客户端路线伪造无效。
2. 扩展既有 `POST /api/component-builds` 使用 `source_file`，兼容旧 `step_file`。
3. 保存源文件、SHA-256 和持久化任务；返回 `part_id/task_id/source_format/processing_route/status`。
4. STEP 与 STP 进入同一分支；CATPart 进入单并发 CATIA 分支。

## M4：STEP Web 闭环

1. 复用 `CadService` 保存与解析 STEP。
2. 解析完成后复用 Feature Center Sidecar 生成统一 GLB 和映射资产。
3. 仅在 GLB 与必需资产存在并通过校验后标记 ready。
4. 使用 `KUANG (2).stp` 走真实 API 和后台任务。

## M5：CATPart Web 闭环

1. 在隔离任务目录运行已有 CAA Batch。
2. 调用已有 `export_catpart_step.ps1` 导出 STEP。
3. 使用 CAA Bundle 与导出 STEP 调用 Feature Center CLI。
4. 分阶段持久化错误；CATIA 不可用时保留源文件并失败，不伪造资产。
5. 使用 `kuang.CATPart` 走真实 API 和后台任务。

## M6：统一 Viewer 与恢复

1. 新增 Viewer 契约和受控文件下载接口。
2. 扩展现有 Feature Center 页面支持按 `build_id` 从 URL 加载 Bundle。
3. STEP 无 Canonical Feature 时正常显示模型；CATPart 继续使用既有高亮和反查。
4. 统一失败原因、重试入口和状态展示。

## M7：验证与提交

1. 后端单元/接口测试、前端测试、类型检查与生产构建。
2. 两个真实样件 API E2E、资产 URL、Bundle 校验和同件几何对照。
3. 尝试自动浏览器验证上传与 Viewer；否则只保留唯一人工点击项。
4. 检查 CATIA 进程残留与输出散落。
5. 仅暂存本轮文件，创建本地提交，不推送。

## 错误和恢复边界

- 当前后台执行继续沿用进程内异步任务，但任务事实持久化；服务重启后可重新调度 queued/failed 任务。
- CATIA 任务使用单进程内锁；不承诺多主机分布式互斥。
- 每个阶段写入独立错误码，普通响应不返回服务端堆栈。
- 原始上传始终保留；解析失败绝不把零件记录删除或标记 ready。
