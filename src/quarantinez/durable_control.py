"""The control state as one row, and why a process dying cannot change where it ends up.

WHAT IS BEING CLAIMED, AND WHAT IS NOT. This is a crash consistency proof: a control decision
survives the process dying. It is deliberately NOT an exactly-once proof about an effect. A
sibling repository in this toolset proves that a paid call happens once and is never replayed;
this proves something different and simpler to state, which is that killing the process at any
point leaves the stored state somewhere the next start agrees with.

THE BREAKER AND THE POSITION ARE ONE ROW. Not two tables kept in step, and not a flag beside a
number. Two rows can disagree, and a control plane that believes the breaker is tripped while the
position row says flat is a control plane that will act on one of them.

WHY THE PROOF WORKS AT ALL. `quarantinez.breaker.decide` is a pure function of what is stored. A
process killed after deciding and before writing has changed nothing, and the next start reads
the same inputs and computes the same decision. A process killed after writing has already
finished, which is true only because `write` commits rather than trusting the caller to have
connected in autocommit: a durability guarantee that depends on a flag somebody else passed is
not a guarantee this module makes. There is no third place to be, so there is no interleaving
that produces a state the next start disagrees with, and `tests/test_durable_control.py` kills at
both points and requires the identical final row.

That is why the purity of `decide` is asserted in its own test rather than left as a comment.
The moment it reads a clock of its own, this claim becomes false and nothing else here changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from quarantinez.breaker import Breaker, Decision, Limits, Obligation, decide

SCHEMA = """
create table if not exists control (
    account     text primary key,
    position    integer not null,
    peak_mark   double precision not null,
    mark        double precision not null,
    breaker     text not null,
    obligation  text not null,
    deadline    double precision,
    decided_at  double precision not null
);
"""


@dataclass(frozen=True)
class ControlRow:
    """Everything the next start needs, in one place."""

    account: str
    position: int
    peak_mark: float
    mark: float
    breaker: Breaker
    obligation: Obligation
    deadline: float | None
    decided_at: float


def install(connection: psycopg.Connection[tuple[object, ...]]) -> None:
    """Idempotent by construction. Applying this twice has to be the same as applying it once."""
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA)


def start(
    connection: psycopg.Connection[tuple[object, ...]],
    account: str,
    *,
    peak_mark: float,
    mark: float,
    position: int,
) -> None:
    """Create the row if it is not there. An upsert, so a restart never fails on it."""
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into control (account, position, peak_mark, mark, breaker, obligation, "
            "deadline, decided_at) values (%s, %s, %s, %s, %s, %s, null, 0) "
            "on conflict (account) do nothing",
            (account, position, peak_mark, mark, Breaker.ARMED.value, Obligation.NONE.value),
        )


def read(connection: psycopg.Connection[tuple[object, ...]], account: str) -> ControlRow | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "select account, position, peak_mark, mark, breaker, obligation, deadline, "
            "decided_at from control where account = %s",
            (account,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return ControlRow(
        account=str(row[0]),
        position=int(str(row[1])),
        peak_mark=float(str(row[2])),
        mark=float(str(row[3])),
        breaker=Breaker(str(row[4])),
        obligation=Obligation(str(row[5])),
        deadline=None if row[6] is None else float(str(row[6])),
        decided_at=float(str(row[7])),
    )


def write(
    connection: psycopg.Connection[tuple[object, ...]],
    account: str,
    decision: Decision,
    *,
    peak_mark: float,
    mark: float,
    position: int,
    now: float,
) -> None:
    """One statement, one row, and the commit that makes the row a fact.

    The commit belongs here rather than to the caller. A psycopg connection is not autocommit by
    default, so an UPDATE on its own sits in an open transaction that a SIGKILL discards: this
    function would return, the claim above would say the work is done, and every other connection
    including the next start would still read the previous decision. Leaving it to the caller
    made the whole proof a property of the flag the test harness happened to pass.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "update control set position = %s, peak_mark = %s, mark = %s, breaker = %s, "
            "obligation = %s, deadline = %s, decided_at = %s where account = %s",
            (
                position,
                peak_mark,
                mark,
                decision.breaker.value,
                decision.obligation.value,
                decision.deadline,
                now,
                account,
            ),
        )
    connection.commit()


def step(
    connection: psycopg.Connection[tuple[object, ...]],
    account: str,
    limits: Limits,
    *,
    mark: float,
    position: int,
    now: float,
    before_write: object = None,
) -> Decision:
    """Read, decide, write. `before_write` is a seam the crash child uses and nothing else does.

    It is a callable invoked between the decision and the write, and it exists because the only
    honest way to test a crash at that instant is to arrange one. It defaults to nothing, it is
    keyword-only, and a caller who does not know about it cannot reach it by accident.
    """
    row = read(connection, account)
    if row is None:
        raise LookupError(f"no control row for {account!r}. Call start() first.")

    # The peak runs, which is what `marks.running_peak` does for the in-memory demonstration and
    # what `drawdown_of` means by a peak. A stored peak that never moved would measure every
    # later decline from whatever level the account was opened at, so a fall off a high reached
    # afterwards could not trip the breaker however deep it went.
    peak_mark = max(row.peak_mark, mark)

    decision = decide(
        limits=limits,
        peak_mark=peak_mark,
        mark=mark,
        position=position,
        breaker=row.breaker,
        obligation=row.obligation,
        deadline=row.deadline,
        now=now,
    )

    if callable(before_write):
        before_write()

    write(
        connection,
        account,
        decision,
        peak_mark=peak_mark,
        mark=mark,
        position=position,
        now=now,
    )
    return decision
