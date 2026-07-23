# STEP/CAD 三维解析后端

这是独立的 STEP/CAD 解析后端，代码位于 `backend/`，不依赖 `raganything_reconstructure_v2`。

## 本地开发环境

本地 Windows 的 `3dcad` conda 环境只需要安装 Python 服务依赖，用于运行 API 和 mock 单元测试：

```powershell
conda activate 3dcad
python -m pip install -r backend/requirements.txt
```

本地没有 FreeCAD 时，不需要配置真实 `FREECAD_CMD`，也不运行真实解析 smoke test。

## 服务器环境

服务器的 `3dcad` 环境需要安装同一份 Python 服务依赖：

```bash
conda activate 3dcad
python -m pip install -r backend/requirements.txt
```

服务器还需要能执行 FreeCAD headless，并在服务器的 `backend/.env` 或服务进程环境中配置：

```bash
FREECAD_CMD=/opt/conda-envs/cad-freecad/bin/freecadcmd
FREECAD_TIMEOUT=600
QT_QPA_PLATFORM=offscreen
LIBGL_ALWAYS_SOFTWARE=1
CAD_SCRIPT_DIR=/opt/cad-service/scripts
CAD_WORK_DIR=/home/pxy/cad-work
```

PostgreSQL 可用 `DATABASE_URL`，也可用拆分配置：

```bash
POSTGRES_HOST=192.168.0.91
POSTGRES_PORT=5432
POSTGRES_USER=rag_admin
POSTGRES_PASSWORD=<从环境变量或服务器 .env 提供>
POSTGRES_DB=rag_db
```

数据库 URL 由 SQLAlchemy `URL.create` 构造，密码不会在源码中硬编码。

## FreeCAD 脚本安装

将仓库脚本复制到服务器配置的 `CAD_SCRIPT_DIR`：

```bash
mkdir -p "$CAD_SCRIPT_DIR"
cp backend/freecad_scripts/parse_step.py "$CAD_SCRIPT_DIR/parse_step.py"
chmod 644 "$CAD_SCRIPT_DIR/parse_step.py"
```

## 数据库初始化

FastAPI 启动时会执行 `Base.metadata.create_all`，幂等创建所需表，不删除既有表。

也可以手动执行：

```bash
python backend/scripts/init_database.py
```

## 启动后端

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 5180 --reload
```

## 测试

本地单元测试：

```powershell
conda run -n 3dcad python -m pytest backend/tests -v
```

服务器真实解析测试使用指定样本文件：

```bash
conda activate 3dcad
python backend/scripts/test_real_freecad.py "D:\3D解析\XMS06-DN80.stp"
```

如果服务器不是 Windows 路径，请把同一个 `XMS06-DN80.stp` 上传到服务器后传入服务器上的实际路径。

## 已实现 API

- `GET /api/health`
- `GET /api/health/database`
- `POST /api/cad/models`
- `GET /api/cad/revisions/{revision_id}/status`
- `POST /api/cad/revisions/{revision_id}/exports/v2`

`/exports/v2` 当前仅预留接口，返回 501，不实现业务联动。
