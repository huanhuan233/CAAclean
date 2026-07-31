<script setup lang="ts">
/**
 * ComponentLibraryDialog.vue
 * ==========================
 * 3-tab dialog for editing/creating a component.
 *
 * Tab 1: 基础信息 — form fields matching createComponentBuild payload
 * Tab 2: 关联数据 — STEP, drawing, fusion status cards
 * Tab 3: YAML / ComponentSpec — field editor + YAML preview
 */

import { computed, nextTick, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  applyComponentSpecFieldEdit,
  componentSpecPayloadForFusion,
  createComponentSpecEditorState,
  createComponentSpecSavePayload,
  importComponentSpecYaml,
  requiresComponentSpecDiscardConfirmation,
  type ComponentSpecEditorState
} from '../component-spec-editor-state'
import type { ComponentSpecFieldPath } from '../component-spec-field-events'
import {
  YamlWorkingDocumentError,
  createYamlWorkingDocument
} from '../yaml-working-document'
import ComponentSpecFieldEditor from './ComponentSpecFieldEditor.vue'
import ComponentYamlPreview from './ComponentYamlPreview.vue'

/**
 * Exposed to index.vue so it can call methods.
 */
defineExpose({
  open,
  close,
  setSourceParsing,
  updateBuildStatuses,
  setComponentSpec,
  setSystemYaml,
  setSpecLoading,
  setSpecSaving,
  setSpecPreviewing
})

const router = useRouter()

// ── Props ──
const props = defineProps<{
  catalog: Api.ComponentBuild.CatalogCategory[]
  catalogLoading: boolean
  submitting: boolean
}>()

// ── Emits ──
const emit = defineEmits<{
  submit: [payload: {
    form: Omit<Api.ComponentBuild.CreatePayload, 'step_file' | 'drawing_file'>
    editingBuild: Api.ComponentBuild.BuildDetail | null
    stepFile: File | null
    drawingFile: File | null
  }]
  refresh: []
  fusion: [buildId: string, payload: Api.ComponentBuild.ComponentSpecSavePayload | null]
  saveSpec: [buildId: string, payload: Api.ComponentBuild.ComponentSpecSavePayload]
  startParsing: [buildId: string, role: Api.ComponentBuild.RetryRole]
}>()

// ── State ──
const visible = ref(false)
const activeTab = ref('basic')
const formRef = ref<FormInstance>()

// Editing state
const editingBuild = ref<Api.ComponentBuild.BuildDetail | null>(null)
const isEditing = computed(() => Boolean(editingBuild.value))

const form = ref(createDefaultForm())
const stepFile = ref<File | null>(null)
const drawingFile = ref<File | null>(null)

// ComponentSpec state
const componentSpec = ref<Api.ComponentBuild.ComponentSpecDocument | null>(null)
const editorState = ref<ComponentSpecEditorState | null>(null)
const specLoading = ref(false)
const specSaving = ref(false)
const specDirty = ref(false)
const specOffline = ref(false)
const specPreviewing = ref(false)
const systemYaml = ref('')
const specParseError = ref<string | null>(null)
const yamlPreviewRef = ref<InstanceType<typeof ComponentYamlPreview> | null>(null)

const currentYaml = computed(() => editorState.value?.working.yaml || '')
const currentYamlFilename = computed(() => editorState.value?.working.sourceFilename || null)
const currentSpecFields = computed(() => editorState.value?.working.fields || [])
const currentSpecData = computed(() => editorState.value?.working.data || {})
const baselineYaml = computed(() => editorState.value?.systemYaml || systemYaml.value)

// Build status
const buildStatuses = ref<Record<string, Api.ComponentBuild.BuildStatus>>({})

const formRules: FormRules = {
  category_code: [{ required: true, message: '请选择大类', trigger: 'change' }],
  part_type_code: [{ required: true, message: '请选择部件类型', trigger: 'change' }],
  component_name: [{ required: true, message: '请输入图元名称', trigger: 'blur' }],
}

