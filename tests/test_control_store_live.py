"""The declared endpoint against a database that is really there.

MARKED `services` AND DESELECTED BY DEFAULT. This is the job that exists because the crash proof
cannot be made against an in-memory stand-in, and it starts here rather than arriving with that
proof for a practical reason worth writing down: a job running `pytest -m services` with no
`services` test collects nothing and exits 5, which fails the build for the one reason that is
not a defect.

The repair is a real test rather than a suppressed exit code. This one asserts the thing the
compose file and `control_store` both claim, which is that the endpoint they name answers and is
the database they say it is. That claim is worth holding on its own, and it will still be worth
holding when the crash proof sits beside it.
"""

from __future__ import annotations

import psycopg
import pytest

from quarantinez import control_store

pytestmark = pytest.mark.services


def test_the_declared_endpoint_answers_and_is_the_declared_database() -> None:
    with psycopg.connect(control_store.ControlStore.from_env().url, autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute("select current_database(), current_user")
            row = cursor.fetchone()
    assert row is not None
    assert row[0] == control_store.DATABASE
    assert row[1] == control_store.USER


def test_the_control_state_survives_a_reconnection() -> None:
    """The weakest possible version of the claim this repository is about, held from day one.

    Not the crash proof: nothing is killed here. It asserts only that a value written through
    one connection is visible through a different one, which is the property everything later
    depends on and the first thing to break if the endpoint quietly points somewhere temporary.
    """
    url = control_store.ControlStore.from_env().url
    with psycopg.connect(url, autocommit=True) as writer, writer.cursor() as cursor:
        cursor.execute("drop table if exists reachability_probe")
        cursor.execute("create table reachability_probe (note text primary key)")
        cursor.execute("insert into reachability_probe (note) values ('written once')")

    with psycopg.connect(url, autocommit=True) as reader, reader.cursor() as cursor:
        cursor.execute("select note from reachability_probe")
        row = cursor.fetchone()
        assert row is not None and row[0] == "written once"
        cursor.execute("drop table reachability_probe")
