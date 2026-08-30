"""The claim, proved by walking the graph rather than by reading the code.

The strongest test here is `test_nothing_reachable_from_unknown_except_quarantine`. It does not
check the edges somebody remembered to write about: it computes the whole reachable set from
UNKNOWN and requires it to be exactly two states. Adding a single edge anywhere that lets
UNKNOWN reach FILLED, however indirectly and however many hops away, fails it.
"""

from __future__ import annotations

import pathlib

import pytest

from quarantinez.states import (
    TABLE,
    TERMINAL,
    Event,
    NoSuchTransition,
    NotYours,
    State,
    outgoing,
    render_table,
    transition,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
STATE_MACHINE = REPO / "docs" / "STATE_MACHINE.md"


def reachable(start: State) -> set[State]:
    """Every state reachable from `start`, following edges to any depth."""
    seen = {start}
    frontier = [start]
    while frontier:
        for target in outgoing(frontier.pop()).values():
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


def test_nothing_reachable_from_unknown_except_quarantine() -> None:
    """The whole claim, as one assertion over the graph.

    Not a list of edges somebody checked. The transitive closure from UNKNOWN must be exactly
    itself and the quarantine record, so an edge added anywhere that eventually lets an
    unconfirmed outcome become a confirmed one fails here however many hops away it is.
    """
    assert reachable(State.UNKNOWN) == {State.UNKNOWN, State.QUARANTINED}


@pytest.mark.parametrize("event", list(Event))
def test_no_event_at_all_escapes_unknown_except_the_declared_one(event: Event) -> None:
    """Exhaustive over every event the machine knows, present and future.

    Parametrised over the enum rather than over a list written here, so an event added later is
    tested against UNKNOWN the moment it exists rather than when somebody remembers.
    """
    if event is Event.QUARANTINED_BY_PERSON:
        assert transition(State.UNKNOWN, event, person="Quelin Zammit") is State.QUARANTINED
        return
    with pytest.raises(NoSuchTransition):
        transition(State.UNKNOWN, event, person="Quelin Zammit")


def test_leaving_unknown_needs_a_person_and_a_blank_name_is_not_one() -> None:
    """The edge exists and is still refused, which is why this is its own exception.

    Whitespace counts as blank. A control plane that accepted a space as a name would have a
    quarantine record naming nobody, which is the same as no record at all with extra steps.
    """
    for blank in (None, "", "   ", "\t\n"):
        with pytest.raises(NotYours):
            transition(State.UNKNOWN, Event.QUARANTINED_BY_PERSON, person=blank)


@pytest.mark.parametrize("state", sorted(TERMINAL))
def test_a_terminal_state_has_no_way_out(state: State) -> None:
    assert outgoing(state) == {}
    for event in Event:
        with pytest.raises(NoSuchTransition):
            transition(state, event, person="Quelin Zammit")


def test_an_impossible_transition_raises_rather_than_returning_the_same_state() -> None:
    """Ignoring an impossible event is how a control plane believes a stale thing for an hour."""
    with pytest.raises(NoSuchTransition) as raised:
        transition(State.FILLED, Event.ACKNOWLEDGED)
    assert "FILLED" in str(raised.value) and "ACKNOWLEDGED" in str(raised.value)


def test_every_state_is_reachable_from_where_an_order_starts() -> None:
    """An unreachable state is a state nobody can test, and a table that lies by omission."""
    assert reachable(State.PENDING) == set(State)


def test_every_event_is_used_somewhere_in_the_table() -> None:
    """A dead event is a name a reader will look for and not find in the machine."""
    used = {event for _, event in TABLE}
    assert used == set(Event)


def test_each_way_a_venue_misbehaves_leads_to_unknown_from_both_live_states() -> None:
    """The four adversarial behaviours are named separately rather than collapsed into a timeout.

    An interviewer asks which of them happened. A single TIMEOUT event answers that with a
    shrug, and the difference between silence and a contradictory acknowledgement is exactly
    the interesting part.
    """
    misbehaviours = (
        Event.SILENCE,
        Event.DOUBLE_ACK,
        Event.FOREIGN_ID,
        Event.UNASKED_QUANTITY,
    )
    for state in (State.PENDING, State.WORKING):
        for event in misbehaviours:
            assert transition(state, event) is State.UNKNOWN


def test_the_rendered_table_describes_the_machine_this_code_implements() -> None:
    """Every edge is rendered, and nothing else is.

    The row count is exact rather than a lower bound. It used to be `count("|") > 3 * len(TABLE)`,
    which is 76 against 42 and slack enough for whole rows to go missing underneath it.
    """
    rendered = render_table()
    for (state, event), target in TABLE.items():
        assert f"| {state.value} | {event.value} | {target.value} |" in rendered
    heading, separator = 1, 1
    expected = heading + separator + len(TABLE) + len(TERMINAL)
    assert len(rendered.splitlines()) == expected, "the rendering gained or lost a row"


def test_the_committed_document_holds_exactly_the_table_this_code_renders() -> None:
    """The document's own header promises this test exists, so here it is.

    Equality rather than containment, and this is the difference that matters. A containment
    check passes with an extra row appended to the document, and an invented row out of UNKNOWN
    is the single thing this repository exists to say cannot happen. Until this test was written
    nothing in the tree read the file at all: it could state the opposite of the headline claim
    and the build stayed green.
    """
    committed = [
        line for line in STATE_MACHINE.read_text("utf-8").splitlines() if line.startswith("|")
    ]
    assert "\n".join(committed) == render_table(), (
        "docs/STATE_MACHINE.md no longer holds the table this code renders. Regenerate it with "
        "scripts/capture_evidence.py rather than editing it."
    )
