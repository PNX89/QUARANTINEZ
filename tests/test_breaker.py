"""The breaker, its obligation, and the window that cannot be un-missed.

Nothing here sleeps. The clock is advanced by hand, which is what makes a deadline test fast
when it passes and deterministic when it fails, and it keeps this repository from implying
anything about wall-clock behaviour that it has not measured.
"""

from __future__ import annotations

import pytest

from quarantinez.breaker import (
    Breaker,
    Decision,
    Limits,
    ManualClock,
    Obligation,
    decide,
    drawdown_of,
)

LIMITS = Limits(max_drawdown=0.10, flatten_within=60.0)


def step(
    *,
    mark: float,
    position: int,
    previous: Decision | None = None,
    now: float = 0.0,
    peak: float = 100.0,
) -> Decision:
    """One decision, carrying the previous one forward the way a stored row would."""
    return decide(
        limits=LIMITS,
        peak_mark=peak,
        mark=mark,
        position=position,
        breaker=previous.breaker if previous else Breaker.ARMED,
        obligation=previous.obligation if previous else Obligation.NONE,
        deadline=previous.deadline if previous else None,
        now=now,
    )


def test_a_decline_inside_the_limit_changes_nothing() -> None:
    outcome = step(mark=95.0, position=5)
    assert outcome.breaker is Breaker.ARMED
    assert outcome.obligation is Obligation.NONE
    assert outcome.deadline is None
    assert outcome.drawdown == pytest.approx(0.05)


def test_crossing_the_limit_creates_an_obligation_with_a_deadline() -> None:
    """The half most implementations skip. A flag with nothing owed is a print statement."""
    outcome = step(mark=88.0, position=5, now=1_000.0)
    assert outcome.breaker is Breaker.TRIPPED
    assert outcome.obligation is Obligation.OPEN
    assert outcome.deadline == 1_060.0, "the deadline is measured on the clock it was given"


def test_flattening_inside_the_window_discharges_the_obligation() -> None:
    tripped = step(mark=88.0, position=5, now=0.0)
    clock = ManualClock()
    clock.advance(30.0)
    settled = step(mark=88.0, position=0, previous=tripped, now=clock.now())
    assert settled.obligation is Obligation.DISCHARGED


def test_a_window_that_passes_with_the_position_open_is_unknown() -> None:
    """The same terminal answer an unconfirmed order gets, for the same reason.

    Nobody can say what the exposure was during the window, and a system that marked it
    resolved because the position closed afterwards would be stating something it cannot know.
    """
    tripped = step(mark=88.0, position=5, now=0.0)
    clock = ManualClock()
    clock.advance(61.0)
    missed = step(mark=88.0, position=5, previous=tripped, now=clock.now())
    assert missed.obligation is Obligation.UNKNOWN


def test_flattening_after_the_window_does_not_un_miss_it() -> None:
    """The absorbing property, applied to the obligation rather than to the order.

    This is the test that stops the obligation being decorative. Without it, a system could
    trip, miss the window, flatten late, and report a clean run.
    """
    tripped = step(mark=88.0, position=5, now=0.0)
    clock = ManualClock()
    clock.advance(61.0)
    missed = step(mark=88.0, position=5, previous=tripped, now=clock.now())
    assert missed.obligation is Obligation.UNKNOWN

    clock.advance(600.0)
    for position in (3, 1, 0):
        later = step(mark=88.0, position=position, previous=missed, now=clock.now())
        assert later.obligation is Obligation.UNKNOWN, "a missed window was resolved after the fact"


def test_the_decision_is_a_pure_function_of_what_is_stored() -> None:
    """The property the crash proof rests on.

    A process killed before writing a decision can be restarted, given the same stored inputs,
    and must produce the identical decision. That only holds if nothing here reads a clock, an
    environment variable or a global of its own, so it is asserted rather than assumed.
    """
    arguments = dict(
        limits=LIMITS,
        peak_mark=100.0,
        mark=88.0,
        position=5,
        breaker=Breaker.ARMED,
        obligation=Obligation.NONE,
        deadline=None,
        now=1_234.5,
    )
    first = decide(**arguments)  # type: ignore[arg-type]
    second = decide(**arguments)  # type: ignore[arg-type]
    assert first == second


def test_the_clock_refuses_to_run_backwards() -> None:
    """A test that needs time to reverse is a test asserting something that cannot happen."""
    clock = ManualClock()
    clock.advance(10.0)
    with pytest.raises(ValueError, match="does not run backwards"):
        clock.advance(-1.0)
    assert clock.now() == 10.0


def test_a_drawdown_is_a_fraction_and_never_negative() -> None:
    assert drawdown_of(100.0, 90.0) == pytest.approx(0.10)
    assert drawdown_of(100.0, 110.0) == 0.0, "a mark above the peak is not a decline"
    with pytest.raises(ValueError, match="no decline to measure"):
        drawdown_of(0.0, 10.0)


def test_a_policy_that_cannot_be_enforced_is_refused() -> None:
    """Both directions: a limit outside its range, and an obligation with no deadline."""
    for bad in (0.0, 1.0, -0.1, 2.0):
        with pytest.raises(ValueError, match="fraction between zero and one"):
            Limits(max_drawdown=bad, flatten_within=60.0)
    for bad_window in (0.0, -1.0):
        with pytest.raises(ValueError, match="not an obligation"):
            Limits(max_drawdown=0.1, flatten_within=bad_window)


def test_a_tripped_breaker_with_no_obligation_is_refused_rather_than_absorbed() -> None:
    """A state this policy cannot reach, and the match says so rather than shrugging.

    An earlier version ended with a catch-all that passed any obligation through unchanged. It
    made the absorbing guard dead code, which a mutation exposed: deleting the guard changed
    nothing, because the fallback preserved UNKNOWN by accident. A fallback that quietly accepts
    anything will accept the next value somebody adds.
    """
    with pytest.raises(ValueError, match="cannot reach"):
        decide(
            limits=LIMITS,
            peak_mark=100.0,
            mark=88.0,
            position=5,
            breaker=Breaker.TRIPPED,
            obligation=Obligation.NONE,
            deadline=None,
            now=0.0,
        )


def test_a_discharged_obligation_stays_discharged() -> None:
    """The other terminal answer, and it must not drift back to open on a later decline."""
    tripped = step(mark=88.0, position=5, now=0.0)
    settled = step(mark=88.0, position=0, previous=tripped, now=10.0)
    assert settled.obligation is Obligation.DISCHARGED
    later = step(mark=80.0, position=7, previous=settled, now=500.0)
    assert later.obligation is Obligation.DISCHARGED
