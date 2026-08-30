"""The breaker, its obligation, and the window that cannot be un-missed.

Nothing here sleeps. The clock is advanced by hand, which is what makes a deadline test fast
when it passes and deterministic when it fails, and it keeps this repository from implying
anything about wall-clock behaviour that it has not measured.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Mapping

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
    """The property the crash proof rests on, as far as running it twice can show.

    A process killed before writing a decision can be restarted, given the same stored inputs,
    and must produce the identical decision. Two adjacent calls catch anything that changes
    between them, which is a clock and little else. The test below carries the rest of it, and
    the docstring here used to claim that rest without asserting it.
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


def test_the_decision_reads_nothing_but_the_arguments_it_was_given() -> None:
    """The half of the purity claim that two identical calls cannot see.

    An environment variable does not change between two adjacent calls, and neither does a module
    global, so equality above rules out neither. The crash proof cannot see them either: the child
    inherits the parent's environment, so a recomputation after the kill agrees by construction.
    A single line adding `os.environ.get("FUDGE")` to the decline tripped a ten per cent breaker
    on a one per cent decline with all ninety-one tests green.

    Checked by naming every global these two functions resolve, because that is the door all
    three arrive through: an environment variable needs `os`, a clock needs `time`, and a global
    of its own needs the global. Any of them shows up here as a name that is not on this list.
    """
    module = vars(sys.modules[decide.__module__])
    referenced = set(decide.__code__.co_names) | set(drawdown_of.__code__.co_names)
    resolved = {name for name in referenced if name in module}
    assert resolved == {"drawdown_of", "Decision", "Breaker", "Obligation"}, (
        f"the decision now reads {sorted(resolved)} out of its own module. It is a pure function "
        "of its arguments or the crash proof is a coincidence, and it cannot be both."
    )


class Hostile(Mapping[str, str]):
    """An environment that answers nothing and says who asked.

    Substituted for `os.environ` rather than filled with a value, because filling it only catches
    a variable whose name the test guessed. Anything reaching the environment at all, by any
    name and through any import, arrives here.
    """

    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"the decision read the environment variable {key!r}")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("the decision walked the environment")

    def __len__(self) -> int:
        raise AssertionError("the decision measured the environment")


def test_the_decision_never_reaches_for_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The named property that neither the equality above nor the crash proof can see.

    An environment variable is constant across two adjacent calls, so equality says nothing about
    it, and the crash child inherits its parent's environment, so a recomputation after the kill
    agrees by construction. One line adding `os.environ.get("FUDGE")` to the decline tripped a ten
    per cent breaker on a one per cent decline with the whole suite green.
    """
    monkeypatch.setattr(os, "environ", Hostile())
    try:
        outcome = step(mark=88.0, position=5)
    finally:
        # Put it back before anything else runs. pytest's own reporting reads the environment,
        # so a window wider than the call under test fails on the test runner rather than on it.
        monkeypatch.undo()
    assert outcome.breaker is Breaker.TRIPPED
    assert outcome.drawdown == pytest.approx(0.12)


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
