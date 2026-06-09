<template>
  <div class="landing">

    <!-- Nav -->
    <nav class="landing-nav" role="navigation" aria-label="Основная навигация">
      <div class="landing-nav-logo">
        <img src="/images/logo.png" alt="AI RunningCoach — логотип">
        <span><span>AI</span>RunningCoach</span>
      </div>
      <div class="landing-nav-actions">
        <button class="theme-btn" @click="themeToggle">
          <i :class="theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon'"></i>
        </button>
        <button class="btn btn-ghost btn-sm" @click="changeLang">{{ nextLang }}</button>
        <button class="btn btn-ghost btn-sm" @click="showAuth('login')">{{ t('auth.login.btn') }}</button>
        <button class="btn btn-primary btn-sm" @click="showAuth('register')">{{ t('landing.tryFree') }}</button>
      </div>
    </nav>

    <!-- Hero -->
    <section class="hero" aria-label="Главный экран">
      <div class="hero-text">
        <div class="hero-label"><i class="fas fa-robot" aria-hidden="true"></i> {{ t('landing.badge') }}</div>
        <h1 class="hero-title">
          {{ t('landing.heroTitle1') }}<br>
          <em>{{ t('landing.heroTitle2') }}</em><br>
          {{ t('landing.heroTitle3') }}
        </h1>
        <p class="hero-desc">{{ t('landing.heroDesc') }}</p>
        <div class="hero-ctas">
          <button class="btn btn-primary" style="padding:13px 28px;font-size:0.95rem"
                  @click="showAuth('register')">
            <i class="fas fa-rocket"></i> {{ t('landing.startFree') }}
          </button>
          <button class="btn btn-secondary" style="padding:13px 28px;font-size:0.95rem"
                  @click="showAuth('login')">
            {{ t('auth.login.btn') }}
          </button>
        </div>
      </div>

      <!-- Mockup -->
      <div class="hero-visual">
        <div class="hero-mockup">
          <div class="hero-mockup-header">
            <div class="hero-mockup-dot" style="background:#F85C1E"></div>
            <div class="hero-mockup-dot" style="background:#FBBF24"></div>
            <div class="hero-mockup-dot" style="background:#34D399"></div>
          </div>
          <div class="hero-mockup-stats">
            <div class="hero-mockup-stat">
              <div class="hero-mockup-stat-val" style="color:var(--brand)">247.3</div>
              <div class="hero-mockup-stat-lbl">{{ t('stats.km') }}</div>
            </div>
            <div class="hero-mockup-stat">
              <div class="hero-mockup-stat-val">5:12</div>
              <div class="hero-mockup-stat-lbl">{{ t('stats.pace') }}</div>
            </div>
            <div class="hero-mockup-stat">
              <div class="hero-mockup-stat-val">42</div>
              <div class="hero-mockup-stat-lbl">{{ t('stats.count') }}</div>
            </div>
            <div class="hero-mockup-stat">
              <div class="hero-mockup-stat-val">38h</div>
              <div class="hero-mockup-stat-lbl">{{ t('stats.time') }}</div>
            </div>
          </div>
          <div class="hero-mockup-run">
            <div>
              <div class="hero-mockup-run-dist">12.4 km</div>
              <div class="hero-mockup-run-meta">{{ t('landing.mockTempo') }}</div>
            </div>
            <div class="badge badge-active">{{ t('landing.mockStatus') }}</div>
          </div>
          <div class="hero-mockup-run" style="opacity:0.6">
            <div>
              <div class="hero-mockup-run-dist" style="color:var(--text)">8.0 km</div>
              <div class="hero-mockup-run-meta">{{ t('landing.mockEasy') }}</div>
            </div>
            <div class="badge badge-done">✓</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="features" aria-label="Возможности приложения">
      <div class="features-label">{{ t('landing.featLabel') }}</div>
      <h2 class="features-title">{{ t('landing.featTitle') }}</h2>
      <div class="features-grid">
        <article v-for="f in features" :key="f.icon" class="feature-card">
          <div class="feature-icon"><i :class="f.icon" aria-hidden="true"></i></div>
          <h3 class="feature-title">{{ f.title }}</h3>
          <p class="feature-desc">{{ f.desc }}</p>
        </article>
      </div>
    </section>

    <!-- FAQ — для SEO и AI-цитирования -->
    <section class="landing-faq" aria-label="Часто задаваемые вопросы">
      <div class="faq-inner">
        <h2 class="faq-title">{{ t('landing.faqTitle') }}</h2>
        <dl class="faq-list">
          <div v-for="item in faqItems" :key="item.q" class="faq-item">
            <dt class="faq-q" @click="item.open = !item.open">
              <span>{{ item.q }}</span>
              <i class="fas" :class="item.open ? 'fa-chevron-up' : 'fa-chevron-down'" aria-hidden="true"></i>
            </dt>
            <Transition name="faq-slide">
              <dd v-if="item.open" class="faq-a">{{ item.a }}</dd>
            </Transition>
          </div>
        </dl>
      </div>
    </section>

    <!-- CTA -->
    <div class="landing-cta" role="complementary" aria-label="Призыв к действию">
      <div class="cta-block">
        <h2>{{ t('landing.ctaTitle') }}</h2>
        <p>{{ t('landing.ctaDesc') }}</p>
        <button class="btn-white" @click="showAuth('register')">
          {{ t('landing.startFree') }} →
        </button>
      </div>
    </div>

    <footer class="landing-footer" role="contentinfo">
      <p>© 2026 AI RunningCoach. {{ t('landing.footer') }}</p>
      <nav class="footer-links" aria-label="Ссылки в подвале">
        <a href="/sitemap.xml" rel="nofollow">Sitemap</a>
      </nav>
    </footer>

    <!-- Auth modal overlay -->
    <Transition name="modal-fade">
      <div v-if="authVisible" class="auth-wrap" style="position:fixed;inset:0;z-index:500;background:rgba(0,0,0,0.55);backdrop-filter:blur(4px)">
        <AuthCard :initial-screen="authScreen" :success-msg="authSuccessMsg" :can-close="true" @close="authVisible = false" />
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { toggleLang } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import AuthCard from '@/components/auth/AuthCard.vue'

