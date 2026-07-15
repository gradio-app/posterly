from render_logbook_embed import _render_embed, _render_hotspot_button


def _hotspot():
    return {
        "label": "Claim 1: benchmark construction",
        "target": "claim-1-benchmark-construction",
        "left": 10,
        "top": 20,
        "width": 30,
        "height": 40,
    }


def test_hotspot_has_link_icon_accessible_label_and_navigation_message():
    button = _render_hotspot_button(_hotspot())

    assert "<svg" in button
    assert ">Open details</span>" not in button
    assert 'aria-label="Open details for Claim 1: benchmark construction"' in button
    assert "trackio-logbook:navigate" in button
    assert "claim-1-benchmark-construction" in button


def test_embed_uses_accessible_minimum_target_size():
    embed = _render_embed("aW1hZ2U=", [_hotspot()])

    assert "width:clamp(44px,5vw,60px)" in embed
    assert ".trackio-poster-hotspot svg{width:62%;height:62%" in embed
    assert "opacity:1" in embed
    assert "clamp(22px,2.4vw,38px)" not in embed
