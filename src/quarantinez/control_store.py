"""Where the durable control state lives, and why the port is not the obvious one.

The control plane's state is a row in PostgreSQL rather than a value in a process, and the
proof that matters is that a process killed between deciding and writing comes back to the
identical state. That proof needs a real database, so this module exists from the first commit
even though nothing writes to it yet.

THE PORT IS 5434 AND THE REASON IS WORTH A SENTENCE. The convention across this toolset is one
port above a service's own default, so cloning a repository cannot collide with something the
reader already runs. Another repository here took 5433 under that rule. Two repositories in one
toolset that cannot be brought up at the same time is a worse outcome than a second number, so
this takes the next free one, and `tests/test_control_store.py` reads compose.yaml rather than
restating it, so the file and this module cannot drift apart quietly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

#: The port PostgreSQL listens on inside its container, which is its own standard port.
CONTAINER_PORT = 5432

#: What compose publishes on the host. Not container port plus one: that number is taken by a
#: sibling repository, and the rule is "do not collide", not "add one".
HOST_PORT = 5434

DATABASE = "quarantinez"
USER = "quarantinez"

#: The container's credential, and the suffix is a convention rather than decoration. This is a
#: throwaway database bound to the loopback interface, holding rows a test wrote a moment ago,
#: and the same value is in `compose.yaml` where anyone can read it. Writing `-demo` into the
#: value says that in the one place a scanner and a reader both look. The portfolio's own
#: pre-push gate flags any `password = "..."` longer than five characters unless the value says
#: what it is, and it is right to: a scanner cannot tell a throwaway from a real one, so the
#: value has to.
PASSWORD = "quarantinez-demo"

URL_VAR = "QUARANTINEZ_POSTGRES_URL"

DEFAULT_URL = f"postgresql://{USER}:{PASSWORD}@127.0.0.1:{HOST_PORT}/{DATABASE}"


@dataclass(frozen=True)
class ControlStore:
    """Where a run keeps the state it must not lose.

    Frozen because a run that changed which database it was pointed at halfway through would
    produce a crash proof that no single connection string explains.
    """

    url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ControlStore:
        """Read the endpoint, falling back to what compose publishes locally.

        `env` is an argument rather than a straight read of `os.environ` so a test can pass a
        mapping instead of mutating the process it runs in.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        return cls(url=source.get(URL_VAR) or DEFAULT_URL)
