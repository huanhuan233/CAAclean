<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchAssemblyBooleans, fetchAssemblyConnections, fetchAssemblyRelations } from '@/service/api';
import type { AssemblyEvidenceRecord } from '@/service/api/cad';

type Group = 'relations' | 'connections' | 'booleans';
const props = defineProps<{ buildId: string; selectedId: string }>();
const emit = defineEmits<{ select: [group: Group, record: AssemblyEvidenceRecord] }>();
const group = ref<Group>('relations');
const records = ref<AssemblyEvidenceRecord[]>([]);
const total = ref(0);
const loading = ref(false);
const error = ref('');
const unavailable = ref('');
let controller: AbortController | null = null;
let generation = 0;
const hasMore = computed(() => records.value.length < total.value);
const groupLabels: Record<Group, string> = { relations: '空间关系', connections: '连接定义', booleans: '派生布尔' };

function rowId(record: AssemblyEvidenceRecord): string {
  return String(record.relation_id || record.connection_id || record.result_version || '');
}
function rowTitle(record: AssemblyEvidenceRecord): string {
  if (group.value === 'connections') return ({ fastener: '紧固件', seal: '密封', bond: '胶接' }[record.kind || ''] || '连接定义');
  if (group.value === 'booleans') return '派生布尔';
  const joint = record.joint_classification as Record<string, unknown> | undefined;
  if (joint?.joint_kind === 'lap') return joint.status === 'confirmed' ? '搭接' : '搭接候选';
  if (joint?.joint_kind === 'butt') return '对接';
  return ({ face_contact: '面接触', interference: '实体干涉', positive_gap: '正间隙',
    line_contact: '线接触', point_contact: '点接触' }[record.contact_kind || ''] || '空间关系');
}
function rowSubtitle(record: AssemblyEvidenceRecord): string {
  if (group.value === 'connections') return String(record.part_number || record.raw_alias || '所属产品未解析');
  if (group.value === 'booleans') return `${record.left_instance_id || '?'} → ${record.right_instance_id || '?'}`;
  return `${record.instance_a || '?'} · ${record.instance_b || '?'}`;
}

async function load(reset = false) {
  if (!props.buildId || loading.value && !reset) return;
  if (reset) {
    controller?.abort();
    controller = new AbortController();
    generation += 1;
    records.value = [];
    total.value = 0;
  }
  const current = generation;
  loading.value = true;
  error.value = '';
  unavailable.value = '';
  const options = { signal: controller?.signal, silent: true };
  const result = group.value === 'connections'
    ? await fetchAssemblyConnections(props.buildId, records.value.length, 50, options)
    : group.value === 'booleans'
      ? await fetchAssemblyBooleans(props.buildId, records.value.length, 50, options)
      : await fetchAssemblyRelations(props.buildId, records.value.length, 50, options);
  if (current !== generation) return;
  loading.value = false;
  if (result.error || !result.data) {
    unavailable.value = '当前 Revision 尚无该类已发布结果，或来源不完整。';
    error.value = '读取失败，请重试；若未运行分析，请先在现有构建流程完成计算。';
    return;
  }
  records.value = [...records.value, ...result.data.records];
  total.value = result.data.total;
}
watch(() => [props.buildId, group.value], () => void load(true), { immediate: true });
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <section class="assembly-explorer" aria-label="装配关系">
    <div class="assembly-groups">
      <button v-for="item in (['relations', 'connections', 'booleans'] as const)" :key="item" type="button"
        :class="{ active: group === item }" @click="group = item">{{ groupLabels[item] }}</button>
    </div>
    <div class="assembly-list">
      <p v-if="loading && !records.length" class="assembly-state">正在读取{{ groupLabels[group] }}…</p>
      <p v-else-if="error" class="assembly-state">{{ error }} <button type="button" @click="load(true)">重试</button></p>
      <p v-else-if="!records.length" class="assembly-state">{{ unavailable || '当前没有此类已发布记录。' }}</p>
      <button v-for="record in records" :key="`${group}:${rowId(record)}`" type="button" class="assembly-row"
        :class="{ selected: selectedId === rowId(record) }" @click="emit('select', group, record)">
        <strong>{{ rowTitle(record) }}</strong>
        <small>{{ rowSubtitle(record) }}</small>
        <small v-if="group === 'relations' && typeof record.distance_mm === 'number'">距离 {{ record.distance_mm }} mm</small>
        <small v-else-if="group === 'connections'">{{ record.native_source_status === 'partial' ? '原生语义部分读取' : record.native_source_status || '状态未知' }}</small>
        <small v-else>{{ record.operation || record.status || '状态未知' }}</small>
      </button>
      <button v-if="hasMore && !loading" type="button" class="assembly-more" @click="load()">继续加载</button>
    </div>
    <footer>已加载 {{ records.length }} / {{ total }} 条 · {{ groupLabels[group] }}</footer>
  </section>
</template>

<style scoped>
.assembly-explorer { display: flex; flex-direction: column; min-height: 0; min-width: 0; flex: 1; }
.assembly-groups { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; padding: 8px; }
.assembly-groups button { min-width: 0; padding: 7px 2px; border-radius: 5px; color: var(--el-text-color-regular); }
.assembly-groups button.active { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.assembly-list { min-height: 0; overflow-y: auto; padding: 0 8px 8px; }
.assembly-row { display: flex; width: 100%; min-width: 0; flex-direction: column; gap: 3px; text-align: left; padding: 9px;
  margin-bottom: 6px; border: 1px solid var(--el-border-color-light); border-radius: 6px; color: var(--el-text-color-primary); }
.assembly-row:hover { background: var(--el-fill-color-light); }
.assembly-row.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.assembly-row strong, .assembly-row small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.assembly-row small { color: var(--el-text-color-secondary); }
.assembly-state { padding: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.assembly-more { width: 100%; padding: 8px; color: var(--el-color-primary); }
footer { flex: none; padding: 8px; border-top: 1px solid var(--el-border-color-light); color: var(--el-text-color-secondary); font-size: 12px; }
</style>
