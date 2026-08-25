"""A simulated venue, and four ways a real one misbehaves.

NOT A STUB. A stub answers correctly and quickly, which makes every test pass and proves that
the happy path works, which nobody doubted. These behaviours are the ones that produce an
outcome nobody can confirm, and each is a named scenario rather than a flag.

  ACCEPTS AND THEN STOPS ANSWERING. The order was taken. Whether it rested, filled or was
  cancelled is unknowable from this side, and no amount of asking changes that.

  ACKNOWLEDGES TWICE, WITH TWO IDENTIFIERS. Both acknowledgements are for one submission. One of
  the identifiers is real and there is no way to tell which, so a control plane that picks one
  has guessed.

  ANSWERS A STATUS QUERY WITH AN IDENTIFIER NOBODY SENT. The answer is about something else, and
  a control plane that reads the state out of it has attached another order's outcome to this one.

  RETURNS A FILL FOR A QUANTITY NOBODY ASKED FOR. Arithmetic that trusts it is arithmetic about a
  position that does not exist.

NO TIMING ANYWHERE, AND THAT IS DELIBERATE. "Stops answering" is modelled as a definite absence
of an answer rather than as a wait, so a test asserts a property instead of racing a clock. This
repository makes no claim about latency, and a simulated wait would look like one.

NO PROTOCOL. There is no wire format here, no session layer, and no vocabulary borrowed from any
real venue's specification. What is modelled is the shape of the misbehaviour, which is the part
that reaches the state machine.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from quarantinez.states import Event


@dataclass(frozen=True)
class Order:
    """What was asked for. No price, because nothing here is priced by the venue."""

    client_id: str
    symbol: str
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("an order for nothing is not an order")
        if not self.client_id.strip():
            raise ValueError("an order without a client identifier cannot be reconciled later")


@dataclass(frozen=True)
class Acknowledgement:
    venue_id: str


@dataclass(frozen=True)
class Rejection:
    reason: str


@dataclass(frozen=True)
class Fill:
    venue_id: str
    quantity: int


@dataclass(frozen=True)
class NoAnswer:
    """The venue did not answer, and this is a value rather than an exception.

    An exception would be caught somewhere and turned into a retry, which is the behaviour this
    repository exists to argue against. As a value it has to be handled, and the type checker
    says so at every call site.
    """


Reply = Acknowledgement | Rejection | Fill | NoAnswer


class Venue(Protocol):
    """The slice of a venue this control plane talks to."""

    name: str

    def submit(self, order: Order) -> list[Reply]:
        """Replies to one submission. A list, because a venue may answer more than once."""
        ...

    def status(self, venue_id: str) -> Reply:
        """What the venue says about an identifier it gave out."""
        ...


@dataclass
class WellBehaved:
    """Answers once, correctly, for the same quantity that was asked for."""

    name: str = "well behaved"
    fills: bool = True
    _seen: dict[str, Order] = field(default_factory=dict)

    def submit(self, order: Order) -> list[Reply]:
        venue_id = f"V-{order.client_id}"
        self._seen[venue_id] = order
        return [Acknowledgement(venue_id=venue_id)]

    def status(self, venue_id: str) -> Reply:
        order = self._seen.get(venue_id)
        if order is None:
            return NoAnswer()
        return Fill(venue_id=venue_id, quantity=order.quantity) if self.fills else NoAnswer()


@dataclass
class AcceptsThenGoesQuiet:
    """Takes the order and never answers about it again."""

    name: str = "accepts then goes quiet"
    _seen: set[str] = field(default_factory=set)

    def submit(self, order: Order) -> list[Reply]:
        venue_id = f"V-{order.client_id}"
        self._seen.add(venue_id)
        return [Acknowledgement(venue_id=venue_id)]

    def status(self, venue_id: str) -> Reply:
        return NoAnswer()


@dataclass
class AcknowledgesTwice:
    """Two acknowledgements, two identifiers, one submission.

    Both answers are about the same order. One identifier is the venue's real handle on it and
    there is no way from here to tell which, so any choice is a guess and the position is
    unconfirmed regardless of how confidently a program picks.
    """

    name: str = "acknowledges twice"

    def submit(self, order: Order) -> list[Reply]:
        return [
            Acknowledgement(venue_id=f"V-{order.client_id}-a"),
            Acknowledgement(venue_id=f"V-{order.client_id}-b"),
        ]

    def status(self, venue_id: str) -> Reply:
        return NoAnswer()


@dataclass
class AnswersAboutSomethingElse:
    """A status query comes back carrying an identifier that was never sent."""

    name: str = "answers about something else"

    def submit(self, order: Order) -> list[Reply]:
        return [Acknowledgement(venue_id=f"V-{order.client_id}")]

    def status(self, venue_id: str) -> Reply:
        return Fill(venue_id=f"{venue_id}-SOMEBODY-ELSE", quantity=1)


@dataclass
class FillsAQuantityNobodySent:
    """A fill arrives, correctly identified, for a quantity nobody asked for."""

    name: str = "fills a quantity nobody sent"
    _seen: dict[str, Order] = field(default_factory=dict)

    def submit(self, order: Order) -> list[Reply]:
        venue_id = f"V-{order.client_id}"
        self._seen[venue_id] = order
        return [Acknowledgement(venue_id=venue_id)]

    def status(self, venue_id: str) -> Reply:
        order = self._seen.get(venue_id)
        if order is None:
            return NoAnswer()
        return Fill(venue_id=venue_id, quantity=order.quantity + 1)


#: Every misbehaviour, in a fixed order, so a transcript can be regenerated identically and a
#: reader can find the scenario a test names.
MISBEHAVIOURS: tuple[type, ...] = (
    AcceptsThenGoesQuiet,
    AcknowledgesTwice,
    AnswersAboutSomethingElse,
    FillsAQuantityNobodySent,
)


def classify(order: Order, replies: list[Reply], status: Reply) -> Event:
    """What happened, expressed as the event the state machine understands.

    This is the whole interpretation layer and it is deliberately small. Everything it can
    conclude is one of the events in `quarantinez.states`, and everything it cannot conclude is
    one of the four that lead to UNKNOWN. There is no fallback branch that returns a hopeful
    answer, and mypy proves the match is exhaustive.
    """
    acknowledgements = [reply for reply in replies if isinstance(reply, Acknowledgement)]
    if len(acknowledgements) > 1:
        return Event.DOUBLE_ACK
    if any(isinstance(reply, Rejection) for reply in replies):
        return Event.REJECTED
    if not acknowledgements:
        return Event.SILENCE

    expected_id = acknowledgements[0].venue_id
    match status:
        case NoAnswer():
            return Event.SILENCE
        case Rejection():
            return Event.REJECTED
        case Acknowledgement():
            return Event.ACKNOWLEDGED
        case Fill(venue_id=venue_id, quantity=quantity):
            if venue_id != expected_id:
                return Event.FOREIGN_ID
            if quantity != order.quantity:
                return Event.UNASKED_QUANTITY
            return Event.FILLED


def transcript(venue: Venue, order: Order) -> Iterator[str]:
    """One scenario, as lines a person can read and a test can compare against."""
    yield f"venue: {venue.name}"
    yield (
        f">>> submit(client_id={order.client_id!r}, symbol={order.symbol!r}, "
        f"quantity={order.quantity})"
    )
    replies = venue.submit(order)
    for reply in replies:
        yield f"    {reply!r}"
    first = next((r for r in replies if isinstance(r, Acknowledgement)), None)
    venue_id = first.venue_id if first else ""
    yield f">>> status({venue_id!r})"
    answer = venue.status(venue_id)
    yield f"    {answer!r}"
    yield f"    classified as {classify(order, replies, answer).value}"
