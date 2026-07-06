<template>
  <div v-if="!ready" class="app-boot-loading" aria-label="Загрузка">
    <i class="fas fa-spinner fa-spin"></i>
  </div>
  <RouterView v-else />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
// Пока роутер не завершит первую навигацию (включая асинхронную проверку
// авторизации в router.beforeEach) — показываем спиннер, а не пустой экран.
// Без этого при медленном /auth/me пользователь видит голый белый экран.
const ready = ref(false)

onMounted(async () => {
  const saved = localStorage.getItem('theme') || 'light'
  document.documentElement.setAttribute('data-theme', saved)
  try {
    await router.isReady()
  } finally {
    // Даже если начальная навигация отклонена — показываем UI, а не вечный спиннер.
    ready.value = true
  }
})
</script>

<style>
.app-boot-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 1.6rem;
  color: var(--brand, #F85C1E);
}
</style>
