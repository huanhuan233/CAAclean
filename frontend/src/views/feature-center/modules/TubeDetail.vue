<script setup lang="ts">
// 导管右侧详情只消费稳定结果：原生路径、辅助几何导管和安装间隙分别展示，不在前端补算尺寸。
import { computed } from 'vue';
import type { TubeClearanceRecord, TubePathRecord } from '@/service/api/cad';
import { tubeGeometryTitle, tubeObjectStatus, tubeSectionRows, tubeSectionSamples } from './tube-section-view';

const props = defineProps<{ group: 'native' | 'step' | 'clearance'; record: TubePathRecord | TubeClearanceRecord;
  segment?: Record<string, unknown> | null; displayCurrent?: boolean }>();
// 间隙记录没有管径载荷；空对象表示无相应字段，不代表尺寸为零。
const path = computed<Record<string, unknown>>(() => props.group !== 'clearance'
  ? (props.record as TubePathRecord).path || {} : {});
const section = computed<Record<string, unknown>>(() => props.group !== 'clearance'
  ? (props.record as TubePathRecord).section || {} : {});
const isClearance = computed(() => props.group === 'clearance');
// 选中分段后仅展开该段的截面站位；整管仍使用后端核验过的统一截面参数。
const samples = computed(() => tubeSectionSamples(section.value,
  typeof props.segment?.order === 'number' ? props.segment.order : undefined));
const confirmed = computed(() => ['confirmed_straight_hollow_tube', 'confirmed_bent_hollow_tube'].includes(String(props.record.status)));
// 小数位仅用于展示，原始 record 保持完整精度；无效/缺失数值不填默认值。
function mm(value: unknown): string | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)} mm` : undefined;
}
function degrees(value: unknown): string | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)}°` : undefined;
}
// 列表与详情共用中文状态映射；查看一个弯段时，标题指向中心线段而非整个导管。
const title = computed(() => isClearance.value ? '导管安装间隙' : props.segment
  ? props.segment.kind === 'arc' ? '中心线弯段' : '中心线直段'
  : props.group === 'native' ? '原生扫掠路径' : tubeGeometryTitle(props.record.status));
const rows = computed(() => {
  if (isClearance.value) {
    // 面板简要展示首组最近点；全部解保留在原始记录与诊断中，不因距离小就判定安装合格。
    const row = props.record as TubeClearanceRecord;
    const witness = row.witnesses?.[0];
    return [['导管实例', row.tube_instance_id], ['目标实例', row.target_instance_id],
      ['外表面最短距离', mm(row.distance_mm) || '未测得'],
      ['相交状态', row.intersection_status], ['管体见证点', witness?.tube?.join(', ')],
      ['目标见证点', witness?.target?.join(', ')],
      ['中心线站位', witness ? mm(witness.s_mm) : undefined],
      ['阈值评价', '未提供最小间隙要求']];
  }
  const row = props.record as TubePathRecord;
  const geometry = props.segment || path.value;
  // 段的 radius_mm 是中心线弯曲半径，管截面外径/内径/壁厚从 section 单独读取。
  return [['来源', row.source === 'native_sweep_path' ? 'CATIA 扫掠中心线引用' : 'STEP 辅助几何恢复'],
    ['对象状态', tubeObjectStatus(row.object_status || row.status)],
    ['起点', (geometry.start_mm || path.value.terminal_a_mm) instanceof Array ?
      ((geometry.start_mm || path.value.terminal_a_mm) as number[]).join(', ') : undefined],
    ['终点', (geometry.end_mm || path.value.terminal_b_mm) instanceof Array ?
      ((geometry.end_mm || path.value.terminal_b_mm) as number[]).join(', ') : undefined],
    ['中心线长度', mm(geometry.length_mm ?? geometry.developed_length_mm)],
    ['累计弧长', typeof geometry.s0_mm === 'number' ? `${mm(geometry.s0_mm)}–${mm(geometry.s1_mm)}` : undefined],
    ['中心线弯曲半径', mm(geometry.radius_mm)],
    ['弯曲角', degrees(geometry.bend_deg)],
    ['弯曲平面转角', geometry.kind === 'arc' ? geometry.rotation_deg === null ? '未定义（首弯）'
      : degrees(geometry.rotation_deg) || '未测得' : undefined],
    ...tubeSectionRows(section.value),
    ['路径身份', row.path_id]];
});
</script>

<template>
  <!-- displayCurrent 由上层统一核对 Revision、快照和结果版本；此组件只呈现状态。 -->
  <section class="tube-detail">
    <header><h3>{{ title }}</h3><small>{{ displayCurrent ? '当前几何' : '历史或未核验显示版本' }} · {{ isClearance ? '静态安装几何' : '导管工程信息' }}</small></header>
    <p v-if="!displayCurrent" class="notice">结果数值可查看；当前模型的几何版本未核验一致，已停用三维定位、路径及见证点叠加。</p>
    <dl><template v-for="[label, value] in rows" :key="String(label)">
      <template v-if="value !== undefined && value !== null && value !== ''"><dt>{{ label }}</dt><dd>{{ value }}</dd></template>
    </template></dl>
    <p v-if="group === 'native'" class="notice">原生中心线可独立显示；管壁映射和空心实体状态尚未由该引用证明。</p>
    <p v-if="group === 'step' && !confirmed" class="notice">当前几何条件未满足，不能确认圆截面空心导管。</p>
    <p v-if="group === 'step' && confirmed" class="notice">尺寸来自当前 CAD 实体。弯管的几何壁厚不代表制造后实测的减薄、增厚或椭圆化。</p>
    <!-- 用后端的段序号及真实累计弧长标识核验位置，不能用显示序号发起对象查询。 -->
    <details v-if="samples.length" class="section-samples"><summary>截面核验位置（{{ samples.length }} 处）</summary>
      <div v-for="sample in samples" :key="`${sample.segment_order}:${sample.station_s_mm}`" class="sample">
        <strong>管段 {{ sample.segment_order }} · 站位 {{ mm(sample.station_s_mm) }}</strong>
        <span>外径 {{ mm(sample.outer_diameter_mm) }} · 内径 {{ mm(sample.inner_diameter_mm) }}</span>
        <span>壁厚 {{ mm(sample.wall_thickness_mm) }} · 残差 {{ mm(sample.residual_mm) }}</span>
      </div>
    </details>
    <p v-if="isClearance" class="notice">仅覆盖本次选定的对象范围；没有阈值时不判定安装合格性。</p>
    <details><summary>来源与诊断</summary><pre>{{ JSON.stringify({ record, segment }, null, 2) }}</pre></details>
  </section>
</template>

<style scoped>
/* 详情沿用右侧窄面板：长坐标换行，内容在面板内部纵向滚动，避免撑宽 Viewer 布局。 */
.tube-detail { min-width: 0; height: 100%; overflow-y: auto; padding: 16px; color: var(--el-text-color-primary); }
header { border-bottom: 1px solid var(--el-border-color-light); padding-bottom: 12px; }
h3 { margin: 0 0 4px; font-size: 17px; }
small, dt { color: var(--el-text-color-secondary); }
dl { display: grid; grid-template-columns: minmax(80px, 38%) minmax(0, 1fr); gap: 0; margin: 12px 0; font-size: 13px; }
dt, dd { margin: 0; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); overflow-wrap: anywhere; }
.notice { padding: 10px; border-radius: 6px; background: var(--el-fill-color-light); font-size: 12px; }
details { margin-top: 16px; font-size: 12px; }
.sample { display: flex; flex-direction: column; gap: 4px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-light); overflow-wrap: anywhere; }
pre { max-height: 320px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
