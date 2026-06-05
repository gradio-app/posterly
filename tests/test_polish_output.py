"""Round-10/12: polish's terminal output must stay ASCII even when the
USER's HTML contains Unicode (orphan glyphs, image src), a broken /
zero-natural-size raster <img> must surface FIG/BROKEN, and a zero-size
SVG (which renders fine) must NOT. Playwright is mocked via an injected
fake module, with page.evaluate() returning canned polish data.
"""
from __future__ import annotations

import argparse
import sys
import types

from _posterly import polish as _polish
from _posterly.textutil import ascii_safe


def _install_fake_playwright(monkeypatch):
    class _PW:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    mod = types.ModuleType("playwright.sync_api")
    mod.TimeoutError = type("_T", (Exception,), {})
    mod.sync_playwright = lambda: _PW()
    parent = types.ModuleType("playwright")
    parent.sync_api = mod
    monkeypatch.setitem(sys.modules, "playwright", parent)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)


class _Page:
    def __init__(self, data):
        self._data = data

    def goto(self, *a, **k):
        pass

    def evaluate(self, *a, **k):
        return self._data


class _Browser:
    def close(self):
        pass


def _poster_html(tmp_path):
    p = tmp_path / "poster.html"
    p.write_text(
        "<html><head><style>@page { size: 24in 36in }</style></head>"
        "<body><div data-measure-role=\"poster\">"
        "<div data-measure-role=\"column\">"
        "<div data-measure-role=\"card\"></div></div></div></body></html>",
        encoding="utf-8",
    )
    return p


