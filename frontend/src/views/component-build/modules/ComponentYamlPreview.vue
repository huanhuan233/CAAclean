<script setup lang="ts">
import { computed, ref } from 'vue'

defineOptions({ name: 'ComponentYamlPreview' })

const props = defineProps<{
  buildId: string
  currentYaml: string
  currentFilename: string | null
  loading: boolean
  loadingLabel: string
  parseError?: string | null
}>()

const emit = defineEmits<{
  uploadYaml: [filename: string, content: string]
}>()

const fileInput = ref<HTMLInputElement>()

const previewText = computed(() => props.currentYaml)
const previewFilename = computed(() =>
  props.currentFilename || `component-spec-${props.buildId}.yaml`
)

function showCurrent() {}

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
      <span class="yaml-title">YAML</span>
      <div class="yaml-actions">
        <ElButton size="small" type="primary" @click="handleUploadClick">上传 YAML</ElButton>
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
        <span class="yaml-state">字段修改会实时同步到这里</span>
      </div>
      <pre v-if="previewText" class="yaml-content">{{ previewText }}</pre>
      <ElEmpty v-else-if="!loading" description="请上传 YAML 文件" :image-size="42">
        <ElButton type="primary" @click="handleUploadClick">上传 YAML</ElButton>
      </ElEmpty>
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

.yaml-title {
  color: #344054;
  font-size: 12px;
  font-weight: 600;
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
