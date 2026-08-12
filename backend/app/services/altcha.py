# app/services/altcha.py
"""Self-hosted ALTCHA (proof-of-work) капча — без внешних сервисов.

Схема ALTCHA простая и стабильная, поэтому реализуем сервер-часть сами (без
доп. зависимости):

  Челлендж:  salt (+срок годности) → secret_number → challenge = SHA256(salt+number)
             signature = HMAC-SHA256(hmac_key, challenge). Состояние на сервере не
             храним — подпись позволяет проверить решение позже.
  Виджет:    перебирает number, пока SHA256(salt+number) == challenge, и присылает
             base64(JSON{algorithm, challenge, number, salt, signature}).
  Проверка:  пересчитываем PoW и подпись, проверяем срок годности.

Замечание про replay: одно решённое задание можно переиспользовать в пределах
срока годности (мы не храним использованные challenge). Стоимость PoW + короткий
TTL делают это приемлемым для MVP; при необходимости добавим учёт в БД/кэше.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from app.core.config import settings

_ALGO = "SHA-256"
_MAXNUMBER = 100_000     # верхняя граница перебора — сложность PoW (доли секунды в браузере)
_TTL_SECONDS = 600       # челлендж живёт 10 минут


def _key() -> bytes:
    return (settings.ALTCHA_HMAC_KEY or "").encode()


def enabled() -> bool:
    """Капча включена, только если задан секретный ключ (иначе — dev-режим без проверки)."""
    return bool(settings.ALTCHA_HMAC_KEY)


def create_challenge() -> dict:
    expires = int(time.time()) + _TTL_SECONDS
    # срок годности зашит в salt — виджет передаёт salt обратно как есть
    salt = os.urandom(12).hex() + f"?expires={expires}"
    secret_number = int.from_bytes(os.urandom(4), "big") % (_MAXNUMBER + 1)
    challenge = hashlib.sha256(f"{salt}{secret_number}".encode()).hexdigest()
    signature = hmac.new(_key(), challenge.encode(), hashlib.sha256).hexdigest()
    return {
        "algorithm": _ALGO,
        "challenge": challenge,
        "salt": salt,
        "signature": signature,
        "maxnumber": _MAXNUMBER,
    }


def verify_solution(payload: str | None) -> tuple[bool, str]:
    """Проверяет решение виджета. Возвращает (ok, code_ошибки)."""
    if not enabled():
        return True, ""  # ключ не настроен (локальная разработка) — пропускаем
    if not payload:
        return False, "captcha_required"
    try:
        data = json.loads(base64.b64decode(payload).decode())
    except Exception:
        return False, "captcha_invalid"

    if data.get("algorithm") != _ALGO:
        return False, "captcha_invalid"

    salt = data.get("salt", "")
    number = data.get("number")
    challenge = data.get("challenge", "")
    signature = data.get("signature", "")

    # срок годности из salt
    try:
        expires = int(salt.split("?expires=")[1])
    except (IndexError, ValueError):
        return False, "captcha_invalid"
    if time.time() > expires:
        return False, "captcha_expired"

    # PoW: SHA256(salt + number) должен совпасть с challenge
    calc = hashlib.sha256(f"{salt}{number}".encode()).hexdigest()
    if not hmac.compare_digest(calc, str(challenge)):
        return False, "captcha_invalid"

    # серверная подпись — что этот challenge выдали именно мы
    expected_sig = hmac.new(_key(), str(challenge).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, str(signature)):
        return False, "captcha_invalid"

    return True, ""
