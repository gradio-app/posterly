"""verify-final: --canvas vs --from-html mutual-exclusion + missing-input
behaviour. Doesn't exercise pdfinfo (system dep, integration-tested via
the hello_world smoke test in CI)."""
from __future__ import annotations

import argparse

from _posterly import verify_final


def _args(**over):
    base = argparse.Namespace(
        pdf="nonexistent.pdf",
        canvas=None,
        from_html=None,
        dim_tol_in=0.05,
        max_size_mb=20.0,
        allow_rotated=False,
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def test_missing_pdf_returns_2(tmp_path) -> None:
    rc = verify_final.cmd_verify_final(_args(pdf=str(tmp_path / "missing.pdf")))
    assert rc == 2


def test_neither_canvas_nor_from_html_returns_2(tmp_path) -> None:
    """The old default was --canvas=60x36in, which silently passed
    a 24x36in poster as wrong-sized. Now both are None → exit 2 with a
    clear message."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf)))
    assert rc == 2


def test_both_canvas_and_from_html_returns_2(tmp_path) -> None:
    """Mutually exclusive — supplying both should fail-fast rather
    than silently preferring one."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    html = tmp_path / "y.html"
    html.write_text(
        "<html><head><style>@page { size: 36in 47in }</style>"
        "</head></html>", encoding="utf-8",
    )
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), canvas=(36.0, 47.0), from_html=str(html))
    )
    assert rc == 2


def test_from_html_missing_path_returns_2(tmp_path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), from_html=str(tmp_path / "missing.html"))
    )
    assert rc == 2


def test_from_html_with_no_page_returns_2(tmp_path) -> None:
    """When --from-html points to a file without an @page rule, fail
    cleanly rather than silently fall back to a default canvas."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    html = tmp_path / "y.html"
    html.write_text("<html><body>no @page here</body></html>",
                    encoding="utf-8")
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), from_html=str(html))
    )
    assert rc == 2
