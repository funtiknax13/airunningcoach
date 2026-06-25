<template>
  <div class="chart-wrap">
    <div class="chart-title"><i class="fas fa-chart-bar"></i> Объём по неделям</div>
    <div class="chart-body">
      <svg :viewBox="`0 0 ${svgW} ${svgH}`" preserveAspectRatio="none" class="chart-svg">
        <g v-for="(bar, i) in bars" :key="i">
          <rect
            :x="bar.x" :y="bar.y" :width="barW - 4" :height="bar.h"
            :fill="bar.isCurrent ? 'var(--brand, #6c63ff)' : 'var(--bar-color, #2a2a3a)'"
            rx="3"
          />
        </g>
      </svg>
      <div class="chart-labels">
        <span v-for="(bar, i) in bars" :key="i" class="chart-label" :class="{ current: bar.isCurrent }">
          {{ bar.label }}
        </span>
      </div>
    </div>
    <div class="chart-legend">
      <span v-for="(bar, i) in bars" :key="i" class="chart-val" :class="{ current: bar.isCurrent }">
        {{ bar.km > 0 ? bar.km.toFixed(0) : '' }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Activity } from '@/api/types'

const props = defineProps<{ activities: Activity[] }>()

const WEEKS = 8
const svgW = 300
const svgH = 80

const barW = computed(() => svgW / WEEKS)

interface Bar { x: number; y: number; h: number; km: number; label: string; isCurrent: boolean }

const bars = computed<Bar[]>(() => {
  const now = new Date()
  // Начало текущей недели (понедельник)
  const weekStart = (date: Date) => {
    const d = new Date(date)
    const day = d.getDay() === 0 ? 6 : d.getDay() - 1
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - day)
    return d
  }

  const currentWeekStart = weekStart(now)
  const weeks: { start: Date; km: number }[] = []

  for (let i = WEEKS - 1; i >= 0; i--) {
    const start = new Date(currentWeekStart)
    start.setDate(start.getDate() - i * 7)
    weeks.push({ start, km: 0 })
  }

  for (const act of props.activities) {
    if (act.activity_type !== 'run') continue
    const d = new Date(act.date)
    const ws = weekStart(d)
    for (const w of weeks) {
      if (ws.getTime() === w.start.getTime()) {
        w.km += act.distance_km
        break
      }
    }
  }

  const maxKm = Math.max(...weeks.map(w => w.km), 1)

  return weeks.map((w, i) => {
    const km = w.km
    const h = Math.max((km / maxKm) * svgH, km > 0 ? 4 : 0)
    const isCurrent = i === WEEKS - 1
    const label = `${w.start.getDate()}.${String(w.start.getMonth() + 1).padStart(2, '0')}`
    return { x: i * barW.value + 2, y: svgH - h, h, km, label, isCurrent }
  })
})
</script>

<style scoped>
.chart-wrap {
  padding: 4px 0 0;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #aaa);
  margin-bottom: 12px;
}
.chart-title i { margin-right: 6px; }
.chart-body { position: relative; }
.chart-svg {
  width: 100%;
  height: 80px;
  display: block;
}
.chart-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}
.chart-label {
  font-size: 10px;
  color: var(--text-muted, #666);
  flex: 1;
  text-align: center;
}
.chart-label.current { color: var(--brand, #6c63ff); font-weight: 600; }
.chart-legend {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
}
.chart-val {
  font-size: 10px;
  color: var(--text-muted, #666);
  flex: 1;
  text-align: center;
}
.chart-val.current { color: var(--brand, #6c63ff); font-weight: 600; }
</style>