const { t, locale } = useI18n()
const router = useRouter()
const auth   = useAuthStore()
const { theme, toggle: themeToggle } = useTheme()

onMounted(async () => {
  await auth.loadMe().catch(() => {})
  if (auth.loggedIn) { router.replace('/dashboard'); return }

  const params = new URLSearchParams(window.location.search)
  if (params.get('verified') === '1') {
    history.replaceState({}, '', '/')
    authSuccessMsg.value = '✅ Email подтверждён! Войдите в аккаунт.'
    authScreen.value = 'login'
    authVisible.value = true
  }
})

const nextLang = computed(() => locale.value === 'ru' ? 'EN' : 'RU')
function changeLang() { toggleLang() }

const authVisible = ref(false)
const authScreen  = ref<'login'|'register'>('register')
const authSuccessMsg = ref('')
function showAuth(s: 'login'|'register') { authScreen.value = s; authVisible.value = true }

const features = computed(() => [
  { icon: 'fas fa-robot',          title: t('landing.f1title'), desc: t('landing.f1desc') },
  { icon: 'fas fa-calendar-week',  title: t('landing.f2title'), desc: t('landing.f2desc') },
  { icon: 'fas fa-chart-line',     title: t('landing.f3title'), desc: t('landing.f3desc') },
  { icon: 'fas fa-bullseye',       title: t('landing.f4title'), desc: t('landing.f4desc') },
  { icon: 'fas fa-person-running', title: t('landing.f5title'), desc: t('landing.f5desc') },
  { icon: 'fas fa-brain',          title: t('landing.f6title'), desc: t('landing.f6desc') },
])

const faqItems = computed(() => [
  {
    q: t('landing.faq1q'),
    a: t('landing.faq1a'),
    open: ref(false),
  },
  {
    q: t('landing.faq2q'),
    a: t('landing.faq2a'),
    open: ref(false),
  },
  {
    q: t('landing.faq3q'),
    a: t('landing.faq3a'),
    open: ref(false),
  },
  {
    q: t('landing.faq4q'),
    a: t('landing.faq4a'),
    open: ref(false),
  },
  {
    q: t('landing.faq5q'),
    a: t('landing.faq5a'),
    open: ref(false),
  },
].map(item => reactive(item)))
</script>
