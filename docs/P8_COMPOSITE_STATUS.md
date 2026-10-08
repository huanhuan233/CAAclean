# P8 复材铺层实施记录

## P8A 原生结构与语义

R21 x86 编译已验证 `CATICciStacking.GetElementsUnderStacking`、`CATICciPliesGroup.GetSequences`、`CATICciSequence.GetPliesAndCores` 和 `CATICciPly.GetCutPiecesGroup` 读取路径。新采集包把接口返回的成员顺序作为原生属性事实保存，无法解析的成员保留 `null` 和 `partial` 状态。旧采集包没有这些事实，层序为 `unavailable`，树遍历位置只用于导航。

`composite_structure` 由对象定义、树出现位置、属性事实生成，按定义 ID 去重并保留多个出现路径。同名且几何相同的不同铺层不会合并；裁片是单层的子对象。每个字段保留原始值、单位、接口和读取状态；已知长度、面积和角度分别规范为 mm、mm²、deg。固化与未固化厚度分开，未知单位不转换，失败值不从组级默认值补齐。材料对象引用单独解析；仅有同名材料时不声称材料身份相同。R21 `get_MassCost` 的币种和质量单位无法从接口签名核实，新采集将其单位标为未知。

现有 `CadNativeEvidence` 事务发布该投影；列表走现有分页接口，详情由数据库按真实 `object_id` 查询。Feature Center 的“工程信息 → 复材铺层”显示定义列表和右侧原生参数。未取得单层可信渲染映射时，明确显示几何未验证，不高亮整件。

历史真实复材包 `caa_new/test-output/semantic-20260922-reviewed` 可投影出 1 个叠层、1 个组、4 个序列和 4 个不同单层，四个序列的原生层序仍是 `unavailable`。该包可以补算结构投影，不能补出新 R21 接口没有采集的成员顺序。要取得原生层序和裁片关系需用新编译的采集器重新采集源 CATPart；本轮尚未找到该源文件，真实新接口样件读取为 `not_run`。

P8B 有序轮廓、独立单层几何和 P8C 覆盖/厚度分区不得从历史的 `composite_contour_vertices_mm` 推出：该字段只是无序顶点枚举。它们需要新证据和各自的验收记录。
