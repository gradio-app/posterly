"""``run_gates.py --strict-polish`` must make a polish advisory BLOCK.

Regression test for the ICML-2026 reproduction bug: under ``--strict-polish``
the polish child (``poster_check.py polish --strict``) exits 1 on a warning,
but ``_status_from_returncode(1, "soft")`` mapped that to WARN and left
``overall: PASS`` -- so a "not ready to pin" poster reported green.

We monkeypatch the child-process runner so the test needs no Chromium: each
gate returns a canned ``(returncode, stdout, stderr)`` and we assert on the
aggregated ``overall`` verdict and the polish gate's recorded severity/status.
"""
from __future__ import annotations

from pathlib import Path

import run_gates


_HTML = """<!DOCTYPE html><html><head>
<style>@page { size: 24in 36in; margin: 0; }</style>
</head><body><div data-measure-role="poster"></div></body></html>
"""


def _write_poster(tmp_path: Path) -> Path:
    p = tmp_path / "poster.html"
    p.write_text(_HTML, encoding="utf-8")
    return p


def _fake_child(polish_rc: int):
    """Return a stand-in for ``run_gates._run_child`` keyed off the argv.

    style speaks JSON (so its summary parses); preflight / measure always
    pass; polish returns the parametrised exit code.
    """
    def _run(argv, cwd):  # noqa: ANN001
        joined = " ".join(argv)
        if "style_check.py" in joined:
            return 0, '{"gate": "style", "status": "PASS", "rules": []}', ""
        if "polish" in argv:
            return polish_rc, "[polish] warnings: 1\nWARN: WIDOW: ...\n", ""
        # preflight / measure
        return 0, "[gate] PASS", ""
    return _run


def _polish_entry(report: dict) -> dict:
    return next(g for g in report["gates"] if g["name"] == "polish")


def test_strict_polish_advisory_flips_overall_to_fail(tmp_path, monkeypatch):
    html = _write_poster(tmp_path)
    monkeypatch.setattr(run_gates, "_run_child", _fake_child(polish_rc=1))
    opts = run_gates.build_parser().parse_args([str(html), "--strict-polish"])

    report = run_gates.run_all(html.resolve(), opts)

    assert report["overall"] == "FAIL"
    assert report["hard_failures"] >= 1
    polish = _polish_entry(report)
    # Under --strict-polish the gate is promoted to a HARD, blocking gate.
    assert polish["severity"] == "hard"
    assert polish["status"] == "FAIL"


def test_strict_polish_clean_run_passes(tmp_path, monkeypatch):
    html = _write_poster(tmp_path)
    monkeypatch.setattr(run_gates, "_run_child", _fake_child(polish_rc=0))
    opts = run_gates.build_parser().parse_args([str(html), "--strict-polish"])

    report = run_gates.run_all(html.resolve(), opts)

    assert report["overall"] == "PASS"
    polish = _polish_entry(report)
    assert polish["severity"] == "hard"
    assert polish["status"] == "PASS"


def test_non_strict_polish_stays_soft_and_non_blocking(tmp_path, monkeypatch):
    # Without --strict, poster_check.py polish exits 0 even with advisories,
    # so the gate is soft and never blocks.
    html = _write_poster(tmp_path)
    monkeypatch.setattr(run_gates, "_run_child", _fake_child(polish_rc=0))
    opts = run_gates.build_parser().parse_args([str(html)])

    report = run_gates.run_all(html.resolve(), opts)

    assert report["overall"] == "PASS"
    assert _polish_entry(report)["severity"] == "soft"
