<template>
  <BaseModal v-model="show">
    <div class="profile-tab-content active">
      <h3 style="margin: 0 0 12px;">{{ $t('support.title') }}</h3>
      <input type="text" v-model="subject" class="modal-input" :placeholder="$t('support.subject')" maxlength="150">
      <textarea v-model="message" class="modal-input" rows="5" :placeholder="$t('support.message')" maxlength="3000"></textarea>
      <div v-if="error" class="auth-error">{{ error }}</div>
      <div v-if="sent" style="color: #22c55e; font-weight: 600; margin: 8px 0;">{{ $t('support.sent') }}</div>
      <div class="modal-buttons">
        <button class="btn-primary" @click="submit" :disabled="sending || sent">{{ $t('support.send') }}</button>
        <button class="btn-secondary" @click="show = false">{{ $t('btn.cancel') }}</button>
      </div>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/common/BaseModal.vue'
import { supportApi } from '@/api'

const { t, locale } = useI18n()
const show = defineModel<boolean>({ default: false })

const subject = ref('')
const message = ref('')
const sending = ref(false)
const sent = ref(false)
const error = ref('')

function open() {
  subject.value = ''; message.value = ''; error.value = ''; sent.value = false
  show.value = true
}

async function submit() {
  error.value = ''
  if (!subject.value.trim() || message.value.trim().length < 10) {
    error.value = t('support.errValidation')
    return
  }
  sending.value = true
  try {
    await supportApi.contact(subject.value.trim(), message.value.trim(), locale.value)
    sent.value = true
  } catch (e: any) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}

defineExpose({ open })
</script>
