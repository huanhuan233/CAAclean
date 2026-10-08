<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { fetchTubeClearances, fetchTubeNativePaths, fetchTubeStepPaths } from '@/service/api';
import type { TubeClearanceRecord, TubePathRecord } from '@/service/api/cad';

type Group = 'native' | 'step' | 'clearance';
type Row = TubePathRecord | TubeClearanceRecord;
const props = defineProps<{ buildId: string; selectedId: string }>();
const emit = defineEmits<{
  select: [group: Group, record: Row, segment?: Record<string, unknown>];
  availability: [available: boolean];
}>();
const group = ref<Group>('native');
const labels: Record<Group, string> = { native: '原生路径', step: '几何导管', clearance: '安装间隙' };
const state = reactive<Record<Group, { rows: Row[]; total: number; loading: boolean; error: string }>>({
  native: { rows: [], total: 0, loading: false, error: '' },
  step: { rows: [], total: 0, loading: false, error: '' },
  clearance: { rows: [], total: 0, loading: false, error: '' }
});
let generation = 0;
let controller: AbortController | null = null;
const current = computed(() => state[group.value]);

async function load(kind: Group, reset = false) {
  if (!props.buildId || state[kind].loading) return;
  if (reset) { state[kind].rows = []; state[kind].total = 0; }
  const token = generation;
  state[kind].loading = true;
  state[kind].error = '';
  const options = { signal: controller?.signal, silent: true };
  const offset = state[kind].rows.length;
  const response = kind === 'native' ? await fetchTubeNativePaths(props.buildId, offset, 50, options)
    : kind === 'step' ? await fetchTubeStepPaths(props.buildId, offset, 50, options)
      : await fetchTubeClearances(props.buildId, offset, 50, options);
  if (token !== generation) return;
  state[kind].loading = false;
  if (!response.data || response.error) {
    state[kind].error = kind === 'native' ? '原生路径读取失败，请重试。' : '当前无已发布分析，或读取失败。';
    return;
  }
  state[kind].rows = [...state[kind].rows, ...response.data.records];
  state[kind].total = response.data.total;
  emit('availability', Object.values(state).some(item => item.total > 0));
}

watch(() => props.buildId, async () => {
  controller?.abort(); controller = new AbortController(); generation += 1;
  (Object.keys(state) as Group[]).forEach(kind => { state[kind].rows = []; state[kind].total = 0; state[kind].error = ''; state[kind].loading = false; });
  emit('availability', false);
  if (!props.buildId) return;
  await Promise.all((['native', 'step', 'clearance'] as Group[]).map(kind => load(kind)));
  group.value = state.native.total ? 'native' : state.step.total ? 'step' : 'clearance';
}, { immediate: true });
onBeforeUnmount(() => controller?.abort());

function isClearance(record: Row): record is TubeClearanceRecord {
  return typeof (record as TubeClearanceRecord).clearance_id === 'string';
}
function rowId(record: Row): string { return isClearance(record) ? record.clearance_id : record.path_id; }
function mm(value: unknown): string { return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(3)} mm` : '长度未测得'; }
function title(record: Row): string {
  if (isClearance(record)) return '安装间隙';
  if (record.source === 'native_sweep_path') return '原生扫掠路径';
  return record.status === 'confirmed_straight_hollow_tube' ? '直管（空心）' : '几何候选';
}
function subtitle(record: Row): string {
  if (isClearance(record)) return `${record.tube_instance_id} · ${record.target_instance_id}`;
  const path = record.path || {};
  const length = path.developed_length_mm ?? path.length_mm;
  return `${record.object_id || record.instance_id || record.solid_id || record.path_id} · ${mm(length)}`;
}
function segments(record: Row): Array<Record<string, unknown>> {
  if (isClearance(record)) return [];
  return Array.isArray(record.path?.segments) ? record.path.segments as Array<Record<string, unknown>> : [];
}
</script>

<template>
  <section class="tube-explorer" aria-label="导管工程信息">
    <div class="tube-groups">
      <button v-for="item in (['native', 'step', 'clearance'] as const)" :key="item" type="button"
        :class="{ active: group === item }" @click="group = item">{{ labels[item] }}</button>
    </div>
    <div class="tube-list">
      <p v-if="current.loading && !current.rows.length" class="tube-state">正在读取{{ labels[group] }}…</p>
      <p v-else-if="current.error && !current.rows.length" class="tube-state">{{ current.error }}
        <button type="button" @click="load(group, true)">重试</button></p>
      <p v-else-if="!current.rows.length" class="tube-state">当前没有{{ labels[group] }}记录。</p>
      <div v-for="record in current.rows" :key="`${group}:${rowId(record)}`" class="tube-row"
        :class="{ selected: selectedId === rowId(record) }">
        <button type="button" class="tube-primary" :aria-label="`查看${title(record)} ${rowId(record)}`"
          @click="emit('select', group, record)">
          <strong>{{ title(record) }}</strong><small>{{ subtitle(record) }}</small>
          <small v-if="isClearance(record)">{{ typeof record.distance_mm === 'number' ? mm(record.distance_mm) : '距离未测得' }}</small>
        </button>
        <div v-if="segments(record).length" class="tube-segments">
          <button v-for="segment in segments(record)" :key="String(segment.source_id)" type="button"
            @click="emit('select', group, record, segment)">
            {{ segment.kind === 'arc' ? '弯段' : '直段' }} {{ segment.order }} · {{ mm(segment.length_mm) }}
          </button>
        </div>
      </div>
      <button v-if="current.rows.length < current.total && !current.loading" type="button" class="tube-more"
        @click="load(group)">继续加载</button>
    </div>
    <footer>已加载 {{ current.rows.length }} / {{ current.total }} 条 · {{ labels[group] }}</footer>
  </section>
</template>

<style scoped>
.tube-explorer { display: flex; flex: 1; flex-direction: column; min-height: 0; min-width: 0; }
.tube-groups { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; padding: 8px; }
.tube-groups button { min-width: 0; padding: 7px 2px; border-radius: 5px; color: var(--el-text-color-regular); font-size: 12px; }
.tube-groups button.active { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tube-list { flex: 1; min-height: 0; overflow-y: auto; padding: 0 8px 8px; }
.tube-row { margin-bottom: 6px; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.tube-row:hover { background: var(--el-fill-color-light); }
.tube-row.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tube-primary { display: flex; width: 100%; flex-direction: column; gap: 4px; min-width: 0; padding: 9px; text-align: left; color: var(--el-text-color-primary); }
.tube-primary strong, .tube-primary small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.tube-primary small { color: var(--el-text-color-secondary); font-size: 11px; }
.tube-segments { display: flex; flex-direction: column; gap: 2px; padding: 0 8px 8px; }
.tube-segments button { text-align: left; color: var(--el-text-color-regular); font-size: 11px; padding: 3px 5px; border-radius: 4px; }
.tube-segments button:hover { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.tube-state { padding: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.tube-more { width: 100%; padding: 8px; color: var(--el-color-primary); }
footer { flex: none; padding: 8px; border-top: 1px solid var(--el-border-color-light); color: var(--el-text-color-secondary); font-size: 12px; }
</style>
