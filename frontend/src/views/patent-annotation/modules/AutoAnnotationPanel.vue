<script setup lang="ts">
import { computed, ref } from 'vue';
import type { PatentSource } from '../types';

defineOptions({ name: 'PatentAutoAnnotationPanel' });

const props = defineProps<{
  parseResult: Api.PatentAnnotation.DocumentParseResult | null;
  parsing: boolean;
  localizing: boolean;
  progressText: string;
  activeSource: PatentSource | null;
  activePage: number;
}>();

const emit = defineEmits<{
  (event: 'parse', file: File): void;
  (event: 'uploadFigures'): void;
  (event: 'updateFigure', figureNo: string): void;
  (event: 'localize'): void;
  (event: 'acceptPage'): void;
}>();

const specificationInputRef = ref<HTMLInputElement | null>(null);

const parserLabel = computed(() => {
  if (!props.parseResult) return '等待解析';
  return props.parseResult.parser === 'mineru' ? 'MinerU 解析' : 'pypdf 备用解析';
});
const parserType = computed(() => (props.parseResult?.parser === 'mineru' ? 'success' : 'warning'));
const activeFigure = computed(
  () => props.parseResult?.figures.find(item => item.figure_no === props.activeSource?.figureNo) ?? null
);
const busy = computed(() => props.parsing || props.localizing);
const hasDocumentContext = computed(() => Boolean(props.parseResult?.document_context?.trim()));
const canLocalize = computed(
  () => Boolean(props.parseResult && props.activeSource && activeFigure.value && hasDocumentContext.value) && !busy.value
);
const warnings = computed(() => {
  const items = props.parseResult?.warnings.map(formatWarning) ?? [];
  if (props.parseResult && !props.parseResult.figures.length) {
    items.push('未识别到附图说明，请确认上传的是完整的专利说明书 PDF');
  }
  return [...new Set(items)];
});

function openSpecificationPicker() {
  if (busy.value) return;
  specificationInputRef.value?.click();
}

function onSpecificationSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (file && !busy.value) emit('parse', file);
}

function formatWarning(warning: string) {
  const warningLabels: Record<string, string> = {
    mineru_not_configured: 'MinerU 未配置，已自动使用 pypdf 备用解析',
    mineru_failed: 'MinerU 解析失败，已自动使用 pypdf 备用解析',
    mineru_timeout: 'MinerU 解析超时，已自动使用 pypdf 备用解析',
    patent_document_context_truncated: '说明书较长，已优先保留附图说明、权利要求和图号相关上下文'
  };
  return warningLabels[warning] ?? warning;
}
</script>

