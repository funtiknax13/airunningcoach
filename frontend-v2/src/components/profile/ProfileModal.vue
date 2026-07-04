<template>
  <BaseModal v-model="show">
    <div class="profile-modal-tabs">
      <button class="profile-tab" :class="{ active: tab === 'info' }"
              @click="tab = 'info'">{{ $t('profile.tabInfo') }}</button>
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
const tab     = ref<'info' | 'password'>('info')
const savingInfo = ref(false); const infoError = ref('')
const savingPw   = ref(false); const pwError   = ref('')
const push = usePush()

const info = ref({ name: '', age: null as number|null, weight: null as number|null, height: null as number|null })
const pw   = ref({ current: '', new_: '', confirm: '' })

function open() {
  tab.value = 'info'; infoError.value = ''; pwError.value = ''
  info.value = { name: auth.user?.name ?? '', age: auth.user?.age ?? null,
                 weight: auth.user?.weight ?? null, height: auth.user?.height ?? null }
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
      age: info.value.age, weight: info.value.weight, height: info.value.height })
    show.value = false
    toast(t('profile.updated'))
  } catch (e: any) { infoError.value = e.message }
  finally { savingInfo.value = false }
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
