<script setup lang="ts">
import { computed } from 'vue';
import type { TubeClearanceRecord, TubePathRecord } from '@/service/api/cad';

const props = defineProps<{ group: 'native' | 'step' | 'clearance'; record: TubePathRecord | TubeClearanceRecord;
  segment?: Record<string, unknown> | null; displayCurrent?: boolean }>();
const path = computed<Record<string, unknown>>(() => props.group !== 'clearance'
  ? (props.record as TubePathRecord).path || {} : {});
const section = computed<Record<string, unknown>>(() => props.group !== 'clearance'
  ? (props.record as TubePathRecord).section || {} : {});
const isClearance = computed(() => props.group === 'clearance');
function mm(value: unknown): string | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)} mm` : undefined;
}
function degrees(value: unknown): string | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)}°` : undefined;
}
function objectStatus(value: unknown): string {
  const labels: Record<string, string> = {
    path_candidate_hollow_unverified: '中心线路径候选，空心状态未核验',
    confirmed_straight_hollow_tube: '已核验空心直管',
    unsupported: '当前几何不支持',
    candidate: '待复核候选'
  };
  return labels[String(value)] || '状态待核实';
}
const title = computed(() => isClearance.value ? '导管安装间隙' : props.segment
  ? props.segment.kind === 'arc' ? '中心线弯段' : '中心线直段'
  : props.group === 'native' ? '原生扫掠路径' : '几何导管');
const rows = computed(() => {
  if (isClearance.value) {
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
  return [['来源', row.source === 'native_sweep_path' ? 'CATIA 扫掠中心线引用' : 'STEP 辅助几何恢复'],
    ['对象状态', objectStatus(row.object_status || row.status)],
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
    ['截面外径', mm(section.value.outer_diameter_mm)],
    ['截面内径', mm(section.value.inner_diameter_mm)],
    ['局部壁厚', mm(section.value.wall_thickness_mm)],
    ['截面方法', section.value.method],
    ['路径身份', row.path_id]];
});
</script>

<template>
  <section class="tube-detail">
    <header><h3>{{ title }}</h3><small>{{ displayCurrent ? '当前几何' : '历史或未核验显示版本' }} · {{ isClearance ? '静态安装几何' : '导管工程信息' }}</small></header>
    <p v-if="!displayCurrent" class="notice">结果数值可查看；当前模型的几何版本未核验一致，已停用三维定位、路径及见证点叠加。</p>
    <dl><template v-for="[label, value] in rows" :key="String(label)">
      <template v-if="value !== undefined && value !== null && value !== ''"><dt>{{ label }}</dt><dd>{{ value }}</dd></template>
    </template></dl>
    <p v-if="group === 'native'" class="notice">原生中心线可独立显示；管壁映射和空心实体状态尚未由该引用证明。</p>
    <p v-if="group === 'step' && (record as TubePathRecord).status !== 'confirmed_straight_hollow_tube'" class="notice">几何条件未满足，不能确认空心直管。</p>
    <p v-if="isClearance" class="notice">仅覆盖本次选定的对象范围；没有阈值时不判定安装合格性。</p>
    <details><summary>来源与诊断</summary><pre>{{ JSON.stringify({ record, segment }, null, 2) }}</pre></details>
  </section>
</template>

<style scoped>
.tube-detail { min-width: 0; height: 100%; overflow-y: auto; padding: 16px; color: var(--el-text-color-primary); }
header { border-bottom: 1px solid var(--el-border-color-light); padding-bottom: 12px; }
h3 { margin: 0 0 4px; font-size: 17px; }
small, dt { color: var(--el-text-color-secondary); }
dl { display: grid; grid-template-columns: minmax(80px, 38%) minmax(0, 1fr); gap: 0; margin: 12px 0; font-size: 13px; }
dt, dd { margin: 0; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); overflow-wrap: anywhere; }
.notice { padding: 10px; border-radius: 6px; background: var(--el-fill-color-light); font-size: 12px; }
details { margin-top: 16px; font-size: 12px; }
pre { max-height: 320px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
