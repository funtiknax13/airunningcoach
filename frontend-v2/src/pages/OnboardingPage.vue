<template>
  <div class="onboarding-wrap">
    <div class="onboarding-card">
      <!-- Прогресс -->
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${(step / 3) * 100}%` }" />
      </div>
      <div class="step-label">Шаг {{ step }} из 3</div>

      <!-- Шаг 1: Уровень -->
      <template v-if="step === 1">
        <h1>Какой у тебя уровень?</h1>
        <p class="subtitle">Это поможет подобрать нагрузку именно под тебя</p>
        <div class="options">
          <button
            v-for="opt in fitnessOptions"
            :key="opt.value"
            class="option-btn"
            :class="{ selected: form.fitness_level === opt.value }"
            @click="form.fitness_level = opt.value"
          >
            <span class="opt-icon">{{ opt.icon }}</span>
            <span class="opt-title">{{ opt.label }}</span>
            <span class="opt-desc">{{ opt.desc }}</span>
          </button>
        </div>
      </template>

      <!-- Шаг 2: Цель -->
      <template v-else-if="step === 2">
        <h1>Какова твоя цель?</h1>
        <p class="subtitle">Тренер выстроит план именно под эту дистанцию</p>
        <div class="options">
          <button
            v-for="opt in goalOptions"
            :key="opt.value"
            class="option-btn"
            :class="{ selected: form.running_goal === opt.value }"
            @click="form.running_goal = opt.value"
          >
            <span class="opt-icon">{{ opt.icon }}</span>
            <span class="opt-title">{{ opt.label }}</span>
            <span class="opt-desc">{{ opt.desc }}</span>
          </button>
        </div>
      </template>

      <!-- Шаг 3: Нагрузка -->
      <template v-else>
        <h1>Текущая нагрузка</h1>
        <p class="subtitle">Тренер учтёт, откуда ты начинаешь</p>

        <div class="field-group">
          <label>Сколько км в неделю бегаешь сейчас?</label>
          <div class="chip-row">
            <button
              v-for="km in kmOptions"
              :key="km.value"
              class="chip"
              :class="{ selected: form.weekly_km === km.value }"
              @click="form.weekly_km = km.value"
            >{{ km.label }}</button>
          </div>
        </div>

        <div class="field-group">
          <label>Сколько дней в неделю готов тренироваться?</label>
          <div class="chip-row">
            <button
              v-for="d in dayOptions"
              :key="d.value"
              class="chip"
              :class="{ selected: form.training_days === d.value }"
              @click="form.training_days = d.value"
            >{{ d.label }}</button>
          </div>
        </div>
      </template>

      <!-- Кнопки навигации -->
      <div class="nav-row">
        <button v-if="step > 1" class="btn-back" @click="step--">Назад</button>
        <button
          class="btn-next"
          :disabled="!canProceed || saving"
          @click="next"
        >
          {{ step < 3 ? 'Далее' : (saving ? 'Сохраняем...' : 'Начать тренировки') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const step = ref(1)
const saving = ref(false)

const form = ref({
  fitness_level: '' as string,
  running_goal: '' as string,
  weekly_km: null as number | null,
  training_days: null as number | null,
})

const fitnessOptions = [
  { value: 'beginner',     icon: '🌱', label: 'Начинающий',  desc: 'Бегаю редко или только начинаю' },
  { value: 'intermediate', icon: '🏃', label: 'Любитель',    desc: '10–30 км в неделю, бегаю регулярно' },
  { value: 'advanced',     icon: '🏅', label: 'Продвинутый', desc: '30+ км в неделю, участвую в соревнованиях' },
]

const goalOptions = [
  { value: '5k',            icon: '🎯', label: '5 км',         desc: 'Пробежать или улучшить время' },
  { value: '10k',           icon: '🎯', label: '10 км',        desc: 'Классическая дистанция' },
  { value: 'half_marathon', icon: '🏁', label: 'Полумарафон',  desc: '21,1 км' },
  { value: 'marathon',      icon: '🏆', label: 'Марафон',      desc: '42,2 км' },
  { value: 'fitness',       icon: '❤️', label: 'Для здоровья', desc: 'Бегать регулярно и с удовольствием' },
]

const kmOptions = [
  { value: 0,  label: '0 км' },
  { value: 10, label: '~10 км' },
  { value: 20, label: '~20 км' },
  { value: 30, label: '~30 км' },
  { value: 40, label: '40+ км' },
]

const dayOptions = [
  { value: 2, label: '2 дня' },
  { value: 3, label: '3 дня' },
  { value: 4, label: '4 дня' },
  { value: 5, label: '5+ дней' },
]

const canProceed = computed(() => {
  if (step.value === 1) return !!form.value.fitness_level
  if (step.value === 2) return !!form.value.running_goal
  return form.value.weekly_km !== null && form.value.training_days !== null
})

async function next() {
  if (step.value < 3) {
    step.value++
    return
  }
  saving.value = true
  try {
    await auth.updateProfile({
      fitness_level: form.value.fitness_level,
      running_goal: form.value.running_goal,
      weekly_km: form.value.weekly_km,
      training_days: form.value.training_days,
      onboarding_completed: true,
    })
    router.push('/dashboard')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.onboarding-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary, #0f0f13);
  padding: 24px 16px;
}

.onboarding-card {
  width: 100%;
  max-width: 520px;
  background: var(--bg-secondary, #1a1a24);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 20px;
  padding: 36px 32px;
}

.progress-bar {
  height: 4px;
  background: var(--border-color, #2a2a3a);
  border-radius: 2px;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--accent, #6c63ff);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.step-label {
  font-size: 12px;
  color: var(--text-muted, #888);
  margin-bottom: 28px;
}

h1 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary, #fff);
  margin: 0 0 6px;
}

.subtitle {
  font-size: 14px;
  color: var(--text-muted, #888);
  margin: 0 0 24px;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 28px;
}

.option-btn {
  display: grid;
  grid-template-columns: 36px 1fr;
  grid-template-rows: auto auto;
  column-gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}

.option-btn:hover {
  border-color: var(--accent, #6c63ff);
  background: rgba(108, 99, 255, 0.06);
}

.option-btn.selected {
  border-color: var(--accent, #6c63ff);
  background: rgba(108, 99, 255, 0.12);
}

.opt-icon {
  grid-row: 1 / 3;
  font-size: 22px;
  line-height: 1;
}

.opt-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #fff);
}

.opt-desc {
  font-size: 13px;
  color: var(--text-muted, #888);
}

.field-group {
  margin-bottom: 24px;
}

.field-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary, #ccc);
  margin-bottom: 12px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 8px 16px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 20px;
  background: transparent;
  color: var(--text-secondary, #ccc);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.chip:hover {
  border-color: var(--accent, #6c63ff);
  color: var(--text-primary, #fff);
}

.chip.selected {
  border-color: var(--accent, #6c63ff);
  background: rgba(108, 99, 255, 0.18);
  color: var(--text-primary, #fff);
}

.nav-row {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 4px;
}

.btn-back {
  padding: 11px 24px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary, #ccc);
  font-size: 15px;
  cursor: pointer;
}

.btn-next {
  padding: 11px 28px;
  border: none;
  border-radius: 10px;
  background: var(--accent, #6c63ff);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-next:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
