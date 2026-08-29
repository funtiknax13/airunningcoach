// Подставляет реальный build id вместо __SW_CACHE_VERSION__ в уже собранный
// dist/sw.js. Отдельный шаг ПОСЛЕ `vite build` (см. package.json), а не
// Vite-плагин — плагин через buildStart/closeBundle гонялся с копированием
// public/ в dist в непредсказуемом порядке и не всегда успевал сработать.
// Здесь всё просто: vite build к этому моменту уже полностью завершён, dist/sw.js
// гарантированно на месте.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const distSwPath = fileURLToPath(new URL('../../frontend-v2-dist/sw.js', import.meta.url))
const buildId = Date.now().toString()

const content = readFileSync(distSwPath, 'utf-8')
if (!content.includes('__SW_CACHE_VERSION__')) {
  console.error(`inject-sw-version: placeholder not found in ${distSwPath} — sw.js changed?`)
  process.exit(1)
}
// replaceAll (не replace) — на случай, если плейсхолдер когда-нибудь встретится
// больше одного раза (комментарий + код и т.п.), не оставляем второе вхождение
// нетронутым молча.
writeFileSync(distSwPath, content.replaceAll('__SW_CACHE_VERSION__', buildId))
console.log(`inject-sw-version: dist/sw.js CACHE version -> ${buildId}`)