const selectedCategory = computed(
  () => props.catalog.find(item => item.category_code === form.value.category_code) || null
)
const availablePartTypes = computed(() => selectedCategory.value?.parts || [])
const selectedPartType = computed(
  () => availablePartTypes.value.find(item => item.part_type_code === form.value.part_type_code) || null
)
const selectedCatalogPath = computed(() => {
  const labels = [selectedCategory.value?.label, selectedPartType.value?.label].filter(Boolean)
  return labels.length ? `/${labels.join('/')}` : '请先选择大类和部件类型'
})
const generatedIdPreview = computed(() =>
  editingBuild.value
    ? editingBuild.value.component_id
    : selectedPartType.value
      ? `${selectedPartType.value.id_prefix}-###（系统自动递增）`
      : '选择部件类型后自动生成'
)

// Source status
const canStartParsing = computed(() => (role: Api.ComponentBuild.RetryRole) => {
  if (!editingBuild.value) return false
  return role === 'reference_step'
    ? Boolean(editingBuild.value.cad_revision_id)
    : Boolean(editingBuild.value.drawing_task_id)
})

const sourceParsing = ref(false)

const currentBuildId = computed(() => editingBuild.value?.id || '')

const stepStatus = computed(() => buildStatuses.value[currentBuildId.value]?.sources.reference_step.status || 'missing')
const drawingStatus = computed(() => buildStatuses.value[currentBuildId.value]?.sources.drawing.status || 'missing')

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    uploading: '上传中',
    parsing_sources: '解析中',
    source_failed: '来源失败',
    sources_ready: '来源就绪',
    sources_partial: '部分来源就绪',
    aligning: '字段对齐中',
    review_required: '待人工处理',
    yaml_ready: 'YAML 就绪',
    saved: '已保存',
    released: '已发布',
    completed: '解析完成',
    ready: '可开始',
    review_ready: '待审核',
    failed: '解析失败',
    waiting_for_step: '等待 STEP',
    missing: '未上传',
    pending: '等待处理',
    future: '后续能力'
  }
  return labels[status] || status
}

function statusType(status: string): 'success' | 'primary' | 'warning' | 'danger' | 'info' {
  if (['released', 'saved', 'completed', 'yaml_ready'].includes(status)) return 'success'
  if (['parsing_sources', 'uploading', 'aligning', 'sources_ready'].includes(status)) return 'primary'
  if (['review_required', 'sources_partial'].includes(status)) return 'warning'
  if (['source_failed', 'failed'].includes(status)) return 'danger'
  return 'info'
}

// ── Methods ──

function createDefaultForm(): Omit<Api.ComponentBuild.CreatePayload, 'step_file' | 'drawing_file'> {
  return {
    category_code: '',
    part_type_code: '',
    component_name: '',
    standard_number: '',
    version: '1.0.0'
  }
}

async function open(build: Api.ComponentBuild.BuildDetail | null, statuses: Record<string, Api.ComponentBuild.BuildStatus>, spec: Api.ComponentBuild.ComponentSpecDocument | null, yaml: string) {
  const nextBuildId = build?.id || null
  if (visible.value && currentBuildId.value === nextBuildId) return false
  if (!(await confirmDiscardChanges(nextBuildId))) return false
  editingBuild.value = build
  buildStatuses.value = statuses
  componentSpec.value = null
  editorState.value = null
  systemYaml.value = yaml
  specLoading.value = Boolean(build && !spec)
  specSaving.value = false
  specDirty.value = false
  specOffline.value = false
  specPreviewing.value = false
  specParseError.value = null
  form.value = {
    category_code: build?.family || '',
    part_type_code: build?.component_type || '',
    component_name: build?.component_name || '',
    standard_number: build?.standard_number || '',
    version: build?.version || '1.0.0'
  }
  stepFile.value = null
  drawingFile.value = null
  activeTab.value = 'basic'
  visible.value = true
  if (build && spec) setComponentSpec(build.id, spec)
  await nextTick()
  formRef.value?.clearValidate()
  return true
}

