# 图元建库首版数据融合设计

## 目标

在图元建库文件树中启用“数据融合”节点。用户点击后，系统读取当前图元版本已关联的图元元数据、二维图纸抽取结果和 STEP 几何解析结果，生成一份可继续人工修改的 ComponentSpec v1.2 草稿。

首版以 `XMS06-DN80` 为验收样例，优先完成确定性规则，不接入大模型或外部标准库。

## 范围

- 新增同步数据融合接口和前端操作页。
- 默认只填 ComponentSpec 中的空值，不覆盖用户已有值。
- 提供显式的“重新融合并覆盖”操作。
- 身份、版本、文件信息支持所有图元类型。
- 专用尺寸映射首版只支持法兰。
- 返回本次融合报告，包括已填、保留、冲突和待复核字段。
- 融合后仍使用现有 ComponentSpec 表单编辑、保存和 YAML 预览。

以下内容不在首版范围内：

- AI 推断和文本生成。
- 外部标准库检索。
- 自动发布和发布校验。
- 将候选几何直接认定为最终工程尺寸。
- 新建独立的融合任务表或异步任务队列。

## 用户流程

1. 用户展开图元版本并点击“数据融合”。
2. 页面展示 STEP、二维图纸和 ComponentSpec 草稿状态。
3. 两个来源均已就绪时可点击“开始数据融合”；只有一个来源时也允许融合可确定的字段。
4. 默认模式只补空值。
5. 融合完成后页面展示统计和待复核项，并提供“查看 ComponentSpec”入口。
6. 用户可进入 ComponentSpec 表单修改、保存并预览 YAML。
7. “重新融合并覆盖”需要显式二次操作，并覆盖规则可生成的字段。

## 架构

### 融合器

新增纯规则模块 `ComponentSpecFusion`，输入为：

- `ComponentBuild` 图元元数据。
- 当前 ComponentSpec 草稿。
- 二维图纸 facts。
- STEP measurements 和 features。
- `overwrite` 模式。

输出为：

- 规范化后的 ComponentSpec v1.2 数据。
- 字段级融合报告。

融合器不直接访问数据库，便于对映射规则做单元测试。

### 数据读取与保存

`ComponentBuildService` 负责：

1. 校验图元版本存在。
2. 读取关联的 `CadDrawingFact`、`CadMeasurement` 和 `CadFeatureCandidate`。
3. 调用融合器。
4. 通过现有 `ComponentSpecDraft` 仓储保存草稿。
5. 返回草稿和融合报告。

不新增草稿存储结构。融合报告作为接口响应返回；可持久化的信息写入 ComponentSpec 的 `provenance`。

### API

`POST /api/component-builds/{build_id}/fusion`

请求：

```json
{
  "overwrite": false
}
```

响应：

```json
{
  "build_id": "...",
  "status": "completed",
  "summary": {
    "filled": 24,
    "preserved": 3,
    "conflicts": 1,
    "needs_review": 4
  },
  "fields": [
    {
      "path": "parameters.flange_outer_diameter.default",
      "value": 200.0,
      "source": "drawing",
      "confidence": 0.85,
      "decision": "filled"
    }
  ],
  "component_spec": {}
}
```

没有任何可用来源时返回 `409`，不创建空草稿。单侧来源可用时正常返回，并在报告中标明缺失来源。

## 合并规则

字段优先级从高到低：

1. 用户已有草稿值。
2. 图元建库元数据。
3. 与目标 DN 匹配的二维图纸事实。
4. STEP 的高置信度测量和特征。
5. 可验证的确定性派生值。

默认模式遇到已有值时记录为 `preserved`。覆盖模式只覆盖融合器负责的字段，不清空未知字段，也不改系统固定字段。

二维图纸存在多行规格时，目标 DN 按以下顺序确定：

1. ComponentSpec 已有 `DN`。
2. 图元名称中的 `DNxx`。
3. 图元默认 DN。

无法确定目标 DN 时，不选择任意尺寸行，只融合产品级字段。

二维图纸给出多个产品代码、材质或系列时，仅在图元名称可唯一匹配时选择单值；否则保留原字符串并标记待复核。

## XMS06-DN80 首版映射

### 身份与标准

| ComponentSpec 字段 | 来源 | 规则 |
| --- | --- | --- |
| `identity.id` | 图元元数据 | `component_id`，当前为 `flange-001` |
| `identity.name` | 图元元数据 | `component_name`，当前为 `XMS06-DN80` |
| `identity.name_en` | 分类和图纸 | `Weld Neck Flange`，待复核 |
| `identity.type` | 图元元数据 | `flange` |
| `identity.subtype` | 图纸 | `带颈对焊` 映射为 `weld_neck` |
| `identity.family` | 图元元数据 | `connection-fastening` |
| `identity.standard.number` | 图元元数据/图纸 | `HG/T 20592-2009` |
| `identity.standard.edition` | 标准号 | `2009` |
| `identity.version` | 图元元数据 | `1.0.0` |
| `identity.status` | 系统规则 | `draft` |
| `identity.default_preset` | DN、PN | `DN80-PN16` |

