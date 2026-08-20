import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from functools import partial

from app.core.config import settings

APP_NAME = "AI RunningCoach"
APP_URL = "{base_url}/dashboard"


def _send_smtp(to_email: str | list[str], subject: str, html_body: str) -> None:
    recipients = to_email if isinstance(to_email, list) else [to_email]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.GMAIL_USER}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
        server.sendmail(settings.GMAIL_USER, recipients, msg.as_string())


async def send_email(to_email: str | list[str], subject: str, html_body: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_send_smtp, to_email, subject, html_body))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_email_html(
    heading: str,
    body: str,
    button_text: str,
    button_url: str,
    footer: str,
    accent: str = "#4f46e5",
    extra_blocks: str = "",
) -> str:
    return f"""
    <div style="font-family: Inter, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px;">
      <h2 style="color: {accent}; margin-bottom: 8px;">{heading}</h2>
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">{body}</p>
      {extra_blocks}
      <a href="{button_url}"
         style="display: inline-block; margin: 24px 0; padding: 14px 28px;
                background: {accent}; color: #fff; border-radius: 8px;
                text-decoration: none; font-size: 16px; font-weight: 600;">
        {button_text}
      </a>
      <p style="color: #9ca3af; font-size: 13px;">{footer}</p>
    </div>
    """


def _feature_list(items: list[str], accent: str = "#4f46e5") -> str:
    rows = "".join(
        f'<li style="padding: 4px 0; color: #374151;">'
        f'<span style="color: {accent}; margin-right: 8px;">✓</span>{item}</li>'
        for item in items
    )
    return f'<ul style="padding: 0; margin: 16px 0; list-style: none;">{rows}</ul>'


def _hours_block(hours: float, accent: str = "#f59e0b") -> str:
    h = round(hours)
    return (
        f'<div style="background: #fef2f2; '
        f'border: 1px solid #fecaca; '
        f'border-radius: 8px; padding: 12px 16px; margin: 16px 0; '
        f'font-size: 15px; color: #ef4444; font-weight: 600;">'
        f'⏳ Осталось ускоренного режима: ~{h} ч</div>'
    )


def _hours_block_en(hours: float, accent: str = "#f59e0b") -> str:
    h = round(hours)
    return (
        f'<div style="background: #fef2f2; '
        f'border: 1px solid #fecaca; '
        f'border-radius: 8px; padding: 12px 16px; margin: 16px 0; '
        f'font-size: 15px; color: #ef4444; font-weight: 600;">'
        f'⏳ Boosted mode left: ~{h}h</div>'
    )


# ── Verification email ────────────────────────────────────────────────────────

_VERIFY_CONTENT = {
    "ru": {
        "subject": f"Подтвердите email — {APP_NAME}",
        "heading": "Добро пожаловать в {app_name}, {name}! 🏃",
        "body": "Вы почти готовы! Подтвердите свой email, чтобы начать тренировки.",
        "button": "Подтвердить email",
        "footer": "Ссылка действительна 24 часа. Если вы не регистрировались — просто проигнорируйте письмо.",
    },
    "en": {
        "subject": f"Confirm your email — {APP_NAME}",
        "heading": "Welcome to {app_name}, {name}! 🏃",
        "body": "You're almost there! Confirm your email to start training.",
        "button": "Confirm email",
        "footer": "This link is valid for 24 hours. If you didn't sign up, just ignore this email.",
    },
}


async def send_verification_email(
    to_email: str, name: str, token: str, lang: str = "ru"
) -> None:
    lang = lang if lang in _VERIFY_CONTENT else "ru"
    c = _VERIFY_CONTENT[lang]
    verify_url = f"{settings.APP_BASE_URL}/api/auth/verify-email?token={token}"
    html = _build_email_html(
        heading=c["heading"].format(app_name=APP_NAME, name=name),
        body=c["body"],
        button_text=c["button"],
        button_url=verify_url,
        footer=c["footer"],
        accent="#4f46e5",
    )
    await send_email(to_email, c["subject"], html)


# ── Password reset email ──────────────────────────────────────────────────────

