from types import SimpleNamespace

from companion.log_companion import (
    BazaarLogState,
    BoxCalibration,
    LogTailer,
    LogStatsCollector,
    TemplateInfo,
    build_calibration,
    parse_resolution,
    socket_box,
)


def calibration_args(**overrides):
    defaults = {
        "stream_resolution": "1280x720",
        "stream_width": None,
        "stream_height": None,
        "disable_window_detect": True,
        "box_profile": "normalized",
        "board_x": 0.09,
        "board_y": 0.52,
        "opponent_board_y": 0.13,
        "board_bottom_y": None,
        "socket_step": 0.075,
        "row_break": None,
        "small_width": 0.07,
        "medium_width": 0.1125,
        "large_width": 0.16875,
        "box_height": 0.2,
        "pad_x": 0.005,
        "pad_y": 0.0037,
        "board_left_px": None,
        "board_top_px": None,
        "opponent_board_top_px": None,
        "board_bottom_top_px": None,
        "socket_step_px": None,
        "socket_9_left_px": None,
        "small_width_px": None,
        "medium_width_px": None,
        "large_width_px": None,
        "box_height_px": None,
        "pad_x_px": None,
        "pad_y_px": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_log_state_links_instances_to_exact_templates():
    templates = {
        "bf90b501-0d87-49ae-a82a-5941db70179c": TemplateInfo(
            template_id="bf90b501-0d87-49ae-a82a-5941db70179c",
            title="Weather Machine",
            size="Large",
            tier="gold",
            cooldown=7,
        ),
        "3132efea-ee79-4b99-b380-d0df3bf1df88": TemplateInfo(
            template_id="3132efea-ee79-4b99-b380-d0df3bf1df88",
            title="Cruise Ship",
            size="Large",
            tier="gold",
            cooldown=6,
        ),
    }
    state = BazaarLogState(templates)

    lines = [
        "[09:38:58.146] [BoardManager] Card Purchased: InstanceId: itm_NrptOas - TemplateIdbf90b501-0d87-49ae-a82a-5941db70179c - Target:PlayerSocket_0 - SectionPlayer",
        "[16:40:16.835] [BoardManager] Card Purchased: InstanceId: itm_aw8weKP - TemplateId3132efea-ee79-4b99-b380-d0df3bf1df88 - Target:PlayerStorageSocket_3 - SectionStorage",
        "[09:41:17.418] [GameSimHandler] Cards Spawned: [itm_NrptOas [Player] [Hand] [Socket_0] [Large] | [itm_aw8weKP [Player] [Hand] [Socket_6] [Large] |",
    ]
    for line in lines:
        state.apply_line(line)

    payload = state.payload("5.0.0")

    assert payload["board"][0]["id"] == "Weather Machine"
    assert payload["board"][0]["slot"] == 0
    assert payload["board"][0]["source"] == "game"
    assert payload["board"][0]["confidence"] == 1
    assert payload["board"][1]["id"] == "Cruise Ship"
    assert payload["board"][1]["slot"] == 6


def test_log_state_keeps_spawned_items_without_templates():
    state = BazaarLogState({})
    state.apply_line(
        "[09:41:17.418] [GameSimHandler] Cards Spawned: "
        "[itm_missing [Player] [Hand] [Socket_1] [Small] |"
    )

    payload = state.payload("5.0.0")

    assert payload["board"][0]["id"] == "unknown:itm_missing"
    assert payload["board"][0]["slot"] == 1
    assert payload["board"][0]["source"] == "game"
    assert payload["board"][0]["confidence"] == 1
    assert payload["board"][0]["bbox"] == socket_box(
        1,
        "Small",
        state.calibration,
    )


def test_log_state_publishes_opponent_board_from_spawned_hand():
    state = BazaarLogState({})
    state.apply_line(
        "[09:41:17.418] [GameSimHandler] Cards Spawned: "
        "[opp_a [Opponent] [Hand] [Socket_2] [Small] | "
        "[opp_b [Opponent] [Hand] [Socket_4] [Medium] |"
    )

    payload = state.payload("5.0.0")

    assert payload["board"] == []
    assert payload["opponentBoard"][0]["id"] == "unknown:opp_a"
    assert payload["opponentBoard"][0]["slot"] == 2
    assert payload["opponentBoard"][0]["bbox"] == socket_box(
        2,
        "Small",
        state.calibration,
        opponent=True,
    )
    assert payload["opponentBoard"][1]["slot"] == 4


def test_log_state_can_resolve_unknown_items_with_visual_fallback():
    class FakeVisualResolver:
        def __init__(self):
            self.began = False

        def begin_frame(self):
            self.began = True

        def match(self, slot, instance_id, size, bbox, hero=None):
            assert slot == 1
            assert instance_id == "itm_missing"
            assert size == "Small"
            assert bbox == socket_box(1, "Small", BoxCalibration())
            return SimpleNamespace(
                title="SMG",
                tier="bronze",
                cooldown=2,
                confidence=0.99,
            )

    resolver = FakeVisualResolver()
    state = BazaarLogState({}, visual_resolver=resolver)
    state.apply_line(
        "[09:41:17.418] [GameSimHandler] Cards Spawned: "
        "[itm_missing [Player] [Hand] [Socket_1] [Small] |"
    )

    payload = state.payload("5.0.0")

    assert resolver.began
    assert payload["board"][0]["id"] == "SMG"
    assert payload["board"][0]["source"] == "vision"
    assert payload["board"][0]["confidence"] == 0.99
    assert payload["board"][0]["tier"] == "bronze"
    assert payload["board"][0]["cd"] == 2


def test_socket_box_uses_calibration_padding():
    box = socket_box(
        2,
        "Small",
        BoxCalibration(
            board_x=0.09,
            board_y=0.52,
            board_bottom_y=None,
            socket_step=0.075,
            row_break=None,
            small_width=0.07,
            medium_width=0.1125,
            large_width=0.16875,
            box_height=0.2,
            pad_x=0.005,
            pad_y=0.0037,
        ),
    )

    assert box == {"x": 0.235, "y": 0.5163, "w": 0.08, "h": 0.2074}


def test_socket_box_can_use_opponent_row():
    box = socket_box(2, "Small", BoxCalibration(opponent_board_y=0.13), opponent=True)

    assert box == {"x": 0.235, "y": 0.1263, "w": 0.08, "h": 0.2074}


def test_socket_box_uses_size_specific_shapes():
    calibration = BoxCalibration(
        board_x=0.09,
        board_y=0.52,
        board_bottom_y=None,
        socket_step=0.075,
        row_break=None,
        small_width=0.07,
        medium_width=0.1125,
        large_width=0.16875,
        box_height=0.2,
        pad_x=0.005,
        pad_y=0.0037,
    )

    assert socket_box(0, "Small", calibration)["w"] == 0.08
    assert socket_box(0, "Medium", calibration)["w"] == 0.1225
    assert socket_box(0, "Large", calibration)["w"] == 0.1788


def test_parse_resolution_accepts_auto_and_explicit_values():
    assert parse_resolution("auto") is None
    assert parse_resolution("1280x720") == (1280, 720)
    assert parse_resolution("1920X1080") == (1920, 1080)


def test_pixel_calibration_is_normalized_from_720p_profile():
    calibration = build_calibration(
        calibration_args(
            board_left_px=20,
            board_top_px=371,
            socket_step_px=105,
            small_width_px=88,
            medium_width_px=144,
            large_width_px=216,
            box_height_px=144,
            pad_x_px=6,
            pad_y_px=3,
        )
    )

    box = socket_box(0, "Small", calibration)

    assert box == {"x": 0.0109, "y": 0.5111, "w": 0.0781, "h": 0.2083}
    assert socket_box(4, "Large", calibration) == {
        "x": 0.3391,
        "y": 0.5111,
        "w": 0.1781,
        "h": 0.2083,
    }


def test_pixel_calibration_can_derive_step_from_last_socket():
    calibration = build_calibration(
        calibration_args(
            board_left_px=20,
            board_top_px=371,
            socket_9_left_px=965,
            small_width_px=88,
            medium_width_px=144,
            large_width_px=216,
            box_height_px=144,
            pad_x_px=6,
            pad_y_px=3,
        )
    )

    box = socket_box(9, "Small", calibration)

    assert box == {"x": 0.7492, "y": 0.5111, "w": 0.0781, "h": 0.2083}


def test_720p_profile_scales_with_detected_frame_size():
    calibration = build_calibration(
        calibration_args(
            box_profile="720p",
            stream_resolution="1920x1080",
        )
    )

    box = socket_box(0, "Small", calibration)

    assert box == {"x": 0.0109, "y": 0.5111, "w": 0.0781, "h": 0.2083}
    assert socket_box(9, "Small", calibration) == {
        "x": 0.7492,
        "y": 0.5111,
        "w": 0.0781,
        "h": 0.2083,
    }


def test_1080p_profile_matches_standard_stream_layout():
    calibration = build_calibration(
        calibration_args(
            box_profile="1080p",
            stream_resolution="1920x1080",
        )
    )

    box = socket_box(0, "Small", calibration)

    assert box == {"x": 0.0109, "y": 0.5111, "w": 0.0781, "h": 0.2083}


def test_row_break_can_place_later_sockets_on_second_row():
    calibration = build_calibration(
        calibration_args(
            board_left_px=552,
            board_top_px=124,
            board_bottom_top_px=307,
            socket_step_px=82.5,
            row_break=4,
            small_width_px=88,
            medium_width_px=144,
            large_width_px=216,
            box_height_px=144,
            pad_x_px=6,
            pad_y_px=3,
        )
    )

    assert socket_box(2, "Small", calibration) == {
        "x": 0.5555,
        "y": 0.1681,
        "w": 0.0781,
        "h": 0.2083,
    }
    assert socket_box(5, "Medium", calibration) == {
        "x": 0.491,
        "y": 0.4222,
        "w": 0.1219,
        "h": 0.2083,
    }


def test_log_tailer_returns_full_content_on_first_read(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("line one\nline two\n", encoding="utf-8")
    tailer = LogTailer([log])

    delta = tailer.read_new()

    assert delta.reset is False
    assert delta.text == "line one\nline two\n"


def test_log_tailer_returns_only_delta_on_subsequent_reads(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("first\n", encoding="utf-8")
    tailer = LogTailer([log])
    tailer.read_new()

    with log.open("a", encoding="utf-8") as fh:
        fh.write("second\n")
    delta = tailer.read_new()

    assert delta.reset is False
    assert delta.text == "second\n"


def test_log_tailer_signals_reset_on_truncation(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("long content that will be truncated\n", encoding="utf-8")
    tailer = LogTailer([log])
    tailer.read_new()

    log.write_text("short\n", encoding="utf-8")
    delta = tailer.read_new()

    assert delta.reset is True
    assert delta.text == "short\n"


def test_log_tailer_buffers_incomplete_trailing_line(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("complete\nincomp", encoding="utf-8")
    tailer = LogTailer([log])

    delta = tailer.read_new()
    assert delta.text == "complete\n"

    with log.open("a", encoding="utf-8") as fh:
        fh.write("lete-now\n")
    delta = tailer.read_new()
    assert delta.text == "incomplete-now\n"


def test_log_tailer_handles_missing_file_gracefully(tmp_path):
    log = tmp_path / "nope.log"
    tailer = LogTailer([log])
    delta = tailer.read_new()
    assert delta.text == ""
    assert delta.reset is False


def test_log_stats_collector_matches_summarize_log_text(tmp_path):
    sample = (
        "Card Purchased: InstanceId: abc - TemplateId12345678-1234-1234-1234-1234567890ab "
        "- Target:PlayerSocket_0 - Section:Player\n"
        "Sold Card xyz for 5 gold\n"
        "State changed from [MainMenuState] to [PVPCombatState]\n"
        "Combat simulation completed\n"
        "Cards Dealt: foo|bar\n"
    )
    from companion.log_stats import summarize_log_text

    collector = LogStatsCollector()
    collector.update(sample)
    snap = collector.snapshot()

    expected = summarize_log_text(sample)
    assert snap == expected


def test_log_state_captures_hero_from_run_configuration():
    state = BazaarLogState({})
    state.apply_line(
        "[21:11:58.898] [RunConfigurationCache] RunConfigurationCache: Changing EHero to Stelle"
    )
    assert state.hero == "stelle"

    # subsequent run change should override
    state.apply_line(
        "[22:00:00.000] [RunConfigurationCache] RunConfigurationCache: Changing EHero to Dooley"
    )
    assert state.hero == "dooley"


def test_log_state_propagates_hero_to_visual_resolver():
    captured = {}

    class FakeResolver:
        def begin_frame(self): pass
        def match(self, slot, instance_id, size, bbox, hero=None):
            captured["hero"] = hero
            return None

    state = BazaarLogState({}, visual_resolver=FakeResolver())
    state.apply_line(
        "[21:11:58] [RunConfigurationCache] RunConfigurationCache: Changing EHero to Stelle"
    )
    state.apply_line(
        "[21:12:09] [GameSimHandler] Cards Spawned: [itm_To-fusc [Player] [Hand] [Socket_3] [Small] | "
    )
    # build payload to trigger _visual_match for unknown items
    state.payload("5.0.0")
    assert captured.get("hero") == "stelle"