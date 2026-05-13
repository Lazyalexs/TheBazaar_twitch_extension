import pytest

from companion.desktop_app import validate_server_url


def test_validate_server_url_requires_https_for_remote_hosts():
    assert validate_server_url("https://api.thebazaar-twitch.online/") == (
        "https://api.thebazaar-twitch.online"
    )
    assert validate_server_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"

    with pytest.raises(ValueError):
        validate_server_url("http://api.thebazaar-twitch.online")