_RESET_CONTENT = {
    "ru": {
        "subject": f"Сброс пароля — {APP_NAME}",
        "heading": f"Сброс пароля — {APP_NAME} 🔑",
        "body": "Привет, {{name}}! Мы получили запрос на сброс пароля для вашего аккаунта.",
        "button": "Сбросить пароль",
        "footer": "Ссылка действительна 1 час. Если вы не запрашивали сброс — просто проигнорируйте письмо.",
    },
    "en": {
        "subject": f"Password reset — {APP_NAME}",
        "heading": f"Password reset — {APP_NAME} 🔑",
        "body": "Hi, {{name}}! We received a request to reset the password for your account.",
        "button": "Reset password",
        "footer": "This link is valid for 1 hour. If you didn't request a reset, just ignore this email.",
    },
}


async def send_password_reset_email(
    to_email: str, name: str, token: str, lang: str = "ru"
) -> None:
    lang = lang if lang in _RESET_CONTENT else "ru"
    c = _RESET_CONTENT[lang]
    reset_url = f"{settings.APP_BASE_URL}/?reset_token={token}"
    html = _build_email_html(
        heading=c["heading"],
        body=c["body"].format(name=name),
        button_text=c["button"],
        button_url=reset_url,
        footer=c["footer"],
        accent="#f97316",
    )
    await send_email(to_email, c["subject"], html)


# ── Trial emails ──────────────────────────────────────────────────────────────
# Продукт бесплатный — регистрация даёт 48 часов ускоренного режима (выше лимиты
# AI-тренера/планов + план на месяц), не «доступ, который потом отберут». Письма
# формулируют это как пробный тест-драйв ускорения, а не как надвигающуюся потерю.

async def send_trial_welcome_email(to_email: str, name: str, lang: str = "ru") -> None:
    """Чекпоинт 0 (~сразу после регистрации): приветствие + 48ч ускоренного режима."""
    app_url = f"{settings.APP_BASE_URL}/dashboard"
    features_ru = [
        "AI-тренер: до 50 сообщений в час (обычно — 10 в день)",
        "Генерация планов: до 10 в час, включая план на месяц",
        "Импорт пробежек из Garmin, Coros, Suunto (GPX/FIT)",
        "Разбор тренировок: пульс, темп, каденс, сплиты, интервалы",
    ]
    features_en = [
        "AI coach: up to 50 messages/hour (normally 10/day)",
        "Plan generation: up to 10/hour, including the monthly plan",
        "Import runs from Garmin, Coros, Suunto (GPX/FIT)",
        "Workout analysis: heart rate, pace, cadence, splits, intervals",
    ]
    if lang == "en":
        html = _build_email_html(
            heading=f"Welcome, {name}! Your account is fully free 🎉",
            body="For the next 48 hours you also get a boosted-limits test drive:",
            extra_blocks=_feature_list(features_en),
            button_text="Go to dashboard",
            button_url=app_url,
            footer="Everything above stays available after — just at regular free limits. Questions? Reply to this email.",
            accent="#4f46e5",
        )
        await send_email(to_email, f"Welcome to {APP_NAME} — your account is free", html)
    else:
        html = _build_email_html(
            heading=f"Привет, {name}! Твой аккаунт полностью бесплатный 🎉",
            body="А на ближайшие 48 часов — ещё и повышенные лимиты, чтобы распробовать:",
            extra_blocks=_feature_list(features_ru),
            button_text="Открыть дашборд",
            button_url=app_url,
            footer="Всё это остаётся доступно и дальше — просто на обычных бесплатных лимитах. Есть вопросы? Просто ответь на это письмо.",
            accent="#4f46e5",
        )
        await send_email(to_email, f"Добро пожаловать в {APP_NAME} — аккаунт бесплатный", html)


