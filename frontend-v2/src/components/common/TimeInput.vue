<template>
  <div class="time-inputs">
    <div class="time-field">
      <input type="number" :value="h" @input="onH" min="0" max="99"
             placeholder="0" class="modal-input time-input">
      <span class="time-label">{{ $t('time.h') }}</span>
    </div>
    <div class="time-field">
      <input type="number" :value="m" @input="onM" min="0" max="59"
             placeholder="0" class="modal-input time-input">
      <span class="time-label">{{ $t('time.min') }}</span>
    </div>
    <div class="time-field">
      <input type="number" :value="s" @input="onS" min="0" max="59"
             placeholder="0" class="modal-input time-input">
      <span class="time-label">{{ $t('time.sec') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// modelValue = total minutes (float)
const props = defineProps<{ modelValue: number | null }>()
const emit  = defineEmits<{ (e: 'update:modelValue', v: number | null): void }>()

const totalSec = computed(() => Math.round((props.modelValue ?? 0) * 60))
const h = computed(() => Math.floor(totalSec.value / 3600))
const m = computed(() => Math.floor((totalSec.value % 3600) / 60))
const s = computed(() => totalSec.value % 60)

function emit_(hv: number, mv: number, sv: number) {
  const total = hv * 60 + mv + sv / 60
  emit('update:modelValue', total > 0 ? total : null)
}
const onH = (e: Event) => emit_(+(e.target as HTMLInputElement).value || 0, m.value, s.value)
const onM = (e: Event) => emit_(h.value, +(e.target as HTMLInputElement).value || 0, s.value)
const onS = (e: Event) => emit_(h.value, m.value, +(e.target as HTMLInputElement).value || 0)
</script>
