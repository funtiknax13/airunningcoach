<template>
  <div class="card">
    <div class="card-title">
      <i class="fas fa-bullseye"></i> {{ $t('goals.title') }}
      <button class="btn-primary" style="margin-left:auto" @click="modal?.open()">
        <i class="fas fa-plus"></i> {{ $t('goals.add') }}
      </button>
    </div>

    <p v-if="!store.goals.length" style="text-align:center;color:#94a3b8;padding:8px 0">
      {{ $t('goals.empty') }}
    </p>

    <GoalCard
      v-for="g in store.goals" :key="g.id" :goal="g"
      @edit="modal?.open($event)"
      @achieve="confirm($event, 'achieve')"
      @abandon="confirm($event, 'abandon')"
      @reactivate="store.reactivate($event)"
      @delete="confirm($event, 'delete')"
    />

    <GoalModal ref="modal" v-model="showModal" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGoalsStore } from '@/stores/goals'
import { useI18n } from 'vue-i18n'
import GoalCard  from './GoalCard.vue'
import GoalModal from './GoalModal.vue'

const store      = useGoalsStore()
const { t }      = useI18n()
const modal      = ref<InstanceType<typeof GoalModal> | null>(null)
const showModal  = ref(false)

async function confirm(id: number, action: 'achieve'|'abandon'|'delete') {
  const msgs: Record<typeof action, string> = {
    achieve: 'goals.confirmAchieve',
    abandon: 'goals.confirmAbandon',
    delete:  'goals.confirmDelete',
  }
  if (!window.confirm(t(msgs[action]))) return
  if (action === 'achieve') await store.achieve(id)
  else if (action === 'abandon') await store.abandon(id)
  else await store.remove(id)
}
</script>
