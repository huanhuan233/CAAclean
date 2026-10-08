<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchCompositeStructure } from '@/service/api/cad';
import type { CompositeStructureRecord } from '@/service/api/cad';
import { compositeListItem } from './composite-view-model';

const props = defineProps<{ buildId: string; revisionId: string; selectedId: string }>();
const emit = defineEmits<{
  select: [record: CompositeStructureRecord]; availability: [available: boolean];
  records: [records: CompositeStructureRecord[]];
}>();
const records = ref<CompositeStructureRecord[]>([]);
const total = ref<number | null>(null);
const loading = ref(false);
const error = ref('');
const query = ref('');
let generation = 0;
let controller: AbortController | null = null;
const visible = computed(() => records.value.map(record => ({ record, item: compositeListItem(record, props.revisionId) }))
  .filter(entry => entry.item.searchText.includes(query.value.trim().toLowerCase())));

async function load(reset = false) {
  if (!props.buildId || loading.value) return;
  if (reset) { records.value = []; total.value = null; emit('records', []); }
  loading.value = true; error.value = '';
  const token = generation;
  const response = await fetchCompositeStructure(props.buildId, records.value.length, 100,
    { signal: controller?.signal, silent: true });
  if (token !== generation) return;
  loading.value = false;
  if (response.error || !response.data) {
    error.value = '复材结构读取失败；请确认采集结果已入库。';
    emit('availability', records.value.length > 0);
    return;
  }
  records.value = [...records.value, ...response.data.records];
  total.value = response.data.total;
  emit('records', records.value);
  emit('availability', total.value > 0);
}

watch(() => [props.buildId, props.revisionId], () => {
  controller?.abort(); controller = new AbortController(); generation += 1;
  records.value = []; total.value = null; error.value = ''; loading.value = false; query.value = '';
  emit('records', []); emit('availability', false);
  if (props.buildId && props.revisionId) void load();
}, { immediate: true });
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <div class="composite-explorer">
    <div class="composite-search"><ElInput v-model="query" clearable placeholder="搜索铺层名称或 ID"
      aria-label="搜索铺层名称或 ID"><template #prefix><SvgIcon icon="mdi:magnify" /></template></ElInput></div>
    <div class="composite-list">
      <button v-for="{ record, item } in visible" :key="item.key" type="button" class="composite-row"
        :class="{ selected: selectedId === item.objectId }" :aria-label="`查看${item.title} ${item.objectId}`"
        @click="emit('select', record)">
        <span class="composite-row-icon"><SvgIcon :icon="item.icon" /></span>
        <span class="composite-row-main"><strong :title="item.title">{{ item.title }}</strong>
          <span>{{ item.summary }}</span><small :title="item.objectId">ID：{{ item.objectId }}</small></span>
        <SvgIcon class="composite-chevron" icon="mdi:chevron-right" />
      </button>
      <p v-if="loading && !records.length" class="composite-empty">正在读取复材对象…</p>
      <p v-else-if="error" class="composite-empty">{{ error }}
        <button type="button" @click="load(true)">重试</button></p>
      <p v-else-if="!records.length" class="composite-empty">当前结果没有复材铺层结构</p>
      <p v-else-if="!visible.length" class="composite-empty">已加载结果中没有匹配对象</p>
    </div>
    <div class="composite-footer">
      <span>已加载 {{ records.length }}{{ total !== null ? ` / ${total}` : '' }} 个对象{{ query ? ' · 仅搜索已加载结果' : '' }}</span>
      <button v-if="total !== null && records.length < total" type="button" :disabled="loading" @click="load()">继续加载</button>
      <span v-else-if="loading">读取中…</span>
    </div>
  </div>
</template>

<style scoped>
.composite-explorer { display: flex; flex-direction: column; min-height: 0; min-width: 0; height: 100%; }
.composite-search { flex: none; padding: 8px 10px; }
.composite-list { flex: 1; min-height: 0; overflow-y: auto; }
.composite-row { position: relative; display: flex; align-items: center; width: 100%; min-width: 0; min-height: 74px;
  gap: 9px; padding: 8px 12px; border: 0; border-bottom: 1px solid var(--el-border-color-extra-light);
  background: transparent; color: var(--el-text-color-primary); text-align: left; cursor: pointer; }
.composite-row:hover, .composite-row:focus-visible { background: var(--el-fill-color-light); }
.composite-row.selected { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.composite-row.selected::before { position: absolute; top: 0; bottom: 0; left: 0; width: 3px;
  background: var(--el-color-primary); content: ''; }
.composite-row-icon { display: grid; place-items: center; flex: none; width: 34px; height: 34px; border-radius: 7px;
  background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 21px; }
.composite-row-main { display: flex; flex: 1; flex-direction: column; min-width: 0; line-height: 1.35; }
.composite-row-main strong { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 13px; font-weight: 600; }
.composite-row-main span, .composite-row-main small { color: var(--el-text-color-secondary); font-size: 11px; }
.composite-row-main small { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.composite-chevron { flex: none; color: var(--el-text-color-placeholder); font-size: 16px; }
.composite-empty { padding: 14px 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.composite-empty button { border: 0; background: transparent; color: var(--el-color-primary); cursor: pointer; }
.composite-footer { display: flex; justify-content: space-between; gap: 8px; flex: none; padding: 8px 10px;
  border-top: 1px solid var(--el-border-color-light); font-size: 11px; color: var(--el-text-color-secondary); }
.composite-footer button { border: 0; background: transparent; color: var(--el-color-primary); cursor: pointer; }
</style>
