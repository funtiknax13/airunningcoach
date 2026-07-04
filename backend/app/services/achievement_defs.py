# app/services/achievement_defs.py
"""
Каталог «достижений» — дискретных разовых событий, в отличие от PersonalRecord
(который про личный рекорд времени на дистанции). Достижение либо есть, либо
его нет — это факт свершения, а не измерение.

type:
  "count"          — суммарное число пробежек за всё время >= value
  "distance"       — хотя бы одна пробежка с distance_km >= value
  "monthly_volume" — сумма distance_km за какой-либо календарный месяц >= value
"""

ACHIEVEMENT_DEFS = [
    {"key": "workouts_5",   "label": "Первые шаги",      "description": "Выполнено 5 тренировок",
     "icon": "fa-shoe-prints", "type": "count", "value": 5},
    {"key": "workouts_25",  "label": "Втянулся",         "description": "Выполнено 25 тренировок",
     "icon": "fa-layer-group", "type": "count", "value": 25},
    {"key": "workouts_100", "label": "Сотня тренировок", "description": "Выполнено 100 тренировок",
     "icon": "fa-crown", "type": "count", "value": 100},

    {"key": "distance_5k",      "label": "Пятёрка",       "description": "Пробежал 5 км за одну тренировку",
     "icon": "fa-flag-checkered", "type": "distance", "value": 5.0},
    {"key": "distance_10k",     "label": "Десятка",       "description": "Пробежал 10 км за одну тренировку",
     "icon": "fa-road", "type": "distance", "value": 10.0},
    {"key": "distance_half",    "label": "Полумарафонец", "description": "Пробежал полумарафон",
     "icon": "fa-mountain", "type": "distance", "value": 21.0975},
    {"key": "distance_marathon","label": "Марафонец",     "description": "Пробежал марафон",
     "icon": "fa-medal", "type": "distance", "value": 42.195},

    {"key": "month_50",  "label": "Разогнался",           "description": "50 км за календарный месяц",
     "icon": "fa-calendar-check", "type": "monthly_volume", "value": 50.0},
    {"key": "month_100", "label": "Сотка за месяц",       "description": "100 км за календарный месяц",
     "icon": "fa-fire", "type": "monthly_volume", "value": 100.0},
    {"key": "month_200", "label": "Марафонский темп жизни", "description": "200 км за календарный месяц",
     "icon": "fa-bolt", "type": "monthly_volume", "value": 200.0},
]
