<template>
  <header class="app-header">
    <div class="logo">
      <img src="/images/logo.png" alt="AI PaceMaker" class="logo-wordmark">
    </div>
    <div class="user-info">
      <button class="profile-btn" @click="profileModal?.open()">
        <i class="fas fa-user-circle"></i>
        <span>{{ auth.user?.name }}</span>
      </button>
      <button class="lang-btn" @click="toggleLang()">{{ nextLang }}</button>
      <button class="logout-btn" @click="auth.logout()">
        <i class="fas fa-sign-out-alt"></i>
        {{ $t('header.logout') }}
      </button>
    </div>
  </header>
  <ProfileModal ref="profileModal" v-model="showProfile" />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { toggleLang } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import ProfileModal from '@/components/profile/ProfileModal.vue'

const { locale } = useI18n()
const auth        = useAuthStore()
const profileModal = ref<InstanceType<typeof ProfileModal> | null>(null)
const showProfile  = ref(false)
const nextLang = computed(() => locale.value === 'ru' ? 'EN' : 'RU')
</script>