async function close() {
  if (!(await confirmDiscardChanges(null))) return false
  visible.value = false
  editingBuild.value = null
  return true
}

async function confirmDiscardChanges(nextBuildId: string | null) {
  if (!requiresComponentSpecDiscardConfirmation(
    specDirty.value,
    currentBuildId.value || null,
    nextBuildId
  )) {
    return true
  }
  try {
    await ElMessageBox.confirm(
      nextBuildId ? '当前 YAML 有未保存修改，切换图元会丢失这些修改。是否继续？' : '当前 YAML 有未保存修改，关闭后会丢失。是否继续？',
      '未保存的 ComponentSpec',
      {
        type: 'warning',
        confirmButtonText: '放弃修改',
        cancelButtonText: '继续编辑'
      }
    )
    return true
  } catch {
    return false
  }
}

async function handleBeforeClose(done: () => void) {
  if (await confirmDiscardChanges(null)) done()
}

function setSourceParsing(value: boolean) {
  sourceParsing.value = value
}

function updateBuildStatuses(statuses: Record<string, Api.ComponentBuild.BuildStatus>) {
  buildStatuses.value = statuses
}

function setComponentSpec(
  buildId: string,
  spec: Api.ComponentBuild.ComponentSpecDocument,
  offline = false
) {
  if (currentBuildId.value !== buildId) return
  try {
    const nextState = createComponentSpecEditorState(spec, {
      generatedYaml: systemYaml.value || undefined
    })
    componentSpec.value = spec
    editorState.value = nextState
    systemYaml.value = nextState.systemYaml
    specOffline.value = offline
    specDirty.value = false
    specParseError.value = null
  } catch (error) {
    specParseError.value = formatYamlError(error)
    editorState.value = null
  }
}

function setSystemYaml(buildId: string, yaml: string) {
  if (currentBuildId.value !== buildId) return
  try {
    createYamlWorkingDocument(yaml, {
      templateSections: editorState.value?.working.templateSections || []
    })
  } catch {
    return
  }
  systemYaml.value = yaml
  if (editorState.value) {
    editorState.value = {
      ...editorState.value,
      systemYaml: yaml
    }
  }
}

function setSpecLoading(buildId: string, value: boolean) {
  if (currentBuildId.value !== buildId) return
  specLoading.value = value
}

function setSpecSaving(buildId: string, value: boolean) {
  if (currentBuildId.value !== buildId) return
  specSaving.value = value
}

function setSpecPreviewing(buildId: string, value: boolean) {
  if (currentBuildId.value !== buildId) return
  specPreviewing.value = value
}

function handleSpecFieldChange(path: ComponentSpecFieldPath, value: unknown) {
  if (!editorState.value) return
  editorState.value = applyComponentSpecFieldEdit(editorState.value, path, value)
  specDirty.value = true
  specParseError.value = null
  yamlPreviewRef.value?.showCurrent()
}

function handleSaveSpec() {
  if (!currentBuildId.value || !editorState.value) return
  emit('saveSpec', currentBuildId.value, createComponentSpecSavePayload(editorState.value))
}

function handleFusion() {
  if (!currentBuildId.value || !editorState.value) return
  emit(
    'fusion',
    currentBuildId.value,
    componentSpecPayloadForFusion(editorState.value, specDirty.value)
  )
}

function handlePreviewSpec() {
  activeTab.value = 'yaml'
  nextTick(() => yamlPreviewRef.value?.showCurrent())
}

