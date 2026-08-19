# CATIA 轻量化显示系统交付说明

## 1. 环境要求

- Windows 10/11
- Node.js `>=20.19`、pnpm `>=8.7`
- Miniconda/Anaconda
- PostgreSQL 14+（默认 `127.0.0.1:5432`）
- FreeCAD（需要 `freecadcmd.exe`）
- CAA V5R21：RADE、CATIA B21 `win_b64`、VS2008 x64 编译器

可用 Docker 启动本地 PostgreSQL：

```powershell
docker run --name caaclean-postgres -e POSTGRES_USER=huanhuan233 -e POSTGRES_PASSWORD=huanhuan123 -e POSTGRES_DB=postgres -p 5432:5432 -d postgres:16
```

## 2. 后端 Conda 环境

```powershell
conda create -n 3dcad python=3.11 -y
conda activate 3dcad
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

复制并修改配置：

```powershell
Copy-Item backend\.env.example backend\.env
```

至少设置：

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=你的用户名
POSTGRES_PASSWORD=你的密码
POSTGRES_DB=postgres
FREECAD_CMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
FREECAD_TIMEOUT=1800
CAD_WORK_DIR=../cad-work
CATIA_WORKER_MODE=http
CATIA_WORKER_URL=http://127.0.0.1:5182
```

## 3. FreeCAD 设置

1. 安装 FreeCAD，并确认存在 `freecadcmd.exe`。
2. 将 `FREECAD_CMD` 指向该文件的绝对路径。
3. 保证 `backend\cad-work` 可写。
4. FreeCAD 解析脚本位于 `backend\freecad_scripts`，后端会按配置调用。

## 4. CAA 64 位编译

RADE 的构建宿主可以是 `intel_a`，目标必须是 `win_b64`。在 **CMD** 中执行：

```cmd
set "REPO_ROOT=D:\path\to\freecadCAA"
cd /d "%REPO_ROOT%\3DjiexiCAA"
set "CAA_RADE_ROOT=%REPO_ROOT%\.caa_toolchain_links\rade21"
set "CAA_PREREQ_ROOT=%REPO_ROOT%\.caa_toolchain_links\catia21"
set "RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE"
call tools\probe_r21_x64_existing_env.bat
call tools\build_r21_x64_host_intel_a.bat
```

成功输出：

```text
3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe
```

如果没有仓库中的链接目录，分别将 `CAA_RADE_ROOT` 指向含 `intel_a\code\command` 的 RADE 根目录，将 `CAA_PREREQ_ROOT` 指向含 `win_b64\code\bin\CNEXT.exe` 的 CATIA 根目录。

## 5. 启动 CATIA Worker

打开新的 PowerShell：

```powershell
$RepoRoot = 'D:\path\to\freecadCAA'
conda activate 3dcad
cd "$RepoRoot\backend"
$env:CAA_RADE_ROOT="$RepoRoot\.caa_toolchain_links\rade21"
$env:CAA_PREREQ_ROOT="$RepoRoot\.caa_toolchain_links\catia21"
python -m uvicorn app.catia_worker.server:app --host 127.0.0.1 --port 5182
```

检查：`http://127.0.0.1:5182/health`

也可编译并双击托盘程序：

```cmd
cd /d D:\path\to\freecadCAA\3DjiexiCAA
call tools\build_catia_worker_tray.bat
```

生成的 `tools\CatiaWorkerTray.exe` 会自动启动 Worker。

## 6. 启动后端

```powershell
conda activate 3dcad
cd D:\path\to\freecadCAA\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 5180
```

后端地址：`http://127.0.0.1:5180`

## 7. 构建与启动前端

```powershell
cd D:\path\to\freecadCAA\frontend
npm install -g pnpm
pnpm install
pnpm approve-builds
pnpm build
```

开发启动：

```powershell
pnpm dev --host 127.0.0.1 --port 9999
```

前端地址：`http://127.0.0.1:9999`

启动顺序：CATIA Worker（5182）→ 后端（5180）→ 前端（9999）。
