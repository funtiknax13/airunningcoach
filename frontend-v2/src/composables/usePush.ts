import { ref } from 'vue'
import { pushApi } from '@/api'

const supported = 'serviceWorker' in navigator && 'PushManager' in window
const subscribed = ref(false)
const loading = ref(false)

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const base64Safe = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64Safe)
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}

async function checkStatus() {
  if (!supported) return
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  subscribed.value = !!sub
}

async function subscribe() {
  if (!supported || loading.value) return false
  loading.value = true
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') return false

    const { key } = await pushApi.vapidKey()
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key) as BufferSource,
    })
    await pushApi.subscribe(sub.toJSON() as PushSubscriptionJSON)
    subscribed.value = true
    return true
  } finally {
    loading.value = false
  }
}

async function unsubscribe() {
  if (!supported || loading.value) return
  loading.value = true
  try {
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    if (sub) {
      await pushApi.unsubscribe(sub.endpoint)
      await sub.unsubscribe()
    }
    subscribed.value = false
  } finally {
    loading.value = false
  }
}

export function usePush() {
  return { supported, subscribed, loading, checkStatus, subscribe, unsubscribe }
}