function handleUploadYaml(filename: string, content: string) {
  if (!editorState.value) return
  try {
    editorState.value = importComponentSpecYaml(editorState.value, content, filename)
    specDirty.value = true
    specParseError.value = null
    window.$message?.success(`已加载 ${filename}，字段与预览已同步更新`)
  } catch (error) {
    specParseError.value = formatYamlError(error)
    window.$message?.error(specParseError.value)
  }
}

async function handleRestoreSystem() {
  if (!componentSpec.value || !editorState.value) return
  if (editorState.value.working.yaml === editorState.value.systemYaml) return
  try {
    await ElMessageBox.confirm(
      '这会替换当前未保存的字段和 YAML，是否继续？',
      '恢复系统生成',
      {
        type: 'warning',
        confirmButtonText: '恢复',
        cancelButtonText: '取消'
      }
    )
    editorState.value = createComponentSpecEditorState({
      ...componentSpec.value,
      yaml: editorState.value.systemYaml,
      source_filename: null
    })
    specDirty.value = true
    specParseError.value = null
    yamlPreviewRef.value?.showCurrent()
  } catch {
    // The user cancelled the destructive replacement.
  }
}

function formatYamlError(error: unknown) {
  if (error instanceof YamlWorkingDocumentError) {
    const location = error.line && error.column ? `第 ${error.line} 行，第 ${error.column} 列：` : ''
    return `${location}${error.message}`
  }
  return error instanceof Error ? error.message : 'YAML 解析失败'
}

function handleCategoryChange() {
  form.value.part_type_code = ''
  nextTick(() => formRef.value?.clearValidate('part_type_code'))
}

function pickFile(role: 'step' | 'drawing', event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null
  if (!file) return
  const valid = role === 'step' ? /\.(step|stp)$/i.test(file.name) : /\.(png|jpe?g|webp)$/i.test(file.name)
  if (!valid) {
    window.$message?.error(role === 'step' ? '请选择 STEP 或 STP 文件' : '请选择 PNG、JPG、JPEG 或 WEBP 图纸')
    ;(event.target as HTMLInputElement).value = ''
    return
  }
  if (role === 'step') stepFile.value = file
  else drawingFile.value = file
}

function handleSubmit() {
  emit('submit', {
    form: { ...form.value },
    editingBuild: editingBuild.value,
    stepFile: stepFile.value,
    drawingFile: drawingFile.value
  })
}

function handleViewCad() {
  if (!editingBuild.value?.cad_revision_id) return
  router.push({
    path: '/cad-model',
    query: {
      revision_id: editingBuild.value.cad_revision_id,
      build_id: editingBuild.value.id
    }
  })
}

function handleViewDrawing() {
  if (!editingBuild.value?.drawing_task_id) return
  router.push({
    path: '/cad-spec',
    query: {
      revision_id: editingBuild.value.cad_revision_id,
      task_id: editingBuild.value.drawing_task_id,
      build_id: editingBuild.value.id
    }
  })
}

function handleStartParsing(role: Api.ComponentBuild.RetryRole) {
  if (!currentBuildId.value) return
  sourceParsing.value = true
  emit('startParsing', currentBuildId.value, role)
}

watch(visible, (val) => {
  if (!val) {
    editingBuild.value = null
    componentSpec.value = null
    editorState.value = null
    systemYaml.value = ''
    specLoading.value = false
    specSaving.value = false
    specDirty.value = false
    specOffline.value = false
    specPreviewing.value = false
    specParseError.value = null
  }
})
</script>

