from ebs.app.database import TokenStore, normalize_channel_login


def test_normalize_channel_login_accepts_common_twitch_inputs():
    assert normalize_channel_login("Streamer_Name") == "streamer_name"
    assert normalize_channel_login("@Streamer_Name") == "streamer_name"
    assert normalize_channel_login("https://www.twitch.tv/Streamer_Name/") == "streamer_name"


def test_token_store_registers_and_verifies_streamer(tmp_path):
    store = TokenStore(tmp_path / "tokens.sqlite3")

    result = store.register_streamer(
        channel_id="274185831",
        channel_login="streamer",
        email="streamer@example.com",
        display_name="Streamer",
        language="en",
    )

    assert result.created is True
    assert result.streamer.channel_id == "274185831"
    assert result.streamer.channel_login == "streamer"
    assert result.streamer.email == "streamer@example.com"
    assert result.streamer.language == "en"
    assert store.verify_token("274185831", result.token) is True
    assert store.verify_token("streamer", result.token) is True
    assert store.verify_token("274185831", "wrong-token") is False


def test_token_store_rotates_existing_token(tmp_path):
    store = TokenStore(tmp_path / "tokens.sqlite3")

    first = store.register_streamer(
        channel_id="274185831",
        channel_login="streamer",
        email="first@example.com",
        display_name="First",
        language="ru",
    )
    second = store.register_streamer(
        channel_id="274185831",
        channel_login="streamer",
        email="second@example.com",
        display_name="Second",
        language="en",
    )

    assert second.created is False
    assert second.token != first.token
    assert store.verify_token("274185831", first.token) is False
    assert store.verify_token("274185831", second.token) is True
    assert store.get_streamer("274185831").display_name == "Second"
    assert store.get_streamer("streamer").channel_id == "274185831"
    assert store.get_streamer("274185831").email == "second@example.com"


def test_token_store_can_register_by_login_only(tmp_path):
    store = TokenStore(tmp_path / "tokens.sqlite3")

    result = store.register_streamer(
        channel_login="@Streamer_Name",
        email="streamer@example.com",
        display_name=None,
        language="ru",
    )

    assert result.streamer.streamer_key == "login:streamer_name"
    assert result.streamer.channel_login == "streamer_name"
    assert store.verify_token("streamer_name", result.token) is True
