<template>
  <div class="card">
    <div class="card-title">
      <i class="fas fa-person-running"></i>
      {{ $t('activities.title') }}
      <button class="btn-primary" style="margin-left:auto" @click="modal?.open()">
        <i class="fas fa-plus"></i> {{ $t('activities.add') }}
      </button>
    </div>

    <p v-if="!store.current.length" style="text-align:center;color:#94a3b8;">
      {{ $t('activities.empty') }}
    </p>

    <ActivityCard
      v-for="act in store.current" :key="act.id" :activity="act"
      @edit="modal?.open($event)"
      @delete="confirmDelete"
    />

    <!-- Pager -->
    <div v-if="store.pages > 1" class="pager">
      <button class="pager-btn" :disabled="store.page === 0" @click="store.setPage(store.page - 1)">
        <i class="fas fa-chevron-left"></i>
      </button>
      <span class="pager-info">{{ store.page + 1 }} / {{ store.pages }}</span>
      <button class="pager-btn" :disabled="store.page >= store.pages - 1" @click="store.setPage(store.page + 1)">
        <i class="fas fa-chevron-right"></i>
      </button>
    </div>

    <ActivityModal ref="modal" v-model="showModal" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useActivitiesStore } from '@/stores/activities'
import { useI18n } from 'vue-i18n'
import ActivityCard  from './ActivityCard.vue'
import ActivityModal from './ActivityModal.vue'

const store     = useActivitiesStore()
const { t }     = useI18n()
const modal     = ref<InstanceType<typeof ActivityModal> | null>(null)
const showModal = ref(false)

async function confirmDelete(id: number) {
  if (!confirm(t('activities.confirmDelete'))) return
  await store.remove(id)
}
</script>