<template>
  <section class="auto-panel">
    <input
      ref="specificationInputRef"
      class="hidden-input"
      type="file"
      accept="application/pdf,.pdf"
      @change="onSpecificationSelected"
    />

    <div class="flow-heading">
      <div>
        <div class="flow-title">自动标注流程</div>
        <div class="flow-subtitle">MinerU 解析一次说明书；每张附图分别携带说明书上下文交给视觉模型定位</div>
      </div>
      <div v-if="progressText" class="progress-pill">
        <span class="progress-dot" />
        {{ progressText }}
      </div>
    </div>

    <div class="step-grid">
      <article class="step-card" :class="{ complete: parseResult }">
        <div class="step-number">1</div>
        <div class="step-content">
          <div class="step-title-row">
            <strong>上传专利说明书</strong>
            <ElTag v-if="parseResult" size="small" :type="parserType">{{ parserLabel }}</ElTag>
            <span v-else class="step-state">未完成</span>
          </div>
          <div v-if="parseResult" class="file-summary" :title="parseResult.file_name">
            {{ parseResult.file_name }}
          </div>
          <div v-else class="step-description">选择包含权利要求、具体实施方式和附图说明的文字版 PDF</div>
          <div v-if="parseResult" class="metric-row">
            <span>
              <b>{{ parseResult.components.length }}</b>
              个部件
            </span>
            <span>
              <b>{{ parseResult.figures.length }}</b>
              张附图
            </span>
          </div>
          <ElButton type="primary" plain :disabled="busy" :loading="parsing" @click="openSpecificationPicker">
            {{ parseResult ? '重新解析说明书' : '选择说明书 PDF' }}
          </ElButton>
        </div>
      </article>

      <article class="step-card" :class="{ complete: activeSource }">
        <div class="step-number">2</div>
        <div class="step-content">
          <div class="step-title-row">
            <strong>上传无引线附图</strong>
            <span v-if="!activeSource" class="step-state">未完成</span>
          </div>
          <div v-if="activeSource" class="file-summary" :title="activeSource.fileName">
            {{ activeSource.fileName }}
          </div>
          <div v-else class="step-description">例如资源 527.pdf；可一次选择多张附图</div>
          <div v-if="activeSource" class="mapping-row">
            <span>当前第 {{ activePage }} 页，对应</span>
            <ElSelect
              :model-value="activeSource.figureNo || ''"
              size="small"
              class="figure-select"
              placeholder="选择图号"
              :disabled="!parseResult || busy"
              @change="emit('updateFigure', String($event))"
            >
              <ElOption
                v-for="figure in parseResult?.figures ?? []"
                :key="figure.figure_no"
                :label="`图 ${figure.figure_no}`"
                :value="figure.figure_no"
              />
            </ElSelect>
          </div>
          <ElButton type="primary" plain :disabled="busy" @click="emit('uploadFigures')">
            {{ activeSource ? '继续添加附图' : '选择附图 PDF' }}
          </ElButton>
        </div>
      </article>

      <article class="step-card action-card" :class="{ complete: canLocalize }">
        <div class="step-number">3</div>
        <div class="step-content">
          <div class="step-title-row">
            <strong>自动标注当前图</strong>
            <span class="step-state">{{ hasDocumentContext ? '说明书上下文已就绪' : '等待说明书上下文' }}</span>
          </div>
          <div class="step-description">
            {{
              canLocalize
                ? `模型将识别图 ${activeSource?.figureNo} 中可见部件并生成引线`
                : '完成说明书解析、上传附图并选择图号后即可开始'
            }}
          </div>
          <div class="action-row">
            <ElButton type="primary" :disabled="!canLocalize" :loading="localizing" @click="emit('localize')">
              自动标注当前页
            </ElButton>
            <ElButton :disabled="!activeSource || busy" @click="emit('acceptPage')">接受本页结果</ElButton>
          </div>
        </div>
      </article>
    </div>

    <div v-if="warnings.length" class="warning-list">
      <ElAlert v-for="warning in warnings" :key="warning" type="warning" :closable="false" show-icon :title="warning" />
    </div>

    <div v-if="parseResult" class="result-strip">
      <div v-if="activeFigure" class="figure-description">
        <b>图 {{ activeFigure.figure_no }}</b>
        <span>{{ activeFigure.description || '暂无附图说明' }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.auto-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 12px;
  background: var(--el-bg-color);
}

.hidden-input {
  display: none;
}

.flow-heading,
.step-title-row,
.metric-row,
.mapping-row,
.action-row,
.result-strip,
.figure-description {
  display: flex;
  align-items: center;
}

.flow-heading {
  justify-content: space-between;
  gap: 16px;
}

.flow-title {
  color: var(--el-text-color-primary);
  font-size: 15px;
  font-weight: 700;
}

.flow-subtitle,
.step-description,
.step-state,
.file-summary,
.metric-row,
.mapping-row,
.figure-description {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.flow-subtitle {
  margin-top: 2px;
}

.progress-pill {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  border-radius: 999px;
  padding: 6px 10px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
}

.progress-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 0 4px color-mix(in srgb, currentcolor 16%, transparent);
  animation: pulse 1.2s ease-in-out infinite;
}

.step-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.step-card {
  position: relative;
  display: grid;
  min-width: 0;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 9px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 9px;
  padding: 10px;
  background: var(--el-fill-color-blank);
}

.step-card.complete {
  border-color: var(--el-color-primary-light-7);
  background: color-mix(in srgb, var(--el-color-primary-light-9) 48%, var(--el-bg-color));
}

.step-number {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 50%;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  font-weight: 700;
}

.complete .step-number {
  background: var(--el-color-primary);
  color: #fff;
}

.step-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}

.step-title-row {
  width: 100%;
  justify-content: space-between;
  gap: 8px;
  color: var(--el-text-color-primary);
}

.file-summary {
  width: 100%;
  overflow: hidden;
  color: var(--el-text-color-regular);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-description {
  min-height: 34px;
  line-height: 17px;
}

.metric-row {
  gap: 14px;
}

.metric-row b {
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.mapping-row {
  min-height: 32px;
  gap: 6px;
}

.figure-select {
  width: 104px;
}

.action-row {
  flex-wrap: wrap;
  gap: 7px;
}

.warning-list {
  display: grid;
  gap: 6px;
}

.warning-list :deep(.el-alert) {
  padding-block: 5px;
}

.result-strip {
  min-height: 32px;
  gap: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
}

.figure-description {
  min-width: 0;
  flex: 1;
  gap: 8px;
}

.figure-description span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.55;
  }

  50% {
    opacity: 1;
  }
}

@media (max-width: 1180px) {
  .step-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .flow-heading,
  .result-strip {
    align-items: flex-start;
    flex-direction: column;
  }

}
</style>
