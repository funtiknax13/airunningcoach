import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from functools import partial

from app.core.config import settings

APP_NAME = "AI RunningCoach"
APP_URL = "{base_url}/dashboard"


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.GMAIL_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
        server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())


async def send_email(to_email: str, subject: str, html_body: str) -> None:
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


def _days_block(days: int, accent: str = "#f59e0b") -> str:
    color = accent if days > 3 else "#ef4444"
    return (
        f'<div style="background: {"#fffbeb" if days > 3 else "#fef2f2"}; '
        f'border: 1px solid {"#fde68a" if days > 3 else "#fecaca"}; '
        f'border-radius: 8px; padding: 12px 16px; margin: 16px 0; '
        f'font-size: 15px; color: {color}; font-weight: 600;">'
        f'⏳ Осталось дней Premium: {days}</div>'
    )


def _days_block_en(days: int, accent: str = "#f59e0b") -> str:
    color = accent if days > 3 else "#ef4444"
    return (
        f'<div style="background: {"#fffbeb" if days > 3 else "#fef2f2"}; '
        f'border: 1px solid {"#fde68a" if days > 3 else "#fecaca"}; '
        f'border-radius: 8px; padding: 12px 16px; margin: 16px 0; '
        f'font-size: 15px; color: {color}; font-weight: 600;">'
        f'⏳ Premium days left: {days}</div>'
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

async def send_trial_day1_email(to_email: str, name: str, lang: str = "ru") -> None:
    """День 1: приветствие + что умеет Premium."""
    app_url = f"{settings.APP_BASE_URL}/dashboard"
    features_ru = [
        "AI-тренер без ограничений — спрашивай сколько угодно",
        "Генерация персональных планов тренировок",
        "Импорт пробежек из Garmin, Coros, Suunto (GPX/FIT)",
        "Детальная аналитика: пульс, темп, каденс, сплиты",
    ]
    features_en = [
        "Unlimited AI coach — ask as much as you want",
        "Personalized training plan generation",
        "Import runs from Garmin, Coros, Suunto (GPX/FIT)",
        "Detailed analytics: heart rate, pace, cadence, splits",
    ]
    if lang == "en":
        html = _build_email_html(
            heading=f"Your 14-day Premium trial has started, {name}! 🎉",
            body="Here's what's available to you right now:",
            extra_blocks=_feature_list(features_en),
            button_text="Go to dashboard",
            button_url=app_url,
            footer="Questions? Just reply to this email.",
            accent="#4f46e5",
        )
        await send_email(to_email, f"Your Premium trial started — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Твой 14-дневный Premium-триал начался, {name}! 🎉",
            body="Вот что тебе доступно прямо сейчас:",
            extra_blocks=_feature_list(features_ru),
            button_text="Открыть дашборд",
            button_url=app_url,
            footer="Есть вопросы? Просто ответь на это письмо.",
            accent="#4f46e5",
        )
        await send_email(to_email, f"Твой Premium-триал начался — {APP_NAME}", html)


async def send_trial_day5_email(
    to_email: str, name: str, days_left: int, lang: str = "ru"
) -> None:
    """День 5: напоминание + подсказка как использовать."""
    app_url = f"{settings.APP_BASE_URL}/coach"
    tips_ru = [
        "Загрузи свою первую пробежку через импорт GPX/FIT",
        "Попроси тренера составить план на следующую неделю",
        "Задай вопрос о пульсовых зонах или темпе",
    ]
    tips_en = [
        "Upload your first run via GPX/FIT import",
        "Ask the coach to build a plan for next week",
        "Ask about heart rate zones or target pace",
    ]
    if lang == "en":
        html = _build_email_html(
            heading=f"How's the training going, {name}? 🏃",
            body="A few ideas to get the most out of your Premium trial:",
            extra_blocks=_days_block_en(days_left) + _feature_list(tips_en, accent="#10b981"),
            button_text="Chat with AI coach",
            button_url=app_url,
            footer=f"Your trial ends in {days_left} days.",
            accent="#10b981",
        )
        await send_email(to_email, f"Getting the most from your trial — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Как тренировки, {name}? 🏃",
            body="Несколько идей, чтобы получить максимум от Premium-триала:",
            extra_blocks=_days_block(days_left) + _feature_list(tips_ru, accent="#10b981"),
            button_text="Открыть AI-тренера",
            button_url=app_url,
            footer=f"Твой триал заканчивается через {days_left} дн.",
            accent="#10b981",
        )
        await send_email(to_email, f"Успей попробовать всё — {APP_NAME}", html)


async def send_trial_day13_email(
    to_email: str, name: str, days_left: int, lang: str = "ru"
) -> None:
    """День 13: предупреждение — 1 день остался."""
    subs_url = f"{settings.APP_BASE_URL}/subscription"
    what_lose_ru = [
        "Безлимитный чат с AI-тренером (вернётся лимит 10/день)",
        "Генерация планов тренировок",
        "Детальная аналитика пробежек",
    ]
    what_lose_en = [
        "Unlimited AI coach chat (limit returns to 10/day)",
        "Training plan generation",
        "Detailed run analytics",
    ]
    if lang == "en":
        html = _build_email_html(
            heading=f"1 day left in your Premium trial, {name} ⚠️",
            body="Tomorrow your trial ends. Here's what you'll lose access to:",
            extra_blocks=_days_block_en(days_left, accent="#ef4444") + _feature_list(what_lose_en, accent="#ef4444"),
            button_text="Keep Premium",
            button_url=subs_url,
            footer="No payment is required today — subscriptions open soon.",
            accent="#f59e0b",
        )
        await send_email(to_email, f"⚠️ 1 day left in your trial — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Остался 1 день Premium-триала, {name} ⚠️",
            body="Завтра триал заканчивается. Вот что перестанет быть доступным:",
            extra_blocks=_days_block(days_left, accent="#ef4444") + _feature_list(what_lose_ru, accent="#ef4444"),
            button_text="Сохранить Premium",
            button_url=subs_url,
            footer="Оплата пока не требуется — подписки скоро откроются.",
            accent="#f59e0b",
        )
        await send_email(to_email, f"⚠️ Остался 1 день триала — {APP_NAME}", html)


async def send_trial_expired_email(
    to_email: str, name: str, lang: str = "ru"
) -> None:
    """День 14: триал истёк."""
    subs_url = f"{settings.APP_BASE_URL}/subscription"
    if lang == "en":
        html = _build_email_html(
            heading=f"Your Premium trial has ended, {name}",
            body=(
                "Your 14-day trial is over. You're now on the Basic plan — "
                "AI coach is limited to 10 messages/day.<br><br>"
                "When payments open, you'll be able to unlock Premium and get "
                "back everything you had during the trial."
            ),
            button_text="View plans",
            button_url=subs_url,
            footer="Thank you for trying AI RunningCoach. Keep running! 🏃",
            accent="#6b7280",
        )
        await send_email(to_email, f"Your trial has ended — {APP_NAME}", html)
    else:
        html = _build_email_html(
            heading=f"Твой Premium-триал завершился, {name}",
            body=(
                "14 дней пробного периода истекли. Теперь ты на плане Basic — "
                "AI-тренер ограничен 10 сообщениями в день.<br><br>"
                "Когда откроется оплата, ты сможешь подключить Premium и вернуть "
                "всё, что было доступно во время триала."
            ),
            button_text="Посмотреть планы",
            button_url=subs_url,
            footer="Спасибо, что попробовал AI RunningCoach. Продолжай бегать! 🏃",
            accent="#6b7280",
        )
        await send_email(to_email, f"Триал завершился — {APP_NAME}", html)
