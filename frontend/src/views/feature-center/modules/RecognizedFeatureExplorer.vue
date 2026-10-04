<script setup lang="ts">
import { computed, ref } from 'vue';
import { filterRecognizedFeatureItems, recognizedFeatureCategories } from './recognized-feature-view-model';
import type { RecognizedFeatureItem } from './recognized-feature-view-model';

const props = defineProps<{
  items: RecognizedFeatureItem[];
  selectedId: string;
  total: number | null;
  hasMore: boolean;
  loading: boolean;
  pageLoading: boolean;
  error: string;
  emptyDescription: string;
}>();
const emit = defineEmits<{
  select: [featureId: string];
  locate: [featureId: string];
  loadMore: [];
  retry: [];
}>();

const keyword = ref('');
const category = ref('all');
const reviewState = ref('all');
const filterOpen = ref(false);
const categories = computed(() => recognizedFeatureCategories(props.items));
const filtered = computed(() =>
  filterRecognizedFeatureItems(props.items, {
    category: category.value,
    status: reviewState.value,
    keyword: keyword.value
  })
);
const selected = computed(() => props.items.find(item => item.featureId === props.selectedId) || null);
const filterActive = computed(() => category.value !== 'all' || reviewState.value !== 'all');
const statusOptions = computed(() => {
  const values = new Map<string, string>();
  for (const item of props.items) values.set(item.status.raw, item.status.label);
  return [{ value: 'all', label: '全部状态' }, ...[...values].map(([value, label]) => ({ value, label }))];
});
const countLabel = computed(() =>
  props.total === null
    ? `已加载 ${props.items.length} 个特征`
    : `共 ${props.total} 个特征（已加载 ${props.items.length}）`
);

