# CAA 端完成门槛

以下门槛全部属于 Python 制造特征识别之前的 CAA 侧。

## G0 构建与运行卫生

- R21 `mkmk` / VS2008 Win32 编译、链接通过。
- `--self-test` 通过。
- 每个合法样件运行返回 0；损坏/不支持输入返回稳定非零码且无崩溃。
- 每次运行后无本工具遗留的 `CNEXT.exe`、`CATSTART.exe` 和打开文档。
- 双跑核心 IR 字节/Hash 一致；Manifest Hash 与实际文件一致。

## G1 注册中心

- 每个专用 Decoder 有稳定 `decoder_id`、版本、优先级、支持的 StartUp/SuperType/接口键、Payload type/schema/version、R21 支持状态。
- 注册表冲突、重复注册、同优先级确定性、异常隔离、Generic、Opaque 均可审计。
- 实际特征记录引用注册表条目及 Payload schema；未知类型不丢失原始指纹。
- `verified / needs_review / unsupported / failed / stale` 状态有真实样例。

## G2 原生 Feature Decoder

- Hole（复用）、Pad、Pocket、Fillet、Chamfer、Shaft、Groove、Rib、Slot、Stiffener、Shell/Thickness、Draft、Pattern、Mirror/Symmetry、Transformation、MultiBody/Boolean、Split/Trim、GSD 基础类型逐类验证。
- 不能因几何相似而误报：Pocket≠Hole、导入圆柱孔≠Native Hole、几何圆角≠Native Fillet。
- 参数包含值、单位、适用性和来源；未验证 API 保持 unsupported/partial。

## G3 完整几何拓扑

- Solid/Shell/Body/Face/Loop/Wire/Edge/Vertex 层级和引用守恒。
- Face：surface type/参数、方向、材料侧、外环/内环、UV/参数域、周期/闭合、面积、质心、包围盒、法向/受控曲率采样。
- Edge：curve type/参数、端点、参数域、周期/闭合、长度、相邻 Face。
- 邻接：共享 Edge、二面角、convex/concave/tangent/unknown、G0/G1/G2（可可靠取得时）。
- 多 Body 和非实体/仅曲面模型不被静默压缩成单一主实体。

## G4 Feature↔Topology 权威关系

- Feature Result cell 与最终 Face/Edge/Vertex 使用 CATIA 原生持久命名、选择对象、历史/Result 追踪或经 R21 Public API 证明的等价权威链路。
- 支持正向和反向查询，并表达 generated/modified/consumed/split/merged。
- `candidate` / `ambiguous` 只作辅证，不能计入 complete。
- 最终实体中每个可归属 Face 有来源；未归属项有原因；前序 Face 消失也保留历史证据。

## G5 FTA/MBD

- 尺寸、极限偏差、形位公差、基准、粗糙度、文本、旗标、NOA、Annotation View/Capture 逐类结构化。
- 保留 TTRS、语义有效性、值/单位/上下偏差、框格/修饰符、基准体系、文本和展示视图。
- FTA/TPS 到 Face/Edge/Vertex/轴线/基准平面的权威引用可正反查。
- 孤立/失效引用不能崩溃，必须输出状态和诊断。

## G6 Mesh Face 映射前置契约

- 每个三角 primitive/range 只映射一个统一最终 `face_id`。
- range 非负、按 primitive 连续、无重叠，triangle count/estimated count 自洽。
- Face orientation 与最终拓扑方向一致；不同 tessellation 参数时映射仍可审计。
- CAA 不生成 GLB 可以接受，但 CAA sidecar 必须足以让 GLB Writer 无猜测地写入映射。

## G7 CATProduct

- Reference 与 Instance 分离；同一 CATPart 多实例共享 reference_id、拥有不同 instance_id/path。
- 输出层级路径、PartNumber/Revision、抑制/加载/缺失状态和 4×4 变换。
- 支持嵌套装配、相同 PartNumber 不同 Revision、失效引用与同 Reference 多姿态。
- Part 内 Face/Feature ID 与装配 instance_id 联合后全局唯一。

## G8 属性、连接与版本对

- 质量、体积、面积、重心、惯性、密度、包围盒、单位和来源可审计。
- 自定义属性、Knowledge 参数与 Alias 不因显示文本而丢失真实类型值。
- 两条紧固件路径、`K_密封定义`、`M_胶接定义` 及嵌套/缺失字段反例均能保真导出。
- V1/V2 可分辨 BOM、实例变换、属性、Feature 参数、几何、FTA 语义与关联、连接定义变化；不要求 CAA 完成最终比对算法，但必须提供足够稳定证据。

## G9 真实回归矩阵

- `fixture_catalog.json` 中 `completion_required=true` 的每项均有真实 CATIA 文件与 verifier 证据。
- 每类至少覆盖最小正例、同族变体、后续拓扑消耗、几何相似反例；高风险类再加组合压力件。
- fixture 生成/验证失败必须保留为 FAIL/BLOCKED，不能删除行后宣称完成。