async def send_trial_reminder_email(
    to_email: str, name: str, hours_left: float, lang: str = "ru"
) -> None:
    """Чекпоинт 1 (~36ч, за ~12ч до конца): напоминание про ускоренный режим."""
    subs_url = f"{settings.APP_BASE_URL}/subscription"
    what_changes_ru = [
        "AI-тренер: 50/час → 10 в день",
        "Планы: 10/час → 1 в день (план на месяц станет доступен только в Premium)",
    ]
    what_changes_en = [
        "AI coach: 50/hour → 10/day",
        "Plans: 10/hour → 1/day (monthly plan becomes Premium-only)",
    ]
    if lang == "en":
        html = _build_email_html(
            heading=f"Boosted mode is wrapping up soon, {name} ⏳",
            body="Your account stays fully free after — limits just go back to normal:",
            extra_blocks=_hours_block_en(hours_left) + _feature_list(what_changes_en, accent="#ef4444"),
            button_text="See Premium",
            button_url=subs_url,
            footer="No payment needed — your account keeps working either way.",
            accent="#f59e0b",
        )
        await send_email(to_email, f"⏳ Boosted mode ending soon — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Ускоренный режим скоро закончится, {name} ⏳",
            body="Аккаунт как был бесплатным, так и останется — просто лимиты вернутся к обычным:",
            extra_blocks=_hours_block(hours_left) + _feature_list(what_changes_ru, accent="#ef4444"),
            button_text="Посмотреть Premium",
            button_url=subs_url,
            footer="Платить не обязательно — аккаунт продолжит работать в любом случае.",
            accent="#f59e0b",
        )
        await send_email(to_email, f"⏳ Ускоренный режим скоро закончится — {APP_NAME}", html)


async def send_trial_expired_email(
    to_email: str, name: str, lang: str = "ru"
) -> None:
    """Чекпоинт 2 (≥48ч): ускоренный режим закончился, аккаунт остаётся бесплатным."""
    subs_url = f"{settings.APP_BASE_URL}/subscription"
    if lang == "en":
        html = _build_email_html(
            heading=f"You're all set, {name} — your account is free",
            body=(
                "The 48-hour boosted test drive is over, but nothing is taken away: "
                "your account stays fully free, with the AI coach at 10 messages/day "
                "and 1 training plan/day.<br><br>"
                "Want more room (or the monthly plan)? Premium is there when you want it — no rush."
            ),
            button_text="See Premium",
            button_url=subs_url,
            footer="Thanks for trying AI RunningCoach. Keep running! 🏃",
            accent="#6b7280",
        )
        await send_email(to_email, f"Your account is free — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Всё в порядке, {name} — твой аккаунт бесплатный",
            body=(
                "48-часовой ускоренный режим закончился, но ничего не отбирается: "
                "аккаунт остаётся полностью бесплатным, с AI-тренером на 10 сообщений в день "
                "и 1 планом тренировок в день.<br><br>"
                "Захочется больше (или план на месяц) — Premium никуда не денется, спешить не нужно."
            ),
            button_text="Посмотреть Premium",
            button_url=subs_url,
            footer="Спасибо, что попробовал AI RunningCoach. Продолжай бегать! 🏃",
            accent="#6b7280",
        )
        await send_email(to_email, f"Твой аккаунт бесплатный — {APP_NAME}", html)


