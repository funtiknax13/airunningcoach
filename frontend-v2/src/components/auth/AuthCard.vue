<template>
  <div class="auth-card">
    <div class="auth-logo">
      <div class="auth-logo-icon">
        <img src="/images/logo.png" alt="logo">
      </div>
      <div class="auth-app-name"><span>AI</span>RunningCoach</div>
      <div class="auth-tagline">{{ $t('auth.tagline') }}</div>
    </div>

    <!-- Login -->
    <div v-if="screen === 'login'" class="auth-form active">
      <div class="auth-form-title">{{ $t('auth.login.title') }}</div>
      <input type="email"    v-model="email"    class="auth-input" placeholder="Email" @keyup.enter="login">
      <input type="password" v-model="password" class="auth-input" :placeholder="$t('auth.pw')" @keyup.enter="login">
      <div v-if="error" class="auth-error">{{ error }}</div>
      <button class="auth-btn" @click="login" :disabled="loading">
        {{ loading ? '...' : $t('auth.login.btn') }}
      </button>
      <div class="auth-switch"><span @click="screen='forgot'">{{ $t('auth.login.forgot') }}</span></div>
      <div class="auth-switch">
        {{ $t('auth.login.noAccount') }}
        <span @click="screen='register'">{{ $t('auth.login.regLink') }}</span>
      </div>
      <div class="auth-divider"><span>или</span></div>
      <button class="auth-btn-google" @click="loginWithGoogle">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
          <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z" fill="#34A853"/>
          <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
          <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
        </svg>
        Войти через Google
      </button>
      <div v-if="canClose" class="auth-switch" style="margin-top:8px">
        <span @click="$emit('close')">✕ {{ $t('btn.cancel') }}</span>
      </div>
    </div>

    <!-- Register -->
    <div v-if="screen === 'register'" class="auth-form active">
      <div class="auth-form-title">{{ $t('auth.reg.title') }}</div>
      <input type="text"     v-model="reg.name"     class="auth-input" :placeholder="$t('auth.reg.name')">
      <input type="email"    v-model="reg.email"    class="auth-input" placeholder="Email">
      <input type="password" v-model="reg.password" class="auth-input" :placeholder="$t('auth.pwMin')">
      <input type="password" v-model="reg.confirm"  class="auth-input" :placeholder="$t('auth.pwRepeat')">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:2px">
        <input type="number" v-model.number="reg.age"    class="auth-input" :placeholder="$t('auth.reg.age')"    style="margin:0">
        <input type="number" v-model.number="reg.weight" class="auth-input" :placeholder="$t('auth.reg.weight')" style="margin:0">
        <input type="number" v-model.number="reg.height" class="auth-input" :placeholder="$t('auth.reg.height')" style="margin:0">
      </div>
      <div v-if="error" class="auth-error">{{ error }}</div>
      <button class="auth-btn" @click="register" :disabled="loading">
        {{ loading ? '...' : $t('auth.reg.btn') }}
      </button>
      <div class="auth-switch">
        {{ $t('auth.reg.haveAccount') }}
        <span @click="screen='login'">{{ $t('auth.reg.loginLink') }}</span>
      </div>
      <div class="auth-divider"><span>или</span></div>
      <button class="auth-btn-google" @click="loginWithGoogle">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
          <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z" fill="#34A853"/>
          <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
          <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
        </svg>
        Зарегистрироваться через Google
      </button>
      <div v-if="canClose" class="auth-switch" style="margin-top:8px">
        <span @click="$emit('close')">✕ {{ $t('btn.cancel') }}</span>
      </div>
    </div>

    <!-- Forgot -->
    <div v-if="screen === 'forgot'" class="auth-form active">
      <div class="auth-form-title">{{ $t('auth.forgot.title') }}</div>
      <p style="color:var(--text-2);font-size:0.85rem;margin-bottom:12px">{{ $t('auth.forgot.desc') }}</p>
      <input type="email" v-model="email" class="auth-input" placeholder="Email">
      <div v-if="error" class="auth-error">{{ error }}</div>
      <button class="auth-btn" @click="forgotPassword" :disabled="loading">{{ $t('auth.forgot.btn') }}</button>
      <div class="auth-switch"><span @click="screen='login'">{{ $t('auth.forgot.back') }}</span></div>
    </div>

    <!-- Reset -->
    <div v-if="screen === 'reset'" class="auth-form active">
      <div class="auth-form-title">{{ $t('auth.reset.title') }}</div>
      <input type="password" v-model="resetPw"      class="auth-input" :placeholder="$t('auth.reset.pw')">
      <input type="password" v-model="resetConfirm" class="auth-input" :placeholder="$t('auth.pwRepeat')">
      <div v-if="error" class="auth-error">{{ error }}</div>
      <button class="auth-btn" @click="resetPassword" :disabled="loading">{{ $t('auth.reset.btn') }}</button>
    </div>

    <!-- Verify notice -->
    <div v-if="screen === 'verify'" class="auth-form active" style="text-align:center">
      <div style="font-size:3rem;margin-bottom:10px">📧</div>
      <div class="auth-form-title">{{ $t('auth.verify.title') }}</div>
      <p style="color:var(--text-2);font-size:0.85rem;margin-bottom:16px">{{ verifyText }}</p>
      <button class="auth-btn" style="font-size:0.85rem;padding:10px"
              @click="resend" :disabled="loading">{{ $t('auth.verify.resend') }}</button>
      <div class="auth-switch"><span @click="screen='login'">{{ $t('auth.verify.back') }}</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useActivitiesStore } from '@/stores/activities'
