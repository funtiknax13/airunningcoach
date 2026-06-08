<template>
  <RouterView />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

// Apply saved theme on mount
onMounted(() => {
  const saved = localStorage.getItem('theme') || 'light'
  document.documentElement.setAttribute('data-theme', saved)
})
</script>
