"""Every misbehaviour, driven end to end, landing where it has to land.

The test that matters is the last one: it is not a list of four scenarios somebody wrote out, it
is parametrised over the declared misbehaviours, so a fifth added to that tuple is exercised the
moment it exists rather than when somebody remembers to add a case.
"""

from __future__ import annotations

import pytest

from quarantinez.control import ControlPlane
from quarantinez.states import TABLE, Event, State
from quarantinez.venue import (
    MISBEHAVIOURS,
    AcceptsThenGoesQuiet,
    AcknowledgesTwice,
    AnswersAboutSomethingElse,
    FillsAQuantityNobodySent,
    Order,
    RejectsAfterAcknowledging,
    RejectsOnSubmission,
    Reply,
    SaysNothingAtAll,
    StillWorkingWhenAsked,
    WellBehaved,
)

ORDER = Order(client_id="C-1", symbol="SYNTH", quantity=10)

#: The behaviours that are not misbehaviours, each with the answer it has to produce. Written out
#: by name rather than read off the module, so deleting one makes this table wrong instead of
#: quietly making the suite cover one case fewer.
ORDINARY: dict[type, tuple[Event, State]] = {
    RejectsOnSubmission: (Event.REJECTED, State.REJECTED),
    RejectsAfterAcknowledging: (Event.REJECTED, State.REJECTED),
    StillWorkingWhenAsked: (Event.ACKNOWLEDGED, State.WORKING),
    SaysNothingAtAll: (Event.SILENCE, State.UNKNOWN),
}


def test_a_venue_that_behaves_produces_a_confirmed_outcome() -> None:
    """Without this the repository could pass everything by never confirming anything."""
    outcome = ControlPlane().place(WellBehaved(), ORDER)
    assert outcome.state is State.FILLED
    assert outcome.event is Event.FILLED
    assert not outcome.needs_a_person


@pytest.mark.parametrize("behaviour", MISBEHAVIOURS)
def test_every_declared_misbehaviour_ends_unconfirmed(behaviour: type) -> None:
    """Parametrised over the declaration, so a fifth misbehaviour is covered when it is added."""
    outcome = ControlPlane().place(behaviour(), ORDER)
    assert outcome.state is State.UNKNOWN, f"{behaviour.__name__} did not end unconfirmed"
    assert outcome.needs_a_person


def test_each_misbehaviour_is_classified_as_itself_rather_than_as_a_timeout() -> None:
    """Which one happened is the interviewer's question, so the four stay distinguishable."""
    expected = {
        AcceptsThenGoesQuiet: Event.SILENCE,
        AcknowledgesTwice: Event.DOUBLE_ACK,
        AnswersAboutSomethingElse: Event.FOREIGN_ID,
        FillsAQuantityNobodySent: Event.UNASKED_QUANTITY,
    }
    for behaviour, event in expected.items():
        assert ControlPlane().place(behaviour(), ORDER).event is event


def test_every_branch_of_the_interpretation_layer_is_reached_by_some_venue() -> None:
    """Four branches of `classify` had nothing that could reach them, so all four were free.

    Each of the four returned a value no test compared to anything: a refusal on submission, a
    refusal in answer to a status query, an acknowledgement that says only that the order is
    still held, and a submission nobody acknowledged. Each one could return any event at all and
    the whole suite stayed green. The four venues below are the four that reach them.
    """
    assert len(ORDINARY) == 4, "a branch of the interpretation layer lost the venue that reaches it"
    for behaviour, (event, state) in ORDINARY.items():
        outcome = ControlPlane().place(behaviour(), ORDER)
        assert outcome.event is event, behaviour.__name__
        assert outcome.state is state, behaviour.__name__


def test_every_event_the_table_names_is_one_a_venue_can_actually_produce() -> None:
    """The half `test_every_event_is_used_somewhere_in_the_table` cannot check.

    That test reads the keys of TABLE and compares them to the Event enum, which is the table
    against itself. This runs the venues and compares what they emit to what the machine claims
    to accept. Two events sat in the table, in the README diagram and in the generated document
    while nothing in the tree emitted either of them.

    QUARANTINED_BY_PERSON is excluded by name: it is the one event a venue cannot cause, which
    is the whole point of it.
    """
    venues = (WellBehaved, *MISBEHAVIOURS, *ORDINARY)
    produced = {ControlPlane().place(behaviour(), ORDER).event for behaviour in venues}
    from_a_venue = {event for _, event in TABLE} - {Event.QUARANTINED_BY_PERSON}
    assert from_a_venue <= produced, f"no venue produces {sorted(from_a_venue - produced)}"


def test_the_replies_survive_into_the_outcome() -> None:
    """A person handed a quarantined position asks what the venue said, not what state it is in."""
    outcome = ControlPlane().place(AcknowledgesTwice(), ORDER)
    assert len(outcome.replies) == 2
    identifiers = {getattr(reply, "venue_id", None) for reply in outcome.replies}
    assert len(identifiers) == 2, "two acknowledgements collapsed into one"


def test_the_unconfirmed_list_is_what_a_person_is_handed() -> None:
    plane = ControlPlane()
    plane.place(WellBehaved(), ORDER)
    for behaviour in MISBEHAVIOURS:
        plane.place(behaviour(), ORDER)
    assert len(plane.outcomes) == len(MISBEHAVIOURS) + 1
    assert len(plane.unconfirmed) == len(MISBEHAVIOURS)
    assert all(outcome.state is State.UNKNOWN for outcome in plane.unconfirmed)


def test_an_order_for_nothing_is_refused_before_it_reaches_a_venue() -> None:
    for bad in ({"quantity": 0}, {"quantity": -5}):
        with pytest.raises(ValueError, match="not an order"):
            Order(client_id="C-1", symbol="SYNTH", **bad)
    with pytest.raises(ValueError, match="cannot be reconciled"):
        Order(client_id="   ", symbol="SYNTH", quantity=1)


def test_the_control_plane_never_retries() -> None:
    """A retry after an unconfirmable outcome is a second order sent on an assumption.

    Counted rather than asserted about the source: the venue records how many submissions it
    saw, and one order must produce exactly one.
    """
    seen: list[Order] = []

    class Counting(AcceptsThenGoesQuiet):
        def submit(self, order: Order) -> list[Reply]:
            seen.append(order)
            return super().submit(order)

    ControlPlane().place(Counting(), ORDER)
    assert len(seen) == 1
