<template>
  <div class="auth-page active">
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-logo">
          <div class="logo-icon"><i class="fas fa-robot"></i></div>
          <h2>AI PaceMaker</h2>
          <p>{{ $t('auth.tagline') }}</p>
        </div>

        <!-- Login -->
        <div v-if="screen === 'login'" class="auth-form active">
          <input type="email" v-model="email" class="auth-input" placeholder="Email">
          <input type="password" v-model="password" class="auth-input" :placeholder="$t('auth.pw')"
                 @keyup.enter="login">
          <div v-if="error" class="auth-error">{{ error }}</div>
          <button class="auth-btn" @click="login" :disabled="loading">{{ $t('auth.login.btn') }}</button>
          <div class="auth-switch"><span @click="screen='forgot'">{{ $t('auth.login.forgot') }}</span></div>
          <div class="auth-switch">
            {{ $t('auth.login.noAccount') }}
            <span @click="screen='register'">{{ $t('auth.login.regLink') }}</span>
          </div>
        </div>

        <!-- Register -->
        <div v-if="screen === 'register'" class="auth-form active">
          <input type="text"     v-model="reg.name"    class="auth-input" :placeholder="$t('auth.reg.name')">
          <input type="email"    v-model="reg.email"   class="auth-input" placeholder="Email">
          <input type="password" v-model="reg.password" class="auth-input" :placeholder="$t('auth.pwMin')">
          <input type="password" v-model="reg.confirm"  class="auth-input" :placeholder="$t('auth.pwRepeat')">
          <input type="number"   v-model.number="reg.age"    class="auth-input" :placeholder="$t('auth.reg.age')">
          <input type="number"   v-model.number="reg.weight" class="auth-input" :placeholder="$t('auth.reg.weight')">
          <input type="number"   v-model.number="reg.height" class="auth-input" :placeholder="$t('auth.reg.height')">
          <div v-if="error" class="auth-error">{{ error }}</div>
          <button class="auth-btn" @click="register" :disabled="loading">{{ $t('auth.reg.btn') }}</button>
          <div class="auth-switch">
            {{ $t('auth.reg.haveAccount') }}
            <span @click="screen='login'">{{ $t('auth.reg.loginLink') }}</span>
          </div>
        </div>

        <!-- Forgot password -->
        <div v-if="screen === 'forgot'" class="auth-form active">
          <h3 style="margin-bottom:8px">{{ $t('auth.forgot.title') }}</h3>
          <p style="color:#6b7280;font-size:14px;margin-bottom:12px">{{ $t('auth.forgot.desc') }}</p>
          <input type="email" v-model="email" class="auth-input" placeholder="Email">
          <div v-if="error" class="auth-error">{{ error }}</div>
          <button class="auth-btn" @click="forgotPassword" :disabled="loading">{{ $t('auth.forgot.btn') }}</button>
          <div class="auth-switch"><span @click="screen='login'">{{ $t('auth.forgot.back') }}</span></div>
        </div>

        <!-- Reset password -->
        <div v-if="screen === 'reset'" class="auth-form active">
          <h3 style="margin-bottom:8px">{{ $t('auth.reset.title') }}</h3>
          <input type="password" v-model="resetPw"      class="auth-input" :placeholder="$t('auth.reset.pw')">
          <input type="password" v-model="resetConfirm" class="auth-input" :placeholder="$t('auth.pwRepeat')">
          <div v-if="error" class="auth-error">{{ error }}</div>
          <button class="auth-btn" @click="resetPassword" :disabled="loading">{{ $t('auth.reset.btn') }}</button>
        </div>

        <!-- Verify notice -->
        <div v-if="screen === 'verify'" class="auth-form active" style="text-align:center">
          <div style="font-size:48px;margin-bottom:12px">📧</div>
          <h3 style="margin-bottom:8px">{{ $t('auth.verify.title') }}</h3>
          <p style="color:#6b7280;font-size:14px;margin-bottom:20px">{{ verifyText }}</p>
          <button class="auth-btn" style="font-size:14px;padding:10px"
                  @click="resend" :disabled="loading">{{ $t('auth.verify.resend') }}</button>
          <div class="auth-switch"><span @click="screen='login'">{{ $t('auth.verify.back') }}</span></div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const { locale } = useI18n()
const auth    = useAuthStore()
const screen  = ref<'login'|'register'|'forgot'|'reset'|'verify'>('login')
const email   = ref(''); const password = ref(''); const loading = ref(false); const error = ref('')
const verifyText = ref(''); const resetToken = ref(''); const resetPw = ref(''); const resetConfirm = ref('')
const reg = ref({ name:'', email:'', password:'', confirm:'', age: null as number|null, weight: null as number|null, height: null as number|null })

onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const tok = params.get('reset_token')
  if (tok) { resetToken.value = tok; screen.value = 'reset'; history.replaceState({}, '', '/') }
  if (params.get('verified') === '1') { screen.value = 'login'; history.replaceState({}, '', '/') }
})

async function login() {
  loading.value = true; error.value = ''
  try { await auth.login(email.value, password.value) }
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
</script>
