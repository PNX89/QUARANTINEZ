"""A control step that kills itself at a chosen instant, so the crash under test is a real one.

Not collected by pytest: the name does not start with `test_`. It is launched as a subprocess
and sends itself SIGKILL, which no `finally`, no `atexit` and no buffered write survives.
Raising an exception instead would test the exception handling, and what is claimed here is
about the row that is in the database after the process stops existing.

Two instants matter and both are tested. Dying BEFORE the write leaves the row untouched, so the
next start reads the same inputs and, because the decision is a pure function of them, computes
the same decision. Dying AFTER the write means the work is already done. There is no third place
to be, which is the whole of the argument.
"""

from __future__ import annotations

import os
import signal
import sys

import psycopg

from quarantinez import durable_control
from quarantinez.breaker import Limits

ACCOUNT = "A-1"
LIMITS = Limits(max_drawdown=0.10, flatten_within=60.0)
MARK = 88.0
POSITION = 5
NOW = 1_000.0


def main(argv: list[str]) -> int:
    url, mode = argv[1], argv[2]
    with psycopg.connect(url, autocommit=True) as connection:
        if mode == "before-write":
            durable_control.step(
                connection,
                ACCOUNT,
                LIMITS,
                mark=MARK,
                position=POSITION,
                now=NOW,
                before_write=lambda: os.kill(os.getpid(), signal.SIGKILL),
            )
        else:
            durable_control.step(connection, ACCOUNT, LIMITS, mark=MARK, position=POSITION, now=NOW)
            if mode == "after-write":
                os.kill(os.getpid(), signal.SIGKILL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
