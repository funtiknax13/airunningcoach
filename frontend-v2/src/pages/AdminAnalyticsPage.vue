<template>
  <AppLayout>
    <template #header-actions>
      <RouterLink to="/admin" class="btn btn-secondary btn-sm">
        <i class="fas fa-arrow-left"></i> {{ t('admin.analytics.backToSupport') }}
      </RouterLink>
      <a href="/sqladmin/" class="btn btn-secondary btn-sm">
        <i class="fas fa-database"></i> {{ t('admin.support.sqlAdmin') }}
      </a>
    </template>

    <div v-if="loading" class="card empty-state"><p>{{ t('common.loading') }}</p></div>

    <template v-else>
      <!-- ── Обзор ── -->
      <div class="section-label">{{ t('admin.analytics.overview') }}</div>
      <div class="stat-grid">
        <div class="card stat-card"><div class="stat-val">{{ overview?.total_users }}</div><div class="stat-lbl">{{ t('admin.analytics.totalUsers') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.verified_users }}</div><div class="stat-lbl">{{ t('admin.analytics.verifiedUsers') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.premium_active }}</div><div class="stat-lbl">{{ t('admin.analytics.premiumActive') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.signups_today }}</div><div class="stat-lbl">{{ t('admin.analytics.signupsToday') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.signups_7d }}</div><div class="stat-lbl">{{ t('admin.analytics.signups7d') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.signups_30d }}</div><div class="stat-lbl">{{ t('admin.analytics.signups30d') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.dau }}</div><div class="stat-lbl">{{ t('admin.analytics.dau') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.wau }}</div><div class="stat-lbl">{{ t('admin.analytics.wau') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.mau }}</div><div class="stat-lbl">{{ t('admin.analytics.mau') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.revenue_30d_rub }} ₽</div><div class="stat-lbl">{{ t('admin.analytics.revenue30d') }}</div></div>
        <div class="card stat-card"><div class="stat-val">{{ overview?.revenue_total_rub }} ₽</div><div class="stat-lbl">{{ t('admin.analytics.revenueTotal') }}</div></div>
      </div>

      <!-- ── Регистрации ── -->
      <div class="section-label">{{ t('admin.analytics.registrations') }}</div>
      <div class="card">
        <BarChart :series="regSeries" />
      </div>
      <div class="card source-table">
        <div class="source-title">{{ t('admin.analytics.bySource') }}</div>
        <div v-for="s in registrations?.by_source" :key="s.utm_source" class="source-row">
          <span class="source-name">{{ s.utm_source === '(direct)' ? t('admin.analytics.direct') : s.utm_source }}</span>
          <div class="source-bar-wrap"><div class="source-bar" :style="{ width: sourcePct(s.count) + '%' }"></div></div>
          <span class="source-count">{{ s.count }}</span>
        </div>
      </div>

      <!-- ── ИИ ── -->
      <div class="section-label">{{ t('admin.analytics.aiUsage') }}</div>
      <div class="card">
        <BarChart :series="chatSeries" color="var(--brand)" :label="t('admin.analytics.chat')" />
        <BarChart :series="planSeries" color="var(--blue)" :label="t('admin.analytics.plan')" />
      </div>

      <!-- ── Retention ── -->
      <div class="section-label">{{ t('admin.analytics.retention') }}</div>
      <p class="hint">{{ t('admin.analytics.retentionHint') }}</p>
      <div class="card" style="overflow-x:auto">
        <table class="cohort-table">
          <thead>
            <tr>
              <th>{{ t('admin.analytics.cohortWeek') }}</th>
              <th>{{ t('admin.analytics.cohortSize') }}</th>
              <th v-for="w in 5" :key="w">{{ t('admin.analytics.week') }} {{ w - 1 }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in retention?.cohorts" :key="c.cohort_week">
              <td>{{ c.cohort_week }}</td>
              <td>{{ c.size }}</td>
              <td v-for="(v, i) in c.retention" :key="i" :style="cohortCellStyle(v)">
                {{ v === null ? '—' : v + '%' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Воронка ── -->
      <div class="section-label">{{ t('admin.analytics.funnel') }}</div>
      <div class="card funnel">
        <div v-for="s in funnel?.steps" :key="s.step" class="funnel-row">
          <span class="funnel-label">{{ (t(`admin.analytics.funnelSteps.${s.step}`)) }}</span>
          <div class="funnel-bar-wrap"><div class="funnel-bar" :style="{ width: s.pct_of_registered + '%' }"></div></div>
          <span class="funnel-count">{{ s.count }} <small>({{ s.pct_of_registered }}%)</small></span>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BarChart from '@/components/admin/BarChart.vue'
import { adminAnalyticsApi } from '@/api'
import type { AdminOverview, AdminRegistrations, AdminAiUsage, AdminRetention, AdminFunnel } from '@/api/types'

const { t } = useI18n()

const loading = ref(true)
const overview = ref<AdminOverview | null>(null)
const registrations = ref<AdminRegistrations | null>(null)
const aiUsage = ref<AdminAiUsage | null>(null)
const retention = ref<AdminRetention | null>(null)
const funnel = ref<AdminFunnel | null>(null)

onMounted(async () => {
  const [o, r, a, ret, f] = await Promise.all([
    adminAnalyticsApi.overview(),
    adminAnalyticsApi.registrations(30),
    adminAnalyticsApi.aiUsage(30),
    adminAnalyticsApi.retention(8),
    adminAnalyticsApi.funnel(),
  ])
  overview.value = o
  registrations.value = r
  aiUsage.value = a
  retention.value = ret
  funnel.value = f
  loading.value = false
})

const regSeries = computed(() => registrations.value?.series.map(d => ({ label: d.date, value: d.count })) ?? [])
const chatSeries = computed(() => aiUsage.value?.series.map(d => ({ label: d.date, value: d.chat })) ?? [])
const planSeries = computed(() => aiUsage.value?.series.map(d => ({ label: d.date, value: d.plan })) ?? [])

const maxSourceCount = computed(() => Math.max(1, ...(registrations.value?.by_source.map(s => s.count) ?? [1])))
function sourcePct(count: number) {
  return Math.round((count / maxSourceCount.value) * 100)
}

function cohortCellStyle(v: number | null) {
  if (v === null) return { opacity: 0.35 }
  // 0% -> прозрачный, 100% -> насыщенный брендовый
  const alpha = Math.max(0.08, Math.min(1, v / 100))
  return { background: `color-mix(in srgb, var(--brand) ${Math.round(alpha * 100)}%, transparent)` }
}
</script>

<style scoped>
.section-label { font-weight: 600; font-size: 0.9rem; color: var(--text-2); margin: 24px 0 10px; text-transform: uppercase; letter-spacing: 0.02em; }
.section-label:first-child { margin-top: 0; }
.hint { font-size: 0.82rem; color: var(--text-3); margin: -4px 0 10px; }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.stat-card { padding: 14px; text-align: left; }
.stat-val { font-size: 1.5rem; font-weight: 700; }
.stat-lbl { font-size: 0.78rem; color: var(--text-3); margin-top: 2px; }

.source-table { margin-top: 10px; }
.source-title { font-weight: 600; font-size: 0.85rem; margin-bottom: 10px; }
.source-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.source-name { width: 110px; flex-shrink: 0; font-size: 0.85rem; }
.source-bar-wrap { flex: 1; height: 10px; background: var(--surface-3); border-radius: 5px; overflow: hidden; }
.source-bar { height: 100%; background: var(--brand); border-radius: 5px; }
.source-count { width: 32px; text-align: right; font-size: 0.85rem; font-weight: 600; }

.cohort-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.cohort-table th, .cohort-table td { padding: 8px 10px; text-align: center; white-space: nowrap; }
.cohort-table th { color: var(--text-3); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
.cohort-table td:first-child, .cohort-table th:first-child { text-align: left; }

.funnel-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.funnel-label { width: 170px; flex-shrink: 0; font-size: 0.85rem; }
.funnel-bar-wrap { flex: 1; height: 14px; background: var(--surface-3); border-radius: 7px; overflow: hidden; }
.funnel-bar { height: 100%; background: var(--brand); border-radius: 7px; }
.funnel-count { width: 100px; text-align: right; font-size: 0.85rem; font-weight: 600; }
.funnel-count small { color: var(--text-3); font-weight: 400; }
</style>
