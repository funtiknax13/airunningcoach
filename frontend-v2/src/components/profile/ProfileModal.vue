<template>
  <BaseModal v-model="show">
    <div class="profile-modal-tabs">
      <button class="profile-tab" :class="{ active: tab === 'info' }"
              @click="tab = 'info'">{{ $t('profile.tabInfo') }}</button>
      <button class="profile-tab" :class="{ active: tab === 'training' }"
              @click="tab = 'training'">{{ $t('profile.tabTraining') }}</button>
      <button class="profile-tab" :class="{ active: tab === 'password' }"
              @click="tab = 'password'">{{ $t('profile.tabPassword') }}</button>
    </div>

    <!-- Profile info -->
    <div v-if="tab === 'info'" class="profile-tab-content active">
      <label class="modal-label">{{ $t('profile.name') }}</label>
      <input type="text" v-model="info.name" class="modal-input" :placeholder="$t('profile.name')">

      <label class="modal-label">{{ $t('profile.age') }}</label>
      <div class="input-suffix-group">
        <input type="number" v-model.number="info.age" class="modal-input" placeholder="—">
        <span class="input-suffix">{{ $t('profile.ageUnit') }}</span>
      </div>

      <label class="modal-label">{{ $t('profile.weight') }}</label>
      <div class="input-suffix-group">
        <input type="number" v-model.number="info.weight" class="modal-input" placeholder="—" step="0.1">
        <span class="input-suffix">{{ $t('profile.weightUnit') }}</span>
      </div>

      <label class="modal-label">{{ $t('profile.height') }}</label>
      <div class="input-suffix-group">
        <input type="number" v-model.number="info.height" class="modal-input" placeholder="—" step="0.1">
        <span class="input-suffix">{{ $t('profile.heightUnit') }}</span>
      </div>

      <label class="modal-label">{{ $t('profile.gender') }}</label>
      <div class="segmented">
        <span class="segmented-thumb" :class="{ right: info.gender === 'female' }" v-show="info.gender"></span>
        <button type="button" class="segmented-option" :class="{ active: info.gender === 'male' }"
                @click="info.gender = 'male'"><i class="fas fa-mars"></i> {{ $t('profile.genderMale') }}</button>
        <button type="button" class="segmented-option" :class="{ active: info.gender === 'female' }"
                @click="info.gender = 'female'"><i class="fas fa-venus"></i> {{ $t('profile.genderFemale') }}</button>
      </div>

      <div v-if="infoError" class="auth-error">{{ infoError }}</div>
      <div class="modal-buttons">
        <button class="btn-primary" @click="saveInfo" :disabled="savingInfo">{{ $t('profile.save') }}</button>
        <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
      </div>

      <div v-if="push.supported" class="switch-row">
        <div class="switch-row-text">
          <div class="switch-row-title">{{ $t('profile.pushTitle') }}</div>
          <div class="switch-row-desc">{{ $t('profile.pushDesc') }}</div>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="push.subscribed.value" :disabled="push.loading.value" @change="togglePush">
          <span class="switch-track"><span class="switch-thumb"></span></span>
        </label>
      </div>
    </div>

    <!-- Training profile (used by the AI coach) -->
    <div v-if="tab === 'training'" class="profile-tab-content active">
      <label class="modal-label">{{ $t('profile.trLevel') }}</label>
      <div class="pm-chips">
        <button v-for="o in fitnessOptions" :key="o.value" type="button" class="pm-chip"
                :class="{ active: training.fitness_level === o.value }"
                @click="training.fitness_level = o.value">{{ o.icon }} {{ o.label }}</button>
      </div>

      <label class="modal-label">{{ $t('profile.trGoal') }}</label>
      <div class="pm-chips">
        <button v-for="o in goalOptions" :key="o.value" type="button" class="pm-chip"
                :class="{ active: training.running_goal === o.value }"
                @click="training.running_goal = o.value">{{ o.icon }} {{ o.label }}</button>
      </div>

      <label class="modal-label">{{ $t('profile.trVolume') }}</label>
      <div class="pm-chips">
        <button v-for="o in kmOptions" :key="o.value" type="button" class="pm-chip"
                :class="{ active: training.weekly_km === o.value }"
                @click="training.weekly_km = o.value">{{ o.label }}</button>
      </div>

      <label class="modal-label">{{ $t('profile.trDays') }}</label>
      <div class="pm-chips">
        <button v-for="o in dayOptions" :key="o.value" type="button" class="pm-chip"
                :class="{ active: training.training_days === o.value }"
                @click="training.training_days = o.value">{{ o.label }}</button>
      </div>

      <div v-if="trainingError" class="auth-error">{{ trainingError }}</div>
      <div class="modal-buttons">
        <button class="btn-primary" @click="saveTraining" :disabled="savingTraining">{{ $t('profile.save') }}</button>
        <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
      </div>
      <p class="pm-hint"><i class="fas fa-robot"></i> {{ $t('profile.trHint') }}</p>
    </div>

    <!-- Change password -->
    <div v-if="tab === 'password'" class="profile-tab-content active">
      <input type="password" v-model="pw.current" class="modal-input" :placeholder="$t('profile.currentPw')">
      <input type="password" v-model="pw.new_"    class="modal-input" :placeholder="$t('profile.newPw')">
      <input type="password" v-model="pw.confirm" class="modal-input" :placeholder="$t('profile.confirmPw')">
      <div v-if="pwError" class="auth-error">{{ pwError }}</div>
      <div class="modal-buttons">
        <button class="btn-primary" @click="savePassword" :disabled="savingPw">{{ $t('profile.changePw') }}</button>
        <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
      </div>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import BaseModal from '@/components/common/BaseModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import { usePush } from '@/composables/usePush'

