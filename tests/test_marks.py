"""The fixture, and whether it actually contains the thing the demonstration needs.

The last test is the one that matters. A fixture can be perfectly well formed and demonstrate
nothing: a series that never declines past the limit would let the breaker never trip, every
other test would still pass, and the demonstration would print a run in which nothing happened.
"""

from __future__ import annotations

import pytest

from quarantinez.breaker import Limits
from quarantinez.marks import deepest_drawdown, running_peak, series

LIMITS = Limits(max_drawdown=0.10, flatten_within=60.0)


def test_the_series_is_dated_ordered_and_positive() -> None:
    marks = series()
    assert len(marks) >= 20
    assert [m.date for m in marks] == sorted(m.date for m in marks)
    assert all(m.mark > 0 for m in marks)
    assert len({m.date for m in marks}) == len(marks), "a date appears twice"


def test_the_running_peak_never_falls() -> None:
    peaks = running_peak(series())
    assert peaks == tuple(sorted(peaks)), "a running peak that falls is not a peak"


def test_the_fixture_contains_a_decline_that_crosses_the_declared_limit() -> None:
    """Otherwise the breaker never trips and the demonstration shows a run where nothing happened.

    Written against the declared limit rather than a hardcoded number, so raising the limit
    without deepening the series fails here rather than quietly producing an empty demonstration.
    """
    deepest = deepest_drawdown(series())
    assert deepest > LIMITS.max_drawdown, (
        f"the deepest decline in the fixture is {deepest:.4f}, which never reaches the "
        f"{LIMITS.max_drawdown} limit, so nothing in this repository would ever trip"
    )


def test_the_decline_is_deep_enough_to_be_unambiguous() -> None:
    """Half a percent past the limit would make the demonstration turn on a rounding decision."""
    assert deepest_drawdown(series()) > LIMITS.max_drawdown * 1.4


def test_the_series_recovers_afterwards_so_the_absorbing_property_is_visible() -> None:
    """The interesting case is a breaker that tripped and a series that then went back up.

    Without a recovery the demonstration could not show that a missed window stays missed, which
    is the property the obligation exists to hold.
    """
    marks = series()
    trough = min(m.mark for m in marks)
    assert marks[-1].mark > trough, "the series never recovers, so a late flatten cannot be shown"


def test_nothing_in_the_fixture_names_a_currency_or_an_instrument() -> None:
    """A drawdown is a fraction. An amount would be a claim this repository does not make."""
    from importlib import resources

    text = (resources.files("quarantinez.data") / "marks.csv").read_text("utf-8")
    for forbidden in ("$", "EUR", "USD", "GBP", "price", "close", "AAPL"):
        assert forbidden not in text, forbidden
    assert text.splitlines()[0] == "date,mark"


@pytest.mark.parametrize("attribute", ["date", "mark"])
def test_every_row_carries_both_fields(attribute: str) -> None:
    assert all(getattr(entry, attribute) for entry in series())
