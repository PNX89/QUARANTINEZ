# QUARANTINEZ

**Being built in the open. The README is written last, from captured output, so this page is
short on purpose and will be replaced rather than extended.**

[![CI](https://github.com/PNX89/QUARANTINEZ/actions/workflows/ci.yml/badge.svg)](https://github.com/PNX89/QUARANTINEZ/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What it sets out to argue

An outcome the venue never confirmed is not a failure to retry. It is a terminal state, and no
code path here escapes it except to a quarantine record naming a person.

That is a claim, and claims here are meant to be checkable. Nothing on this page is evidence for
it yet.

## What is here today

The scaffold, and no more than the scaffold:

- `src/quarantinez/control_store.py`, the endpoint of the one service this repository needs.
- `compose.yaml`, which brings it up.
- `.github/workflows/ci.yml`, which calls the pipeline shared across this toolset, pinned to a
  tag rather than a branch so somebody else's commit cannot turn this badge red.

The dependency list in `pyproject.toml` is empty, and here that is an argument rather than an
oversight. This repository is deliberately thin on dependencies because everything interesting in
it is a property rather than an integration: an absorbing state, a control decision that survives
a process dying, an obligation with a deadline.

## Running the service

```bash
docker compose up -d
docker compose down -v
```

PostgreSQL is published on 5434 and bound to 127.0.0.1. The convention across this toolset is one
port above a service's own default so that a clone cannot collide with something the reader
already runs, and a sibling repository took 5433 under that rule. Two repositories in one toolset
that cannot run at the same time is a worse outcome than a second number.

No test in the ordinary suite needs the service. The crash proof does, and it runs in its own job
against a real database, because a claim about what survives a process being killed cannot be
made against an in-memory stand-in.

## Working on it

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Those are what continuous integration runs. `CONTRIBUTING.md` carries the rest.

## Licence

MIT. See [LICENSE](LICENSE).