function chooseCategory(value: string) {
  category.value = value;
  filterOpen.value = false;
}
function chooseStatus(value: string) {
  reviewState.value = value;
  filterOpen.value = false;
}
function selectFromKeyboard(event: KeyboardEvent, item: RecognizedFeatureItem) {
  if (event.target !== event.currentTarget) return;
  emit('select', item.featureId);
}
function focusAdjacent(event: KeyboardEvent, delta: number) {
  const rows = Array.from(
    (event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLElement>('.recognized-card') || []
  );
  const index = rows.indexOf(event.currentTarget as HTMLElement);
  rows[Math.max(0, Math.min(rows.length - 1, index + delta))]?.focus();
}
async function copyId(item: RecognizedFeatureItem) {
  await navigator.clipboard.writeText(item.featureId);
}
function menuAction(command: string, item: RecognizedFeatureItem) {
  if (command === 'copy') copyId(item).catch(() => undefined);
  else if (command === 'locate' && item.canLocate) emit('locate', item.featureId);
  else if (command === 'detail') emit('select', item.featureId);
}
</script>

<template>
  <section class="recognized-explorer" aria-label="识别特征浏览器">
    <div class="explorer-controls">
      <div class="search-row">
        <ElInput
          v-model="keyword"
          clearable
          placeholder="搜索特征名称、ID 或关键词"
          aria-label="搜索特征名称、ID 或关键词"
        >
          <template #prefix><SvgIcon icon="lucide:search" /></template>
        </ElInput>
        <ElPopover v-model:visible="filterOpen" trigger="click" placement="bottom-end" :width="212" :teleported="true">
          <template #reference>
            <button
              type="button"
              class="filter-trigger"
              aria-label="筛选识别特征"
              title="筛选"
              :aria-expanded="filterOpen"
            >
              <SvgIcon icon="lucide:list-filter" />
              <span>筛选</span>
            </button>
          </template>
          <div class="filter-options">
            <small>特征类别</small>
            <button
              v-for="option in categories"
              :key="option.value"
              type="button"
              :class="{ active: category === option.value }"
              @click="chooseCategory(option.value)"
            >
              {{ option.label }}
              <SvgIcon v-if="category === option.value" icon="lucide:check" />
            </button>
            <small>核验状态</small>
            <button
              v-for="option in statusOptions"
              :key="option.value"
              type="button"
              :class="{ active: reviewState === option.value }"
              @click="chooseStatus(option.value)"
            >
              {{ option.label }}
              <SvgIcon v-if="reviewState === option.value" icon="lucide:check" />
            </button>
            <button
              v-if="filterActive"
              type="button"
              class="reset-filter"
              @click="
                category = 'all';
                reviewState = 'all';
                filterOpen = false;
              "
            >
              清空筛选
            </button>
          </div>
        </ElPopover>
      </div>
      <div class="category-shortcuts" aria-label="快捷类别">
        <button
          v-for="option in categories"
          :key="option.value"
          type="button"
          :class="{ active: category === option.value }"
          @click="category = option.value"
        >
          {{ option.label }}
        </button>
      </div>
      <div v-if="filterActive || keyword" class="filter-summary">
        已加载结果中匹配 {{ filtered.length }} 个
        <button
          type="button"
          @click="
            category = 'all';
            reviewState = 'all';
            keyword = '';
          "
        >
          重置
        </button>
      </div>
    </div>

    <div class="explorer-list" role="list" aria-label="识别特征列表">
      <template v-if="filtered.length">
        <div
          v-for="item in filtered"
          :key="item.key"
          class="recognized-card"
          role="listitem"
          tabindex="0"
          :class="{ selected: selectedId === item.featureId, uncertain: item.status.tone === 'warning' || item.candidatePreview }"
          :aria-selected="selectedId === item.featureId"
          :aria-label="`${item.title}，${item.status.label}，ID ${item.featureId}`"
          @click="emit('select', item.featureId)"
          @keydown.enter.prevent="selectFromKeyboard($event, item)"
          @keydown.up.prevent="focusAdjacent($event, -1)"
          @keydown.down.prevent="focusAdjacent($event, 1)"
        >
          <div class="card-top">
            <strong :title="item.title">{{ item.title }}</strong>
            <ElTag size="small" effect="light" :type="item.status.tone" :title="item.status.raw">
              {{ item.status.label }}
            </ElTag>
            <ElDropdown trigger="click" :teleported="true" @command="(command: string) => menuAction(command, item)">
              <button type="button" class="card-more" :aria-label="`${item.title} 更多操作`" @click.stop>
                <SvgIcon icon="lucide:ellipsis-vertical" />
              </button>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem command="detail">查看详情</ElDropdownItem>
                  <ElTooltip :content="item.canLocate ? (item.candidatePreview ? '候选范围预览' : '在三维中定位') : item.locateReason" placement="right">
                    <span>
                      <ElDropdownItem command="locate" :disabled="!item.canLocate">{{ item.candidatePreview ? '在三维中预览' : '在三维中定位' }}</ElDropdownItem>
                    </span>
                  </ElTooltip>
                  <ElDropdownItem command="copy">复制特征 ID</ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </div>
          <div class="card-descriptors">
            <span v-for="tag in item.descriptors" :key="tag">{{ tag }}</span>
          </div>
          <small class="card-id" :title="item.featureId">ID：{{ item.featureId }}</small>
          <small v-if="selectedId === item.featureId && item.candidatePreview" class="preview-note">候选范围预览</small>
        </div>
        <button v-if="hasMore" type="button" class="load-more" :disabled="pageLoading" @click="emit('loadMore')">
          {{ pageLoading ? '正在加载…' : '继续加载识别特征' }}
        </button>
      </template>
      <div v-else-if="error" class="list-state" role="alert">
        <span>识别特征列表读取失败：{{ error }}</span>
        <button type="button" @click="emit('retry')">重试</button>
      </div>
      <div v-else-if="loading" class="list-state">正在加载识别特征…</div>
      <div v-else-if="keyword || filterActive" class="list-state">已加载结果中没有匹配的特征</div>
      <div v-else class="list-state">{{ emptyDescription }}</div>
      <div v-if="error && filtered.length" class="list-state" role="alert">
        继续加载失败：{{ error }}
        <button type="button" @click="emit('retry')">重试</button>
      </div>
    </div>

    <footer class="explorer-footer">
      <div class="footer-copy">
        <span>{{ countLabel }}</span>
        <small>仅搜索已加载结果 · 已选择 {{ selected ? 1 : 0 }} 个</small>
      </div>
      <ElTooltip :content="selected?.canLocate ? (selected.candidatePreview ? '候选范围预览' : '在三维中定位') : selected?.locateReason || '请选择识别特征'">
        <span>
          <ElButton
            size="small"
            :disabled="!selected?.canLocate"
            @click="selected && emit('locate', selected.featureId)"
          >
            <SvgIcon icon="lucide:scan-eye" />
            {{ selected?.candidatePreview ? '在三维中预览' : '在三维中定位' }}
          </ElButton>
        </span>
      </ElTooltip>
    </footer>
  </section>
</template>

<style scoped>
.recognized-explorer {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  background: var(--el-bg-color);
}
.explorer-controls {
  flex: none;
  padding: 10px 10px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 7px;
  min-width: 0;
}
.search-row :deep(.el-input) {
  min-width: 0;
}
.filter-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  font-size: 12px;
  cursor: pointer;
}
.filter-trigger:hover,
.filter-trigger[aria-expanded='true'] {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.category-shortcuts {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  min-width: 0;
  margin-top: 9px;
  padding-bottom: 2px;
  scrollbar-width: thin;
}
.category-shortcuts button {
  flex: none;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  padding: 5px 9px;
  font-size: 12px;
  cursor: pointer;
}
.category-shortcuts button.active {
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.filter-summary {
  display: flex;
  justify-content: space-between;
  gap: 5px;
  margin-top: 7px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
}
.filter-summary button {
  border: 0;
  background: none;
  color: var(--el-color-primary);
  cursor: pointer;
}
.filter-options {
  display: flex;
  flex-direction: column;
  max-height: min(55vh, 420px);
  overflow: auto;
}
.filter-options small {
  padding: 6px 8px 3px;
  color: var(--el-text-color-secondary);
}
.filter-options button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 34px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--el-text-color-primary);
  padding: 5px 8px;
  text-align: left;
  cursor: pointer;
}
.filter-options button:hover,
.filter-options button.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.filter-options .reset-filter {
  color: var(--el-color-primary);
}
.explorer-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 9px 10px;
  overscroll-behavior: contain;
}
.recognized-card {
  min-width: 0;
  margin-bottom: 7px;
  padding: 9px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  cursor: pointer;
  outline: none;
}
.recognized-card:hover,
.recognized-card:focus-visible {
  background: var(--el-fill-color-light);
}
.recognized-card.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  min-height: 25px;
}
.card-top strong {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}
.recognized-card.selected .card-top strong {
  color: var(--el-color-primary);
}
.recognized-card.selected.uncertain {
  border-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}
