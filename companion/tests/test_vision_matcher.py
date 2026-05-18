from pathlib import Path

from PIL import Image

from companion import vision_matcher as vm


def image_signature(pixel_value: int) -> vm.ImageSignature:
    return vm.ImageSignature(phash=pixel_value)


def visual_resolver(
    tmp_path: Path,
    monkeypatch,
    ref_values: list[int],
    ambiguity_margin: float = 0.035,
) -> vm.VisualCardResolver:
    items_path = tmp_path / "items.min.json"
    items_path.write_text("[]", encoding="utf-8")
    target_signature = image_signature(0)
    monkeypatch.setattr(vm, "capture_game_window", lambda: Image.new("RGB", (100, 100)))
    monkeypatch.setattr(vm, "crop_variants", lambda _image: [_image])
    monkeypatch.setattr(vm, "signature", lambda _image: target_signature)

    resolver = vm.VisualCardResolver(
        items_data_path=items_path,
        cache_dir=tmp_path,
        threshold=0.2,
        ambiguity_margin=ambiguity_margin,
    )
    refs = [
        vm.ItemArtRef(
            title=f"Candidate {index}",
            size="small",
            tier="bronze",
            cooldown=None,
            image_url=f"https://example.test/{index}.png",
            cache_key=f"candidate-{index}",
        )
        for index, _value in enumerate(ref_values)
    ]
    resolver._refs = refs
    resolver._ref_signatures = {
        ref.cache_key: image_signature(value)
        for ref, value in zip(refs, ref_values)
    }
    return resolver


def test_visual_resolver_rejects_ambiguous_matches(tmp_path, monkeypatch):
    # Values 3 (popcnt=2) and 5 (popcnt=2) give equal Hamming distances from 0
    resolver = visual_resolver(tmp_path, monkeypatch, [3, 5])

    match = resolver.match(0, "itm_test", "Small", {"x": 0, "y": 0, "w": 1, "h": 1})

    assert match is None
    assert resolver._resolved == {}


def test_visual_resolver_accepts_unambiguous_matches(tmp_path, monkeypatch):
    # Value 1 (popcnt=1) vs 15 (popcnt=4): margin = (4-1)/64 = 0.046875 >= 0.035
    resolver = visual_resolver(tmp_path, monkeypatch, [1, 15])

    match = resolver.match(0, "itm_test", "Small", {"x": 0, "y": 0, "w": 1, "h": 1})

    assert match is not None
    assert match.title == "Candidate 0"
    assert match.runner_up == "Candidate 1"
    assert match.margin >= 0.035
    assert resolver.match(0, "itm_test", "Small", {"x": 0, "y": 0, "w": 1, "h": 1}) is match
