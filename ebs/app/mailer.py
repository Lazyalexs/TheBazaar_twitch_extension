from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .config import Settings
from .database import normalize_language


@dataclass(frozen=True)
class RegistrationCredentials:
    recipient: str
    channel_id: str
    channel_login: str
    companion_token: str
    display_name: str
    language: str
    public_url: str


SUBJECT = {
    "ru": "The Bazaar Live Board: данные для companion app",
    "en": "The Bazaar Live Board: companion app credentials",
}


def build_registration_body(credentials: RegistrationCredentials) -> str:
    lang = normalize_language(credentials.language)
    if lang == "en":
        name = credentials.recipient
        return (
            f"Hello, {name}!\n\n"
            "Your The Bazaar Live Board companion app credentials:\n\n"
            f"Twitch Nick: {credentials.channel_login or credentials.channel_id}\n"
            f"Companion Token: {credentials.companion_token}\n\n"
            "Paste these values into the desktop companion app and press Verify.\n"
            "The token is shown only once and stored on the server as a hash.\n\n"
            f"Registration page: {credentials.public_url}/register?lang=en\n"
        )

    name = credentials.recipient
    return (
        f"Привет, {name}!\n\n"
        "Данные для приложения The Bazaar Live Board Companion:\n\n"
        f"Twitch Nick: {credentials.channel_login or credentials.channel_id}\n"
        f"Companion Token: {credentials.companion_token}\n\n"
        "Вставь эти значения в desktop companion app и нажми Verify.\n"
        "Токен показывается один раз и хранится на сервере только как hash.\n\n"
        f"Страница регистрации: {credentials.public_url}/register?lang=ru\n"
    )


def build_yandex_postbox_payload(
    credentials: RegistrationCredentials,
    *,
    from_address: str,
) -> dict[str, Any]:
    lang = normalize_language(credentials.language)
    return {
        "FromEmailAddress": from_address,
        "Destination": {
            "ToAddresses": [credentials.recipient],
        },
        "Content": {
            "Simple": {
                "Subject": {
                    "Data": SUBJECT[lang],
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": build_registration_body(credentials),
                        "Charset": "UTF-8",
                    },
                },
            },
        },
    }


def _signing_key(
    *,
    secret_key: str,
    date_stamp: str,
    region: str,
    service: str,
) -> bytes:
    key_date = hmac.new(
        ("AWS4" + secret_key).encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    key_region = hmac.new(key_date, region.encode("utf-8"), hashlib.sha256).digest()
    key_service = hmac.new(key_region, service.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


def aws_sigv4_headers(
    *,
    method: str,
    url: str,
    body: bytes,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    service: str = "ses",
    now: dt.datetime | None = None,
) -> dict[str, str]:
    timestamp = now or dt.datetime.now(dt.timezone.utc)
    timestamp = timestamp.astimezone(dt.timezone.utc)
    amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = timestamp.strftime("%Y%m%d")
    parsed = urlparse(url)
    canonical_uri = quote(parsed.path or "/", safe="/-_.~")
    canonical_querystring = parsed.query
    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_headers = (
        "content-type:application/json\n"
        f"host:{parsed.netloc}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(
            secret_key=secret_access_key,
            date_stamp=date_stamp,
            region=region,
            service=service,
        ),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Authorization": (
            "AWS4-HMAC-SHA256 "
            f"Credential={access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        ),
        "Content-Type": "application/json",
        "Host": parsed.netloc,
        "X-Amz-Content-Sha256": payload_hash,
        "X-Amz-Date": amz_date,
    }


class EmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.mail_configured

    def send_registration(self, credentials: RegistrationCredentials) -> bool:
        if not self.configured:
            return False
        if self.settings.mail_provider == "yandex_postbox":
            self._send_yandex_postbox(credentials)
            return True

        lang = normalize_language(credentials.language)
        message = EmailMessage()
        message["Subject"] = SUBJECT[lang]
        message["From"] = self.settings.smtp_from
        message["To"] = credentials.recipient
        message.set_content(build_registration_body(credentials))

        context = ssl.create_default_context()
        if self.settings.smtp_ssl:
            with smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=12,
                context=context,
            ) as smtp:
                self._send(smtp, message)
        else:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=12,
            ) as smtp:
                if self.settings.smtp_starttls:
                    smtp.starttls(context=context)
                self._send(smtp, message)
        return True

    def _send(self, smtp: smtplib.SMTP, message: EmailMessage) -> None:
        if self.settings.smtp_username:
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
        smtp.send_message(message)

    def _send_yandex_postbox(self, credentials: RegistrationCredentials) -> None:
        payload = build_yandex_postbox_payload(
            credentials,
            from_address=self.settings.yandex_postbox_from,
        )
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        endpoint = self.settings.yandex_postbox_endpoint
        headers = {"Content-Type": "application/json"}
        if self.settings.yandex_postbox_iam_token:
            headers["X-YaCloud-SubjectToken"] = self.settings.yandex_postbox_iam_token
        else:
            headers.update(
                aws_sigv4_headers(
                    method="POST",
                    url=endpoint,
                    body=body,
                    access_key_id=self.settings.yandex_postbox_access_key_id,
                    secret_access_key=self.settings.yandex_postbox_secret_access_key,
                    region=self.settings.yandex_postbox_region,
                )
            )
        request = Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=12) as response:
            response.read()
