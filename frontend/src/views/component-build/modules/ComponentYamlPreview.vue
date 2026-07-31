<script setup lang="ts">
/**
 * ComponentYamlPreview.vue
 * ========================
 * YAML preview panel with local upload support.
 *
 * Displays system-generated YAML alongside optional locally-uploaded YAML.
 * User can toggle between "系统生成" and "本地上传" views.
 */

import { computed, ref, watch } from 'vue'
import { getLocalYaml, clearLocalYaml, saveLocalYaml, type LocalYamlRecord } from '../mock/library-ui'

const props = defineProps<{
  buildId: string
  systemYaml: string
  loading: boolean
  loadingLabel: string
}>()

const emit = defineEmits<{
  close: []
}>()

const activeTab = ref<'system' | 'local'>('system')
const localYaml = ref<LocalYamlRecord | null>(null)
const previewText = computed(() => {
  if (activeTab.value === 'local' && localYaml.value) {
    return localYaml.value.content
  }
  return props.systemYaml
})

const fileInput = ref<HTMLInputElement>()

watch(() => props.buildId, (id) => {
  if (id) {
    localYaml.value = getLocalYaml(id)
    activeTab.value = localYaml.value ? 'local' : 'system'
  } else {
    localYaml.value = null
    activeTab.value = 'system'
  }
}, { immediate: true })

function handleUploadClick() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (!/\.ya?ml$/i.test(file.name)) {
    window.$message?.warning('请选择 .yaml 或 .yml 文件')
    input.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    const content = reader.result as string
    const record: LocalYamlRecord = {
      filename: file.name,
      size: file.size,
      modifiedAt: new Date(file.lastModified).toISOString(),
      content,
      uploadedAt: new Date().toISOString()
    }
    saveLocalYaml(props.buildId, record)
    localYaml.value = record
    activeTab.value = 'local'
    window.$message?.success('本地 YAML 已保存到浏览器缓存')
  }
  reader.onerror = () => {
    window.$message?.error('文件读取失败')
  }
  reader.readAsText(file)
  input.value = ''
}

function handleClearLocal() {
  if (!props.buildId) return
  clearLocalYaml(props.buildId)
  localYaml.value = null
  activeTab.value = 'system'
  window.$message?.info('本地 YAML 已清除')
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(previewText.value)
    window.$message?.success('YAML 已复制')
  } catch {
    window.$message?.error('复制失败')
  }
}

function handleRecoverSystem() {
  activeTab.value = 'system'
}
</script>

<template>
  <div class="yaml-preview-panel">
    <!-- Header controls -->
    <div class="yaml-controls">
      <div class="yaml-tabs">
        <button
          :class="{ active: activeTab === 'system' }"
          class="yaml-tab"
          @click="activeTab = 'system'"
        >
          系统生成
        </button>
        <button
          v-if="localYaml"
          :class="{ active: activeTab === 'local' }"
          class="yaml-tab"
          @click="activeTab = 'local'"
        >
          本地上传
        </button>
      </div>
      <div class="yaml-actions">
        <ElButton size="small" @click="handleUploadClick">
          <template #icon>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          </template>
          上传 YAML
        </ElButton>
        <ElButton v-if="localYaml && activeTab === 'local'" size="small" @click="handleClearLocal">
          清除本地
        </ElButton>
        <ElButton v-if="localYaml && activeTab === 'local'" size="small" @click="handleRecoverSystem">
          恢复系统生成
        </ElButton>
        <ElButton size="small" @click="handleCopy">
          <template #icon>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          </template>
          复制
        </ElButton>
      </div>
    </div>

    <!-- Info alert for local upload -->
    <ElAlert
      v-if="activeTab === 'local' && localYaml"
      title="当前 YAML 上传仅用于前端预览，不会覆盖服务器中的 ComponentSpec 数据。"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 8px;"
    />

    <!-- YAML content -->
    <div v-loading="loading" :element-loading-text="loadingLabel" class="yaml-viewer">
      <div v-if="!loading && previewText" class="yaml-header">
        <span class="yaml-filename">
          {{ activeTab === 'local' && localYaml ? localYaml.filename : `system-spec-${buildId}.yaml` }}
        </span>
        <span class="yaml-schema-version" v-if="activeTab === 'system'">Schema v1.2</span>
      </div>
      <pre v-if="previewText" class="yaml-content">{{ previewText }}</pre>
      <ElEmpty v-else-if="!loading" description="暂无 YAML 内容" :image-size="42" />
    </div>

    <!-- Hidden file input -->
    <input
      ref="fileInput"
      type="file"
      accept=".yaml,.yml"
      style="display: none"
      @change="handleFileChange"
    />
  </div>
</template>

<script lang="ts">
export default { name: 'ComponentYamlPreview' }
</script>

<style scoped>
.yaml-preview-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  gap: 8px;
}

.yaml-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.yaml-tabs {
  display: flex;
  gap: 0;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  overflow: hidden;
}

.yaml-tab {
  padding: 4px 12px;
  font-size: 12px;
  border: none;
  background: #fff;
  color: #5a6a7e;
  cursor: pointer;
  transition: all 0.15s;
}

.yaml-tab.active {
  background: #6c5ce7;
  color: #fff;
}

.yaml-tab:not(.active):hover {
  background: #f0f2f6;
}

.yaml-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.yaml-viewer {
  flex: 1;
  min-height: 200px;
  overflow: auto;
}

.yaml-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0 6px;
}

.yaml-filename {
  font-size: 12px;
  font-weight: 500;
  color: #1a2332;
}

.yaml-schema-version {
  font-size: 11px;
  color: #8e99aa;
}

.yaml-content {
  margin: 0;
  overflow: auto;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  background: #f7f9fc;
  padding: 14px;
  color: #1a2332;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre;
}
</style>
