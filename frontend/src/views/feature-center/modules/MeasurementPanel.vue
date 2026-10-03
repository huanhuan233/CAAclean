<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { GeometryQueryResponse, GeometryReferencePayload } from '@/service/api/cad';
import type { MeasurementOperation } from './measurement-session';

const props = defineProps<{
  operation: MeasurementOperation;
  references: GeometryReferencePayload[];
  result: GeometryQueryResponse | null;
  loading: boolean;
  error: string;
  snapshotAvailable: boolean;
  seedPoint: number[] | null;
}>();
const emit = defineEmits<{
  start: [operation: Exclude<MeasurementOperation, 'idle'>];
  calculate: [parameters: Record<string, unknown>];
  clear: [];
}>();

const pointText = ref('');
const planeOriginText = ref('');
const planeNormalText = ref('0, 0, 1');
const orientation = ref<'directed' | 'unoriented'>('unoriented');
watch(() => props.operation, mode => {
  const seed = props.seedPoint?.map(value => Number(value.toFixed(4))).join(', ') || '';
  pointText.value = mode === 'local_thickness' ? seed : '';
  planeOriginText.value = mode === 'section' ? seed : '';
  planeNormalText.value = '0, 0, 1';
  orientation.value = 'unoriented';
});
watch(() => props.seedPoint, point => {
  if (!point || point.length !== 3) return;
  const formatted = point.map(value => Number(value.toFixed(4))).join(', ');
  if (props.operation === 'local_thickness') pointText.value = formatted;
  if (props.operation === 'section') planeOriginText.value = formatted;
});
const requiredCount = computed(() => ['distance', 'angle'].includes(props.operation) ? 2 : 1);
const ready = computed(() => props.operation !== 'idle' && props.references.length === requiredCount.value);
const valueRows = computed(() => {
  const values = props.result?.values;
  if (!values) return [];
  const keys = [
    ['distance_mm', '最短距离', 'mm'], ['angle_deg', '夹角', '°'],
    ['local_normal_thickness_mm', '局部法向厚度', 'mm'],
    ['net_area_mm2', '截面净面积', 'mm²'], ['region_count', '截面区域', '']
  ] as const;
  return keys.filter(([key]) => values[key] !== undefined).map(([key, label, unit]) => ({
    key, label, text: `${typeof values[key] === 'number' ? Number(values[key]).toFixed(4) : values[key]} ${unit}`.trim()
  }));
});

function parsePoint(text: string): number[] | null {
  const values = text.split(/[，,\s]+/u).filter(Boolean).map(Number);
  return values.length === 3 && values.every(Number.isFinite) ? values : null;
}

function calculate() {
  if (!ready.value) return;
  if (props.operation === 'angle') {
    emit('calculate', { orientation: orientation.value });
  } else if (props.operation === 'section') {
    const origin = parsePoint(planeOriginText.value);
    const normal = parsePoint(planeNormalText.value);
    if (!origin || !normal) return;
    emit('calculate', { origin, normal });
  } else if (props.operation === 'local_thickness') {
    const point = parsePoint(pointText.value);
    if (!point) return;
    emit('calculate', { point });
  } else emit('calculate', {});
}
</script>

<template>
  <section class="measurement-panel">
    <div class="measurement-heading">
      <strong>几何测量</strong>
      <ElButton v-if="operation !== 'idle'" text size="small" @click="emit('clear')">清除</ElButton>
    </div>
    <p v-if="!snapshotAvailable" class="measurement-hint">当前版本缺少可信 B-Rep 快照，精确测量不可用。</p>
    <div class="measurement-modes">
      <ElButton size="small" :disabled="!snapshotAvailable" :type="operation === 'distance' ? 'primary' : 'default'" @click="emit('start', 'distance')">距离</ElButton>
      <ElButton size="small" :disabled="!snapshotAvailable" :type="operation === 'angle' ? 'primary' : 'default'" @click="emit('start', 'angle')">夹角</ElButton>
      <ElButton size="small" :disabled="!snapshotAvailable" :type="operation === 'section' ? 'primary' : 'default'" @click="emit('start', 'section')">截面</ElButton>
      <ElButton size="small" :disabled="!snapshotAvailable" :type="operation === 'local_thickness' ? 'primary' : 'default'" @click="emit('start', 'local_thickness')">局部厚度</ElButton>
    </div>
    <template v-if="operation !== 'idle'">
      <p class="measurement-hint">{{ operation === 'distance' || operation === 'angle' ? '依次选择对象 A、B' : '选择一个真实几何对象' }}：{{ references.map(item => item.entity_id).join(' → ') || '等待选择' }}</p>
      <label v-if="operation === 'angle'">角度定义
        <select v-model="orientation"><option value="unoriented">无向最小角</option><option value="directed">有向角</option></select>
      </label>
      <template v-if="operation === 'section'">
        <label>截面原点 X, Y, Z<ElInput v-model="planeOriginText" placeholder="0, 0, 0" /></label>
        <label>截面法向 X, Y, Z<ElInput v-model="planeNormalText" placeholder="0, 0, 1" /></label>
      </template>
      <label v-if="operation === 'local_thickness'">面内测量点 X, Y, Z<ElInput v-model="pointText" placeholder="输入真实面上的点" /></label>
      <div class="measurement-actions">
        <ElButton size="small" type="primary" :loading="loading" :disabled="!ready" @click="calculate">{{ result ? '重新计算' : '计算' }}</ElButton>
        <ElButton size="small" @click="emit('clear')">取消</ElButton>
      </div>
      <p v-if="error" class="measurement-error">{{ error }}</p>
      <div v-if="result" class="measurement-result">
        <span>状态：{{ result.status }}</span>
        <div v-for="row in valueRows" :key="row.key" class="measurement-row"><span>{{ row.label }}</span><strong>{{ row.text }}</strong></div>
        <span v-if="result.result_id">结果 ID：{{ result.result_id }}</span>
        <details><summary>来源与诊断</summary><span>{{ result.source || '辅助 B-Rep' }} · {{ result.diagnostic || '无诊断' }}</span></details>
      </div>
    </template>
  </section>
</template>

<style scoped>
.measurement-panel { display: flex; flex-direction: column; gap: 10px; min-width: 0; padding: 12px; border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.measurement-heading, .measurement-actions, .measurement-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.measurement-modes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.measurement-modes .el-button { margin: 0; min-width: 0; }
.measurement-hint, .measurement-result { overflow-wrap: anywhere; color: var(--el-text-color-secondary); font-size: 12px; }
.measurement-error { overflow-wrap: anywhere; color: var(--el-color-danger); }
.measurement-panel label { display: flex; flex-direction: column; gap: 4px; min-width: 0; font-size: 12px; }
.measurement-panel select { width: 100%; padding: 6px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-bg-color); color: var(--el-text-color-primary); }
.measurement-result { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--el-border-color-light); padding-top: 8px; }
.measurement-row strong { color: var(--el-text-color-primary); text-align: right; }
</style>
