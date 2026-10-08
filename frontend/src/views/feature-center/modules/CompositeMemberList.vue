<script setup lang="ts">
import type { CompositeMember } from './composite-view-model';

defineProps<{ items: CompositeMember[]; emptyText: string }>();
const emit = defineEmits<{ select: [objectId: string] }>();
</script>

<template>
  <p v-if="!items.length" class="composite-muted">{{ emptyText }}</p>
  <button v-for="item in items" :key="item.objectId" type="button" class="composite-member"
    :aria-label="`查看${item.title} ${item.objectId}`" @click="emit('select', item.objectId)">
    <span v-if="item.index !== null" class="composite-member-index">{{ item.index }}</span>
    <span class="composite-row-icon"><SvgIcon :icon="item.icon" /></span>
    <span class="composite-member-body"><strong>{{ item.title }}</strong>
      <small>{{ item.summary ? `${item.summary} · ` : '' }}{{ item.objectId }}</small></span>
    <SvgIcon icon="mdi:chevron-right" />
  </button>
</template>
