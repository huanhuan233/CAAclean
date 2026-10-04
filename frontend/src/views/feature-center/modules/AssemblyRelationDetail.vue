<script setup lang="ts">
import { computed } from 'vue';
import type { AssemblyEvidenceRecord } from '@/service/api/cad';

const props = defineProps<{ record: AssemblyEvidenceRecord; group: 'relations' | 'connections' | 'booleans' }>();
const title = computed(() => {
  if (props.group === 'connections') return ({ fastener: '紧固件', seal: '密封', bond: '胶接' }[props.record.kind || ''] || '连接定义');
  if (props.group === 'booleans') return '派生布尔';
  return props.record.joint_classification && typeof props.record.joint_classification === 'object'
    ? '装配关系 · 搭接' : '装配空间关系';
});
const summary = computed(() => {
  const row = props.record;
  if (props.group === 'relations') return [
    ['实例 A', row.instance_a], ['实例 B', row.instance_b], ['关系', row.contact_kind],
    ['最短距离', typeof row.distance_mm === 'number' ? `${row.distance_mm} mm` : undefined],
    ['真实接触面积', typeof row.actual_contact_area_mm2 === 'number' ? `${row.actual_contact_area_mm2} mm²` : undefined],
    ['干涉体积', typeof row.interference_volume_mm3 === 'number' ? `${row.interference_volume_mm3} mm³` : undefined],
    ['几何状态', (row.joint_classification as Record<string, unknown> | undefined)?.status],
  ];
  if (props.group === 'connections') return [
    ['原生 Alias', row.raw_alias], ['PartNumber', row.part_number], ['模型规则', row.model_role],
    ['点位数', row.point_count], ['坐标与几何', row.geometry_link_status],
  ];
  const result = row.result as Record<string, unknown> | undefined;
  return [['操作', row.operation], ['壳体角色', row.shell_role_status], ['源', row.source],
    ['结果状态', result?.status], ['结果体积', typeof result?.volume_mm3 === 'number' ? `${result.volume_mm3} mm³` : undefined]];
});
</script>

<template>
  <section class="assembly-detail">
    <header><h3>{{ title }}</h3><small>当前 Revision 的已发布记录</small></header>
    <dl><template v-for="[label, value] in summary" :key="String(label)">
      <template v-if="value !== undefined && value !== null && value !== ''"><dt>{{ label }}</dt><dd>{{ value }}</dd></template>
    </template></dl>
    <p class="assembly-notice">该记录暂无可信 Viewer 对象映射；右侧属性可查看，三维精确定位暂不可用。</p>
    <details><summary>来源与诊断</summary><pre>{{ JSON.stringify(record, null, 2) }}</pre></details>
  </section>
</template>

<style scoped>
.assembly-detail { min-width: 0; height: 100%; overflow-y: auto; padding: 16px; color: var(--el-text-color-primary); }
header { border-bottom: 1px solid var(--el-border-color-light); padding-bottom: 12px; }
h3 { margin: 0 0 4px; font-size: 17px; }
small, dt { color: var(--el-text-color-secondary); }
dl { display: grid; grid-template-columns: minmax(80px, 38%) minmax(0, 1fr); gap: 0; margin: 12px 0; font-size: 13px; }
dt, dd { margin: 0; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); overflow-wrap: anywhere; }
.assembly-notice { padding: 10px; border-radius: 6px; background: var(--el-fill-color-light); font-size: 12px; }
details { margin-top: 16px; font-size: 12px; }
pre { max-height: 320px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
