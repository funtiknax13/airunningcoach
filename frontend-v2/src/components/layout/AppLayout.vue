<template>
  <!-- App shell: sidebar + main -->
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <img src="/logo.png" alt="logo">
        <div class="sidebar-logo-brand">
          <div class="sidebar-logo-text">
            <span>AI</span>RunningCoach
          </div>
          <!-- ECG / heartbeat line -->
          <svg class="sidebar-ecg" viewBox="0 0 110 18" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polyline
              points="0,9 14,9 18,9 20,5 22,14 24,2 26,14 28,9 32,9 38,9 40,6 42,9 46,9 60,9 62,7 64,9 68,9 110,9"
              stroke="#F85C1E" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.7"/>
          </svg>
        </div>
      </div>

      <nav class="sidebar-nav">
        <RouterLink v-for="item in navItems" :key="item.to"
          :to="item.to" class="nav-item"
          :class="{ active: route.path === item.to }">
          <span class="nav-icon-wrap">
            <i :class="item.icon"></i>
            <span v-if="item.to === '/coach' && chatStore.hasUnread" class="nav-badge"></span>
          </span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <button class="nav-item" @click="profileModal?.open()">
          <i class="fas fa-user-circle"></i>
          <span>{{ auth.user?.name || t('header.profile') }}</span>
        </button>
        <RouterLink to="/subscription" class="nav-item nav-item--plan" :class="isPremium ? 'nav-item--premium' : 'nav-item--basic'">
          <i class="fas" :class="isPremium ? 'fa-crown' : 'fa-circle-user'"></i>
          <span>{{ isPremium ? 'Premium' : 'Basic' }}</span>
          <span v-if="isPremium && daysLeft !== null" class="plan-days">{{ daysLeft }}д</span>
        </RouterLink>
        <button class="nav-item" @click="themeToggle">
          <i :class="theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon'"></i>
          <span>{{ theme === 'dark' ? t('header.light') : t('header.dark') }}</span>
        </button>
        <button class="nav-item" @click="changeLang">
          <i class="fas fa-globe"></i>
          <span>{{ nextLang }}</span>
        </button>
        <a href="/blog/" class="nav-item" target="_blank" rel="noopener">
          <i class="fas fa-newspaper"></i>
          <span>Блог</span>
        </a>
        <a href="/tools/" class="nav-item" target="_blank" rel="noopener">
          <i class="fas fa-calculator"></i>
          <span>Инструменты</span>
        </a>
        <button class="nav-item" @click="supportModal?.open()">
          <i class="fas fa-life-ring"></i>
          <span>{{ t('support.title') }}</span>
        </button>
        <button class="nav-item logout" @click="logout()">
          <i class="fas fa-sign-out-alt"></i>
          <span>{{ t('header.logout') }}</span>
        </button>
      </div>
    </aside>

    <div class="main-content">
      <header class="page-header">
        <span class="page-header-title">{{ currentTitle }}</span>
        <div class="page-header-actions">
          <slot name="header-actions" />
          <button class="theme-btn" @click="themeToggle"
                  :title="theme === 'dark' ? t('header.light') : t('header.dark')">
            <i :class="theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon'"></i>
          </button>
          <!-- Бутерброд — только на мобиле -->
          <button class="burger-btn" @click="menuOpen = !menuOpen">
            <i class="fas" :class="menuOpen ? 'fa-xmark' : 'fa-bars'"></i>
          </button>
        </div>
      </header>

      <!-- Мобильное выпадающее меню -->
      <Transition name="menu-drop">
        <div v-if="menuOpen" class="mobile-menu" @click.self="menuOpen = false">
          <div class="mobile-menu-inner">
            <button class="mobile-menu-item" @click="profileModal?.open(); menuOpen = false">
              <i class="fas fa-user-circle"></i> {{ auth.user?.name || t('header.profile') }}
            </button>
            <RouterLink to="/subscription" class="mobile-menu-item" @click="menuOpen = false"
              :class="isPremium ? 'nav-item--premium' : 'nav-item--basic'">
              <i class="fas" :class="isPremium ? 'fa-crown' : 'fa-circle-user'"></i>
              {{ isPremium ? 'Premium' : 'Basic' }}
              <span v-if="isPremium && daysLeft !== null" class="plan-days">{{ daysLeft }}д</span>
            </RouterLink>
            <button class="mobile-menu-item" @click="themeToggle; menuOpen = false">
              <i :class="theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon'"></i>
              {{ theme === 'dark' ? t('header.light') : t('header.dark') }}
            </button>
            <button class="mobile-menu-item" @click="changeLang(); menuOpen = false">
              <i class="fas fa-globe"></i> {{ nextLang }}
            </button>
            <a href="/blog/" class="mobile-menu-item" target="_blank" rel="noopener" @click="menuOpen = false">
              <i class="fas fa-newspaper"></i> Блог
            </a>
            <a href="/tools/" class="mobile-menu-item" target="_blank" rel="noopener" @click="menuOpen = false">
              <i class="fas fa-calculator"></i> Инструменты
            </a>
            <button class="mobile-menu-item" @click="supportModal?.open(); menuOpen = false">
              <i class="fas fa-life-ring"></i> {{ t('support.title') }}
            </button>
            <button class="mobile-menu-item logout" @click="logout(); menuOpen = false">
              <i class="fas fa-sign-out-alt"></i> {{ t('header.logout') }}
            </button>
          </div>
        </div>
      </Transition>

      <div class="page-body">
        <slot />
      </div>
    </div>
  </div>

  <!-- ⚠️ Bottom nav is OUTSIDE app-shell to avoid overflow/stacking context bugs -->
  <nav class="bottom-nav">
    <RouterLink v-for="item in navItems" :key="item.to"
      :to="item.to" class="bottom-nav-item"
      :class="{ active: route.path === item.to }">
      <span class="nav-icon-wrap">
        <i :class="item.icon"></i>
        <span v-if="item.to === '/coach' && chatStore.hasUnread" class="nav-badge"></span>
      </span>
      <span>{{ item.label }}</span>
    </RouterLink>
  </nav>

  <ProfileModal ref="profileModal" v-model="showProfile" />
  <SupportModal ref="supportModal" v-model="showSupport" />
  <AppDialog />
  <TrialExpiredBanner />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { toggleLang } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useTheme } from '@/composables/useTheme'