const { t }   = useI18n()
const auth    = useAuthStore()
const show    = defineModel<boolean>({ default: false })
const tab     = ref<'info' | 'training' | 'password'>('info')
const savingInfo = ref(false); const infoError = ref('')
const savingTraining = ref(false); const trainingError = ref('')
const savingPw   = ref(false); const pwError   = ref('')
const push = usePush()

const info = ref({ name: '', age: null as number|null, weight: null as number|null, height: null as number|null, gender: '' as string })
const training = ref({ fitness_level: '' as string, running_goal: '' as string,
                       weekly_km: null as number|null, training_days: null as number|null })
const pw   = ref({ current: '', new_: '', confirm: '' })

// Те же варианты, что и в онбординге — их использует AI-тренер в планах и советах.
const fitnessOptions = [
  { value: 'beginner',     icon: '🌱', label: 'Начинающий' },
  { value: 'intermediate', icon: '🏃', label: 'Любитель' },
  { value: 'advanced',     icon: '🏅', label: 'Продвинутый' },
]
const goalOptions = [
  { value: '5k',            icon: '🎯', label: '5 км' },
  { value: '10k',           icon: '🎯', label: '10 км' },
  { value: 'half_marathon', icon: '🏁', label: 'Полумарафон' },
  { value: 'marathon',      icon: '🏆', label: 'Марафон' },
  { value: 'fitness',       icon: '❤️', label: 'Для здоровья' },
]
const kmOptions  = [
  { value: 0, label: '0 км' }, { value: 10, label: '~10 км' }, { value: 20, label: '~20 км' },
  { value: 30, label: '~30 км' }, { value: 40, label: '40+ км' },
]
const dayOptions = [
  { value: 2, label: '2 дня' }, { value: 3, label: '3 дня' }, { value: 4, label: '4 дня' }, { value: 5, label: '5+ дней' },
]

function open() {
  tab.value = 'info'; infoError.value = ''; pwError.value = ''; trainingError.value = ''
  info.value = { name: auth.user?.name ?? '', age: auth.user?.age ?? null,
                 weight: auth.user?.weight ?? null, height: auth.user?.height ?? null,
                 gender: auth.user?.gender ?? '' }
  training.value = { fitness_level: auth.user?.fitness_level ?? '', running_goal: auth.user?.running_goal ?? '',
                     weekly_km: auth.user?.weekly_km ?? null, training_days: auth.user?.training_days ?? null }
  pw.value = { current: '', new_: '', confirm: '' }
  show.value = true
  push.checkStatus()
}

function togglePush() {
  if (push.subscribed.value) push.unsubscribe()
  else push.subscribe()
}

async function saveInfo() {
  savingInfo.value = true; infoError.value = ''
  try {
    await auth.updateProfile({ name: info.value.name || undefined,
      age: info.value.age, weight: info.value.weight, height: info.value.height,
      gender: info.value.gender || undefined })
    show.value = false
    toast(t('profile.updated'))
  } catch (e: any) { infoError.value = e.message }
  finally { savingInfo.value = false }
}

async function saveTraining() {
  savingTraining.value = true; trainingError.value = ''
  try {
    await auth.updateProfile({
      fitness_level: training.value.fitness_level || undefined,
      running_goal:  training.value.running_goal || undefined,
      weekly_km:     training.value.weekly_km,
      training_days: training.value.training_days,
    })
    show.value = false
    toast(t('profile.updated'))
  } catch (e: any) { trainingError.value = e.message }
  finally { savingTraining.value = false }
}

async function savePassword() {
  if (pw.value.new_ !== pw.value.confirm) { pwError.value = t('profile.errMismatch'); return }
  savingPw.value = true; pwError.value = ''
  try {
    await auth.changePassword({ current_password: pw.value.current,
      new_password: pw.value.new_, confirm_password: pw.value.confirm })
    show.value = false
    toast(t('profile.pwUpdated'))
  } catch (e: any) { pwError.value = e.message }
  finally { savingPw.value = false }
}

function toast(msg: string) {
  const el = document.createElement('div')
  el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#22c55e;color:#fff;padding:12px 24px;border-radius:10px;font-weight:600;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.15)'
  el.textContent = msg; document.body.appendChild(el)
  setTimeout(() => el.remove(), 3500)
}

defineExpose({ open })
</script>

<style scoped>
.pm-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 4px; }
.pm-chip {
  border: 1px solid var(--border); background: var(--surface); color: var(--text-2);
  border-radius: 99px; padding: 8px 14px; font-size: 0.82rem; font-weight: 600;
  cursor: pointer; font-family: inherit; transition: border-color .15s, color .15s, background .15s;
}
.pm-chip:hover { border-color: var(--border-2); color: var(--text); }
.pm-chip.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.pm-hint { margin-top: 12px; font-size: 0.78rem; color: var(--text-3); display: flex; align-items: center; gap: 6px; }
.pm-hint i { color: var(--brand); }
</style>
