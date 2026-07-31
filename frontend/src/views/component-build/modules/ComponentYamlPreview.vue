<script setup lang="ts">
import { computed, ref, watch } from 'vue'

defineOptions({ name: 'ComponentYamlPreview' })

const props = defineProps<{
  buildId: string
  systemYaml: string
  currentYaml: string
  currentFilename: string | null
  loading: boolean
  loadingLabel: string
  parseError?: string | null
}>()

const emit = defineEmits<{
  uploadYaml: [filename: string, content: string]
  restoreSystem: []
}>()

const activeTab = ref<'system' | 'current'>('current')
const fileInput = ref<HTMLInputElement>()

const previewText = computed(() =>
  activeTab.value === 'system' ? props.systemYaml : props.currentYaml
)
const previewFilename = computed(() => {
  if (activeTab.value === 'system') return `system-spec-${props.buildId}.yaml`
  return props.currentFilename || `component-spec-${props.buildId}.yaml`
})

watch(
  () => props.buildId,
  () => {
    activeTab.value = 'current'
  }
)

watch(
  () => props.currentFilename,
  filename => {
    if (filename) activeTab.value = 'current'
  }
)

function showCurrent() {
  activeTab.value = 'current'
}

function handleUploadClick() {
  fileInput.value?.click()
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!/\.ya?ml$/i.test(file.name)) {
    window.$message?.warning('请选择 .yaml 或 .yml 文件')
    return
  }
  try {
    emit('uploadYaml', file.name, await file.text())
    activeTab.value = 'current'
  } catch {
    window.$message?.error('YAML 文件读取失败')
  }
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(previewText.value)
    window.$message?.success('YAML 已复制')
  } catch {
    window.$message?.error('复制失败')
  }
}

defineExpose({ showCurrent })
</script>

<template>
  <div class="yaml-preview-panel">
    <div class="yaml-controls">
      <div class="yaml-tabs">
        <button
          :class="{ active: activeTab === 'system' }"
          class="yaml-tab"
          type="button"
          @click="activeTab = 'system'"
        >
          系统生成
        </button>
        <button
          :class="{ active: activeTab === 'current' }"
          class="yaml-tab"
          type="button"
          @click="activeTab = 'current'"
        >
          当前编辑
        </button>
      </div>
      <div class="yaml-actions">
        <ElButton size="small" @click="handleUploadClick">上传 YAML</ElButton>
        <ElButton size="small" :disabled="currentYaml === systemYaml" @click="emit('restoreSystem')">
          恢复系统生成
        </ElButton>
        <ElButton size="small" :disabled="!previewText" @click="handleCopy">复制</ElButton>
      </div>
    </div>

    <ElAlert
      v-if="parseError"
      :title="parseError"
      type="error"
      :closable="false"
      show-icon
    />

    <div v-loading="loading" :element-loading-text="loadingLabel" class="yaml-viewer">
      <div v-if="!loading && previewText" class="yaml-header">
        <span class="yaml-filename">{{ previewFilename }}</span>
        <span v-if="activeTab === 'current'" class="yaml-state">字段修改会实时同步到这里</span>
      </div>
      <pre v-if="previewText" class="yaml-content">{{ previewText }}</pre>
      <ElEmpty v-else-if="!loading" description="暂无 YAML 内容" :image-size="42" />
    </div>

    <input
      ref="fileInput"
      type="file"
      accept=".yaml,.yml"
      class="hidden-file-input"
      @change="handleFileChange"
    />
  </div>
</template>

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
  overflow: hidden;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
}

.yaml-tab {
  border: none;
  padding: 4px 12px;
  background: #fff;
  color: #5a6a7e;
  cursor: pointer;
  font-size: 12px;
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
  flex-wrap: wrap;
  gap: 4px;
}

.yaml-viewer {
  min-height: 200px;
  flex: 1;
  overflow: auto;
}

.yaml-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0 6px;
}

.yaml-filename {
  color: #1a2332;
  font-size: 12px;
  font-weight: 500;
}

.yaml-state {
  color: #8e99aa;
  font-size: 11px;
}

.yaml-content {
  margin: 0;
  overflow: auto;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  padding: 14px;
  background: #f7f9fc;
  color: #1a2332;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre;
}

.hidden-file-input {
  display: none;
}
</style>
