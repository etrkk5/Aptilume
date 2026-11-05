"""ASGI boundary: bounded bodies, fixed production origin, sanitized errors and headers."""

import asyncio
import json
import math
from urllib.parse import urlsplit
from uuid import uuid4
from starlette.responses import JSONResponse
from starlette.datastructures import Headers
from .store import DomainError
from .audit import correlation_context, record
from .language import error_message

CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'"


def authority(value):
    try:
        parsed = urlsplit("//" + value)
        if (
            parsed.username
            or parsed.password
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or any(ord(c) < 33 or ord(c) == 127 for c in value)
        ):
            raise ValueError()
        return parsed.hostname.casefold(), parsed.port
    except (ValueError, TypeError):
        raise DomainError("invalid_host", "İstek sunucusu geçersiz.", 400)


class SecurityEnvelope:
    def __init__(self, app, store):
        self.app = app
        self.store = store

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        token = correlation_context.set(request_id)
        started = False
        headers = Headers(scope=scope)
        path = scope.get("path", "")

        async def secure_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                additions = {
                    "x-content-type-options": "nosniff",
                    "referrer-policy": "same-origin",
                    "x-frame-options": "DENY",
                    "content-security-policy": CSP,
                    "x-request-id": request_id,
                    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
                }
                if path.startswith("/api/") or any(
                    k.lower() == b"content-type" and b"text/html" in v
                    for k, v in message.get("headers", [])
                ):
                    additions["cache-control"] = "no-store"
                    additions["pragma"] = "no-cache"
                if not self.store.settings.demo:
                    additions["strict-transport-security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
                existing = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.decode().lower() not in additions
                ]
                message = {
                    **message,
                    "headers": existing
                    + [(k.encode(), v.encode()) for k, v in additions.items()],
                }
            await send(message)

        try:
            if not self.store.settings.demo:
                expected = urlsplit(self.store.settings.public_base_url)
                host, port = authority(headers.get("host", ""))
                is_health = path in {
                    "/health/live",
                    "/health/ready",
                    "/health/startup",
                    "/health/application",
                }
                if not is_health and (
                    host,
                    port or 443,
                ) != (expected.hostname.casefold(), expected.port or 443):
                    raise DomainError(
                        "host_denied", "İstek sunucusu izinli değil.", 400
                    )
            if path.startswith("/api/"):
                if headers.get("sec-fetch-site") == "cross-site":
                    raise DomainError(
                        "origin_denied", "İstek kaynağı doğrulanamadı.", 403
                    )
                origin = headers.get("origin")
                if self.store.settings.demo:
                    allowed = {
                        f"{scope.get('scheme','http')}://{headers.get('host','')}"
                    }
                    if self.store.settings.public_base_url:
                        allowed.add(self.store.settings.public_base_url.rstrip("/"))
                else:
                    allowed = {self.store.settings.public_base_url}
                if origin and origin not in allowed:
                    raise DomainError(
                        "origin_denied", "İstek kaynağı doğrulanamadı.", 403
                    )
                limit = 8192 if path.startswith("/api/v1/auth/") else 65536
                lengths = headers.getlist("content-length")
                if len(lengths) > 1:
                    raise DomainError("invalid_length", "İstek uzunluğu geçersiz.", 400)
                if lengths:
                    try:
                        length = int(lengths[0])
                    except ValueError:
                        raise DomainError(
                            "invalid_length", "İstek uzunluğu geçersiz.", 400
                        )
                    if length < 0:
                        raise DomainError(
                            "invalid_length", "İstek uzunluğu geçersiz.", 400
                        )
                    if length > limit:
                        raise DomainError(
                            "request_too_large",
                            "İstek boyutu izin verilen sınırı aşıyor.",
                            413,
                        )
                if headers.get("content-encoding", "identity") != "identity":
                    raise DomainError(
                        "encoding_denied",
                        "Sıkıştırılmış istek gövdesi kabul edilmiyor.",
                        415,
                    )
                body = bytearray()
                async with asyncio.timeout(10):
                    while True:
                        chunk = await receive()
                        if chunk["type"] == "http.disconnect":
                            return
                        if chunk["type"] != "http.request":
                            continue
                        body.extend(chunk.get("body", b""))
                        if len(body) > limit:
                            raise DomainError(
                                "request_too_large",
                                "İstek boyutu izin verilen sınırı aşıyor.",
                                413,
                            )
                        if not chunk.get("more_body", False):
                            break
                if (
                    body
                    and scope["method"] not in {"GET", "HEAD"}
                    and headers.get("content-type", "").split(";")[0].strip().lower()
                    != "application/json"
                ):
                    raise DomainError(
                        "json_required", "JSON istek gövdesi gerekli.", 415
                    )
                if (
                    body
                    and headers.get("content-type", "").split(";")[0].strip().lower()
                    == "application/json"
                ):

                    def pairs(items):
                        result = {}
                        for key, value in items:
                            if key in result:
                                raise ValueError("duplicate_key")
                            result[key] = value
                        return result

                    def invalid_constant(value):
                        raise ValueError("non_finite_json")

                    try:
                        parsed = json.loads(
                            body,
                            object_pairs_hook=pairs,
                            parse_constant=invalid_constant,
                        )
                        stack = [(parsed, 0)]
                        while stack:
                            value, depth = stack.pop()
                            if depth > 32:
                                raise ValueError("json_depth")
                            if isinstance(value, float) and not math.isfinite(value):
                                raise ValueError("non_finite_json")
                            if isinstance(value, dict):
                                stack.extend((v, depth + 1) for v in value.values())
                            elif isinstance(value, list):
                                stack.extend((v, depth + 1) for v in value)
                    except (ValueError, UnicodeError, RecursionError):
                        raise DomainError(
                            "invalid_json",
                            "JSON biçimi, derinliği veya alanları geçersiz.",
                            400,
                        )
                delivered = False

                async def replay():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {
                            "type": "http.request",
                            "body": bytes(body),
                            "more_body": False,
                        }
                    return await receive()

                await self.app(scope, replay, secure_send)
            else:
                await self.app(scope, receive, secure_send)
        except (DomainError, TimeoutError) as exc:
            if started:
                raise
            if isinstance(exc, DomainError):
                status, code, message = exc.status, exc.code, exc.message
            else:
                status, code, message = 408, "request_timeout", "İstek süresi aşıldı."
            from starlette.concurrency import run_in_threadpool

            await run_in_threadpool(
                record,
                self.store,
                "request_rejected",
                "denied",
                reason=code,
                status=status,
            )
            await JSONResponse(
                {
                    "code": code,
                    "message": error_message(
                        code, message, headers.get("x-aptilume-language", "en")
                    ),
                    "correlation_id": request_id,
                },
                status_code=status,
            )(scope, receive, secure_send)
        except Exception:
            if started:
                raise
            # A stable identifier is logged; exception text may contain credentials/DSNs.
            record(self.store, "internal_error", "error", reason="unhandled_exception")
            await JSONResponse(
                {
                    "code": "internal_error",
                    "message": error_message(
                        "internal_error",
                        "İşlem tamamlanamadı. Destek ekibine istek kimliğini iletin.",
                        headers.get("x-aptilume-language", "en"),
                    ),
                    "correlation_id": request_id,
                },
                status_code=500,
            )(scope, receive, secure_send)
        finally:
            correlation_context.reset(token)