.recognized-card.selected.uncertain .card-top strong {
  color: var(--el-color-warning);
}
.card-top :deep(.el-tag) {
  flex: none;
  max-width: 90px;
  font-size: 11px;
}
.card-more {
  flex: none;
  display: grid;
  place-items: center;
  width: 23px;
  height: 23px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--el-text-color-placeholder);
  opacity: 0;
  cursor: pointer;
}
.recognized-card:hover .card-more,
.recognized-card:focus-within .card-more,
.recognized-card.selected .card-more {
  opacity: 1;
}
.card-more:hover {
  background: var(--el-fill-color);
  color: var(--el-color-primary);
}
.card-descriptors {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 3px;
  min-height: 17px;
}
.card-descriptors span {
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  padding: 1px 5px;
  font-size: 11px;
  line-height: 16px;
}
.card-id {
  display: block;
  overflow: hidden;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-note {
  display: block;
  margin-top: 3px;
  color: var(--el-color-warning);
  font-size: 11px;
}
.load-more {
  display: block;
  width: 100%;
  padding: 7px;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  font-size: 12px;
  cursor: pointer;
}
.list-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 10px;
  color: var(--el-text-color-secondary);
  text-align: center;
  font-size: 12px;
}
.list-state button {
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  cursor: pointer;
}
.explorer-footer {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-height: 51px;
  padding: 7px 10px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}
.footer-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  color: var(--el-text-color-regular);
  font-size: 11px;
}
.footer-copy span,
.footer-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.footer-copy small {
  color: var(--el-text-color-secondary);
  font-size: 10px;
}
.explorer-footer :deep(.el-button) {
  white-space: nowrap;
}
@media (max-width: 365px) {
  .filter-trigger span {
    display: none;
  }
  .filter-trigger {
    width: 34px;
    padding: 0;
  }
  .explorer-footer :deep(.el-button) {
    padding: 5px 7px;
    font-size: 11px;
  }
}
</style>
