"""The control plane: submit, ask, and record what can honestly be said afterwards.

It is deliberately small. Everything it can conclude comes from `quarantinez.venue.classify`,
every state change goes through `quarantinez.states.transition`, and there is no branch anywhere
that turns an unconfirmed outcome into a confirmed one. If that branch existed it would be the
only interesting line in the repository, and it would make the claim false.

WHAT IT DOES NOT DO. It does not retry. A retry after an unconfirmable outcome is a second order
sent on the assumption that the first one did not happen, which is the assumption that costs
something when it is wrong. It does not poll: asking again cannot turn silence into an answer,
and a loop that keeps asking is a loop that eventually gives up and guesses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarantinez.states import Event, State, transition
from quarantinez.venue import Order, Reply, Venue, classify


@dataclass(frozen=True)
class Outcome:
    """Where an order ended, and everything needed to argue about it afterwards.

    The replies and the status answer are kept even when the outcome is clear, because the
    question a person asks about a quarantined position is what the venue actually said, and a
    control plane that discarded it would answer with a state name and nothing else.
    """

    order: Order
    venue: str
    state: State
    event: Event
    replies: tuple[Reply, ...]
    status: Reply

    @property
    def needs_a_person(self) -> bool:
        return self.state is State.UNKNOWN


@dataclass
class ControlPlane:
    """One run's worth of outcomes, in the order they happened."""

    outcomes: list[Outcome] = field(default_factory=list)

    def place(self, venue: Venue, order: Order) -> Outcome:
        """Submit once, ask once, and record what can be said. No retry and no polling."""
        replies = venue.submit(order)
        first_id = next(
            (r.venue_id for r in replies if hasattr(r, "venue_id")),
            "",
        )
        status = venue.status(str(first_id))
        event = classify(order, replies, status)
        outcome = Outcome(
            order=order,
            venue=venue.name,
            state=transition(State.PENDING, event),
            event=event,
            replies=tuple(replies),
            status=status,
        )
        self.outcomes.append(outcome)
        return outcome

    @property
    def unconfirmed(self) -> list[Outcome]:
        """Everything a person has to be handed. The list this repository exists to produce."""
        return [outcome for outcome in self.outcomes if outcome.needs_a_person]
