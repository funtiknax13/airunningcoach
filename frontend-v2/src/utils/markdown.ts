// Рендер markdown для AI-сообщений в чате. marked сам по себе НЕ экранирует
// сырой HTML в исходном тексте — если модель когда-нибудь дословно повторит
// содержимое (prompt injection через заметки/имена файлов, или просто
// галлюцинация), это уходило бы напрямую в v-html без какой-либо очистки.
// DOMPurify — обязательный шаг перед v-html, не косметика.
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

export function renderMd(content: string): string {
  return DOMPurify.sanitize(marked.parse(content) as string)
}