async def send_weekly_stats_email(
    to_email: str,
    name: str,
    runs: int,
    total_km: float,
    avg_pace: float | None,
    prev_km: float,
    plan_items: list | None = None,
    lang: str = "ru",
) -> None:
    """Еженедельная статистика + план на следующую неделю — каждое воскресенье в 21:00 МСК."""
    subs_url = f"{settings.APP_BASE_URL}/dashboard"
    plan_items = plan_items or []

    def fmt_pace(pace: float | None) -> str:
        if not pace:
            return "—"
        m = int(pace); s = round((pace - m) * 60)
        return f"{m}:{s:02d} мин/км"

    def plan_block_ru(items: list) -> str:
        if not items:
            return ""
        rows_html = []
        for it in items:
            km_str = (" · " + str(round(it["km"])) + " км") if it.get("km") else ""
            rows_html.append(
                f"<tr style='border-bottom:1px solid #2a2a3a'>"
                f"<td style='padding:6px 8px;color:#aaa;white-space:nowrap'>{it['date']}</td>"
                f"<td style='padding:6px 8px;color:#ccc'><b>{it['type']}</b> — {it['desc']}{km_str}</td>"
                f"</tr>"
            )
        rows = "".join(rows_html)
        return (
            f"<br><b>На следующей неделе запланировано {len(items)} тренировок:</b><br><br>"
            f"<table style='width:100%;border-collapse:collapse;font-size:14px'>{rows}</table>"
        )

    def plan_block_en(items: list) -> str:
        if not items:
            return ""
        type_en = {"Лёгкий бег": "Easy run", "Темповая": "Tempo", "Интервалы": "Intervals",
                   "Длинная": "Long run", "Восстановление": "Recovery", "Отдых": "Rest"}
        rows_html = []
        for it in items:
            km_str = (" · " + str(round(it["km"])) + " km") if it.get("km") else ""
            t = type_en.get(it["type"], it["type"])
            rows_html.append(
                f"<tr style='border-bottom:1px solid #2a2a3a'>"
                f"<td style='padding:6px 8px;color:#aaa;white-space:nowrap'>{it['date']}</td>"
                f"<td style='padding:6px 8px;color:#ccc'><b>{t}</b> — {it['desc']}{km_str}</td>"
                f"</tr>"
            )
        rows = "".join(rows_html)
        return (
            f"<br><b>Next week: {len(items)} workouts planned:</b><br><br>"
            f"<table style='width:100%;border-collapse:collapse;font-size:14px'>{rows}</table>"
        )

    delta = total_km - prev_km
    delta_str = f"+{delta:.1f} км" if delta > 0 else f"{delta:.1f} км"
    trend = "↑" if delta > 0 else ("↓" if delta < 0 else "→")

    if lang == "en":
        stats_block = (
            f"Here's your running week summary:<br><br>"
            f"🏃 <b>Runs:</b> {runs}<br>"
            f"📏 <b>Total distance:</b> {total_km:.1f} km<br>"
            f"⏱ <b>Average pace:</b> {fmt_pace(avg_pace).replace('мин/км', 'min/km')}<br>"
            f"📈 <b>vs last week:</b> {trend} {abs(delta):.1f} km"
        ) if runs > 0 else "You didn't log any runs this week — but your plan is ready!"
        body = stats_block + plan_block_en(plan_items)
        if runs > 0 and not plan_items:
            body += "<br><br>Keep it up — consistency is the key to progress!"
        html = _build_email_html(
            heading=f"Your week in running, {name}",
            body=body,
            button_text="Open dashboard",
            button_url=subs_url,
            footer="Sent every Sunday at 9 PM MSK · AI RunningCoach",
            accent="#6c63ff",
        )
        await send_email(to_email, f"Weekly digest — {APP_NAME}", html)
    else:
        stats_block = (
            f"Итоги твоей беговой недели:<br><br>"
            f"🏃 <b>Пробежек:</b> {runs}<br>"
            f"📏 <b>Общий километраж:</b> {total_km:.1f} км<br>"
            f"⏱ <b>Средний темп:</b> {fmt_pace(avg_pace)}<br>"
            f"📈 <b>По сравнению с прошлой неделей:</b> {trend} {delta_str}"
        ) if runs > 0 else "На этой неделе пробежек не было — но твой план уже ждёт!"
        body = stats_block + plan_block_ru(plan_items)
        if runs > 0 and not plan_items:
            body += "<br><br>Продолжай в том же духе — регулярность важнее скорости!"
        html = _build_email_html(
            heading=f"Твоя неделя в цифрах, {name}",
            body=body,
            button_text="Открыть дашборд",
            button_url=subs_url,
            footer="Отправляется каждое воскресенье в 21:00 МСК · AI RunningCoach",
            accent="#6c63ff",
        )
        await send_email(to_email, f"Дайджест недели — {APP_NAME}", html)


# Поддержка теперь через тикеты в приложении (routers/support.py,
# routers/admin_support.py) — писем по обращениям не шлём.