<template>
  <ElDialog
    v-model="visible"
    :before-close="handleBeforeClose"
    :title="`编辑图元 · ${editingBuild?.component_id || '新建'}`"
    :width="720"
    :close-on-click-modal="false"
    :destroy-on-close="true"
    class="library-dialog"
  >
    <!-- Tabs -->
    <ElTabs v-model="activeTab" class="dialog-tabs">
      <!-- Tab 1: 基础信息 -->
      <ElTabPane label="基础信息" name="basic">
        <ElForm
          ref="formRef"
          v-loading="catalogLoading"
          :model="form"
          :rules="formRules"
          label-position="top"
          class="basic-form"
        >
          <div class="form-grid-2">
            <ElFormItem label="图元编码">
              <ElInput :model-value="editingBuild?.component_id || generatedIdPreview" readonly />
            </ElFormItem>
            <ElFormItem label="图元名称" prop="component_name">
              <ElInput v-model="form.component_name" placeholder="例如 带颈对焊法兰" />
            </ElFormItem>
          </div>
          <div class="form-grid-2">
            <ElFormItem label="所属目录">
              <ElInput :model-value="selectedCatalogPath" readonly />
            </ElFormItem>
            <ElFormItem label="执行标准">
              <ElInput v-model="form.standard_number" placeholder="可选" />
            </ElFormItem>
          </div>
          <div class="form-grid-2">
            <ElFormItem label="大类" prop="category_code">
              <ElSelect
                v-model="form.category_code"
                filterable
                placeholder="请选择大类"
                @change="handleCategoryChange"
              >
                <ElOption
                  v-for="category in catalog"
                  :key="category.category_code"
                  :label="`${category.label} · ${category.label_en}`"
                  :value="category.category_code"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="部件类型" prop="part_type_code">
              <ElSelect
                v-model="form.part_type_code"
                filterable
                :disabled="!form.category_code"
                placeholder="请先选择大类"
              >
                <ElOption
                  v-for="part in availablePartTypes"
                  :key="part.part_type_code"
                  :label="`${part.label} · ${part.label_en}`"
                  :value="part.part_type_code"
                />
              </ElSelect>
            </ElFormItem>
          </div>
          <div class="form-grid-2">
            <ElFormItem label="版本">
              <ElInput v-model="form.version" />
            </ElFormItem>
            <ElFormItem label="&nbsp;" />
          </div>

          <ElDivider />

          <div class="upload-fields">
            <div class="upload-field">
              <span class="upload-label">参考 STEP <small>可稍后补充</small></span>
              <label class="file-input">
                <input accept=".step,.stp" type="file" @change="pickFile('step', $event)" />
                <span>
                  {{
                    stepFile?.name ||
                    (editingBuild?.cad_revision_id ? '已有关联 STEP；选择新文件可替换' : '选择 STEP / STP 文件')
                  }}
                </span>
              </label>
            </div>
            <div class="upload-field">
              <span class="upload-label">二维参数图 <small>可稍后补充</small></span>
              <label class="file-input">
                <input accept=".png,.jpg,.jpeg,.webp" type="file" @change="pickFile('drawing', $event)" />
                <span>
                  {{
                    drawingFile?.name ||
                    (editingBuild?.drawing_task_id ? '已有关联图纸；选择新文件可替换' : '选择 PNG、JPG、JPEG 或 WEBP 图纸')
                  }}
                </span>
              </label>
            </div>
          </div>
        </ElForm>
      </ElTabPane>

      <!-- Tab 2: 关联数据 -->
      <ElTabPane label="关联数据" name="related" :disabled="!currentBuildId">
        <template v-if="currentBuildId">
          <div class="status-cards">
            <!-- STEP card -->
            <div class="status-card">
              <div class="status-card-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
                <span>STEP 三维模型</span>
              </div>
              <div class="status-card-body">
                <div class="status-row">
                  <span>关联状态</span>
                  <el-tag v-if="editingBuild?.cad_revision_id" size="small" type="success">已关联</el-tag>
                  <el-tag v-else size="small" type="info">未关联</el-tag>
                </div>
                <div v-if="editingBuild?.cad_revision_id" class="status-row">
                  <span>解析状态</span>
                  <el-tag :type="statusType(stepStatus)" size="small">{{ statusLabel(stepStatus) }}</el-tag>
                </div>
                <div v-if="editingBuild?.cad_revision_id" class="status-row">
                  <span>Revision ID</span>
                  <code class="mono">{{ editingBuild.cad_revision_id }}</code>
                </div>
              </div>
              <div class="status-card-actions">
                <ElButton v-if="editingBuild?.cad_revision_id" size="small" @click="handleViewCad">
                  查看三维模型
                </ElButton>
                <ElButton
                  v-if="editingBuild?.cad_revision_id"
                  size="small"
                  :loading="sourceParsing"
                  :disabled="!canStartParsing('reference_step')"
                  @click="handleStartParsing('reference_step')"
                >
                  开始解析
                </ElButton>
              </div>
            </div>

            <!-- Drawing card -->
            <div class="status-card">
              <div class="status-card-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                <span>二维图纸</span>
              </div>
              <div class="status-card-body">
                <div class="status-row">
                  <span>关联状态</span>
                  <el-tag v-if="editingBuild?.drawing_task_id" size="small" type="success">已关联</el-tag>
                  <el-tag v-else size="small" type="info">未关联</el-tag>
                </div>
                <div v-if="editingBuild?.drawing_task_id" class="status-row">
                  <span>解析状态</span>
                  <el-tag :type="statusType(drawingStatus)" size="small">{{ statusLabel(drawingStatus) }}</el-tag>
                </div>
                <div v-if="editingBuild?.drawing_task_id" class="status-row">
                  <span>Task ID</span>
                  <code class="mono">{{ editingBuild.drawing_task_id }}</code>
                </div>
              </div>
              <div class="status-card-actions">
                <ElButton v-if="editingBuild?.drawing_task_id" size="small" @click="handleViewDrawing">
                  查看解析结果
                </ElButton>
                <ElButton
                  v-if="editingBuild?.drawing_task_id"
                  size="small"
                  :loading="sourceParsing"
                  :disabled="!canStartParsing('drawing')"
                  @click="handleStartParsing('drawing')"
                >
                  开始解析
                </ElButton>
              </div>
            </div>

            <!-- ComponentSpec/YAML card -->
            <div class="status-card">
              <div class="status-card-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                <span>ComponentSpec / YAML</span>
              </div>
              <div class="status-card-body">
                <div class="status-row">
                  <span>生成状态</span>
                  <el-tag v-if="componentSpec?.saved" size="small" type="success">已保存</el-tag>
                  <el-tag v-else size="small" type="info">待生成</el-tag>
                </div>
                <div class="status-row" v-if="baselineYaml">
                  <span>YAML</span>
                  <el-tag size="small" type="success">已生成</el-tag>
                </div>
              </div>
              <div class="status-card-actions">
                <ElButton size="small" @click="handleFusion">
                  数据融合
                </ElButton>
                <ElButton
                  size="small"
                  :loading="specSaving"
                  :disabled="specLoading || !editorState"
                  @click="handleSaveSpec"
                >
                  保存 ComponentSpec
                </ElButton>
                <ElButton
                  size="small"
                  :loading="specPreviewing"
                  :disabled="specLoading || !editorState"
                  @click="handlePreviewSpec"
                >
                  预览 YAML
                </ElButton>
              </div>
            </div>
          </div>
        </template>
        <ElEmpty v-else description="请先保存图元基本信息" :image-size="42" />
      </ElTabPane>

      <!-- Tab 3: YAML / ComponentSpec -->
      <ElTabPane label="YAML / ComponentSpec" name="yaml" :disabled="!currentBuildId">
        <template v-if="currentBuildId">
          <div class="yaml-layout">
            <div class="yaml-editor-section">
              <div class="section-title">
                <span>ComponentSpec 字段编辑</span>
                <div class="section-actions">
                  <ElButton
                    size="small"
                    :loading="specSaving"
                    :disabled="specLoading || !editorState || (!specDirty && componentSpec?.saved)"
                    @click="handleSaveSpec"
                  >
                    <template #icon>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                    </template>
                    保存草稿
                  </ElButton>
                </div>
              </div>
              <div v-loading="specLoading" class="spec-fields-scroll">
                <ElAlert
                  v-if="componentSpec && specOffline"
                  title="后端 ComponentSpec 暂不可用，当前已加载浏览器中的本地草稿或内置模板。"
                  type="warning"
                  :closable="false"
                  show-icon
                  style="margin-bottom: 10px;"
                />
                <ComponentSpecFieldEditor
                  v-for="field in currentSpecFields"
                  :key="field.path"
                  :field="field"
                  :model-value="currentSpecData[field.key]"
                  :path="[field.key]"
                  @field-change="handleSpecFieldChange"
                />
                <ElEmpty
                  v-if="!editorState && !specLoading"
                  description="ComponentSpec 加载失败"
                  :image-size="42"
                />
              </div>
            </div>
            <div class="yaml-preview-section">
              <div class="section-title">
                <span>YAML 预览</span>
              </div>
              <ComponentYamlPreview
                ref="yamlPreviewRef"
                :build-id="currentBuildId"
                :system-yaml="baselineYaml"
                :current-yaml="currentYaml"
                :current-filename="currentYamlFilename"
                :loading="specPreviewing"
                :parse-error="specParseError"
                loading-label="生成 YAML 预览…"
                @restore-system="handleRestoreSystem"
                @upload-yaml="handleUploadYaml"
              />
            </div>
          </div>
        </template>
        <ElEmpty v-else description="请先保存图元基本信息" :image-size="42" />
      </ElTabPane>
    </ElTabs>

    <!-- Footer -->
    <template #footer>
      <ElButton @click="close">取消</ElButton>
      <ElButton
        type="primary"
        :loading="submitting"
        :disabled="catalogLoading || !catalog.length"
        @click="handleSubmit"
      >
        {{ isEditing ? '保存修改' : '创建图元' }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<script lang="ts">
export default { name: 'ComponentLibraryDialog' }
</script>

<style scoped>
.library-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
  max-height: 68vh;
  overflow: hidden;
}