import ProfileModal       from '@/components/profile/ProfileModal.vue'
import SupportModal       from '@/components/support/SupportModal.vue'
import AppDialog          from '@/components/common/AppDialog.vue'
import TrialExpiredBanner from '@/components/common/TrialExpiredBanner.vue'

const { t, locale } = useI18n()
const route     = useRoute()
const auth      = useAuthStore()
const chatStore = useChatStore()
const supportModal = ref<InstanceType<typeof SupportModal> | null>(null)
const showSupport  = ref(false)

const isPremium = computed(() => {
  if (!auth.user?.is_premium) return false
  if (!auth.user.premium_until) return true
  return new Date(auth.user.premium_until) > new Date()
})
const daysLeft = computed(() => {
  const until = auth.user?.premium_until
  if (!until) return null
  return Math.max(0, Math.ceil((new Date(until).getTime() - Date.now()) / 86_400_000))
})
const { theme, toggle: themeToggle } = useTheme()
const profileModal = ref<InstanceType<typeof ProfileModal> | null>(null)
const showProfile  = ref(false)

const nextLang = computed(() => locale.value === 'ru' ? 'EN' : 'RU')
function changeLang() { toggleLang() }
function logout() { auth.logout(); window.location.href = '/' }
const menuOpen = ref(false)

const navItems = computed(() => [
  { to: '/dashboard',    icon: 'fas fa-home',          label: t('nav.dashboard')  },
  { to: '/activities',   icon: 'fas fa-person-running', label: t('nav.activities') },
  { to: '/training',     icon: 'fas fa-calendar-week',  label: t('nav.training')   },
  { to: '/goals',        icon: 'fas fa-bullseye',        label: t('nav.goals')      },
  { to: '/achievements', icon: 'fas fa-trophy',          label: t('nav.achievements') },
  { to: '/coach',        icon: 'fas fa-robot',           label: t('nav.coach')      },
])

const titles: Record<string, string> = {
  '/dashboard':    'nav.dashboard',
  '/activities':   'nav.activities',
  '/training':     'nav.training',
  '/goals':        'nav.goals',
  '/achievements': 'nav.achievements',
  '/coach':        'nav.coach',
}
const currentTitle = computed(() => t(titles[route.path] ?? 'nav.dashboard'))
</script>
