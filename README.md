# CATIA 轻量化显示系统：本机启动

本仓库包含 Vue 前端、FastAPI 后端、PostgreSQL，以及调用 CATIA V5R21 CAA 的独立 Worker。当前交付的本机 CAA 是 **32 位 `intel_a`**；后端/Worker 的 Python 进程可用 64 位，调用器通过子进程运行 32 位 CAA，并不要求把整套服务编译成 32 位。启动顺序是 PostgreSQL → CAA Worker → 后端 → 前端。

原生采集、数据库详情、Feature Center 与前端联动的实际能力和验收边界见 [三维语义端到端状态](docs/END_TO_END_STATUS.md)。旧结果恢复默认只读，不能再无参数运行回填；命令见该文档。

## 一、首次准备（Windows）

1. 安装并可运行 CATIA V5R21、RADE R21 及其许可证。当前机器的路径是 `D:\CATIA\Rade21`、`D:\CATIA`；其他机器改为自己的路径。
2. 安装 Python 3.11 或 3.12、Node.js **20.19+**、pnpm 8.7+、PostgreSQL（可用 Docker）。安装 CAA 编译工具仅在需要重新编译时必需。
3. 在仓库根目录打开 PowerShell，准备后端。后端只读 `backend\.env`，不要提交真实密码：

   ```powershell
   py -3.12 -m venv backend\.venv
   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   Copy-Item backend\.env.example backend\.env
   ```

   编辑 `backend\.env`，至少正确填写 `POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`（也可用 `DATABASE_URL`），以及 `CAA_RADE_ROOT`、`CAA_PREREQ_ROOT`。如果要复用当前机器已有数据，PostgreSQL 是 Docker 容器 `caaclean-postgres-live`，映射到本机 `127.0.0.1:55400`；**不要新建空库替代旧库**。`CATIA_WORKER_MODE=http`、`CATIA_WORKER_URL=http://127.0.0.1:5182` 由启动脚本在进程中固定，`CAA_CAPTURE_PROJECT_ROOT` 自动指向当前检出的 `caa_new`。

4. 准备前端依赖：

   ```powershell
   cd frontend
   pnpm install --frozen-lockfile
   cd ..
   ```

5. 确认已有 `caa_new\intel_a\code\bin\CadCapture.exe`。如果是新克隆且没有编译产物，先在已配置 RADE/VS2008 x86 的 CMD 里执行：

   ```cmd
   set "CAA_RADE_ROOT=D:\CATIA\Rade21"
   set "CAA_PREREQ_ROOT=D:\CATIA"
   call caa_new\tools\build_r21_x86.bat
   ```

   编译后的 32 位程序可以通过 `call caa_new\tools\run_r21_x86.bat --self-test` 检查。64 位环境如需编译，请使用仓库单独的 x64 构建脚本和对应工具链；本启动脚本明确使用当前 32 位产物，不把 x64 产物冒充 x86。

## 二、启动

先确保 PostgreSQL 正在运行。当前机器如容器停止，可执行 `docker start caaclean-postgres-live`；其他部署按 `backend\.env` 的连接信息启动自己的库。启动脚本**不会改动或清空数据库**。

双击仓库根目录的 [`启动系统.cmd`](./启动系统.cmd)。它先检查 Python/Node/CAA 程序与端口，然后依次启动三个隐藏的服务进程，检查 Worker、数据库和前端健康状态，成功后打开浏览器：

```text
http://127.0.0.1:9999/
```

也可以在 CMD 中运行：

```cmd
启动系统.cmd -Check
启动系统.cmd -NoOpen
```

前端监听 `0.0.0.0:9999`，后端 `127.0.0.1:5181`，CAA Worker `127.0.0.1:5182`。从其他电脑访问前端时使用 `http://这台电脑的局域网IP:9999/`，并由机器管理员在 Windows 防火墙允许入站 TCP 9999。后端和 Worker 不对外暴露；前端 `/proxy-default` 会把 API 请求转发到本机后端。

## 三、验证与排错