.library-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 16px 24px 8px;
  border-bottom: 1px solid #e5eaf2;
}

.library-dialog :deep(.el-dialog__body) {
  padding: 12px 24px;
}

.dialog-tabs :deep(.el-tabs__content) {
  max-height: 52vh;
  overflow-y: auto;
  padding: 4px 0;
}

.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.basic-form {
  max-width: 100%;
}

.upload-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upload-label {
  font-size: 13px;
  color: #1a2332;
  display: flex;
  align-items: center;
  gap: 6px;
}

.upload-label small {
  color: #8e99aa;
  font-size: 12px;
}

.file-input {
  display: block;
  position: relative;
  overflow: hidden;
  border: 1px dashed #d0d5dd;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #5a6a7e;
  cursor: pointer;
  background: #f7f9fc;
}

.file-input:hover {
  border-color: #6c5ce7;
}

.file-input input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-input span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cards {
  display: grid;
  gap: 14px;
}

.status-card {
  border: 1px solid #e5eaf2;
  border-radius: 10px;
  padding: 14px;
}

.status-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1a2332;
  margin-bottom: 10px;
}

.status-card-header svg {
  color: #6c5ce7;
}

.status-card-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #5a6a7e;
}

.status-row code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: #6c5ce7;
}

.status-card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.yaml-layout {
  display: grid;
  grid-template-columns: 55% 1fr;
  gap: 16px;
  min-height: 300px;
}

.yaml-editor-section,
.yaml-preview-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #5a6a7e;
}

.section-actions {
  display: flex;
  gap: 4px;
}

.spec-fields-scroll {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  padding: 12px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

@media (max-width: 760px) {
  .form-grid-2,
  .upload-fields {
    grid-template-columns: 1fr;
  }

  .yaml-layout {
    grid-template-columns: 1fr;
  }
}
</style>
