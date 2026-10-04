<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { filterTopologyItems, sameTopologySelection, topologyCategories } from './topology-view-model';
import type { TopologyCategory, TopologyExplorerItem } from './topology-view-model';

const props = defineProps<{
  items: TopologyExplorerItem[];
  diagnostics: string[];
  selected: { id: string; kind: string; namespace?: string } | null;
  loading: boolean;
  error?: string;
}>();
const emit = defineEmits<{
  select: [item: TopologyExplorerItem];
  locate: [item: TopologyExplorerItem];
}>();
const category = ref<TopologyCategory>('face');
const keyword = ref('');
const limit = ref(160);
const filterOpen = ref(false);
const filtered = computed(() => filterTopologyItems(props.items, category.value, keyword.value));
const visible = computed(() => filtered.value.slice(0, limit.value));
const currentCategory = computed(() => topologyCategories.find(item => item.value === category.value)!);
watch([category, keyword], () => { limit.value = 160; });

function changeCategory(value: TopologyCategory) {
  category.value = value;
  filterOpen.value = false;
}
function focusAdjacent(event: KeyboardEvent, delta: number) {
  const rows = Array.from((event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLElement>('.topology-row') || []);
  const index = rows.indexOf(event.currentTarget as HTMLElement);
  rows[Math.max(0, Math.min(rows.length - 1, index + delta))]?.focus();
}
async function copyId(item: TopologyExplorerItem) {
  await navigator.clipboard.writeText(item.entityId);
}
</script>

<template>
  <section class="topology-explorer" aria-label="几何拓扑浏览器">
    <div class="topology-controls">
      <div class="topology-search-row">
        <ElInput v-model="keyword" clearable placeholder="搜索编号、名称或拓扑类型" aria-label="搜索编号、名称或拓扑类型">
          <template #prefix><SvgIcon icon="lucide:search" /></template>
        </ElInput>
        <ElPopover v-model:visible="filterOpen" trigger="click" placement="bottom-end" :width="204" :teleported="true">
          <template #reference>
            <button type="button" class="topology-filter-trigger" aria-label="过滤拓扑类型" :aria-expanded="filterOpen">
              <SvgIcon icon="lucide:list-filter" />
            </button>
          </template>
          <div class="topology-filter-options" role="radiogroup" aria-label="拓扑类别">
            <button v-for="option in topologyCategories" :key="option.value" type="button" role="radio"
              :aria-checked="category === option.value" :class="{ active: category === option.value }"
              @click="changeCategory(option.value)">
              <SvgIcon :icon="option.icon" /><span>{{ option.label }}</span>
              <SvgIcon v-if="category === option.value" icon="lucide:check" class="filter-check" />
            </button>
          </div>
        </ElPopover>
      </div>
      <div class="topology-current"><span>当前类别</span><ElTag effect="light" size="small">{{ currentCategory.label }}</ElTag></div>
    </div>

    <div class="topology-list" role="list" aria-label="拓扑对象">
      <template v-if="visible.length">
        <div v-for="item in visible" :key="item.key" class="topology-row"
          :class="{ selected: sameTopologySelection(item, selected) }" role="listitem" tabindex="0"
          :aria-selected="sameTopologySelection(item, selected)" @click="emit('select', item)"
          @keydown.enter.prevent="emit('select', item)" @keydown.up.prevent="focusAdjacent($event, -1)"
          @keydown.down.prevent="focusAdjacent($event, 1)">
          <SvgIcon :icon="topologyCategories.find(option => option.value === item.category)?.icon || 'lucide:box'" class="row-icon" />
          <div class="row-copy"><strong :title="item.title">{{ item.title }}</strong><small :title="item.subtitle">{{ item.subtitle }}</small></div>
          <ElDropdown trigger="click" :teleported="true" @command="(command: string) => command === 'copy' ? copyId(item) : command === 'locate' ? emit('locate', item) : emit('select', item)">
            <button type="button" class="row-more" :aria-label="`${item.title} 更多操作`" @click.stop><SvgIcon icon="lucide:ellipsis" /></button>
            <template #dropdown><ElDropdownMenu>
              <ElDropdownItem command="detail">查看详情</ElDropdownItem>
              <ElTooltip :content="item.canLocate ? '在模型中定位' : '没有该对象的可信显示映射'" placement="right">
                <span><ElDropdownItem command="locate" :disabled="!item.canLocate">在模型中定位</ElDropdownItem></span>
              </ElTooltip>
              <ElDropdownItem command="copy">复制对象 ID</ElDropdownItem>
            </ElDropdownMenu></template>
          </ElDropdown>
        </div>
      </template>
      <ElEmpty v-else :description="error ? '拓扑读取失败' : loading ? '正在读取拓扑…' : keyword ? '已加载对象中没有匹配项' : '当前类别暂无拓扑对象'" :image-size="56" />
    </div>
    <footer class="topology-footer">
      <span v-if="error" class="topology-error" :title="error">{{ error }}</span>
      <span v-else-if="diagnostics.length" class="topology-error" :title="diagnostics.join('\n')">{{ diagnostics.length }} 条身份诊断</span>
      <span v-else>{{ loading ? '正在加载' : `已加载 ${filtered.length} 条${keyword ? '匹配对象' : '当前类别对象'}` }} · 仅搜索已加载数据</span>
      <button v-if="visible.length < filtered.length" type="button" @click="limit += 160">继续加载</button>
    </footer>
  </section>
</template>

<style scoped>
.topology-explorer{display:flex;flex:1;min-height:0;min-width:0;flex-direction:column;background:var(--el-bg-color)}
.topology-controls{flex:none;padding:10px 10px 8px;border-bottom:1px solid var(--el-border-color-lighter)}
.topology-search-row{display:grid;grid-template-columns:minmax(0,1fr) 34px;gap:8px;align-items:center}
.topology-search-row :deep(.el-input){min-width:0}
.topology-filter-trigger{width:34px;height:34px;display:grid;place-items:center;border:1px solid var(--el-border-color);border-radius:6px;background:var(--el-bg-color);color:var(--el-text-color-regular);cursor:pointer}
.topology-filter-trigger:hover,.topology-filter-trigger[aria-expanded=true]{color:var(--el-color-primary);border-color:var(--el-color-primary);background:var(--el-color-primary-light-9)}
.topology-current{display:flex;align-items:center;gap:8px;margin-top:9px;color:var(--el-text-color-secondary);font-size:12px}
.topology-list{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain}
.topology-row{position:relative;display:flex;align-items:center;gap:10px;box-sizing:border-box;min-width:0;min-height:55px;padding:7px 10px 7px 12px;border-bottom:1px solid var(--el-border-color-extra-light);color:var(--el-text-color-primary);cursor:pointer;outline:none}
.topology-row:hover,.topology-row:focus-visible{background:var(--el-fill-color-light)}
.topology-row.selected{background:var(--el-color-primary-light-9);color:var(--el-color-primary)}
.topology-row.selected:before{position:absolute;top:0;bottom:0;left:0;width:3px;background:var(--el-color-primary);content:''}
.row-icon{flex:none;font-size:19px;color:var(--el-text-color-secondary)}
.topology-row.selected .row-icon,.topology-row.selected strong{color:var(--el-color-primary)}
.row-copy{display:flex;flex:1;min-width:0;flex-direction:column;gap:3px;line-height:1.25}
.row-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:600}
.row-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--el-text-color-secondary);font-size:11px}
.row-more{flex:none;display:grid;place-items:center;width:28px;height:28px;border:0;border-radius:5px;background:transparent;color:var(--el-text-color-placeholder);opacity:0;cursor:pointer}
.topology-row:hover .row-more,.topology-row:focus-within .row-more,.topology-row.selected .row-more{opacity:1}
.row-more:hover{background:var(--el-fill-color);color:var(--el-color-primary)}
.topology-footer{display:flex;flex:none;min-height:34px;align-items:center;justify-content:space-between;gap:6px;padding:4px 10px;border-top:1px solid var(--el-border-color-lighter);color:var(--el-text-color-secondary);font-size:11px}
.topology-footer span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.topology-error{color:var(--el-color-warning)}
.topology-footer button{flex:none;border:0;background:transparent;color:var(--el-color-primary);cursor:pointer}
.topology-filter-options{display:flex;flex-direction:column;gap:2px}
.topology-filter-options button{display:flex;align-items:center;gap:10px;width:100%;height:38px;padding:0 10px;border:0;border-radius:5px;background:transparent;color:var(--el-text-color-primary);font-size:13px;text-align:left;cursor:pointer}
.topology-filter-options button:hover,.topology-filter-options button.active{background:var(--el-color-primary-light-9);color:var(--el-color-primary)}
.topology-filter-options button span{flex:1}.filter-check{margin-left:auto}
</style>
