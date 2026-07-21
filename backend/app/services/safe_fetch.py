# app/services/safe_fetch.py
"""
Скачивание файла тренировки по ссылке, которую вводит пользователь (экспорт
из часов — Suunto/Garmin/Coros и т.п.). Ссылка приходит от пользователя, а не
из доверенного источника, поэтому это классический SSRF-вектор: без проверок
можно было бы подсунуть адрес внутреннего сервиса (postgres, backend, докер-сеть)
вместо реальной ссылки на GPX/FIT.

Защита: только https, hostname не должен резолвиться в приватный/локальный
IP, редиректы не поддерживаются (сервисы часов, которые мы проверяли, отдают
файл напрямую), размер ответа ограничен потоково — Content-Length заголовку
не доверяем, злоумышленный сервер может его не прислать или соврать.
"""
import ipaddress
import socket

import httpx
from fastapi import HTTPException

MAX_IMPORT_BYTES = 20 * 1024 * 1024  # 20 МБ с большим запасом — GPX/FIT обычно в разы меньше
FETCH_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


def _validate_external_url(url: str) -> None:
    parsed = httpx.URL(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="Ссылка должна начинаться с https://")

    hostname = parsed.host
    if not hostname:
        raise HTTPException(status_code=400, detail="Некорректная ссылка")

    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Не удалось разрешить адрес по ссылке")

    for *_, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(status_code=400, detail="Ссылка на этот адрес запрещена")


async def fetch_external_workout_file(url: str) -> tuple[bytes, str, str]:
    """Скачивает файл тренировки по внешней ссылке. Возвращает (содержимое, content-type, content-disposition)."""
    _validate_external_url(url)

    async with httpx.AsyncClient(follow_redirects=False, timeout=FETCH_TIMEOUT) as client:
        try:
            async with client.stream("GET", url) as resp:
                if resp.is_redirect:
                    raise HTTPException(
                        status_code=400,
                        detail="Ссылка перенаправляет на другой адрес — это не поддерживается",
                    )
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Сервис часов вернул ошибку ({resp.status_code})",
                    )

                content_type = resp.headers.get("content-type", "")
                content_disposition = resp.headers.get("content-disposition", "")

                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_IMPORT_BYTES:
                        raise HTTPException(status_code=400, detail="Файл слишком большой")
                    chunks.append(chunk)
        except httpx.RequestError:
            raise HTTPException(status_code=400, detail="Не удалось скачать файл по ссылке")

    return b"".join(chunks), content_type, content_disposition


def detect_workout_format(content: bytes, content_type: str, content_disposition: str) -> str | None:
    """Определяет gpx/fit по заголовкам ответа, а если сервис их не даёт — по содержимому файла."""
    ct = content_type.lower()
    cd = content_disposition.lower()

    if "gpx" in ct or ".gpx" in cd:
        return "gpx"
    if "fit" in ct or ".fit" in cd:
        return "fit"

    stripped = content.lstrip()[:200]
    if stripped.startswith(b"<?xml") or b"<gpx" in stripped:
        return "gpx"
    if len(content) > 12 and content[8:12] == b".FIT":
        return "fit"

    return None
