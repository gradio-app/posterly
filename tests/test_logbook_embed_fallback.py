"""When no ``data-logbook-target`` sections apply, the embed generator must
still emit the SAME self-contained ``poster_embed.html`` wrapper -- just
without hotspot buttons -- not error out or produce a separate PNG-only
artifact (SKILL.md: "poster_embed.html is still the fallback ... with no
hotspot buttons").
"""
from __future__ import annotations

from render_logbook_embed import _render_embed


def test_no_hotspots_still_self_contained_data_uri_no_buttons():
    embed = _render_embed("aW1hZ2U=", [])

    # Self-contained: the poster image is inlined as a data-URI <img>.
    assert 'src="data:image/png;base64,aW1hZ2U="' in embed
    assert "<!doctype html>" in embed.lower()
    # No hotspot BUTTON elements in the fallback (the shared stylesheet still
    # carries the .trackio-poster-hotspot rules, which is harmless).
    assert "<button" not in embed
    assert "postMessage" not in embed
    # Still the same wrapper shell.
    assert 'class="trackio-poster"' in embed


def test_hotspot_run_still_emits_buttons():
    hotspot = {
        "label": "Claim 1",
        "target": "claim-1",
        "left": 10, "top": 20, "width": 30, "height": 40,
    }
    embed = _render_embed("aW1hZ2U=", [hotspot])
    assert "trackio-poster-hotspot" in embed
    assert "<button" in embed
