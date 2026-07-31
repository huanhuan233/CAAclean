<script setup lang="ts">
import { computed } from 'vue';
import {
  appendFieldPath,
  parseScalarArrayInput,
  type ComponentSpecFieldPath
} from '../component-spec-field-events';

defineOptions({ name: 'ComponentSpecFieldEditor' });

const props = defineProps<{
  field: Api.ComponentBuild.ComponentSpecField;
  modelValue: any;
  path?: ComponentSpecFieldPath;
}>();

const emit = defineEmits<{
  (event: 'update:modelValue', value: any): void;
  (event: 'field-change', path: ComponentSpecFieldPath, value: any): void;
}>();

const currentPath = computed<ComponentSpecFieldPath>(() => props.path || [props.field.key]);
const objectValue = computed<Record<string, any>>(() =>
  props.modelValue && typeof props.modelValue === 'object' && !Array.isArray(props.modelValue)
    ? props.modelValue
    : {}
);
const arrayValue = computed<any[]>(() => (Array.isArray(props.modelValue) ? props.modelValue : []));
const scalarArrayText = computed(() => arrayValue.value.join(', '));
const genericText = computed(() => JSON.stringify(props.modelValue, null, 2));

function blankValue(field: Api.ComponentBuild.ComponentSpecField): any {
  if (field.read_only) return field.fixed_value ?? null;
  if (field.kind === 'object') {
    return Object.fromEntries((field.children || []).map(child => [child.key, blankValue(child)]));
  }
  if (field.kind === 'object_array') {
    return [Object.fromEntries((field.item?.children || []).map(child => [child.key, blankValue(child)]))];
  }
  if (field.kind === 'scalar_array') return [];
  return null;
}

function updateObjectField(key: string, value: any) {
  emit('update:modelValue', { ...objectValue.value, [key]: value });
}

function updateArrayItem(index: number, value: any) {
  const next = [...arrayValue.value];
  next[index] = value;
  emit('update:modelValue', next);
}

function addArrayItem() {
  const children = props.field.item?.children || [];
  const item = Object.fromEntries(children.map(child => [child.key, blankValue(child)]));
  emitValue([...arrayValue.value, item]);
}

function removeArrayItem(index: number) {
  emitValue(arrayValue.value.filter((_, itemIndex) => itemIndex !== index));
}

function updateScalarArray(value: string) {
  try {
    emitValue(parseScalarArrayInput(value, props.field.value_type));
  } catch (error) {
    window.$message?.warning(error instanceof Error ? error.message : '数组格式无效');
  }
}

function emitValue(value: any) {
  emit('update:modelValue', value);
  emit('field-change', currentPath.value, value);
}

function bubbleFieldChange(path: ComponentSpecFieldPath, value: any) {
  emit('field-change', path, value);
}

function updateGeneric(value: string) {
  try {
    emitValue(JSON.parse(value));
  } catch {
    window.$message?.warning('请输入有效的 JSON；当前字段尚未修改');
  }
}
</script>

<template>
  <div v-if="field.kind === 'object'" class="spec-object">
    <div class="group-heading">
      <div>
        <strong>{{ field.label }}</strong>
        <small>{{ field.path }}</small>
      </div>
    </div>
    <div class="field-grid">
      <ComponentSpecFieldEditor
        v-for="child in field.children || []"
        :key="child.path"
        :field="child"
        :model-value="objectValue[child.key]"
        :path="appendFieldPath(currentPath, child.key)"
        @field-change="bubbleFieldChange"
        @update:model-value="updateObjectField(child.key, $event)"
      />
    </div>
  </div>

  <div v-else-if="field.kind === 'object_array'" class="spec-array">
    <div class="group-heading">
      <div>
        <strong>{{ field.label }}</strong>
        <small>{{ field.path }}</small>
      </div>
      <ElButton size="small" @click="addArrayItem">
        <template #icon><icon-carbon-add /></template>
        新增
      </ElButton>
    </div>
    <ElEmpty v-if="!arrayValue.length" description="暂无记录" :image-size="42" />
    <div v-for="(item, index) in arrayValue" :key="index" class="array-item">
      <div class="array-item-heading">
        <span>第 {{ index + 1 }} 项</span>
        <ElTooltip content="删除本项" placement="top">
          <ElButton text type="danger" circle @click="removeArrayItem(index)">
            <template #icon><icon-carbon-trash-can /></template>
          </ElButton>
        </ElTooltip>
      </div>
      <div class="field-grid">
        <ComponentSpecFieldEditor
          v-for="child in field.item?.children || []"
          :key="`${index}:${child.path}`"
          :field="child"
          :model-value="item?.[child.key]"
          :path="appendFieldPath(currentPath, index, child.key)"
          @field-change="bubbleFieldChange"
          @update:model-value="updateArrayItem(index, { ...item, [child.key]: $event })"
        />
      </div>
    </div>
  </div>

  <label v-else class="spec-field" :class="{ wide: field.kind === 'scalar_array' }">
    <span class="field-label">
      {{ field.label }}
      <b v-if="field.required">*</b>
      <ElTag v-if="field.read_only" size="small" type="info" effect="plain">系统固定</ElTag>
    </span>
    <small class="field-path">{{ field.path }}</small>

    <ElSelect
      v-if="field.kind === 'boolean'"
      :model-value="modelValue"
      clearable
      :disabled="field.read_only"
      placeholder="请选择"
      @update:model-value="emitValue"
    >
      <ElOption label="是" :value="true" />
      <ElOption label="否" :value="false" />
    </ElSelect>
    <ElInputNumber
      v-else-if="field.kind === 'number'"
      :model-value="modelValue"
      :disabled="field.read_only"
      controls-position="right"
      @update:model-value="emitValue"
    />
    <ElInput
      v-else-if="field.kind === 'scalar_array'"
      :model-value="scalarArrayText"
      :disabled="field.read_only"
      placeholder="多个值请用逗号分隔"
      @update:model-value="updateScalarArray"
    />
    <ElInput
      v-else-if="field.kind === 'generic'"
      :model-value="genericText"
      :readonly="field.read_only"
      :rows="6"
      type="textarea"
      @change="updateGeneric"
    />
    <ElInput
      v-else
      :model-value="modelValue ?? ''"
      :readonly="field.read_only"
      clearable
      placeholder="请输入"
      @update:model-value="emitValue($event || null)"
    />
    <small v-if="field.source && !field.read_only" class="field-source">来源：{{ field.source }}</small>
  </label>
</template>

<style scoped>
.spec-object, .spec-array { min-width: 0; grid-column: 1 / -1; }
.group-heading, .array-item-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.group-heading { margin-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 9px; }
.group-heading strong { display: block; font-size: 14px; font-weight: 600; }
.group-heading small { display: block; margin-top: 2px; color: var(--el-text-color-secondary); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }
.field-grid { display: grid; min-width: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
.array-item { margin-top: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; padding: 12px; }
.array-item-heading { margin-bottom: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.spec-field { display: flex; min-width: 0; flex-direction: column; gap: 5px; }
.spec-field.wide { grid-column: 1 / -1; }
.field-label { display: flex; min-height: 22px; align-items: center; gap: 6px; color: var(--el-text-color-primary); font-size: 13px; }
.field-label b { color: var(--el-color-danger); font-weight: 500; }
.field-path, .field-source { overflow: hidden; color: var(--el-text-color-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.field-path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.spec-field :deep(.el-input-number), .spec-field :deep(.el-select) { width: 100%; }
@media (max-width: 900px) { .field-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
