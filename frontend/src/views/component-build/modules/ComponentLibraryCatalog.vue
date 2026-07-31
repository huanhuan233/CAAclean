<script setup lang="ts">
/**
 * ComponentLibraryCatalog.vue
 * ===========================
 * Left-side catalog navigation panel for the component library page.
 *
 * Supports expand/collapse for parent categories. Parent items (depth=0)
 * can be toggled to show/hide their child items (depth=1).
 */

import { computed, ref, watch } from 'vue'

interface CatalogItem {
  id: string
  label: string
  code: string
  count: number
  parentCode?: string
  depth: number
}

const props = defineProps<{
  catalogItems: CatalogItem[]
  selectedCatalogId: string
  totalBuildCount: number
  loading: boolean
}>()

const emit = defineEmits<{
  select: [catalogId: string]
}>()

const rootNode = computed<CatalogItem>(() => ({
  id: '__root__',
  label: '机械工程图元库',
  code: '__root__',
  count: props.totalBuildCount,
  depth: 0
}))

// ── Expand/collapse state ──
// Track which parent category ids are expanded. All parents start expanded.
const expandedParentIds = ref<Set<string>>(new Set())

// Initialize: expand all parent categories by default
watch(() => props.catalogItems, (items) => {
  if (expandedParentIds.value.size === 0) {
    const parentIds = items.filter(item => item.depth === 0).map(item => item.id)
    expandedParentIds.value = new Set(parentIds)
  }
}, { immediate: true })

// Visible items: root + parent items + expanded parents' children
const visibleItems = computed(() => {
  const result: CatalogItem[] = []
  for (const item of props.catalogItems) {
    if (item.depth === 0) {
      result.push(item) // always show parents
    } else if (item.depth === 1 && item.parentCode && expandedParentIds.value.has(item.parentCode)) {
      result.push(item) // only show if parent is expanded
    }
  }
  return result
})

function isParent(id: string): boolean {
  return props.catalogItems.some(item => item.parentCode === id)
}

function isExpanded(id: string): boolean {
  return expandedParentIds.value.has(id)
}

function handleParentClick(categoryId: string) {
  // Toggle expand/collapse
  const next = new Set(expandedParentIds.value)
  if (next.has(categoryId)) {
    next.delete(categoryId)
  } else {
    next.add(categoryId)
  }
  expandedParentIds.value = next
  // Also fire the select event so the right table filters
  emit('select', categoryId)
}

function handleItemClick(item: CatalogItem) {
  if (item.depth === 0) {
    handleParentClick(item.id)
  } else {
    emit('select', item.id)
  }
}

function handleRootClick() {
  // Expand all parents when root is clicked
  const allParentIds = props.catalogItems.filter(item => item.depth === 0).map(item => item.id)
  expandedParentIds.value = new Set(allParentIds)
  emit('select', '__root__')
}

function isSelected(id: string) {
  return props.selectedCatalogId === id
}
</script>

<template>
  <div class="catalog-panel">
    <div class="catalog-header">
      <span class="catalog-title">目录层级</span>
    </div>

    <div v-loading="loading" class="catalog-body" element-loading-text="加载目录中…">
      <!-- Root node -->
      <div
        class="catalog-item root-item"
        :class="{ active: isSelected(rootNode.id) }"
        @click="handleRootClick"
      >
        <span class="catalog-item-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
          </svg>
        </span>
        <span class="catalog-item-label">{{ rootNode.label }}</span>
        <span class="catalog-item-count">{{ rootNode.count }}</span>
      </div>

      <!-- Divider -->
      <div class="catalog-divider" />

      <!-- Category nodes -->
      <template v-for="item in visibleItems" :key="item.id">
        <!-- Parent items -->
        <div
          v-if="item.depth === 0"
          class="catalog-item"
          :class="{ active: isSelected(item.id), expanded: isExpanded(item.id) }"
          @click="handleParentClick(item.id)"
        >
          <span class="catalog-item-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
            </svg>
          </span>
          <span class="catalog-item-label">{{ item.label }}</span>
          <span class="catalog-item-count">{{ item.count }}</span>
          <span class="expand-icon">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" :class="{ rotated: isExpanded(item.id) }">
              <path d="M12 16l-6-6h12z" />
            </svg>
          </span>
        </div>

        <!-- Child items -->
        <div
          v-else-if="item.depth === 1"
          class="catalog-item is-child"
          :class="{ active: isSelected(item.id) }"
          @click="handleItemClick(item)"
        >
          <span class="catalog-item-icon child-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </span>
          <span class="catalog-item-label">{{ item.label }}</span>
          <span class="catalog-item-count">{{ item.count }}</span>
        </div>
      </template>

      <ElEmpty v-if="!loading && !catalogItems.length" description="" :image-size="40" />
    </div>

    <!-- Info footer -->
    <div class="catalog-footer">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      <span>支持多级目录扩展。新增目录将同步至用户端图元选择器与检索命名空间。</span>
    </div>
  </div>
</template>

<style scoped>
.catalog-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fff;
  border: 1px solid #e5eaf2;
  border-radius: 12px;
}

.catalog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
}

.catalog-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2332;
}

.catalog-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.catalog-item {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #5a6a7e;
  transition: background-color 0.15s;
}

.catalog-item.is-child {
  padding-left: 22px;
  height: 30px;
  font-size: 12px;
}

.catalog-item:hover {
  background-color: #f0f2f6;
}

.catalog-item.active {
  background-color: #f0edff;
  color: #6c5ce7;
  font-weight: 500;
}

.catalog-item.active .catalog-item-icon {
  color: #6c5ce7;
}

.catalog-item-icon.child-icon {
  color: #9aa6b5;
}

.catalog-item.active .catalog-item-icon.child-icon {
  color: #6c5ce7;
}

.catalog-item.root-item {
  font-weight: 600;
  color: #1a2332;
}

.catalog-item-icon {
  display: inline-flex;
  flex-shrink: 0;
  color: #8e99aa;
}

.catalog-item.active .catalog-item-icon {
  color: #6c5ce7;
}

.catalog-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.catalog-item-count {
  flex-shrink: 0;
  min-width: 20px;
  text-align: right;
  font-size: 12px;
  color: #8e99aa;
  font-variant-numeric: tabular-nums;
}

.catalog-divider {
  height: 1px;
  margin: 4px 10px;
  background: #e5eaf2;
}

.catalog-footer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 14px;
  font-size: 11px;
  line-height: 1.5;
  color: #8e99aa;
  border-top: 1px solid #e5eaf2;
}

.catalog-footer svg {
  margin-top: 1px;
  flex-shrink: 0;
}

.expand-icon {
  display: inline-flex;
  flex-shrink: 0;
  color: #9aa6b5;
  transition: transform 0.2s;
}

.expand-icon svg {
  transition: transform 0.2s;
}

.expand-icon svg.rotated {
  transform: rotate(180deg);
}
</style>
