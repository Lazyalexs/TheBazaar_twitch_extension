from types import SimpleNamespace

from companion.log_companion import (
    BazaarLogState,
    BoxCalibration,
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
        "socket_step": 0.075,
        "small_width": 0.105,
        "box_height": 0.2,
        "pad_x": 0.018,
        "pad_y": 0.005,
        "board_left_px": None,
        "board_top_px": None,
        "socket_step_px": None,
        "socket_9_left_px": None,
        "small_width_px": None,
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


def test_socket_box_uses_calibration_padding():
    box = socket_box(
        2,
        "Small",
        BoxCalibration(
            board_x=0.09,
            board_y=0.52,
            socket_step=0.075,
            small_width=0.105,
            box_height=0.2,
            pad_x=0.018,
            pad_y=0.005,
        ),
    )

    assert box == {"x": 0.222, "y": 0.515, "w": 0.141, "h": 0.21}


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
            small_width_px=118,
            box_height_px=144,
            pad_x_px=8,
            pad_y_px=4,
        )
    )

    box = socket_box(0, "Small", calibration)

    assert box == {"x": 0.0094, "y": 0.5097, "w": 0.1047, "h": 0.2111}


def test_pixel_calibration_can_derive_step_from_last_socket():
    calibration = build_calibration(
        calibration_args(
            board_left_px=20,
            board_top_px=371,
            socket_9_left_px=965,
            small_width_px=118,
            box_height_px=144,
            pad_x_px=8,
            pad_y_px=4,
        )
    )

    box = socket_box(9, "Small", calibration)

    assert box == {"x": 0.7477, "y": 0.5097, "w": 0.1047, "h": 0.2111}


def test_720p_profile_scales_with_detected_frame_size():
    calibration = build_calibration(
        calibration_args(
            box_profile="720p",
            stream_resolution="1920x1080",
        )
    )

    box = socket_box(0, "Small", calibration)

    assert box == {"x": 0.0094, "y": 0.5097, "w": 0.1047, "h": 0.2111}
