<template>
  <div class="notfound-wrap">
    <div class="notfound-code">404</div>
    <svg class="notfound-route" viewBox="0 0 120 36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M2,30 C20,30 24,10 40,10 C56,10 58,26 74,26 C90,26 88,6 106,6" stroke="#F85C1E" stroke-width="2.5" stroke-linecap="round" fill="none"/>
      <circle cx="106" cy="6" r="4" fill="#F85C1E"/>
    </svg>
    <h1 class="notfound-title">{{ t('notFound.title') }}</h1>
    <p class="notfound-desc">{{ t('notFound.desc') }}</p>
    <div class="notfound-actions">
      <router-link to="/" class="btn btn-primary"><i class="fas fa-home"></i> {{ t('notFound.home') }}</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<style scoped>
.notfound-wrap {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 80vh; padding: 24px; text-align: center;
}
.notfound-code {
  font-size: clamp(4.5rem, 15vw, 8rem); font-weight: 800; color: var(--brand);
  opacity: 0.14; line-height: 1; letter-spacing: -0.04em; user-select: none;
}
.notfound-route { width: 110px; height: 34px; margin: -1.2rem 0 16px; opacity: 0.8; }
.notfound-title {
  font-size: clamp(1.3rem, 3vw, 1.6rem); font-weight: 800; letter-spacing: -0.02em;
  margin-bottom: 10px; max-width: 460px;
}
.notfound-desc { color: var(--text-2); max-width: 380px; margin-bottom: 28px; line-height: 1.6; }
</style>
