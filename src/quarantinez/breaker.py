"""A drawdown breaker whose obligation has a deadline, and what happens when it is missed.

WHY A BREAKER IS USUALLY A PRINT STATEMENT. Tripping is the easy half: compare a decline against
a threshold and set a flag. What follows is the half that decides whether the breaker did
anything, and most implementations stop at the flag. The position is still open, somebody is
supposed to flatten it, and nothing in the system knows whether that happened.

So tripping creates an OBLIGATION with a deadline. The obligation is discharged when the
position reaches zero, and if the deadline passes with it still open, the outcome is UNKNOWN:
the same absorbing state an unconfirmed order lands in, for the same reason. Nobody can say what
the exposure is, and a system that marked it resolved would be guessing.

THE CLOCK IS INJECTED AND THE TESTS ADVANCE IT. Nothing here sleeps. A test that waits for a
deadline is a test that is slow when it passes and flaky when it does not, and it would also be
making a claim about wall-clock behaviour that this repository does not make.

THE MARKS ARE UNITLESS AND INVENTED. There is no currency here and no price feed. A drawdown is
a decline from a peak expressed as a fraction, which needs an index and not an amount, and the
committed fixture says plainly that the numbers were made up for the demonstration.

WHAT THIS IS BOUGHT ON, STATED PLAINLY. Drawdown, kill switch, circuit breaker and position
limit each reach zero employers in the posting register behind this portfolio. This tool is here
for the integrity of the argument rather than for reach, and the card says so rather than
implying demand that was not measured.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Clock(Protocol):
    """Whatever tells the time. Injected everywhere, so nothing here ever sleeps."""

    def now(self) -> float: ...


@dataclass
class ManualClock:
    """A clock a test moves by hand.

    Not a mock. It is the clock the tests use and the same interface production would use, so
    the code path under test is the code path that runs.
    """

    ticks: float = 0.0

    def now(self) -> float:
        return self.ticks

    def advance(self, by: float) -> None:
        if by < 0:
            raise ValueError("time does not run backwards, and a test that needs it to is wrong")
        self.ticks += by


class Breaker(StrEnum):
    ARMED = "ARMED"
    TRIPPED = "TRIPPED"


class Obligation(StrEnum):
    """What is owed after a trip, and whether it was met."""

    NONE = "NONE"
    OPEN = "OPEN"
    DISCHARGED = "DISCHARGED"
    #: The deadline passed with the position still open. Absorbing, like an unconfirmed order.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Limits:
    """The declared policy. Both numbers are fractions and neither is a currency amount."""

    max_drawdown: float
    flatten_within: float

    def __post_init__(self) -> None:
        if not 0 < self.max_drawdown < 1:
            raise ValueError("a drawdown limit is a fraction between zero and one")
        if self.flatten_within <= 0:
            raise ValueError("an obligation with no deadline is not an obligation")


@dataclass(frozen=True)
class Decision:
    """The whole control decision, derived from state and inputs alone.

    Deliberately a pure function of what is stored. That is what makes the crash proof possible:
    a process killed before writing this can be restarted, given the same stored inputs, and
    must produce the identical decision.
    """

    breaker: Breaker
    obligation: Obligation
    drawdown: float
    deadline: float | None


def drawdown_of(peak_mark: float, mark: float) -> float:
    """The decline from a peak, as a fraction. Unitless by construction."""
    if peak_mark <= 0:
        raise ValueError("a peak of zero or less has no decline to measure")
    return max(0.0, (peak_mark - mark) / peak_mark)


def decide(
    *,
    limits: Limits,
    peak_mark: float,
    mark: float,
    position: int,
    breaker: Breaker,
    obligation: Obligation,
    deadline: float | None,
    now: float,
) -> Decision:
    """The one place a control decision is made, and it reads nothing it was not given.

    Keyword-only throughout. This function has eight inputs of three types and a positional call
    would be a bug nobody spots in review.
    """
    decline = drawdown_of(peak_mark, mark)

    if obligation is Obligation.UNKNOWN:
        # Absorbing, exactly as in the order state machine. Nothing recomputes its way out.
        return Decision(Breaker.TRIPPED, Obligation.UNKNOWN, decline, deadline)

    if breaker is Breaker.ARMED:
        if decline < limits.max_drawdown:
            return Decision(Breaker.ARMED, Obligation.NONE, decline, None)
        return Decision(Breaker.TRIPPED, Obligation.OPEN, decline, now + limits.flatten_within)

    # Every remaining obligation is handled by name, and the match is exhaustive. An earlier
    # version ended with a catch-all that passed the obligation through unchanged, which made
    # the absorbing guard above DEAD CODE: mutating it away changed nothing, because the
    # fallback preserved UNKNOWN by accident rather than by decision. A fallback that quietly
    # accepts anything is a fallback that will accept the next value somebody adds.
    match obligation:
        case Obligation.OPEN:
            if position == 0:
                return Decision(Breaker.TRIPPED, Obligation.DISCHARGED, decline, deadline)
            if deadline is not None and now >= deadline:
                # The deadline passed with the position still open. Nobody can say what the
                # exposure was, so this is the same terminal answer an unconfirmed order gets.
                return Decision(Breaker.TRIPPED, Obligation.UNKNOWN, decline, deadline)
            return Decision(Breaker.TRIPPED, Obligation.OPEN, decline, deadline)
        case Obligation.DISCHARGED:
            return Decision(Breaker.TRIPPED, Obligation.DISCHARGED, decline, deadline)
        case Obligation.NONE:
            raise ValueError(
                "a tripped breaker with no obligation is a state this policy cannot reach. "
                "Tripping creates one, and nothing clears it back to none."
            )
        case Obligation.UNKNOWN:  # pragma: no cover - handled above, kept for exhaustiveness
            raise AssertionError("unreachable: the absorbing case returns before this point")
