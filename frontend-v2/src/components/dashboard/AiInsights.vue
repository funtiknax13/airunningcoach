<template>
  <div class="card ai-insights-card">
    <div class="card-title"><i class="fas fa-brain"></i> {{ $t('ai.title') }}</div>
    <div v-if="!insights?.length" class="insight-item">{{ $t('ai.empty') }}</div>
    <div v-for="(item, i) in insights" :key="i" class="insight-item">
      <i class="fas fa-lightbulb"></i> {{ item }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ insights: string[] | null | undefined }>()
</script>