### DN80-PN16 参数

| 参数 | 图纸符号或来源 | 值 | 处理 |
| --- | --- | ---: | --- |
| `DN` | 目标行 | 80 | 确定 |
| `PN` | `product.pressure_class` | 16 | 从 `PN16` 解析 |
| `flange_outer_diameter` | `D` | 200 mm | 确定 |
| `bolt_circle_diameter` | `K` | 160 mm | 确定 |
| `bolt_hole_count` | `n` | 8 | 确定 |
| `bolt_hole_diameter` | `L` | 18 mm | 确定，并由 STEP 孔候选辅助确认 |
| `flange_thickness` | `C` | 20 mm | 确定 |
| `pipe_outer_diameter` | `A1` | 89 mm | 确定 |
| `wall_thickness` | `S` | 3.2 mm | 原操作符为 `>=`，标记待复核 |
| `hub_small_end_diameter` | `N` | 105 mm | 待复核 |
| `hub_height` | `H1` | 10 mm | 原操作符为约等于，标记待复核 |
| `overall_height` | `H` | 50 mm | 确定 |
| `raised_face_diameter` | `d` | 138 mm | 确定，并与 STEP 直径候选核对 |
| `raised_face_height` | `f1` | 2 mm | 确定 |
| `root_fillet_radius` | `R` | 6 mm | 确定 |
| `bore_diameter` | `A1 - 2 * S` | 82.6 mm | 仅在 STEP 存在 82.6 mm 直径候选时填写 |
| `facing_type` | 产品信息 | `RF` | 从“突面 (RF)”解析 |

同一组值同步写入 `presets[0]`，预设名为 `DN80-PN16`，来源引用标准号和二维图纸任务。

### STEP 与交付信息

- `validation.topology.expected_body_count` 使用 STEP 解析实体数。
- `validation.topology.solid_required` 填 `true`。
- `validation.geometry.expected_through_hole_count_expression` 使用 `bolt_hole_count`。
- `artifacts.reference_step.role` 填 `reference_geometry`。
- `artifacts.reference_step.format` 填 `STEP`。
- `artifacts.reference_step.length_unit` 填 `mm`。
- 无可靠值的 SHA256、作者、许可证、端口定义和生成脚本继续留空。

STEP 中的包围盒和二维图纸外径存在冲突时，不自动写入包围盒校验表达式，报告中记录冲突并要求人工检查。

## 前端

- `数据融合`节点在图元版本存在时可点击，不再作为“后续能力”禁用。
- 页面显示来源状态、当前草稿状态、默认合并策略和操作按钮。
- 融合完成后展示四项统计：已填、保留、冲突、待复核。
- 字段报告按“冲突/待复核”优先展示。
- 提供“查看 ComponentSpec”按钮切换到现有表单。
- 覆盖模式使用明确文案，不作为默认主按钮。

## 错误处理

- 无 STEP 且无二维图纸：`409 no_sources_available`。
- 图元没有关联到目标来源：跳过对应来源，不误用其他图元的数据。
- 目标 DN 无法确定：只融合产品级字段，并返回警告。
- 来源读取失败：不保存半成品草稿，返回明确错误。
- 保存失败：事务回滚，现有草稿保持不变。

## 测试与验收

### 单元测试

- 正确选择 DN80 行，不混用其他 DN。
- 默认模式只填空值。
- 覆盖模式覆盖规则字段但不清空未知字段。
- 多产品值按图元名称唯一匹配。
- `bore_diameter` 只有二维派生值与 STEP 候选一致时才填。
- 不确定或冲突字段进入 `needs_review`。

### API 测试

- 双来源、单来源和无来源。
- 草稿保存后 ComponentSpec GET 可读取融合结果。
- 文件树数据融合节点状态随来源和草稿变化。
- XMS06-DN80 返回预期字段。

### 前端验收

在 `/图元库/连接与紧固类/法兰/XMS06-DN80/1.0.0/数据融合`：

1. 点击“开始数据融合”成功。
2. 页面显示融合统计和待复核项。
3. 进入 ComponentSpec 后可看到上述字段已填。
4. 用户修改字段并再次默认融合，人工值保持不变。
5. YAML 预览仍符合 ComponentSpec v1.2 模板结构。
