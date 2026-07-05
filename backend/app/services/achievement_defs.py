# app/services/achievement_defs.py
"""
Каталог «достижений» — дискретных разовых событий, в отличие от PersonalRecord
(который про личный рекорд времени на дистанции). Достижение либо есть, либо
его нет — это факт свершения, а не измерение.

Порядок списка = порядок отображения в сетке (группировка по смыслу, от
активации к продвинутым/бонусным категориям, финал — completionist).

"points" — скрытая внутренняя оценка ценности/редкости, не показывается
пользователю; зарезервирована под будущую сортировку/тотал-скор.

type:
  "count"           — суммарное число пробежек за всё время >= value
  "distance"        — хотя бы одна пробежка с distance_km >= value
  "total_distance"  — суммарный км за всё время >= value
  "monthly_volume"  — сумма км за какой-либо календарный месяц >= value
  "streak"          — >= weeks подряд недель, в каждой из которых >= min_per_week пробежек
  "pace"            — хотя бы одна пробежка ~distance_km за <= max_time_min минут
  "comeback"        — где-либо в истории пропуск >= gap_days дней между соседними пробежками
  "time_of_day"      — хотя бы одна пробежка начата до before_hour / после after_hour
  "elevation"       — хотя бы одна пробежка с elevation_gain >= value
  "elevation_total" — суммарный набор высоты за всё время >= value
  "plan_adherence"  — "plan_week_perfect": была хотя бы одна полностью выполненная неделя плана;
                       "plan_discipline": >= weeks подряд недель без "не подтверждена"
  "goal"            — есть хотя бы одна достигнутая цель (Goal.is_achieved)
  "variety"         — выполнены тренировки >= min_types разных типов
  "meta"            — получены все достижения, кроме перечисленных в exclude
"""

