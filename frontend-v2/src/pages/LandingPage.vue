<template>
  <div class="landing">

    <!-- Nav -->
    <nav class="landing-nav" role="navigation" aria-label="Основная навигация">
      <div class="landing-nav-logo">
        <img src="/logo.png" alt="AI RunningCoach — логотип">
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
        <div class="hero-trust">
          <span class="hero-trust-item"><i class="fas fa-check" aria-hidden="true"></i> {{ t('landing.trust1') }}</span>
          <span class="hero-trust-item"><i class="fas fa-check" aria-hidden="true"></i> {{ t('landing.trust2') }}</span>
          <span class="hero-trust-item"><i class="fas fa-check" aria-hidden="true"></i> {{ t('landing.trust3') }}</span>
        </div>
      </div>

      <!-- Mockup -->
      <div class="hero-visual" aria-hidden="true">
        <div class="hero-mockup">
          <div class="hero-mockup-header">
            <div class="hero-mockup-dot" style="background:#FF5F57"></div>
            <div class="hero-mockup-dot" style="background:#FFBD2E"></div>
            <div class="hero-mockup-dot" style="background:#28CA41"></div>
          </div>
          <div class="hero-mockup-stats">
            <div class="hero-mockup-stat">
              <div class="hero-mockup-stat-val" style="color:var(--brand)">247 {{ t('misc.km') }}</div>
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
              <div class="hero-mockup-run-dist">12.4 {{ t('misc.km') }}</div>
              <div class="hero-mockup-run-meta">{{ t('landing.mockTempo') }}</div>
            </div>
            <div class="badge badge-active">{{ t('landing.mockStatus') }}</div>
          </div>
          <div class="hero-mockup-run" style="opacity:0.6">
            <div>
              <div class="hero-mockup-run-dist" style="color:var(--text)">8.0 {{ t('misc.km') }}</div>
              <div class="hero-mockup-run-meta">{{ t('landing.mockEasy') }}</div>
            </div>
            <div class="badge badge-done">✓</div>
          </div>
          <div class="mockup-chat-box">
            <div class="mockup-chat-tag">AI {{ t('nav.ai') }}</div>
            <div class="mockup-chat-text">{{ t('landing.mockChat') }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Definition -->
    <section class="l-definition" aria-label="Что такое AI-тренер по бегу">
      <div class="l-inner">
        <p v-html="t('landing.defP')"></p>
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

    <!-- How it works -->
    <section class="l-hiw" aria-labelledby="hiw-heading">
      <div class="l-section-header">
        <div class="features-label">{{ t('landing.hiwLabel') }}</div>
        <h2 id="hiw-heading" class="features-title" style="margin-bottom:0">{{ t('landing.hiwTitle') }}</h2>
      </div>
      <div class="l-steps">
        <div v-for="(step, i) in steps" :key="i" class="l-step">
          <div class="l-step-num">{{ i + 1 }}</div>
          <div>
            <h3 class="l-step-title">{{ step.title }}</h3>
            <p class="l-step-desc">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Stats -->
    <section class="l-stats" aria-label="Статистика">
      <div class="l-section-header">
        <div class="features-label">{{ t('landing.statsLabel') }}</div>
        <h2 class="features-title" style="margin-bottom:0">{{ t('landing.statsTitle') }}</h2>
      </div>
      <div class="l-stats-grid">
        <div v-for="s in stats" :key="s.val" class="stat-card">
          <div class="stat-card-value">{{ s.val }}</div>
          <p class="stat-card-desc">{{ s.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Comparison -->
    <section class="l-compare" aria-labelledby="compare-heading">
      <div class="l-section-header">
        <div class="features-label">{{ t('landing.cmpLabel') }}</div>
        <h2 id="compare-heading" class="features-title" style="margin-bottom:6px">{{ t('landing.cmpTitle') }}</h2>
        <p class="l-section-desc">{{ t('landing.cmpDesc') }}</p>
      </div>
      <div class="l-compare-wrap">
        <table class="l-compare-table" role="table">
          <thead>
            <tr>
              <th scope="col"></th>
              <th scope="col" class="l-col-hl">AIRunningCoach</th>
              <th scope="col">{{ t('landing.cmpH2') }}</th>
              <th scope="col">{{ t('landing.cmpH3') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in compareRows" :key="row.label">
              <td class="l-row-label">{{ row.label }}</td>
              <td class="l-col-hl" :class="row.arcClass">{{ row.arc }}</td>
              <td :class="row.humanClass">{{ row.human }}</td>
              <td :class="row.appClass">{{ row.app }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Pricing -->
    <section class="l-pricing" aria-labelledby="pricing-heading">
      <div class="l-section-header">
        <div class="features-label">{{ t('landing.priceLabel') }}</div>
        <h2 id="pricing-heading" class="features-title" style="margin-bottom:6px">{{ t('landing.priceTitle') }}</h2>
        <p class="l-section-desc">{{ t('landing.priceDesc') }}</p>
      </div>
      <div class="l-pricing-grid">
        <!-- Free -->
        <div class="l-price-card">
          <div class="l-plan-name">{{ t('landing.pFree') }}</div>
          <div class="l-plan-price">0 <span class="l-plan-sub">₽/{{ locale === 'ru' ? 'мес' : 'mo' }}</span></div>
          <div class="l-plan-saving">&nbsp;</div>
          <hr class="l-plan-hr">
          <ul class="l-plan-features">
            <li v-for="f in freeFeatures" :key="f">{{ f }}</li>
          </ul>
          <button class="btn btn-secondary" style="width:100%;justify-content:center" @click="showAuth('register')">
            {{ t('landing.startFree') }}
          </button>
        </div>
        <!-- Month -->
        <div class="l-price-card">
          <div class="l-plan-name">{{ t('landing.pMonth') }}</div>
          <div class="l-plan-price"><sup>₽</sup>490 <span class="l-plan-sub">/{{ locale === 'ru' ? 'мес' : 'mo' }}</span></div>
          <div class="l-plan-saving">&nbsp;</div>
          <hr class="l-plan-hr">
          <ul class="l-plan-features">
            <li v-for="f in proFeatures" :key="f">{{ f }}</li>
          </ul>
          <button class="btn btn-secondary" style="width:100%;justify-content:center" @click="showAuth('register')">
            {{ t('landing.selectPlan') }}
          </button>
        </div>
        <!-- Year — featured -->
        <div class="l-price-card l-price-card--featured">
          <div class="l-plan-badge">{{ t('landing.pBest') }}</div>
          <div class="l-plan-name">{{ t('landing.pYear') }}</div>
          <div class="l-plan-price"><sup>₽</sup>343 <span class="l-plan-sub">/{{ locale === 'ru' ? 'мес' : 'mo' }}</span></div>
          <div class="l-plan-saving">{{ t('landing.pYearSave') }}</div>
          <hr class="l-plan-hr">
          <ul class="l-plan-features">
            <li v-for="f in yearFeatures" :key="f">{{ f }}</li>
          </ul>
          <button class="btn btn-primary" style="width:100%;justify-content:center" @click="showAuth('register')">
            {{ t('landing.startPremium') }}
          </button>
        </div>
      </div>
      <p class="l-pricing-note">{{ t('landing.priceNote') }}</p>
    </section>

    <!-- FAQ -->
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

const authVisible    = ref(false)
const authScreen     = ref<'login'|'register'>('register')
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

const steps = computed(() => [
  { title: t('landing.s1t'), desc: t('landing.s1d') },
  { title: t('landing.s2t'), desc: t('landing.s2d') },
  { title: t('landing.s3t'), desc: t('landing.s3d') },
])

const stats = computed(() => [
  { val: t('landing.stat1v'), desc: t('landing.stat1d') },
  { val: t('landing.stat2v'), desc: t('landing.stat2d') },
  { val: t('landing.stat3v'), desc: t('landing.stat3d') },
  { val: t('landing.stat4v'), desc: t('landing.stat4d') },
])

type CmpClass = 'c-yes' | 'c-no' | 'c-partial' | ''
const compareRows = computed<{ label: string; arc: string; arcClass: CmpClass; human: string; humanClass: CmpClass; app: string; appClass: CmpClass }[]>(() => [
  { label: t('landing.cmpR1l'), arc: t('landing.cmpR1a'), arcClass: 'c-yes',     human: t('landing.cmpR1h'), humanClass: '',          app: t('landing.cmpR1p'), appClass: '' },
  { label: t('landing.cmpR2l'), arc: t('landing.cmpR2a'), arcClass: 'c-yes',     human: t('landing.cmpR2h'), humanClass: 'c-no',       app: t('landing.cmpR2p'), appClass: '' },
  { label: t('landing.cmpR3l'), arc: t('landing.cmpR3a'), arcClass: 'c-yes',     human: t('landing.cmpR3h'), humanClass: 'c-yes',      app: t('landing.cmpR3p'), appClass: 'c-partial' },
  { label: t('landing.cmpR4l'), arc: t('landing.cmpR4a'), arcClass: 'c-yes',     human: t('landing.cmpR4h'), humanClass: 'c-partial',  app: t('landing.cmpR4p'), appClass: 'c-partial' },
  { label: t('landing.cmpR5l'), arc: t('landing.cmpR5a'), arcClass: 'c-yes',     human: t('landing.cmpR5h'), humanClass: '',           app: t('landing.cmpR5p'), appClass: 'c-no' },
  { label: t('landing.cmpR6l'), arc: t('landing.cmpR6a'), arcClass: 'c-yes',     human: t('landing.cmpR6h'), humanClass: '',           app: t('landing.cmpR6p'), appClass: 'c-no' },
  { label: t('landing.cmpR7l'), arc: t('landing.cmpR7a'), arcClass: 'c-yes',     human: t('landing.cmpR7h'), humanClass: '',           app: t('landing.cmpR7p'), appClass: 'c-no' },
])

const freeFeatures = computed(() => [
  t('landing.pf1'), t('landing.pf2'), t('landing.pf3'),
  t('landing.pf4'), t('landing.pf5'), t('landing.pf6'),
])
const proFeatures = computed(() => [
  t('landing.pp1'), t('landing.pp2'), t('landing.pp3'),
  t('landing.pp4'), t('landing.pp5'),
])
const yearFeatures = computed(() => [
  t('landing.pp1'), t('landing.pp2'), t('landing.pp3'),
  t('landing.pp4'), t('landing.pyExtra'),
])

const faqItems = computed(() => [
  { q: t('landing.faq1q'), a: t('landing.faq1a'), open: ref(false) },
  { q: t('landing.faq2q'), a: t('landing.faq2a'), open: ref(false) },
  { q: t('landing.faq3q'), a: t('landing.faq3a'), open: ref(false) },
  { q: t('landing.faq4q'), a: t('landing.faq4a'), open: ref(false) },
  { q: t('landing.faq5q'), a: t('landing.faq5a'), open: ref(false) },
].map(item => reactive(item)))
</script>

<style scoped>
/* ── Hero trust ── */
.hero-trust {
  display: flex; gap: 18px; flex-wrap: wrap; margin-top: 20px;
}
.hero-trust-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.82rem; color: var(--text-3); font-weight: 500;
}
.hero-trust-item i { color: var(--green); font-size: 0.75rem; }

/* ── Mockup chat box ── */
.mockup-chat-box {
  margin-top: 10px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 12px;
}
.mockup-chat-tag {
  font-size: 0.65rem; font-weight: 700;
  letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--brand); margin-bottom: 4px;
}
.mockup-chat-text { font-size: 0.8rem; color: var(--text-2); line-height: 1.5; }

/* ── Definition ── */
.l-definition {
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 36px 32px;
}
.l-inner { max-width: 760px; margin: 0 auto; text-align: center; }
.l-inner p { font-size: 1.05rem; line-height: 1.75; color: var(--text-2); }
.l-inner :deep(strong) { color: var(--text); }

/* ── Section layout helpers ── */
.l-section-header { text-align: center; margin-bottom: 44px; }
.l-section-desc { font-size: 1rem; color: var(--text-2); max-width: 580px; margin: 0 auto; }

/* ── How it works ── */
.l-hiw {
  padding: 64px 32px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  max-width: 1100px; margin: 0 auto;
}
.l-steps {
  display: flex; gap: 0; position: relative;
}
.l-steps::before {
  content: ''; position: absolute;
  top: 27px; left: 10%; right: 10%;
  height: 2px; background: var(--border); z-index: 0;
}
.l-step { flex: 1; padding: 0 24px; text-align: center; position: relative; z-index: 1; }
.l-step-num {
  width: 56px; height: 56px;
  background: var(--surface); border: 2px solid var(--brand);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem; font-weight: 800; color: var(--brand);
  margin: 0 auto 18px;
}
.l-step-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 8px; color: var(--text); }
.l-step-desc  { font-size: 0.83rem; color: var(--text-2); line-height: 1.6; }

/* ── Stats ── */
.l-stats {
  padding: 64px 32px;
  max-width: 1100px; margin: 0 auto;
}
.l-stats-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
}
.l-stats .stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 24px 20px; text-align: center;
  transition: box-shadow 0.2s;
}
.l-stats .stat-card:hover { box-shadow: var(--shadow); }
.l-stats .stat-card-value {
  font-size: 1.5rem; font-weight: 800;
  color: var(--brand); letter-spacing: -0.03em;
  margin-bottom: 6px;
}
.l-stats .stat-card-desc { font-size: 0.82rem; color: var(--text-2); line-height: 1.5; }

/* ── Comparison ── */
.l-compare {
  padding: 64px 32px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.l-compare > * { max-width: 1100px; margin-left: auto; margin-right: auto; }
.l-compare-wrap { overflow-x: auto; }
.l-compare-table {
  width: 100%; border-collapse: collapse; font-size: 0.875rem;
}
.l-compare-table th {
  padding: 12px 16px;
  background: var(--surface-2);
  text-align: center;
  font-size: 0.72rem; font-weight: 700;
  color: var(--text-3); text-transform: uppercase;
  letter-spacing: 0.07em;
  border-bottom: 2px solid var(--border);
}
.l-compare-table th:first-child { text-align: left; }
.l-compare-table th.l-col-hl { color: var(--brand); background: var(--brand-light); }
.l-compare-table td {
  padding: 13px 16px; border-bottom: 1px solid var(--border);
  text-align: center;
}
.l-compare-table td.l-row-label { text-align: left; color: var(--text-2); font-size: 0.82rem; }
.l-compare-table td.l-col-hl   { background: rgba(248,92,30,0.04); }
.l-compare-table tr:last-child td { border-bottom: none; }
.l-compare-table tr:hover td   { background: var(--surface-2); }
.l-compare-table tr:hover td.l-col-hl { background: var(--brand-light); }
.c-yes     { color: var(--green); font-weight: 600; }
.c-no      { color: var(--red); }
.c-partial { color: var(--yellow); }

/* ── Pricing ── */
.l-pricing {
  padding: 64px 32px;
  max-width: 1100px; margin: 0 auto;
}
.l-pricing-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px; max-width: 880px; margin: 0 auto;
}
.l-price-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-xl); padding: 28px 24px;
  position: relative; transition: box-shadow 0.2s;
}
.l-price-card:hover { box-shadow: var(--shadow); }
.l-price-card--featured { border-color: var(--brand); border-width: 2px; }
.l-plan-badge {
  position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
  background: var(--brand); color: white;
  font-size: 0.65rem; font-weight: 800;
  padding: 4px 14px; border-radius: 100px;
  letter-spacing: 0.06em; white-space: nowrap;
}
.l-plan-name {
  font-size: 0.72rem; font-weight: 700;
  color: var(--text-3); text-transform: uppercase;
  letter-spacing: 0.08em; margin-bottom: 10px;
}
.l-plan-price {
  font-size: 2.4rem; font-weight: 800;
  letter-spacing: -0.04em; color: var(--text); line-height: 1;
}
.l-plan-price sup { font-size: 1rem; font-weight: 700; vertical-align: top; margin-top: 6px; }
.l-plan-sub { font-size: 0.9rem; font-weight: 400; color: var(--text-3); }
.l-plan-saving { font-size: 0.78rem; color: var(--green); font-weight: 600; margin: 6px 0 16px; min-height: 18px; }
.l-plan-hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
.l-plan-features { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 9px; margin-bottom: 22px; }
.l-plan-features li { font-size: 0.83rem; color: var(--text-2); display: flex; gap: 8px; }
.l-plan-features li::before { content: '✓'; color: var(--green); font-weight: 700; flex-shrink: 0; }
.l-pricing-note { text-align: center; margin-top: 20px; font-size: 0.8rem; color: var(--text-3); }

/* ── Responsive ── */
@media (max-width: 900px) {
  .l-stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .l-hiw, .l-stats, .l-compare, .l-pricing, .l-definition { padding-left: 16px; padding-right: 16px; }
  .l-steps { flex-direction: column; gap: 24px; }
  .l-steps::before { display: none; }
  .l-step { text-align: left; display: flex; gap: 14px; align-items: flex-start; padding: 0; }
  .l-step-num { flex-shrink: 0; margin: 0; width: 48px; height: 48px; }
  .l-pricing-grid { grid-template-columns: 1fr; max-width: 420px; margin: 0 auto; }
  .l-compare-table { font-size: 0.8rem; }
  .l-compare-table td, .l-compare-table th { padding: 10px 10px; }
  .hero-trust { gap: 12px; }
}
</style>