import { useGoalsStore } from '@/stores/goals'
import { useTrainingStore } from '@/stores/training'
import { useChatStore } from '@/stores/chat'
import { useInsightsStore } from '@/stores/insights'

const props = defineProps<{ initialScreen?: 'login'|'register'; canClose?: boolean }>()
defineEmits(['close'])

const router     = useRouter()
const { locale } = useI18n()
const auth       = useAuthStore()
const activities = useActivitiesStore()
const goals      = useGoalsStore()
const training   = useTrainingStore()
const chat       = useChatStore()
const insights   = useInsightsStore()

const screen  = ref<'login'|'register'|'forgot'|'reset'|'verify'>(props.initialScreen ?? 'login')
const email   = ref('')
const password = ref('')
const loading = ref(false)
const error   = ref('')
const verifyText  = ref('')
const resetToken  = ref('')
const resetPw     = ref('')
const resetConfirm = ref('')
const reg = ref({ name:'', email:'', password:'', confirm:'',
  age: null as number|null, weight: null as number|null, height: null as number|null })

onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const tok = params.get('reset_token')
  if (tok) { resetToken.value = tok; screen.value = 'reset'; history.replaceState({}, '', '/') }
  if (params.get('verified') === '1') { screen.value = 'login'; history.replaceState({}, '', '/') }
})

async function afterLogin() {
  await Promise.all([activities.load(), goals.load(), training.load(), chat.load(), insights.load()])
  router.push('/dashboard')
}

async function login() {
  loading.value = true; error.value = ''
  try { await auth.login(email.value, password.value); await afterLogin() }
  catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}

async function register() {
  if (reg.value.password !== reg.value.confirm) { error.value = 'Пароли не совпадают'; return }
  loading.value = true; error.value = ''
  try {
    await authApi.register({ email: reg.value.email, password: reg.value.password,
      confirm_password: reg.value.confirm, name: reg.value.name,
      age: reg.value.age, weight: reg.value.weight, height: reg.value.height,
      lang: locale.value })
    verifyText.value = `Письмо отправлено на ${reg.value.email}`
    screen.value = 'verify'
  } catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}

async function forgotPassword() {
  loading.value = true; error.value = ''
  try {
    await authApi.forgotPassword(email.value, locale.value)
    verifyText.value = `Ссылка для сброса отправлена на ${email.value}`
    screen.value = 'verify'
  } catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}

async function resetPassword() {
  loading.value = true; error.value = ''
  try {
    await authApi.resetPassword(resetToken.value, resetPw.value, resetConfirm.value)
    screen.value = 'login'
  } catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}

async function resend() {
  loading.value = true
  try { await authApi.resendVerification(reg.value.email || email.value) }
  finally { loading.value = false }
}

function loginWithGoogle() {
  window.location.href = '/auth/google'
}
</script>
