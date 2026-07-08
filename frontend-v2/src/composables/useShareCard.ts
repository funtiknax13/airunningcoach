import { useI18n } from 'vue-i18n'

const CARD_SIZE = 1080
const BRAND = '#F85C1E'

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(' ')
  const lines: string[] = []
  let line = ''
  for (const word of words) {
    const test = line ? `${line} ${word}` : word
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line)
      line = word
    } else {
      line = test
    }
  }
  if (line) lines.push(line)
  return lines
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`failed to load ${src}`))
    img.src = src
  })
}

async function renderCard(opts: { emoji: string; title: string; subtitle: string; imageUrl?: string }): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = CARD_SIZE
  canvas.height = CARD_SIZE
  const ctx = canvas.getContext('2d')!

  const bg = ctx.createLinearGradient(0, 0, 0, CARD_SIZE)
  bg.addColorStop(0, '#161616')
  bg.addColorStop(1, '#0a0a0a')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, CARD_SIZE, CARD_SIZE)

  ctx.strokeStyle = BRAND
  ctx.lineWidth = 6
  ctx.strokeRect(24, 24, CARD_SIZE - 48, CARD_SIZE - 48)

  // Иконки достижений — двухцветный PNG (оранжевый + тёмный контур), рисовать
  // их на сплошном оранжевом круге нельзя — оранжевые части сольются с фоном
  // (та же история, что и с бейджами в интерфейсе). Светлый круг только когда
  // реально рисуем картинку; для эмодзи-фолбэка круг остаётся брендовым.
  const badgeImage = opts.imageUrl ? await loadImage(opts.imageUrl).catch(() => null) : null

  // Меряем текст заранее и центрируем всю группу (иконка + заголовок + подпись
  // + брендинг) как единое целое по вертикали. Раньше блок текста начинался с
  // фиксированного y, а подвал был жёстко прибит к низу карты — при коротком
  // заголовке/подписи (частый случай) между ними оставался большой пустой
  // провал, из-за чего карточка выглядела разбалансированной.
  ctx.textAlign = 'center'
  ctx.font = 'bold 64px sans-serif'
  const titleLines = wrapText(ctx, opts.title, CARD_SIZE - 160)
  ctx.font = '40px sans-serif'
  const subtitleLines = wrapText(ctx, opts.subtitle, CARD_SIZE - 200)

  const CIRCLE_D = 260
  const GAP_CIRCLE_TITLE = 70
  const TITLE_LH = 76
  const GAP_TITLE_SUB = 30
  const SUB_LH = 52
  const GAP_SUB_BRAND = 70
  const BRAND_BLOCK = 74

  const blockHeight =
    CIRCLE_D + GAP_CIRCLE_TITLE +
    titleLines.length * TITLE_LH + GAP_TITLE_SUB +
    subtitleLines.length * SUB_LH + GAP_SUB_BRAND +
    BRAND_BLOCK
  const top = (CARD_SIZE - blockHeight) / 2

  const circleCenterY = top + CIRCLE_D / 2
  ctx.beginPath()
  ctx.arc(CARD_SIZE / 2, circleCenterY, CIRCLE_D / 2, 0, Math.PI * 2)
  ctx.fillStyle = badgeImage ? '#FCEBE3' : BRAND
  ctx.fill()

  if (badgeImage) {
    const size = 190
    ctx.drawImage(badgeImage, CARD_SIZE / 2 - size / 2, circleCenterY - size / 2, size, size)
  } else {
    ctx.textBaseline = 'middle'
    ctx.font = '150px sans-serif'
    ctx.fillText(opts.emoji, CARD_SIZE / 2, circleCenterY + 10)
    ctx.textBaseline = 'alphabetic'
  }

  let y = top + CIRCLE_D + GAP_CIRCLE_TITLE + TITLE_LH * 0.7
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 64px sans-serif'
  for (const line of titleLines) {
    ctx.fillText(line, CARD_SIZE / 2, y)
    y += TITLE_LH
  }

  y += GAP_TITLE_SUB
  ctx.fillStyle = '#a3a3a3'
  ctx.font = '40px sans-serif'
  for (const line of subtitleLines) {
    ctx.fillText(line, CARD_SIZE / 2, y)
    y += SUB_LH
  }

  y += GAP_SUB_BRAND
  ctx.fillStyle = BRAND
  ctx.font = 'bold 34px sans-serif'
  ctx.fillText('AI RunningCoach', CARD_SIZE / 2, y)
  y += 40
  ctx.fillStyle = '#737373'
  ctx.font = '28px sans-serif'
  ctx.fillText('airunningcoach.pro', CARD_SIZE / 2, y)

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('canvas.toBlob failed'))), 'image/png')
  })
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function toast(msg: string) {
  const el = document.createElement('div')
  el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#22c55e;color:#fff;padding:12px 24px;border-radius:10px;font-weight:600;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.15)'
  el.textContent = msg
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 3500)
}

interface ShareOpts {
  emoji: string
  title: string
  subtitle: string
  utmCampaign: string
  imageUrl?: string
}

export function useShareCard() {
  const { t } = useI18n()

  async function share(opts: ShareOpts) {
    const blob = await renderCard(opts)
    const link = `https://airunningcoach.pro/?register=1&utm_source=share&utm_medium=achievement&utm_campaign=${opts.utmCampaign}`
    const caption = `${opts.emoji} ${opts.title} — ${opts.subtitle}. Тренируюсь с AI RunningCoach! ${link}`

    const file = new File([blob], 'achievement.png', { type: 'image/png' })
    const nav = navigator as Navigator & {
      canShare?: (data: { files?: File[] }) => boolean
      share?: (data: { files?: File[]; text?: string }) => Promise<void>
    }

    if (nav.canShare?.({ files: [file] }) && nav.share) {
      try {
        await nav.share({ files: [file], text: caption })
        return
      } catch (e) {
        if ((e as Error)?.name === 'AbortError') return
      }
    }

    downloadBlob(blob, 'achievement.png')
    try {
      await navigator.clipboard.writeText(caption)
    } catch {
      /* буфер обмена недоступен — не критично, картинка всё равно скачалась */
    }
    toast(t('achievements.shareFallback'))
  }

  return { share }
}
