const ACTIVITY_ICONS: Record<string, string> = {
  run:      'fas fa-person-running',
  ride:     'fas fa-bicycle',
  walk:     'fas fa-person-walking',
  hike:     'fas fa-mountain',
  swim:     'fas fa-person-swimming',
  strength: 'fas fa-dumbbell',
  workout:  'fas fa-heart-pulse',
  other:    'fas fa-bolt',
}
export function activityIcon(type: string | null | undefined): string {
  return ACTIVITY_ICONS[type ?? 'run'] ?? 'fas fa-person-running'
}

const ACTIVITY_LABELS: Record<string, Record<string, string>> = {
  run:      { ru: 'Пробежка', en: 'Run' },
  ride:     { ru: 'Велопоездка', en: 'Ride' },
  walk:     { ru: 'Прогулка', en: 'Walk' },
  hike:     { ru: 'Поход', en: 'Hike' },
  swim:     { ru: 'Плавание', en: 'Swim' },
  strength: { ru: 'Силовая', en: 'Strength' },
  workout:  { ru: 'Тренировка', en: 'Workout' },
  other:    { ru: 'Активность', en: 'Activity' },
}
export function activityLabel(type: string | null | undefined, locale: string): string {
  const lang = locale === 'ru' ? 'ru' : 'en'
  return ACTIVITY_LABELS[type ?? 'run']?.[lang] ?? (lang === 'ru' ? 'Пробежка' : 'Run')
}
