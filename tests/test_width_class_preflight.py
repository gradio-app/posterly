"""``undefined_width_classes`` -- flag ``w-NN`` utility classes used in the
markup that have no matching ``.w-NN`` rule (they silently no-op in the
browser, leaving the element at its default width with no error).
"""
from __future__ import annotations

from _posterly.preflight import undefined_width_classes


_CSS = """
<style>
  .w-45 { width: 45%; }
  .w-50 { width: 50%; }
  .w-100 { width: 100%; }
</style>
"""


def test_flags_offscale_width_class():
    html = _CSS + '<img class="w-40">'  # w-40 is not defined
    assert undefined_width_classes(html) == ["40"]


def test_defined_width_classes_are_ok():
    html = _CSS + '<img class="w-50"><figure class="ff-fig w-45">'
    assert undefined_width_classes(html) == []


def test_multiple_offscale_sorted_numerically():
    html = _CSS + '<img class="w-33"><img class="w-7"><img class="w-120">'
    assert undefined_width_classes(html) == ["7", "33", "120"]


def test_dot_definitions_do_not_count_as_usage():
    # A `.w-45` in CSS is a definition, not a usage; only bare class tokens
    # inside class="..." count as used.
    html = _CSS
    assert undefined_width_classes(html) == []