ACHIEVEMENT_DEFS = [
    {"key": "first_run", "label": "Первая пробежка", "description": "Самая первая тренировка в приложении",
     "icon": "fa-play", "type": "count", "value": 1, "points": 5},

    {"key": "workouts_5", "label": "Первые шаги", "description": "Выполнено 5 тренировок",
     "icon": "fa-shoe-prints", "type": "count", "value": 5, "points": 10},
    {"key": "workouts_25", "label": "Втянулся", "description": "Выполнено 25 тренировок",
     "icon": "fa-layer-group", "type": "count", "value": 25, "points": 30},
    {"key": "workouts_100", "label": "Сотня тренировок", "description": "Выполнено 100 тренировок",
     "icon": "fa-crown", "type": "count", "value": 100, "points": 100},

    {"key": "distance_5k", "label": "Пятёрка", "description": "Пробежал 5 км за одну тренировку",
     "icon": "fa-flag-checkered", "type": "distance", "value": 5.0, "points": 10},
    {"key": "fast_5k", "label": "Быстрая пятёрка", "description": "5 км быстрее 25 минут",
     "icon": "fa-bolt-lightning", "type": "pace", "distance_km": 5.0, "max_time_min": 25.0, "points": 50},
    {"key": "distance_10k", "label": "Десятка", "description": "Пробежал 10 км за одну тренировку",
     "icon": "fa-road", "type": "distance", "value": 10.0, "points": 20},
    {"key": "distance_half", "label": "Полумарафонец", "description": "Пробежал полумарафон",
     "icon": "fa-person-running", "type": "distance", "value": 21.0975, "points": 60},
    {"key": "distance_marathon", "label": "Марафонец", "description": "Пробежал марафон",
     "icon": "fa-medal", "type": "distance", "value": 42.195, "points": 150},
    {"key": "distance_ultra", "label": "Ультрамарафонец", "description": "Пробежал 50 км за одну тренировку",
     "icon": "fa-fire-flame-curved", "type": "distance", "value": 50.0, "points": 250},

    {"key": "total_100", "label": "Первая сотня", "description": "100 км суммарно за всё время",
     "icon": "fa-route", "type": "total_distance", "value": 100.0, "points": 20},
    {"key": "total_500", "label": "Полтысячи", "description": "500 км суммарно",
     "icon": "fa-map", "type": "total_distance", "value": 500.0, "points": 60},
    {"key": "total_1000", "label": "Тысяча километров", "description": "1000 км суммарно",
     "icon": "fa-globe", "type": "total_distance", "value": 1000.0, "points": 150},
    {"key": "total_5000", "label": "Марафон длиною в жизнь", "description": "5000 км суммарно",
     "icon": "fa-earth-americas", "type": "total_distance", "value": 5000.0, "points": 400},

    {"key": "month_50", "label": "Разогнался", "description": "50 км за календарный месяц",
     "icon": "fa-calendar-check", "type": "monthly_volume", "value": 50.0, "points": 20},
    {"key": "month_100", "label": "Сотка за месяц", "description": "100 км за календарный месяц",
     "icon": "fa-fire", "type": "monthly_volume", "value": 100.0, "points": 60},
    {"key": "month_200", "label": "Марафонский темп жизни", "description": "200 км за календарный месяц",
     "icon": "fa-bolt", "type": "monthly_volume", "value": 200.0, "points": 150},

    {"key": "streak_4weeks", "label": "Месяц без пропусков", "description": "≥3 пробежки в каждую из 4 недель подряд",
     "icon": "fa-link", "type": "streak", "weeks": 4, "min_per_week": 3, "points": 90},
    {"key": "streak_12weeks", "label": "Три месяца в ритме", "description": "≥3 пробежки в каждую из 12 недель подряд",
     "icon": "fa-calendar-week", "type": "streak", "weeks": 12, "min_per_week": 3, "points": 220},
    {"key": "streak_52weeks", "label": "Год в деле", "description": "≥3 пробежки в каждую из 52 недель подряд",
     "icon": "fa-infinity", "type": "streak", "weeks": 52, "min_per_week": 3, "points": 350},

    {"key": "comeback", "label": "Возвращение", "description": "Пробежка после паузы 30+ дней",
     "icon": "fa-rotate-left", "type": "comeback", "gap_days": 30, "points": 30},

    {"key": "early_bird", "label": "Ранняя пташка", "description": "Пробежка начата до 07:00",
     "icon": "fa-sun", "type": "time_of_day", "before_hour": 7, "points": 15},
    {"key": "night_owl", "label": "Полуночник", "description": "Пробежка начата после 21:00",
     "icon": "fa-moon", "type": "time_of_day", "after_hour": 21, "points": 15},

    {"key": "elevation_500", "label": "Покоритель холмов", "description": "Набор высоты 500 м за одну тренировку",
     "icon": "fa-hill-rockslide", "type": "elevation", "value": 500.0, "points": 40},
    {"key": "elevation_10000", "label": "Альпинист", "description": "Суммарный набор высоты 10 000 м за всё время",
     "icon": "fa-mountain", "type": "elevation_total", "value": 10000.0, "points": 150},

    {"key": "plan_week_perfect", "label": "Идеальная неделя",
     "description": "Все тренировки недельного плана (кроме отдыха) выполнены",
     "icon": "fa-clipboard-check", "type": "plan_adherence", "mode": "perfect_week", "points": 100},
    {"key": "plan_discipline", "label": "Дисциплина",
     "description": "4 недели подряд без единого «Не подтверждена»",
     "icon": "fa-list-check", "type": "plan_adherence", "mode": "discipline", "weeks": 4, "points": 150},

    {"key": "goal_completed", "label": "Цель достигнута", "description": "Завершена хотя бы одна цель в приложении",
     "icon": "fa-bullseye", "type": "goal", "points": 70},

    {"key": "variety", "label": "Универсал",
     "description": "Выполнены тренировки минимум 4 разных типов (лёгкая/темповая/интервальная/длинная/восстановление)",
     "icon": "fa-shuffle", "type": "variety", "min_types": 4, "points": 50},

    {"key": "completionist", "label": "Коллекционер", "description": "Получены все остальные достижения, кроме «Возвращение»",
     "icon": "fa-trophy", "type": "meta", "exclude": ["comeback"], "points": 500},
]
