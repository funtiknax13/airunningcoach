import { createI18n } from 'vue-i18n'
import ru from './ru'
import en from './en'

const saved = localStorage.getItem('lang')
const browser = (navigator.language || 'ru').toLowerCase()
const locale = saved ?? (browser.startsWith('ru') ? 'ru' : 'en')

export const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'ru',
  messages: { ru, en },
})

export function toggleLang() {
  const current = i18n.global.locale.value
  const next = current === 'ru' ? 'en' : 'ru'
  i18n.global.locale.value = next
  localStorage.setItem('lang', next)
  document.documentElement.lang = next
}
