<script setup lang="ts">
defineProps<{ rows: Array<{ key: string; label: string; text: string; raw: string; status: string; source: string }>; emptyText: string }>();
</script>

<template>
  <dl v-if="rows.length" class="composite-fields">
    <template v-for="row in rows" :key="row.key">
      <dt>{{ row.label }}</dt><dd :title="`${row.source} · 原始值：${row.raw} · ${row.status}`">{{ row.text }}</dd>
    </template>
  </dl>
  <p v-else class="composite-muted">{{ emptyText }}</p>
</template>
