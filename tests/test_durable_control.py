"""Killing the process at both instants and requiring the same row afterwards.

MARKED `services`. The claim is about what a real database holds after a real process stops
existing, and an in-memory stand-in cannot make it.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from collections.abc import Iterator

import psycopg
import pytest

from quarantinez import control_store, durable_control
from quarantinez.breaker import Breaker, Limits, Obligation

pytestmark = pytest.mark.services

CHILD = pathlib.Path(__file__).resolve().parent / "crash_child.py"
ACCOUNT = "A-1"
LIMITS = Limits(max_drawdown=0.10, flatten_within=60.0)
PEAK, MARK, POSITION, NOW = 100.0, 88.0, 5, 1_000.0


@pytest.fixture
def fresh() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """A control row in a known state, rebuilt every test so a rerun cannot inherit anything."""
    url = control_store.ControlStore.from_env().url
    with psycopg.connect(url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("drop table if exists control")
        durable_control.install(connection)
        durable_control.start(connection, ACCOUNT, peak_mark=PEAK, mark=PEAK, position=POSITION)
        yield connection


def crash(mode: str) -> int:
    url = control_store.ControlStore.from_env().url
    done = subprocess.run([sys.executable, str(CHILD), url, mode], capture_output=True, check=False)
    return done.returncode


def test_the_child_really_dies_of_a_signal(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    """If this ever becomes a tidy exit, everything below is testing something else."""
    assert crash("before-write") == -9


def test_a_crash_before_the_write_leaves_the_row_untouched(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    before = durable_control.read(fresh, ACCOUNT)
    assert crash("before-write") == -9
    after = durable_control.read(fresh, ACCOUNT)
    assert after == before, "a decision that was never written changed the stored state"


def test_the_restart_after_that_crash_reaches_the_state_the_crash_was_going_to_write(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    """The heart of it. The decision is a pure function of the row, so recomputing agrees.

    This is what makes a crash between deciding and writing harmless: nothing was lost, because
    nothing that was going to be written depended on anything the dead process held in memory.
    """
    assert crash("before-write") == -9
    durable_control.step(fresh, ACCOUNT, LIMITS, mark=MARK, position=POSITION, now=NOW)
    restarted = durable_control.read(fresh, ACCOUNT)
    assert restarted is not None
    assert restarted.breaker is Breaker.TRIPPED
    assert restarted.obligation is Obligation.OPEN
    assert restarted.deadline == NOW + LIMITS.flatten_within


def test_a_crash_after_the_write_leaves_the_same_state_as_a_clean_run(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    """The other instant, and it must land in the identical row."""
    assert crash("after-write") == -9
    crashed = durable_control.read(fresh, ACCOUNT)

    with fresh.cursor() as cursor:
        cursor.execute("drop table control")
    durable_control.install(fresh)
    durable_control.start(fresh, ACCOUNT, peak_mark=PEAK, mark=PEAK, position=POSITION)
    assert crash("clean") == 0
    cleanly = durable_control.read(fresh, ACCOUNT)

    assert crashed == cleanly, "where the process died changed where the state ended up"


def test_the_breaker_and_the_position_are_the_same_row(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Two rows can disagree, and a control plane that believes both is going to act on one.

    Asserted against the schema rather than the code, so splitting them into two tables later
    fails here rather than passing quietly.
    """
    with fresh.cursor() as cursor:
        cursor.execute(
            "select column_name from information_schema.columns where table_name = 'control'"
        )
        columns = {str(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "select count(*) from information_schema.tables where table_schema = 'public'"
        )
        row = cursor.fetchone()
    assert {"breaker", "position", "obligation", "deadline"} <= columns
    assert row is not None and int(str(row[0])) == 1, "the control state is spread across tables"


def test_applying_the_schema_twice_is_the_same_as_applying_it_once(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    """A second deployment against an existing database must not fail on the first statement."""
    durable_control.install(fresh)
    durable_control.install(fresh)
    durable_control.start(fresh, ACCOUNT, peak_mark=PEAK, mark=PEAK, position=POSITION)
    assert durable_control.read(fresh, ACCOUNT) is not None


def test_a_step_without_a_row_is_refused_rather_than_inventing_one(
    fresh: psycopg.Connection[tuple[object, ...]],
) -> None:
    with pytest.raises(LookupError, match="no control row"):
        durable_control.step(fresh, "A-NOBODY", LIMITS, mark=MARK, position=POSITION, now=NOW)
