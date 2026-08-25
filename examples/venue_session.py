"""The whole argument in one run: five orders, then a window that closes with exposure open.

    uv run python examples/venue_session.py

Offline, deterministic, no key and no container. The marks are committed and invented, the
venues are simulated, and nothing here has ever touched a real one.
"""

from __future__ import annotations

from quarantinez.breaker import Breaker, Decision, Limits, ManualClock, Obligation, decide
from quarantinez.control import ControlPlane
from quarantinez.marks import running_peak, series
from quarantinez.states import State
from quarantinez.venue import MISBEHAVIOURS, Order, WellBehaved

LIMITS = Limits(max_drawdown=0.10, flatten_within=60.0)
POSITION = 5


def orders() -> None:
    plane = ControlPlane()
    print("Five orders against five venues. Only one of them ends with an answer.\n")
    for index, behaviour in enumerate((WellBehaved, *MISBEHAVIOURS), start=1):
        venue = behaviour()
        order = Order(client_id=f"C-{index}", symbol="SYNTH", quantity=10)
        outcome = plane.place(venue, order)
        verdict = (
            outcome.state.value
            if outcome.state is not State.UNKNOWN
            else f"{outcome.state.value} via {outcome.event.value}"
        )
        print(f">>> place(order, venue={venue.name!r})")
        print(f"    {verdict}\n")

    print(
        f"{len(plane.unconfirmed)} of {len(plane.outcomes)} ended unconfirmed. None of them is a "
        "failure to retry:"
    )
    print("each is a terminal state, and each is handed to a person by name.\n")


def breaker() -> None:
    marks = series()
    peaks = running_peak(marks)
    clock = ManualClock()
    state = Decision(Breaker.ARMED, Obligation.NONE, 0.0, None)
    position = POSITION
    tripped_at: str | None = None

    print("The breaker, walked over the committed marks. Every number below is invented.\n")
    print("  date        mark    drawdown  breaker   obligation")
    for peak, entry in zip(peaks, marks, strict=True):
        # One decision per observation, on a clock the run advances rather than waits on.
        state = decide(
            limits=LIMITS,
            peak_mark=peak,
            mark=entry.mark,
            position=position,
            breaker=state.breaker,
            obligation=state.obligation,
            deadline=state.deadline,
            now=clock.now(),
        )
        if state.breaker is Breaker.TRIPPED and tripped_at is None:
            tripped_at = entry.date
        interesting = state.breaker is Breaker.TRIPPED or entry.date == tripped_at
        if interesting or entry.mark == max(m.mark for m in marks):
            print(
                f"  {entry.date}  {entry.mark:6.1f}    {state.drawdown:6.3f}  "
                f"{state.breaker.value:8s}  {state.obligation.value}"
            )
        clock.advance(20.0)

    print(
        f"\nThe breaker tripped on {tripped_at} and the position stayed open past the window, "
        "so the obligation is UNKNOWN."
    )

    flattened = decide(
        limits=LIMITS,
        peak_mark=peaks[-1],
        mark=marks[-1].mark,
        position=0,
        breaker=state.breaker,
        obligation=state.obligation,
        deadline=state.deadline,
        now=clock.now(),
    )
    print(f"Flattening afterwards leaves it {flattened.obligation.value}.")
    print("A window that closed with exposure open is a fact about the past, and closing the")
    print("position later does not reach back into it.")


def main() -> int:
    orders()
    breaker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
