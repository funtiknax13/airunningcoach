<template>
  <!-- Activity / generic list rows -->
  <template v-if="type === 'activity-list'">
    <div v-for="i in count" :key="i" class="sk-activity-row">
      <div class="sk-icon"></div>
      <div class="sk-info">
        <div class="sk-line sk-line--sm" style="width:80px"></div>
        <div class="sk-line" style="width:130px"></div>
      </div>
      <div class="sk-stats">
        <div class="sk-stat" v-for="j in 3" :key="j">
          <div class="sk-line sk-line--lg" style="width:36px"></div>
          <div class="sk-line sk-line--sm" style="width:24px"></div>
        </div>
      </div>
      <div class="sk-actions">
        <div class="sk-btn"></div>
        <div class="sk-btn"></div>
      </div>
    </div>
  </template>

  <!-- Goal items -->
  <template v-else-if="type === 'goal-list'">
    <div v-for="i in count" :key="i" class="sk-goal-item">
      <div class="sk-goal-header">
        <div class="sk-line" style="width:160px"></div>
        <div class="sk-badge"></div>
      </div>
      <div class="sk-goal-meta">
        <div class="sk-line sk-line--sm" style="width:70px"></div>
        <div class="sk-line sk-line--sm" style="width:60px"></div>
        <div class="sk-line sk-line--sm" style="width:90px"></div>
      </div>
    </div>
  </template>

  <!-- Workout / training rows -->
  <template v-else-if="type === 'workout-list'">
    <div v-for="i in count" :key="i" class="sk-workout-row">
      <div class="sk-date-block">
        <div class="sk-line sk-line--lg" style="width:28px"></div>
        <div class="sk-line sk-line--sm" style="width:22px"></div>
      </div>
      <div class="sk-workout-body">
        <div class="sk-badge" style="width:80px;margin-bottom:6px"></div>
        <div class="sk-line" style="width:220px"></div>
        <div class="sk-line sk-line--sm" style="width:120px;margin-top:4px"></div>
      </div>
      <div class="sk-btn" style="width:72px"></div>
    </div>
  </template>

  <!-- Dashboard stat cards -->
  <template v-else-if="type === 'stat-grid'">
    <div class="sk-stat-grid">
      <div v-for="i in count" :key="i" class="sk-stat-card">
        <div class="sk-line sk-line--sm" style="width:60px"></div>
        <div class="sk-line sk-line--xl" style="width:80px;margin-top:8px"></div>
      </div>
    </div>
  </template>

  <!-- Dashboard: recent runs list -->
  <template v-else-if="type === 'dash-runs'">
    <div v-for="i in count" :key="i" class="sk-dash-row">
      <div class="sk-icon sk-icon--sm"></div>
      <div class="sk-info">
        <div class="sk-line" style="width:110px"></div>
        <div class="sk-line sk-line--sm" style="width:70px"></div>
      </div>
      <div class="sk-line sk-line--lg" style="width:50px;margin-left:auto"></div>
    </div>
  </template>

  <!-- Insight items -->
  <template v-else-if="type === 'insights'">
    <div v-for="i in count" :key="i" class="sk-insight-item">
      <div class="sk-icon sk-icon--sm"></div>
      <div style="flex:1">
        <div class="sk-line" style="width:100%"></div>
        <div class="sk-line sk-line--sm" style="width:75%;margin-top:4px"></div>
      </div>
    </div>
  </template>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  type: 'activity-list' | 'goal-list' | 'workout-list' | 'stat-grid' | 'dash-runs' | 'insights'
  count?: number
}>(), { count: 4 })
</script>
