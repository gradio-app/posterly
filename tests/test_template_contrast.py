"""Shipped templates must not place low-contrast accent text on their
callout / section-title tags out of the box.

The neutral templates used to color ``.callout strong`` and
``.section-title .tag-key`` in ``--gold`` (#C9A24A): gold-on-accent-blue is
~2.8:1 and gold-on-white is ~2.4:1, both below the WCAG AA floor (3:1 large
text, 4.5:1 normal). These are small-text tags, so we assert the stronger
4.5:1. The fix recolors them to a token that clears it in their actual
context (a LIGHT token on the dark callout, a DARK token on the light card).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = sorted((REPO_ROOT / "templates").glob("*_neutral.html"))

AA_NORMAL = 4.5


def _rel_lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_rel_lum(a), _rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _tokens(css: str) -> dict[str, str]:
    return {
        name: hexv
        for name, hexv in re.findall(
            r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", css
        )
    }


def _rule_color_token(css: str, selector: str) -> str | None:
    """Return the ``--token`` a rule sets `color:` to, or None if absent."""
    m = re.search(
        re.escape(selector) + r"\s*\{[^}]*?color\s*:\s*var\((--[\w-]+)\)",
        css, re.DOTALL,
    )
    return m.group(1) if m else None


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_callout_strong_meets_aa_on_accent(template: Path):
    css = template.read_text(encoding="utf-8")
    tokens = _tokens(css)
    fg = _rule_color_token(css, ".callout strong")
    assert fg is not None, "template lost its .callout strong rule"
    # The default .callout background is the solid --accent.
    ratio = _contrast(tokens[fg], tokens["--accent"])
    assert ratio >= AA_NORMAL, (
        f"{template.name}: .callout strong ({fg}={tokens[fg]}) on "
        f"--accent={tokens['--accent']} is {ratio:.2f}:1 (< {AA_NORMAL})"
    )


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_tag_key_meets_aa_on_card(template: Path):
    css = template.read_text(encoding="utf-8")
    tokens = _tokens(css)
    fg = _rule_color_token(css, ".section-title .tag-key")
    if fg is None:
        pytest.skip("template has no .section-title .tag-key rule")
    # A section title sits on a card (--bg-card) or a light accent tint.
    for bg_token in ("--bg-card", "--accent-light"):
        ratio = _contrast(tokens[fg], tokens[bg_token])
        assert ratio >= AA_NORMAL, (
            f"{template.name}: .tag-key ({fg}={tokens[fg]}) on "
            f"{bg_token}={tokens[bg_token]} is {ratio:.2f}:1 (< {AA_NORMAL})"
        )
