#!/usr/bin/env python3
"""Create a self-contained interactive Trackio-logbook poster embed.

The source poster marks navigable sections with
``data-logbook-target="<page-slug>"``. This tool renders those element bounds
in print layout, validates every slug against the generated logbook manifest,
then overlays accessible buttons on the rendered poster PNG.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import sys
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _posterly import canvas as _canvas  # noqa: E402
from _posterly import render as _render  # noqa: E402


def _slugs(node: dict) -> set[str]:
    found = {str(node.get("slug", ""))}
    for child in node.get("children", []) or []:
        found.update(_slugs(child))
    return found


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("poster_html", help="Annotated source poster HTML")
    p.add_argument("poster_png", help="Rendered poster PNG from render_preview.py")
    p.add_argument(
        "--logbook-manifest", required=True,
        help="Path to .trackio/logbook/logbook.json for slug validation",
    )
    p.add_argument("--out", default="poster_embed.html", help="Output HTML path")
    return p


def _main() -> int:
    args = _parser().parse_args()
    poster_html = Path(args.poster_html).resolve()
    poster_png = Path(args.poster_png).resolve()
    manifest_path = Path(args.logbook_manifest).resolve()
    if not poster_html.is_file() or not poster_png.is_file() or not manifest_path.is_file():
        print("ERROR: poster HTML, poster PNG, and logbook manifest must exist.", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid_slugs = _slugs(manifest["root"])
    resolved = _canvas.resolve_canvas(poster_html, None, label="[logbook_embed]")
    if resolved is None:
        return 2
    _canvas_size, viewport = resolved

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is required; install it and Chromium first.", file=sys.stderr)
        return 2

    script = """() => {
      const poster = document.querySelector('[data-measure-role="poster"]') || document.querySelector('.poster');
      if (!poster) throw new Error('poster root not found');
      const root = poster.getBoundingClientRect();
      return [...poster.querySelectorAll('[data-logbook-target]')].map((el) => {
        const r = el.getBoundingClientRect();
        return {
          target: (el.dataset.logbookTarget || '').replace(/^#?\\//, ''),
          label: el.dataset.logbookLabel || el.getAttribute('aria-label') || el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 120),
          left: 100 * (r.left - root.left) / root.width,
          top: 100 * (r.top - root.top) / root.height,
          width: 100 * r.width / root.width,
          height: 100 * r.height / root.height,
        };
      });
    }"""
    with sync_playwright() as pw:
        browser, _ctx, page = _render.open_print_emulated_page(pw, viewport)
        page.goto(poster_html.as_uri())
        hotspots = page.evaluate(script)
        browser.close()

    if not hotspots:
        print("ERROR: no [data-logbook-target] sections found.", file=sys.stderr)
        return 2
    for hotspot in hotspots:
        if hotspot["target"] not in valid_slugs:
            print(f"ERROR: unknown logbook page slug: {hotspot['target']}", file=sys.stderr)
            return 2
        if hotspot["width"] <= 0 or hotspot["height"] <= 0:
            print(f"ERROR: empty hotspot for {hotspot['target']}", file=sys.stderr)
            return 2

    image = base64.b64encode(poster_png.read_bytes()).decode("ascii")
    buttons = "\n".join(
        '<button class="trackio-poster-hotspot" '
        f'style="left:{h["left"]:.4f}%;top:{h["top"]:.4f}%;width:{h["width"]:.4f}%;height:{h["height"]:.4f}%" '
        f'aria-label="Open {html.escape(h["label"], quote=True)}" '
        f'onclick="parent.postMessage({{type:\'trackio-logbook:navigate\',target:\'{html.escape(h["target"], quote=True)}\'}}, \'*\')"></button>'
        for h in hotspots
    )
    output = Path(args.out)
    output.write_text(
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "body{margin:0;background:#fff}.trackio-poster{position:relative;line-height:0}"
        ".trackio-poster img{display:block;width:100%;height:auto}"
        ".trackio-poster-hotspot{position:absolute;border:3px solid transparent;background:transparent;cursor:pointer;border-radius:12px}"
        ".trackio-poster-hotspot:hover,.trackio-poster-hotspot:focus-visible{border-color:#0f766e;background:rgba(13,148,136,.12);outline:none}"
        "</style></head><body><div class=\"trackio-poster\">"
        f"<img src=\"data:image/png;base64,{image}\" alt=\"Interactive reproduction poster\">{buttons}"
        "</div></body></html>",
        encoding="utf-8",
    )
    print(f"[logbook_embed] wrote {output} with {len(hotspots)} hotspot(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
