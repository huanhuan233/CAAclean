<script setup lang="ts">
export type ToolMode = 'select' | 'orbit' | 'pan';
export type SceneMode = 'whole' | 'explode' | 'transparent' | 'section';

defineOptions({ name: 'CadViewerControls' });

const props = defineProps<{
  toolMode: ToolMode;
  sceneMode: SceneMode;
  transparent: boolean;
  isolated: boolean;
  sectionEnabled: boolean;
  canExplode: boolean;
  canIsolate: boolean;
}>();

const emit = defineEmits<{
  toolChange: [mode: ToolMode];
  sceneModeChange: [mode: SceneMode];
  transparentChange: [value: boolean];
  isolatedChange: [value: boolean];
  sectionChange: [value: boolean];
  command: [command: 'fit' | 'open-layers'];
}>();

const tools = [
  { key: 'select', label: '选择', icon: 'lucide:mouse-pointer-2' },
  { key: 'orbit', label: '旋转', icon: 'lucide:rotate-3d' },
  { key: 'pan', label: '平移', icon: 'lucide:hand' }
] as const;

const sceneModes = [
  { key: 'whole', label: '整体' },
  { key: 'explode', label: '爆炸' },
  { key: 'transparent', label: '透明' },
  { key: 'section', label: '剖切' }
] as const;

// 用途：把模式按钮转换成单一的父级 Viewer 状态，组件自身不保存第二份控制状态。
function chooseSceneMode(mode: SceneMode) {
  if (mode === 'explode' && !props.canExplode) return;
  emit('sceneModeChange', props.sceneMode === mode && mode !== 'whole' ? 'whole' : mode);
}

</script>

<template>
  <div class="cad-control-layer">
    <section class="cad-primary-toolbar" @pointerdown.stop @pointerup.stop>
      <ElTooltip v-for="tool in tools" :key="tool.key" :content="tool.label" placement="top">
        <button
          type="button"
          class="cad-icon-button"
          :class="{ active: toolMode === tool.key }"
          @click="emit('toolChange', tool.key)"
        >
          <SvgIcon :icon="tool.icon" />
        </button>
      </ElTooltip>
      <ElTooltip content="适合窗口" placement="top">
        <button type="button" class="cad-icon-button" @click="emit('command', 'fit')">
          <SvgIcon icon="lucide:scan" />
        </button>
      </ElTooltip>
      <ElTooltip :content="canExplode ? '爆炸视图' : '单零件没有可分离的装配实例'" placement="top">
        <button
          type="button"
          class="cad-icon-button"
          :disabled="!canExplode"
          :class="{ active: sceneMode === 'explode' }"
          @click="chooseSceneMode('explode')"
        >
          <SvgIcon icon="lucide:move-3d" />
        </button>
      </ElTooltip>
      <ElTooltip :content="canIsolate ? '隔离所选对象' : '请先选择零件、特征或面'" placement="top">
        <button
          type="button"
          class="cad-icon-button"
          :disabled="!canIsolate"
          :class="{ active: isolated }"
          @click="emit('isolatedChange', !isolated)"
        >
          <SvgIcon icon="lucide:focus" />
        </button>
      </ElTooltip>
      <ElTooltip content="图层与可见性" placement="top">
        <button type="button" class="cad-icon-button" @click="emit('command', 'open-layers')">
          <SvgIcon icon="lucide:layers-3" />
        </button>
      </ElTooltip>
    </section>

    <section class="cad-scene-panel" @pointerdown.stop @pointerup.stop>
      <div class="cad-mode-segment">
        <button
          v-for="mode in sceneModes"
          :key="mode.key"
          type="button"
          :class="{ active: sceneMode === mode.key }"
          :disabled="mode.key === 'explode' && !canExplode"
          @click="chooseSceneMode(mode.key)"
        >
          {{ mode.label }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cad-control-layer {
  position: absolute;
  z-index: 5;
  bottom: 24px;
  left: 50%;
  width: min(500px, calc(100% - 20px));
  transform: translateX(-50%);
  pointer-events: none;
}
.cad-primary-toolbar,
.cad-scene-panel {
  border: 1px solid var(--el-border-color-light);
  background: color-mix(in srgb, var(--el-bg-color) 94%, transparent);
  box-shadow: var(--el-box-shadow-light);
  backdrop-filter: blur(14px);
  pointer-events: auto;
}
.cad-primary-toolbar {
  display: grid;
  grid-template-columns: repeat(7, 52px);
  width: fit-content;
  margin: 0 auto;
  border-radius: 11px;
  padding: 9px 12px;
  column-gap: 4px;
}
.cad-icon-button {
  display: grid;
  width: 48px;
  height: 44px;
  place-items: center;
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 22px;
}
.cad-icon-button.active {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  box-shadow: inset 0 0 0 1px var(--el-color-primary-light-7);
}
.cad-scene-panel {
  width: min(460px, 100%);
  margin: 12px auto 0;
  overflow: hidden;
  border-radius: 10px;
}
.cad-mode-segment {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 10px;
}
.cad-mode-segment button {
  height: 42px;
  border-radius: 0;
  background: transparent;
  padding: 0;
}
.cad-mode-segment button:first-child {
  border-radius: 6px 0 0 6px;
}
.cad-mode-segment button:last-child {
  border-radius: 0 6px 6px 0;
}
.cad-mode-segment button + button {
  margin-left: -1px;
}
@media (max-width: 720px) {
  .cad-primary-toolbar {
    grid-template-columns: repeat(7, 40px);
    padding: 7px 8px;
    column-gap: 2px;
  }
  .cad-icon-button {
    width: 38px;
    height: 40px;
  }
}
</style>