```powershell
Invoke-WebRequest http://127.0.0.1:5182/health
Invoke-WebRequest http://127.0.0.1:5181/api/health/database
Invoke-WebRequest http://127.0.0.1:9999/
```

Worker 健康响应中的 `accepting_jobs` 应为 `true`。启动日志位于 `.runtime\startup-logs\`，分别为 `worker`、`backend`、`frontend` 的 `.out.log` 和 `.err.log`。例如：

```powershell
Get-Content .runtime\startup-logs\backend.err.log -Tail 50 -Wait
```

- 提示 `backend/.env` 不存在：按首次准备填写真实数据库与 CATIA 路径。不要把 `.env` 提交到 Git。
- 提示 Node 版本太旧：切到 20.19+；当前机器也可设置 `CAD_NODE_EXE=C:\nvm4w\nodejs\node.exe` 再启动。
- 数据库健康检查失败：先检查 PostgreSQL 容器是否运行、端口/账号是否与 `backend/.env` 一致。前端的“暂无数据”通常也要先查这一步。
- Worker 返回 `degraded`：检查 `CAA_RADE_ROOT`、`CAA_PREREQ_ROOT`、许可证、32 位 `CadCapture.exe`，以及 `worker.err.log`。
- 端口被占用：脚本会报告占用进程 PID，不会杀掉已有进程。先确定那是不是你之前启动的实例，再自行关闭。

要停止本次服务，请在任务管理器中按启动时显示的 PID 结束三个进程；**不要直接按进程名批量结束 `python.exe` 或 `node.exe`**，以免影响其他项目。脚本若在启动途中失败，只清理它本次启动的进程。

### 查看原生树的补充采集记录

Feature Center 的“特征 → 原生特征”默认只显示与 CATIA 主规格树对应的节点。`Sag`、`Step`、`Edge`、`Angle` 等通过容器扫描取得的铺层参数属于补充采集记录，仍保存在原解析包和 PostgreSQL 中，但不会被提升到主树最外层。页面底部的“显示系统节点”只控制技术容器的显示，**不会**显示这批补充记录；“MBD 标注”页签展示的是另一类 FT&A/TPS 标注。

需要检查补充记录时，从 Feature Center 页面地址复制 `build_id`，访问后端原生树接口，并传入 `include_supplemental=true`。例如在 PowerShell 中查看根层，再用返回的 `node_id` 查询某一层：

```powershell
$buildId = '<页面地址中的 build_id>'
$api = "http://127.0.0.1:5181/api/component-builds/$buildId/viewer/native/tree"
$root = Invoke-RestMethod "${api}?include_supplemental=true&page_size=200"
$root.roots | Select-Object node_id, display_name, presentation_status

$parentId = '<要展开的父节点 node_id>'
$page = Invoke-RestMethod "${api}?include_supplemental=true&parent_id=$([uri]::EscapeDataString($parentId))&page_size=200"
$page.roots | Select-Object node_id, display_name, presentation_status, parameter_value
```

`presentation_status=non_primary` 表示补充发现节点。接口按父节点分页；若 `has_more=true`，用返回的 `next_offset` 继续请求同一 `parent_id`。这些数据只是采集证据，不应当作 CATIA 主树节点或 MBD 标注。切换默认显示不需要重新解析、回填或清理数据库。

## 四、手动启动（调试时）

先在三个终端设置相同的 `backend\.env`，并确保 `CAA_CAPTURE_PROJECT_ROOT` 指向当前仓库的 `caa_new`；终端一、二的工作目录设为 `backend`，终端三设为 `frontend`：

```powershell
# 终端一：在 backend 目录
..\backend\.venv\Scripts\python.exe -m uvicorn app.catia_worker.server:app --host 127.0.0.1 --port 5182

# 终端二：在 backend 目录
..\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5181

# 终端三：在 frontend 目录
pnpm exec vite --mode test --host 0.0.0.0 --port 9999 --strictPort --no-open
```

老的 `交付readme.md` 和 `caa_new/README.md` 含有旧部署示例（如 x64 编译、其他端口）；本机整套服务以本文件和当前配置为准。
