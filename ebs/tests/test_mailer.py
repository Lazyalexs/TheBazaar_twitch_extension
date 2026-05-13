import datetime as dt

from ebs.app.mailer import (
    RegistrationCredentials,
    aws_sigv4_headers,
    build_registration_body,
    build_yandex_postbox_payload,
)


def test_registration_email_contains_channel_id_and_token():
    body = build_registration_body(
        RegistrationCredentials(
            recipient="streamer@example.com",
            channel_id="274185831",
            channel_login="streamer",
            companion_token="secret-token",
            display_name="Streamer",
            language="en",
            public_url="https://example.com",
        )
    )

    assert "Hello, streamer@example.com!" in body
    assert "Twitch Nick: streamer" in body
    assert "Companion Token: secret-token" in body
    assert "https://example.com/register?lang=en" in body


def test_yandex_postbox_payload_contains_credentials():
    payload = build_yandex_postbox_payload(
        RegistrationCredentials(
            recipient="streamer@example.com",
            channel_id="274185831",
            channel_login="streamer",
            companion_token="secret-token",
            display_name="Streamer",
            language="ru",
            public_url="https://example.com",
        ),
        from_address="sender@example.com",
    )

    assert payload["FromEmailAddress"] == "sender@example.com"
    assert payload["Destination"]["ToAddresses"] == ["streamer@example.com"]
    text = payload["Content"]["Simple"]["Body"]["Text"]["Data"]
    assert "Привет, streamer@example.com!" in text
    assert "Twitch Nick: streamer" in text
    assert "Companion Token: secret-token" in text


def test_aws_sigv4_headers_are_deterministic():
    headers = aws_sigv4_headers(
        method="POST",
        url="https://postbox.cloud.yandex.net/v2/email/outbound-emails",
        body=b'{"ok":true}',
        access_key_id="test-access",
        secret_access_key="test-secret",
        region="ru-central1",
        now=dt.datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert headers["X-Amz-Date"] == "20260501T120000Z"
    assert headers["X-Amz-Content-Sha256"] == (
        "4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93"
    )
    assert "Credential=test-access/20260501/ru-central1/ses/aws4_request" in headers[
        "Authorization"
    ]
