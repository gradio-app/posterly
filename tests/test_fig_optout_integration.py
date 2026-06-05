"""Chromium-gated integration test for the ``data-fig-layout="beside-text"``
opt-out on Gate A (figure sizing by aspect ratio).

The unit tests in ``test_polish_output.py`` feed the Python loop canned
``figures`` data and never execute ``_POLISH_JS``, so the new JS line that
reads ``img.getAttribute('data-fig-layout')`` is only exercised here,
against a real headless Chromium. This verifies the WHOLE path -- attribute
read in JS, passthrough in the figure record, and the skip in the Python
Gate A -- not just the Python half.

The wide-figure cases share one builder, differing only by the marker:

  * a wide figure (AR ~ 4) sized at 45 % of card width WARNS as FIG/WIDE;
  * the same figure with ``data-fig-layout="beside-text"`` is SILENCED;
  * a BROKEN image still warns FIG/BROKEN even WITH the opt-out -- the
    opt-out skips only the AR width gates, never the blank-image check.

A second builder covers the TALL case (AR < 0.8) end-to-end against the
shipped ``.fig-wrap`` / ``.ff-fig`` float CSS:

  * a tall figure centered at 30 % of card width WARNS as FIG/TALL-SMALL;
  * the same figure float-wrapped + ``data-fig-layout="beside-text"`` is
    SILENCED.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse

import pytest

from _posterly import polish as _polish


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="playwright + chromium not available",
)


# A tiny solid 8x2 PNG (AR = 4, so > 1.3 "wide") as a data URI -- gives the
# <img> a real intrinsic naturalWidth/naturalHeight so the AR gate engages.
_WIDE_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAACCAIAAADq9gq6"
    "AAAAEUlEQVR42mPQje/GihhwSQAArlERcd+KZDQAAAAASUVORK5CYII="
)


def _html(*, src: str, beside_text: bool) -> str:
    attr = ' data-fig-layout="beside-text"' if beside_text else ""
    # card 400px wide, figure pinned to 180px (45 %) -> below the 65 % wide
    # threshold, so FIG/WIDE fires unless the opt-out skips it.
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; box-sizing: border-box; }}
  .card {{ width: 400px; border: 1px solid #888; padding: 10px; }}
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <p>Caption beside the figure.</p>
      <img src="{src}" alt="wide figure"{attr}
           style="width: 180px; display: block;">
    </div>
  </div>
  </div>
</body></html>
"""


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )


def _run(tmp_path, capsys, *, src: str, beside_text: bool) -> str:
    poster = tmp_path / "poster.html"
    poster.write_text(_html(src=src, beside_text=beside_text), encoding="utf-8")
    rc = _polish.cmd_polish(_args(poster))
    assert rc == 0  # warn-only, not --strict
    return "".join(capsys.readouterr())


def test_wide_figure_warns_without_optout(tmp_path, capsys) -> None:
    out = _run(tmp_path, capsys, src=_WIDE_PNG, beside_text=False)
    assert "FIG/WIDE" in out  # the control: gate engages on a narrow wide fig


def test_beside_text_optout_suppresses_wide(tmp_path, capsys) -> None:
    out = _run(tmp_path, capsys, src=_WIDE_PNG, beside_text=True)
    assert "FIG/WIDE" not in out          # opt-out silences the AR width gate
    assert "warnings            : 0" in out


def test_optout_does_not_mask_broken_image(tmp_path, capsys) -> None:
    # A non-existent local image reports zero natural size -> FIG/BROKEN.
    # The opt-out must NOT hide it: the skip sits AFTER the broken check.
    out = _run(tmp_path, capsys, src="does-not-exist.png", beside_text=True)
    assert "FIG/BROKEN" in out
    assert "FIG/WIDE" not in out


# A tall PNG (30x100 -> AR 0.30 < 0.8) as a data URI: gives a real tall
# naturalWidth/naturalHeight so the FIG/TALL-SMALL gate engages in Chromium.
_TALL_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAABkCAIAAAAe6xdS"
    "AAAAUUlEQVR4nO3MsQ3AIBAAMcj0Pzb9paZAsgfwnpl1x3fpXeofdahDHepQhzrUoQ"
    "51qEMd6lCHOtShDnWoQx3qUIc61KEOdahDHepQhzrU8WZ9AK5GAmDQfiLbAAAAAElF"
    "TkSuQmCC"
)


def _tall_html(*, wrapped: bool) -> str:
    """A tall figure (AR 0.30) at 120px = 30% of a 400px card -- below the
    0.36 floor. As a plain centered .figure it is the bug (FIG/TALL-SMALL);
    floated in a .fig-wrap + figure.ff-fig and marked beside-text it is an
    intentional text-rich layout the gate must leave alone."""
    if wrapped:
        body = (
            '<div class="fig-wrap">'
            '<figure class="ff-fig" style="width:120px">'
            f'<img src="{_TALL_PNG}" alt="tall" data-fig-layout="beside-text">'
            '</figure>'
            '<p>Body text long enough to wrap to the left of and below the '
            'floated tall figure -- exactly when wrapping beats centering for '
            'a tall figure in a text-rich card.</p>'
            '</div>'
        )
    else:
        body = (
            '<div class="figure" style="text-align:center">'
            f'<img src="{_TALL_PNG}" alt="tall" '
            'style="width:120px; display:block; margin:0 auto;">'
            '</div>'
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; box-sizing: border-box; }}
  .card {{ width: 400px; border: 1px solid #888; padding: 10px; }}
  .fig-wrap::after {{ content: ""; display: table; clear: both; }}
  .ff-fig {{ float: right; margin: 0 0 6px 14px; text-align: center; }}
  .ff-fig img {{ display: block; width: 100%; }}
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">{body}</div>
  </div>
  </div>
</body></html>
"""


def test_tall_small_fires_on_centered_figure(tmp_path, capsys) -> None:
    """Control (real Chromium): a tall figure centered at 30% of card width
    warns FIG/TALL-SMALL -- exercises the whole JS->Python tall path."""
    poster = tmp_path / "poster.html"
    poster.write_text(_tall_html(wrapped=False), encoding="utf-8")
    rc = _polish.cmd_polish(_args(poster))
    assert rc == 0  # soft warn, not --strict
    assert "FIG/TALL-SMALL" in "".join(capsys.readouterr())


def test_float_wrap_tall_figure_is_exempt(tmp_path, capsys) -> None:
    """Treatment: the SAME tall figure floated in the shipped .fig-wrap /
    .ff-fig layout and marked beside-text is intentional -> NO FIG warning.
    Verifies the float CSS renders + the JS attribute read + the exemption."""
    poster = tmp_path / "poster.html"
    poster.write_text(_tall_html(wrapped=True), encoding="utf-8")
    rc = _polish.cmd_polish(_args(poster))
    assert rc == 0
    out = "".join(capsys.readouterr())
    assert "FIG/TALL-SMALL" not in out
    assert "FIG/" not in out
