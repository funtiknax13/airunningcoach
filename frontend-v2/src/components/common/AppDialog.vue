<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="dialogState.visible" class="modal-overlay" @click.self="cancel">
        <div class="modal-box app-dialog" :class="{ 'app-dialog--danger': dialogState.type === 'danger' }">

          <div class="app-dialog-icon" v-if="dialogState.type === 'danger'">
            <i class="fas fa-triangle-exclamation"></i>
          </div>
          <div class="app-dialog-icon app-dialog-icon--prompt" v-else-if="dialogState.type === 'prompt'">
            <i class="fas fa-pencil"></i>
          </div>

          <h3 class="app-dialog-title">{{ dialogState.title }}</h3>
          <p v-if="dialogState.message" class="app-dialog-msg">{{ dialogState.message }}</p>

          <input
            v-if="dialogState.type === 'prompt'"
            ref="inputRef"
            v-model="dialogState.inputValue"
            class="modal-input"
            :placeholder="dialogState.inputPlaceholder"
            @keyup.enter="confirm"
            @keyup.escape="cancel"
          />

          <div class="modal-buttons">
            <button
              class="btn-primary"
              :class="{ 'btn-danger': dialogState.type === 'danger' }"
              @click="confirm"
            >
              {{ dialogState.confirmLabel || t('btn.confirm') }}
            </button>
            <button class="btn-secondary" @click="cancel">
              {{ dialogState.cancelLabel || t('btn.cancel') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { dialogState } from '@/composables/useDialog'

const { t } = useI18n()
const inputRef = ref<HTMLInputElement | null>(null)

watch(() => dialogState.visible, (v) => {
  if (v && dialogState.type === 'prompt') {
    nextTick(() => inputRef.value?.focus())
  }
})

function confirm() {
  if (!dialogState.resolve) return
  if (dialogState.type === 'prompt') {
    dialogState.resolve(dialogState.inputValue)
  } else {
    dialogState.resolve(true)
  }
  dialogState.visible = false
}

function cancel() {
  if (!dialogState.resolve) return
  dialogState.resolve(null)
  dialogState.visible = false
}
</script>
