<template>
  <div class="bar-chart">
    <div v-if="label" class="bar-chart-label">{{ label }}</div>
    <div class="bar-chart-bars">
      <div v-for="(d, i) in series" :key="i" class="bar-chart-col" :title="`${d.label}: ${d.value}`">
        <div class="bar-chart-bar" :style="{ height: `${(d.value / max) * 100}%`, background: color }"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  series: { label: string; value: number }[]
  color?: string
  label?: string
}>(), {
  color: 'var(--brand)',
  label: '',
})

const max = computed(() => Math.max(1, ...props.series.map(d => d.value)))
</script>

<style scoped>
.bar-chart { margin-bottom: 16px; }
.bar-chart:last-child { margin-bottom: 0; }
.bar-chart-label { font-size: 0.8rem; color: var(--text-2); margin-bottom: 6px; font-weight: 600; }
.bar-chart-bars { display: flex; align-items: flex-end; gap: 2px; height: 90px; }
.bar-chart-col { flex: 1; height: 100%; display: flex; align-items: flex-end; min-width: 2px; }
.bar-chart-bar { width: 100%; border-radius: 2px 2px 0 0; min-height: 1px; }
</style>
