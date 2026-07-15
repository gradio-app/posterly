#!/usr/bin/env python3
"""Create a self-contained interactive Trackio-logbook poster embed.

The source poster marks navigable sections with
``data-logbook-target="<page-slug>"``. This tool renders those element bounds
in print layout, validates every slug against the generated logbook manifest,
requires a fresh, passing strict-polish gate report, then overlays accessible
buttons on the rendered poster PNG.
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


def _render_hotspot_button(hotspot: dict) -> str:
    label = html.escape(hotspot["label"], quote=True)
    target = html.escape(hotspot["target"], quote=True)
    return (
        '<button class="trackio-poster-hotspot" '
        f'style="left:{hotspot["left"] + hotspot["width"]:.4f}%;'
        f'top:{hotspot["top"]:.4f}%" '
        f'aria-label="Open details for {label}" '
        "onclick=\"parent.postMessage({type:'trackio-logbook:navigate',"
        f"target:'{target}'}}, '*')\">"
        '<span>Open details</span><span aria-hidden="true">↗</span>'
        "</button>"
    )


def _render_embed(image: str, hotspots: list[dict]) -> str:
    buttons = "\n".join(_render_hotspot_button(h) for h in hotspots)
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "body{margin:0;background:#fff}.trackio-poster{position:relative;line-height:0}"
        ".trackio-poster img{display:block;width:100%;height:auto}"
        ".trackio-poster-hotspot{position:absolute;transform:translate(calc(-100% - 8px),8px);min-width:44px;min-height:44px;padding:0 14px;display:flex;align-items:center;justify-content:center;gap:6px;border:1px solid rgba(15,118,110,.3);border-radius:999px;background:rgba(255,255,255,.94);box-shadow:0 2px 6px rgba(15,23,42,.22);color:#0f766e;cursor:pointer;font:700 clamp(12px,1.45vw,16px)/1 system-ui,-apple-system,sans-serif;white-space:nowrap;opacity:1}"
        ".trackio-poster-hotspot:hover,.trackio-poster-hotspot:focus-visible{background:#fff;box-shadow:0 0 0 3px rgba(13,148,136,.32),0 3px 8px rgba(15,23,42,.24);outline:none}"
        "</style></head><body><div class=\"trackio-poster\">"
        f'<img src="data:image/png;base64,{image}" alt="Interactive reproduction poster">{buttons}'
        "</div></body></html>"
    )


def _slugs(node: dict) -> set[str]:
    found = {str(node.get("slug", ""))}
    for child in node.get("children", []) or []:
        found.update(_slugs(child))
    return found


def _validate_gate_report(
    report_path: Path,
    poster_html: Path,
    poster_png: Path,
) -> str | None:
    """Return an actionable error when the poster is not release-ready."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"cannot read gate report {report_path}: {exc}"

    if report.get("overall") != "PASS":
        return "gate report overall status is not PASS"

    reported_html = report.get("poster_html")
    if not reported_html:
        return "gate report does not identify poster_html"
    if Path(reported_html).resolve() != poster_html:
        return "gate report belongs to a different poster HTML"

    gates = {
        gate.get("name"): gate
        for gate in report.get("gates", [])
        if isinstance(gate, dict)
    }
    for required in ("measure", "polish"):
        if gates.get(required, {}).get("status") != "PASS":
            return f"required {required} gate did not PASS"

    polish_command = [str(arg) for arg in gates["polish"].get("command", [])]
    if "--strict" not in polish_command:
        return "polish gate was not run in strict mode"

    try:
        if report_path.stat().st_mtime < poster_html.stat().st_mtime:
            return "gate report is older than poster HTML; rerun the gates"
        if poster_png.stat().st_mtime < poster_html.stat().st_mtime:
            return "poster PNG is older than poster HTML; rerender the preview"
    except OSError as exc:
        return f"cannot compare poster artifact timestamps: {exc}"

    return None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("poster_html", help="Annotated source poster HTML")
    p.add_argument("poster_png", help="Rendered poster PNG from render_preview.py")
    p.add_argument(
        "--logbook-manifest", required=True,
        help="Path to .trackio/logbook/logbook.json for slug validation",
    )
    p.add_argument(
        "--gate-report", required=True,
        help="Fresh passing GATE_REPORT.json from run_gates.py --strict-polish",
    )
    p.add_argument("--out", default="poster_embed.html", help="Output HTML path")
    return p


def _main() -> int:
    args = _parser().parse_args()
    poster_html = Path(args.poster_html).resolve()
    poster_png = Path(args.poster_png).resolve()
    manifest_path = Path(args.logbook_manifest).resolve()
    report_path = Path(args.gate_report).resolve()
    required_paths = (poster_html, poster_png, manifest_path, report_path)
    if not all(path.is_file() for path in required_paths):
        print(
            "ERROR: poster HTML, poster PNG, logbook manifest, and gate report "
            "must exist.",
            file=sys.stderr,
        )
        return 2
    gate_error = _validate_gate_report(report_path, poster_html, poster_png)
    if gate_error:
        print(f"ERROR: poster is not release-ready: {gate_error}.", file=sys.stderr)
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
    output = Path(args.out)
    output.write_text(_render_embed(image, hotspots), encoding="utf-8")
    print(f"[logbook_embed] wrote {output} with {len(hotspots)} hotspot(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
