<template>
  <BaseModal v-model="show">
    <h3>{{ editId ? $t('activities.modal.edit') : $t('activities.modal.add') }}</h3>

    <input type="datetime-local" v-model="form.date" class="modal-input">

    <select v-model="form.activity_type" class="modal-input">
      <option v-for="opt in activityTypes" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>

    <input type="number" v-model.number="form.distance_km"
           :placeholder="$t('activities.distance')" step="0.01" class="modal-input">

    <label class="modal-label">{{ $t('activities.timeLabel') }}</label>
    <TimeInput v-model="durationMin" />

    <input type="number" v-model.number="form.avg_heart_rate"
           :placeholder="$t('activities.hr')" class="modal-input">
    <textarea v-model="form.notes" :placeholder="$t('activities.notes')" class="modal-input"></textarea>

    <div v-if="error" class="auth-error">{{ error }}</div>

    <div class="modal-buttons">
      <button class="btn-primary" @click="save" :disabled="saving">
        {{ editId ? $t('activities.modal.saveEdit') : $t('btn.save') }}
      </button>
      <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import BaseModal from '@/components/common/BaseModal.vue'
import TimeInput from '@/components/common/TimeInput.vue'
import { useActivitiesStore } from '@/stores/activities'
import { activitiesApi } from '@/api'
import type { Activity } from '@/api/types'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const store = useActivitiesStore()

const show    = defineModel<boolean>({ default: false })
const editId  = ref<number | null>(null)
const saving  = ref(false)
const error   = ref('')
const durationMin = ref<number | null>(null)

const form = ref({
  date: '', distance_km: null as number | null,
  avg_heart_rate: null as number | null, notes: '',
  activity_type: 'run',
})

const activityTypes = computed(() => {
  const ru = locale.value === 'ru'
  return [
    { value: 'run',      label: ru ? 'Пробежка'    : 'Run' },
    { value: 'walk',     label: ru ? 'Прогулка'    : 'Walk' },
    { value: 'ride',     label: ru ? 'Велопоездка' : 'Ride' },
    { value: 'hike',     label: ru ? 'Поход'       : 'Hike' },
    { value: 'swim',     label: ru ? 'Плавание'    : 'Swim' },
    { value: 'strength', label: ru ? 'Силовая'     : 'Strength' },
    { value: 'workout',  label: ru ? 'Тренировка'  : 'Workout' },
    { value: 'other',    label: ru ? 'Другое'      : 'Other' },
  ]
})

async function open(id?: number) {
  error.value = ''; durationMin.value = null
  form.value = { date: '', distance_km: null, avg_heart_rate: null, notes: '', activity_type: 'run' }
  if (id) {
    editId.value = id
    const act = store.all.find(a => a.id === id)!
    const dt = new Date(act.date)
    const pad = (n: number) => String(n).padStart(2, '0')
    form.value.date = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`
    form.value.distance_km    = act.distance_km
    form.value.avg_heart_rate = act.avg_heart_rate
    form.value.notes          = act.notes ?? ''
    form.value.activity_type  = act.activity_type ?? 'run'
    durationMin.value         = act.duration_min
  } else {
    editId.value = null
  }
  show.value = true
}

async function save() {
  if (!form.value.date || !form.value.distance_km) { error.value = t('activities.errDateDist'); return }
  if (!durationMin.value || durationMin.value <= 0)  { error.value = t('activities.errTime'); return }
  saving.value = true; error.value = ''
  try {
    const data = {
      date: new Date(form.value.date).toISOString(),
      distance_km: form.value.distance_km!,
      duration_min: durationMin.value,
      avg_heart_rate: form.value.avg_heart_rate || null,
      notes: form.value.notes || null,
      activity_type: form.value.activity_type,
    }
    if (editId.value) await store.update(editId.value, data)
    else              await store.create(data)
    show.value = false
  } catch (e: any) { error.value = e.message }
  finally { saving.value = false }
}

defineExpose({ open })
</script>
