# Feature Center 第一阶段实施计划

> **面向自动化执行者：** 必须逐任务执行、先测试后实现，并在每项完成后记录验证结果。

**目标：** 建立从现有原生孔解析结果到 STEP/B-Rep、eAAG 和原生孔面映射的确定性 Feature Center 底座。

**架构：** CAA R21 进程仍只负责 CATPart 原生语义；现代 Sidecar 复用仓库内的 FreeCAD 1.1 解析脚本提取 STEP 拓扑和面级网格。Feature Center Bundle 独立于既有 CAA JSONL，避免改变 275/941 对象守恒语义。

**技术栈：** CAA R21、VS2008/C++03、Python 3dcad Conda 环境、FreeCAD 1.1.3、OpenCascade、FastAPI 现有解析边界。

## 全局约束

- CAA 模块保持 C++03、x86、只使用可验证公开接口。
- Sidecar 不进入 CATIA 进程；FreeCAD 只通过 `freecadcmd.exe` 子进程调用。
- 所有新增注释使用中文；公共 JSON 字段名保持英文。
- 视觉复核默认关闭，本阶段不调用真实视觉服务。
- 不修改既有 `cad_parse_mvp_v2` 输出语义，不把 Feature Center 对象计入原始 CAA 覆盖率。
- 不提交密钥、绝对路径样例、临时输出或用户已有未提交修改。

---

### 任务 1：固化 CAA 回归边界与通用解码器协议

**文件：**

- 修改：`CadParseMvp.edu/CadParseMvp.m/src/CadParseContracts.h`
- 修改：`CadParseMvp.edu/CadParseMvp.m/src/CadParseCore.cpp`
- 修改：`CadParseMvp.edu/CadParseMvp.m/src/CadParseSelfTests.cpp`

**产物：** Capability 查询、可克隆类型化载荷、统一解码状态统计；原生孔作为第一个 Capability/Payload 实现。

- [ ] 先增加 Synthetic Capability/Payload 的失败测试，断言中央对象视图、爬取器和写出器无需新增特征分支。
- [ ] 运行 VS2008 核心测试，确认新测试因接口缺失而失败。
- [ ] 实现 C++03 所有权、复制和异常隔离协议；使原生孔 JSON 载荷保持兼容。
- [ ] 重跑核心测试和 R21 构建。

### 任务 2：Feature Center Bundle 与 Sidecar 入口

**文件：**

- 创建：`backend/app/feature_center/contracts.py`
- 创建：`backend/app/feature_center/bundle.py`
- 创建：`backend/scripts/build_feature_center.py`
- 测试：`backend/tests/test_feature_center_bundle.py`

**产物：** 独立的 `cad_feature_center_v1` Bundle、跨文件引用校验、稳定 JSONL 写出和清单哈希。

- [ ] 先为清单、Observation、Canonical Feature、关系和 Measurement 写失败测试。
- [ ] 实现纯 Python 数据模型、稳定编号和事务式 Bundle 写出。
- [ ] 使用临时目录运行测试，确认输入路径不会写入交付文件。

### 任务 3：STEP/B-Rep 与 eAAG 确定性底座

**文件：**

- 修改：`backend/freecad_scripts/parse_step.py`
- 创建：`backend/app/feature_center/topology.py`
- 创建：`backend/app/feature_center/eaag.py`
- 测试：`backend/tests/test_feature_center_topology.py`

**产物：** 读取现有 FreeCAD 拓扑结果，输出面、边、线环、实体和 eAAG 关系；ID 只在相同 Shape Hash 与算法版本范围内稳定。

- [ ] 先为面邻接、共享边、曲面类型和稳定排序写失败测试。
- [ ] 扩展 FreeCAD 输出以保留必要的面几何、边界和网格映射依据。
- [ ] 实现 eAAG 图和空间候选统计，不以 Face 序号作为跨模型身份。
- [ ] 在真实 STEP 样件连续运行两次，比较核心 JSONL 哈希。

### 任务 4：原生孔到 B-Rep 面映射

**文件：**

- 创建：`backend/app/feature_center/hole_mapping.py`
- 创建：`backend/tests/test_feature_center_hole_mapping.py`
- 创建：`backend/tests/fixtures/feature_center/`

**产物：** 使用孔轴、直径、终止方式、圆柱轴与半径、位置残差和凹凸关系进行候选评分，输出孔壁、底面和沉孔角色；无法确定时保留诊断。

- [ ] 先为盲孔、贯穿孔、沉孔、重命名孔和反例写失败测试。
- [ ] 实现候选生成、分项残差、面角色验证和冲突保留。
- [ ] 读取现有 CAA `features.jsonl` 与 STEP 输出，生成 Feature Center Observation 和 Canonical Feature。

### 任务 5：第一期集成、文档与回归

**文件：**

- 创建：`docs/FEATURE_CENTER_ARCHITECTURE.md`
- 创建：`docs/STEP_BREP_PIPELINE.md`
- 创建：`docs/EAAG_MODEL.md`
- 创建：`docs/HOLE_FEATURE_FACE_MAPPING.md`
- 创建：`docs/FEATURE_CENTER_TEST_MATRIX.md`

**产物：** 可重复运行的 Sidecar 命令、第一期 Bundle、性能和确定性报告，以及 CAA 回归证据。

- [ ] 先运行 CAA 自测、R21 构建和现有 Hole Smoke Test。
- [ ] 执行真实 STEP Sidecar 测试并验证 Bundle。
- [ ] 双跑比较核心 JSONL 的 SHA-256。
- [ ] 只暂存本阶段直接相关文件并创建本地提交，不推送远端。
