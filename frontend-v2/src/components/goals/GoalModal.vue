<template>
  <BaseModal v-model="show">
    <h3>{{ editId ? $t('goals.modal.edit') : $t('goals.modal.add') }}</h3>

    <select v-model="form.goal_type" class="modal-input" @change="onTypeChange">
      <option value="half_marathon">{{ $t('goals.type.half_marathon') }}</option>
      <option value="full_marathon">{{ $t('goals.type.full_marathon') }}</option>
      <option value="10k">{{ $t('goals.type.10k') }}</option>
      <option value="5k">{{ $t('goals.type.5k') }}</option>
      <option value="custom">{{ $t('goals.type.custom') }}</option>
    </select>

    <input type="number" v-model.number="form.target_distance_km"
           :placeholder="$t('goals.distance')" step="0.01" class="modal-input"
           :readonly="isPreset" :style="isPreset ? 'background:#f1f5f9;color:#64748b' : ''">

    <label class="modal-label">{{ $t('goals.timeLabel') }}</label>
    <TimeInput v-model="targetTimeMin" />

    <input type="date" v-model="form.target_date" class="modal-input">
    <textarea v-model="form.description" :placeholder="$t('goals.description')" class="modal-input"></textarea>

    <div v-if="error" class="auth-error">{{ error }}</div>

    <div class="modal-buttons">
      <button class="btn-primary" @click="save" :disabled="saving">
        {{ editId ? $t('goals.modal.saveEdit') : $t('btn.save') }}
      </button>
      <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import BaseModal from '@/components/common/BaseModal.vue'
import TimeInput from '@/components/common/TimeInput.vue'
import { useGoalsStore } from '@/stores/goals'
import { useI18n } from 'vue-i18n'
import type { GoalType } from '@/api/types'

const { t }   = useI18n()
const store   = useGoalsStore()
const show    = defineModel<boolean>({ default: false })
const editId  = ref<number | null>(null)
const saving  = ref(false)
const error   = ref('')
const targetTimeMin = ref<number | null>(null)

const PRESETS: Record<string, number> = {
  half_marathon: 21.1, full_marathon: 42.195, '10k': 10, '5k': 5,
}

const form = ref({
  goal_type: 'half_marathon' as GoalType,
  target_distance_km: null as number | null,
  target_date: '',
  description: '',
})

const isPreset = computed(() => form.value.goal_type !== 'custom')

function onTypeChange() {
  const p = PRESETS[form.value.goal_type]
  form.value.target_distance_km = p ?? null
}

function open(id?: number) {
  error.value = ''; targetTimeMin.value = null
  form.value = { goal_type: 'half_marathon', target_distance_km: null, target_date: '', description: '' }
  if (id) {
    editId.value = id
    const g = store.goals.find(x => x.id === id)!
    form.value.goal_type           = g.goal_type
    form.value.target_distance_km  = g.target_distance_km
    form.value.target_date         = g.target_date ? g.target_date.slice(0, 10) : ''
    form.value.description         = g.description ?? ''
    targetTimeMin.value            = g.target_time_min
  } else {
    editId.value = null
    onTypeChange()
  }
  show.value = true
}

async function save() {
  saving.value = true; error.value = ''
  try {
    const data = {
      goal_type: form.value.goal_type,
      target_distance_km: form.value.target_distance_km,
      target_time_min: targetTimeMin.value,
      target_date: form.value.target_date ? new Date(form.value.target_date).toISOString() : null,
      description: form.value.description || null,
    }
    if (editId.value) await store.update(editId.value, data)
    else              await store.create(data)
    show.value = false
  } catch (e: any) { error.value = e.message }
  finally { saving.value = false }
}

defineExpose({ open })
</script>
