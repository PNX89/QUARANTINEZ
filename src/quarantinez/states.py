"""The state machine, and the one state that has no way out.

THE CLAIM THIS FILE CARRIES. An outcome the venue never confirmed is not a failure to retry. It
is a terminal state, and no code path escapes it except to a quarantine record naming a person.

WHY THAT IS UNUSUAL. Every control plane has a state for an outcome it could not confirm, and
most of them treat it as transient: retry, poll, and if the venue eventually answers, resolve it.
That works until the venue never answers. Then the state has to become something, and whatever it
becomes is a guess, made by a program, about a position somebody holds.

Here UNKNOWN is ABSORBING. No retry escapes it, no timeout collapses it into rejected, and no
reconciliation pass quietly decides it was filled after all. The only edge out is to QUARANTINED,
that edge requires a person's name, and nothing in this package takes that edge on its own.

WHY THE TABLE IS DATA RATHER THAN A METHOD PER STATE. A transition written as an `if` inside a
handler is a transition nobody can enumerate. As a mapping it can be walked, printed, rendered
into the document beside it, and asserted over exhaustively, which is what makes "no edge leaves
UNKNOWN" a test rather than a claim about code somebody read carefully.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class State(StrEnum):
    """Where an order stands, as far as this control plane can honestly say."""

    PENDING = "PENDING"
    WORKING = "WORKING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    QUARANTINED = "QUARANTINED"


class Event(StrEnum):
    """What happened, from this side of the connection.

    The four that lead to UNKNOWN are named separately rather than collapsed into one, because
    an interviewer's question is which of them happened, and a single TIMEOUT would answer it
    with a shrug.
    """

    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"

    #: The venue accepted and then stopped answering.
    SILENCE = "SILENCE"
    #: The venue acknowledged twice, with two different order identifiers.
    DOUBLE_ACK = "DOUBLE_ACK"
    #: A status query came back about an order nobody sent.
    FOREIGN_ID = "FOREIGN_ID"
    #: A fill arrived for a quantity nobody asked for.
    UNASKED_QUANTITY = "UNASKED_QUANTITY"

    #: A person took the position. This is the only event that leaves UNKNOWN.
    QUARANTINED_BY_PERSON = "QUARANTINED_BY_PERSON"


#: States from which nothing further happens. QUARANTINED is terminal in this machine because
#: what happens next is a person's problem, recorded elsewhere and not modelled here.
TERMINAL: Final[frozenset[State]] = frozenset({State.FILLED, State.REJECTED, State.QUARANTINED})

#: The whole machine, as data. Every edge in the repository is in this mapping and nowhere else.
TABLE: Final[dict[tuple[State, Event], State]] = {
    (State.PENDING, Event.ACKNOWLEDGED): State.WORKING,
    (State.PENDING, Event.FILLED): State.FILLED,
    (State.PENDING, Event.REJECTED): State.REJECTED,
    (State.PENDING, Event.SILENCE): State.UNKNOWN,
    (State.PENDING, Event.DOUBLE_ACK): State.UNKNOWN,
    (State.PENDING, Event.FOREIGN_ID): State.UNKNOWN,
    (State.PENDING, Event.UNASKED_QUANTITY): State.UNKNOWN,
    (State.WORKING, Event.FILLED): State.FILLED,
    (State.WORKING, Event.REJECTED): State.REJECTED,
    (State.WORKING, Event.SILENCE): State.UNKNOWN,
    (State.WORKING, Event.DOUBLE_ACK): State.UNKNOWN,
    (State.WORKING, Event.FOREIGN_ID): State.UNKNOWN,
    (State.WORKING, Event.UNASKED_QUANTITY): State.UNKNOWN,
    # The only edge out of UNKNOWN, and it needs a person. Everything about this repository is
    # arranged so that this line stays the only one.
    (State.UNKNOWN, Event.QUARANTINED_BY_PERSON): State.QUARANTINED,
}


class NoSuchTransition(ValueError):
    """The machine was asked for an edge that does not exist.

    Raised rather than returning the current state unchanged. Silently ignoring an impossible
    event is how a control plane ends up believing an order is WORKING an hour after the venue
    rejected it, and the error names both halves so the caller can see which assumption was wrong.
    """

    def __init__(self, state: State, event: Event) -> None:
        why = (
            "That state is terminal." if state in TERMINAL else "That pairing is not in the table."
        )
        super().__init__(f"no transition from {state.value} on {event.value}. {why}")
        self.state = state
        self.event = event


class NotYours(PermissionError):
    """Something tried to leave UNKNOWN without naming a person.

    A separate exception from `NoSuchTransition` on purpose. The edge exists; what is missing is
    the only thing that makes taking it meaningful, and conflating the two would let a caller
    read "no such transition" and go looking for a bug in the table.
    """

    def __init__(self) -> None:
        super().__init__(
            "leaving UNKNOWN requires the name of the person taking the position. An unconfirmed "
            "outcome is not resolved by a program deciding it is fine."
        )


def transition(state: State, event: Event, *, person: str | None = None) -> State:
    """The single place a state changes. Raises rather than guessing.

    `person` is keyword-only and is required exactly on the edge out of UNKNOWN, so a caller
    cannot supply it by accident in positional order and cannot omit it where it matters.
    """
    key = (state, event)
    if key not in TABLE:
        raise NoSuchTransition(state, event)
    if state is State.UNKNOWN and not (person or "").strip():
        raise NotYours()
    return TABLE[key]


def outgoing(state: State) -> dict[Event, State]:
    """Every edge leaving `state`, which is what makes the claim enumerable."""
    return {event: target for (source, event), target in TABLE.items() if source is state}


def render_table() -> str:
    """The machine as text, for the document that sits beside it.

    Generated rather than typed, so the committed artefact cannot describe a machine this code
    does not implement. `tests/test_states.py` compares the two.
    """
    lines = ["| from | on | to |", "|---|---|---|"]
    for state in State:
        for event, target in outgoing(state).items():
            lines.append(f"| {state.value} | {event.value} | {target.value} |")
    for state in sorted(TERMINAL):
        lines.append(f"| {state.value} | anything | refused, this state is terminal |")
    return "\n".join(lines)