def _args(html, **over):
    base = dict(
        html=str(html), canvas=None, settle_ms=500,
        mathjax_timeout_ms=15000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _run(monkeypatch, tmp_path, capsys, data, **args_over):
    """Drive cmd_polish with `data` as the canned _POLISH_JS result.
    Extra kwargs override the polish args (e.g. strict=True,
    tall_min_ratio=0.45). Returns (combined stdout+stderr, return code)."""
    _install_fake_playwright(monkeypatch)
    page = _Page(data)
    monkeypatch.setattr(
        _polish._render, "open_print_emulated_page",
        lambda p, vp: (_Browser(), None, page),
    )
    monkeypatch.setattr(_polish._render, "settle_page", lambda *a, **k: object())
    monkeypatch.setattr(
        _polish._render, "hard_fail_on_settle_problems", lambda *a, **k: None
    )
    rc = _polish.cmd_polish(_args(_poster_html(tmp_path), **args_over))
    return "".join(capsys.readouterr()), rc


def test_ascii_safe_escapes_non_ascii() -> None:
    s = ascii_safe("a × b ↑ –")
    s.encode("ascii")  # must not raise
    assert "×" not in s and "↑" not in s
    assert ascii_safe("plain ascii") == "plain ascii"


def test_polish_output_ascii_and_flags_broken_image(
    tmp_path, monkeypatch, capsys
) -> None:
    data = {
        "figures": [
            {"src": "https://cdn.example.com/broken.png",
             "rendered_w": 100.0, "card_w": 200.0,
             "natural_w": 0.0, "natural_h": 0.0},
        ],
        "orphans": [
            {"text": "1.18–1.30× ↑", "ws": "", "tag": "span",
             "cls": "stat-num"},
        ],
        "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    combined.encode("ascii")  # raises if user Unicode leaked through
    assert "FIG/BROKEN" in combined          # zero-size raster surfaced
    assert "ORPHAN" in combined              # orphan still detected
    assert "↑" not in combined and "×" not in combined  # escaped
    assert rc == 0                           # warnings only (not --strict)


def test_svg_zero_natural_size_not_flagged_broken(
    tmp_path, monkeypatch, capsys
) -> None:
    """A viewBox-only SVG reports zero natural size but renders fine --
    it must NOT be flagged FIG/BROKEN."""
    data = {
        "figures": [
            {"src": "assets/logo.svg?v=2",
             "rendered_w": 150.0, "card_w": 200.0,
             "natural_w": 0.0, "natural_h": 0.0},
        ],
        "orphans": [],
        "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/BROKEN" not in combined      # SVG is exempt
    assert rc == 0


def test_hero_broken_image_flagged(tmp_path, monkeypatch, capsys) -> None:
    """Round-13: a broken main figure inside data-measure-role='hero'
    must surface FIG/BROKEN. The card-only scan used to miss the hero
    centerpiece -- the worst image to silently lose."""
    data = {
        "figures": [
            {"src": "images/hero-figure.png", "role": "hero",
             "rendered_w": 800.0, "card_w": 1000.0,
             "natural_w": 0.0, "natural_h": 0.0},
        ],
        "orphans": [],
        "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/BROKEN" in combined
    assert "hero-figure.png" in combined
    assert rc == 0


def test_hero_figure_skips_card_ar_gates(tmp_path, monkeypatch, capsys) -> None:
    """Hero figures get the broken-image check but NOT the card-width AR
    sizing gates: identical geometry (30% width, wide AR) raises FIG/WIDE
    as a CARD but is silent as a HERO, whose panel has no 'card width'."""
    wide_small = {
        "src": "images/fig.png",
        "rendered_w": 300.0, "card_w": 1000.0,     # 30% of width
        "natural_w": 1600.0, "natural_h": 900.0,   # AR ~1.78 -> wide
    }
    card_combined, _ = _run(
        monkeypatch, tmp_path, capsys,
        {"figures": [{**wide_small, "role": "card"}],
         "orphans": [], "cols": []},
    )
    assert "FIG/WIDE" in card_combined            # fires for a card
    hero_combined, rc = _run(
        monkeypatch, tmp_path, capsys,
        {"figures": [{**wide_small, "role": "hero"}],
         "orphans": [], "cols": []},
    )
    assert "FIG/WIDE" not in hero_combined        # suppressed for a hero
    assert "FIG/BROKEN" not in hero_combined      # valid natural size
    assert rc == 0


def test_polish_unicode_path_stays_ascii(tmp_path, monkeypatch, capsys) -> None:
    """Round-13: polish's OWN path echoes -- the missing-file error and
    the `[polish] <name>` header -- must stay ASCII under a Unicode dir."""
    _install_fake_playwright(monkeypatch)
    d = tmp_path / "张三"  # Unicode dir
    d.mkdir()
    # (a) missing-file branch (reached after the fake-Playwright import).
    rc = _polish.cmd_polish(_args(d / "nope.html"))
    capsys.readouterr().err.encode("ascii")  # raises if path leaked
    assert rc == 2
    # (b) the `[polish] <name>` header on a real run under the Unicode dir.
    poster = d / "poster.html"
    poster.write_text(
        "<html><head><style>@page { size: 24in 36in }</style></head>"
        "<body><div data-measure-role=\"poster\">"
        "<div data-measure-role=\"column\">"
        "<div data-measure-role=\"card\"></div></div></div></body></html>",
        encoding="utf-8",
    )
    page = _Page({"figures": [], "orphans": [], "cols": []})
    monkeypatch.setattr(
        _polish._render, "open_print_emulated_page",
        lambda p, vp: (_Browser(), None, page),
    )
    monkeypatch.setattr(
        _polish._render, "settle_page", lambda *a, **k: object())
    monkeypatch.setattr(
        _polish._render, "hard_fail_on_settle_problems", lambda *a, **k: None
    )
    rc = _polish.cmd_polish(_args(poster))
    "".join(capsys.readouterr()).encode("ascii")  # raises if header leaked
    assert rc == 0


def test_card_trailing_blank_warns(tmp_path, monkeypatch, capsys) -> None:
    """A card stretched to align but padded with whitespace below the
    last line must surface CARD/TRAILING (the single-card sibling of
    Gate C; measure only checks the bottom edge so it can't see this)."""
    data = {
        "figures": [], "orphans": [], "cols": [],
        "cards": [{"card_index": 0, "card_h": 1000.0, "trailing_px": 250.0}],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "CARD/TRAILING" in combined  # 25% > 10% default
    assert rc == 0                      # warn only (not --strict)


def test_card_trailing_under_threshold_silent(
    tmp_path, monkeypatch, capsys
) -> None:
    """A card filled within the threshold must NOT warn -- near-zero or
    padding-only trailing is healthy breathing room, not a band."""
    data = {
        "figures": [], "orphans": [], "cols": [],
        "cards": [
            {"card_index": 0, "card_h": 1000.0, "trailing_px": 80.0},   # 8%
            {"card_index": 1, "card_h": 1000.0, "trailing_px": 0.0},    # flush
            {"card_index": 2, "card_h": 1000.0, "trailing_px": -3.0},   # rounding
        ],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "CARD/TRAILING" not in combined
    assert rc == 0


def test_tall_small_centered_raster_flagged(tmp_path, monkeypatch, capsys) -> None:
    """A tall raster figure (AR<0.8) centered far below the floor renders
    small with wide symmetric side margins -- FIG/TALL-SMALL must fire
    (the silent bug this gate was added for)."""
    data = {
        "figures": [{
            "src": "images/arch.png",
            "rendered_w": 350.0, "rendered_h": 1000.0, "card_w": 1000.0,  # 35%
            "natural_w": 680.0, "natural_h": 1000.0,                      # AR 0.68
        }],
        "orphans": [], "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/TALL-SMALL" in combined
    assert rc == 0  # soft warn, no --strict


def test_tall_small_exempt_when_beside_text(tmp_path, monkeypatch, capsys) -> None:
    """The same narrow tall figure marked data-fig-layout=beside-text
    (float-wrap / side-by-side) is intentional and must NOT warn."""
    data = {
        "figures": [{
            "src": "images/arch.png", "fig_layout": "beside-text",
            "rendered_w": 350.0, "rendered_h": 1000.0, "card_w": 1000.0,
            "natural_w": 680.0, "natural_h": 1000.0,
        }],
        "orphans": [], "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/TALL-SMALL" not in combined
    assert "FIG/TALL" not in combined
    assert rc == 0


def test_tall_small_floor_is_tunable(tmp_path, monkeypatch, capsys) -> None:
    """A centered tall figure rendered at 38% of card width is above the
    0.36 default floor -> silent (this is the real accepted Multi-Head
    figure). Raising --tall-min-ratio to 0.45 makes the SAME figure warn,
    proving the lever is live."""
    fig = {
        "src": "images/mha.png",
        "rendered_w": 380.0, "rendered_h": 500.0, "card_w": 1000.0,  # 38%
        "natural_w": 760.0, "natural_h": 1000.0,                     # AR 0.76
    }
    data = {"figures": [fig], "orphans": [], "cols": []}
    combined, _ = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/TALL-SMALL" not in combined               # 0.38 > 0.36 default
    combined2, _ = _run(
        monkeypatch, tmp_path, capsys, data, tall_min_ratio=0.45
    )
    assert "FIG/TALL-SMALL" in combined2                  # 0.38 < 0.45


def test_tall_small_svg_uses_rendered_ar(tmp_path, monkeypatch, capsys) -> None:
    """An SVG reports zero natural size; the sizing gate falls back to the
    RENDERED aspect ratio, so a narrow tall SVG still warns (and is not
    mistaken for FIG/BROKEN)."""
    data = {
        "figures": [{
            "src": "images/arch.svg",
            "rendered_w": 350.0, "rendered_h": 1000.0,    # rendered AR 0.35 -> tall
            "card_w": 1000.0, "natural_w": 0.0, "natural_h": 0.0,
        }],
        "orphans": [], "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data)
    assert "FIG/BROKEN" not in combined
    assert "FIG/TALL-SMALL" in combined
    assert rc == 0


def test_strict_exits_nonzero_on_tall_small(tmp_path, monkeypatch, capsys) -> None:
    """--strict promotes the soft FIG/TALL-SMALL warn to a non-zero exit."""
    data = {
        "figures": [{
            "src": "images/arch.png",
            "rendered_w": 350.0, "rendered_h": 1000.0, "card_w": 1000.0,
            "natural_w": 680.0, "natural_h": 1000.0,
        }],
        "orphans": [], "cols": [],
    }
    combined, rc = _run(monkeypatch, tmp_path, capsys, data, strict=True)
    assert "FIG/TALL-SMALL" in combined
    assert rc == 1


def test_tall_min_ratio_missing_falls_back_to_default(
    tmp_path, monkeypatch, capsys
) -> None:
    """A programmatic caller whose Namespace predates --tall-min-ratio must
    fall back to the SAME 0.36 floor as the CLI -- not a stale stricter
    value. A 38% figure is silent under 0.36; it would warn if the fallback
    were 0.40, so this pins the default to one source of truth."""
    _install_fake_playwright(monkeypatch)
    page = _Page({
        "figures": [{
            "src": "images/mha.png",
            "rendered_w": 380.0, "rendered_h": 500.0, "card_w": 1000.0,  # 38%
            "natural_w": 760.0, "natural_h": 1000.0,                     # AR 0.76
        }],
        "orphans": [], "cols": [],
    })
    monkeypatch.setattr(
        _polish._render, "open_print_emulated_page",
        lambda p, vp: (_Browser(), None, page),
    )
    monkeypatch.setattr(_polish._render, "settle_page", lambda *a, **k: object())
    monkeypatch.setattr(
        _polish._render, "hard_fail_on_settle_problems", lambda *a, **k: None
    )
    args = _args(_poster_html(tmp_path))
    delattr(args, "tall_min_ratio")  # simulate a pre-flag programmatic caller
    rc = _polish.cmd_polish(args)
    combined = "".join(capsys.readouterr())
    assert "FIG/TALL-SMALL" not in combined  # 0.38 > 0.36 fallback
    assert rc == 0
