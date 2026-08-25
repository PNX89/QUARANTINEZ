# QUARANTINEZ

**An outcome the venue never confirmed is not a failure to retry. It is a terminal state, and no
code path here escapes it except to a quarantine record naming a person.**

[![CI](https://github.com/PNX89/QUARANTINEZ/actions/workflows/ci.yml/badge.svg)](https://github.com/PNX89/QUARANTINEZ/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

One file to start with: [`src/quarantinez/states.py`](src/quarantinez/states.py). It is the
machine, as data rather than as a method per state, which is what makes the claim below
enumerable instead of something a reader has to take on trust.

```text
                 submit
                   |
                   v
              +----------+   ack     +----------+   fill    +----------+
              | PENDING  |---------->| WORKING  |---------->|  FILLED  |
              +----------+           +----------+           +----------+
                   |                      |                  terminal
                   | reject               | reject
                   v                      v
              +----------+           +----------+
              | REJECTED |           | REJECTED |
              +----------+           +----------+
                terminal               terminal

        silence, a second acknowledgement, an answer about
        somebody else, or a quantity nobody sent
                   |
                   v
              +----------+
              | UNKNOWN  |
              +----------+
                   |
                   | one edge out, and it is not automatic
                   v
              +-----------------------------+
              | QUARANTINED, named to a     |
              | person, with the transcript |
              +-----------------------------+
```

**This repository is deliberately thin on dependencies, because everything interesting in it is a
property rather than an integration.** There is one third-party package in the whole tree and it
is the database driver. What is being shown is a state that cannot be escaped, a decision that
survives the process dying, and an obligation that cannot be un-missed, and none of those is
something you install.

## The state that has no way out

Every control plane has a state for an outcome it could not confirm. Most treat it as transient:
retry, poll, and if the venue eventually answers, resolve it. That works until the venue never
answers. Then the state has to become something, and whatever it becomes is a guess made by a
program about a position somebody holds.

Here UNKNOWN is absorbing. No retry escapes it, no deadline collapses it into rejected, and no
reconciliation pass quietly decides it was filled after all. There is exactly **one edge** out of
it, it goes to a quarantine record, and it needs a person's name. Whitespace is not a name: a
quarantine record naming nobody is no record with extra steps.

**The proof is a reachability computation rather than a list of edges somebody checked.** The
test computes the transitive closure from UNKNOWN and requires it to be exactly two states, so an
edge added anywhere that eventually lets an unconfirmed outcome become a confirmed one fails
however many hops away it sits. That was verified by adding one two hops away and watching it
fail.

The machine is in a table rather than in a method per state, which is what makes any of this
enumerable, and [`docs/STATE_MACHINE.md`](docs/STATE_MACHINE.md) is generated from that table so
the two cannot disagree.

## Four ways a venue misbehaves

A stub answers correctly and quickly, which makes every test pass and proves the happy path
works, which nobody doubted. These are the behaviours that produce an outcome nobody can confirm,
and each is a named scenario rather than a flag:

```text
>>> place(order, venue='well behaved')
    FILLED

>>> place(order, venue='accepts then goes quiet')
    UNKNOWN via SILENCE

>>> place(order, venue='acknowledges twice')
    UNKNOWN via DOUBLE_ACK

>>> place(order, venue='answers about something else')
    UNKNOWN via FOREIGN_ID

>>> place(order, venue='fills a quantity nobody sent')
    UNKNOWN via UNASKED_QUANTITY
```

Which one happened is the question somebody asks afterwards, so the four stay distinguishable. A
single collapsed timeout would answer it with a shrug, and the difference between silence and a
contradictory acknowledgement is exactly the interesting part.

**There is no timing anywhere, and that is deliberate.** Stopping answering is modelled as a
definite absence of an answer rather than as a wait, so a test asserts a property instead of
racing a clock. This repository makes no claim about how fast anything is, and a simulated wait
would look like one.

**The absence of an answer is a value, not an exception.** An exception gets caught somewhere and
turned into a retry, which is the behaviour this whole repository argues against. As a value it
has to be handled, and the type checker says so at every call site.

The control plane submits once and asks once. It does not retry, because a retry after an
unconfirmable outcome is a second order sent on the assumption that the first one did not happen,
and it does not poll, because asking again cannot turn silence into an answer and a loop that
keeps asking is a loop that eventually gives up and guesses. That is counted rather than asserted
about the source: a venue records how many submissions it saw, and one order must produce exactly
one.

## Run it

```bash
git clone https://github.com/PNX89/QUARANTINEZ.git && cd QUARANTINEZ
uv sync --dev
uv run python examples/venue_session.py
```

Well under a second, offline, with nothing to configure and no key to supply. Every number it
prints comes from a fixture committed in this repository.

The crash proof needs a real database, and only that:

```bash
docker compose up -d
uv run pytest -m services
docker compose down -v
```

PostgreSQL is published on 5434 and bound to 127.0.0.1. The convention across this toolset is one
port above a service's own default so that a clone cannot collide with something the reader
already runs, and a sibling repository took 5433 under that rule. Two repositories that cannot be
brought up at the same time is a worse outcome than a second number.

## Proving it survives the process dying

The breaker state and the position are **one row**. Not two tables kept in step and not a flag
beside a number, because two rows can disagree and a control plane that believes the breaker is
tripped while the position says flat is going to act on one of them. That is asserted against the
schema rather than against the code, so splitting them into two tables later fails the test.

The proof kills the process on both sides of the write:

- Killed **after deciding and before writing**, nothing changed. The next start reads the same
  inputs and computes the same decision, because the decision is a pure function of what is
  stored.
- Killed **after writing**, the work is already done.

There is no third place to be, so no interleaving produces a state the next start disagrees with.
The child sends itself `SIGKILL`, which no `finally` block and no buffered write survives, because
what is claimed is about the row that is in the database after the process stops existing.

**The coupling is proved rather than asserted.** Giving the decision a clock of its own breaks
four tests across two files: both crash tests and the purity test that exists to explain why they
hold. That is what makes the purity test worth having rather than decorative.

This is a crash consistency proof, and it is deliberately **not** the exactly-once proof a sibling
repository in this toolset makes. That one shows a paid effect happens once and is never
replayed. This shows something different and simpler to state: killing the process at any point
leaves the stored state somewhere the next start agrees with.

## The obligation with a deadline

Tripping a breaker is the easy half: compare a decline against a threshold and set a flag. Most
implementations stop there, and a flag with nothing owed is a print statement. The position is
still open, somebody is supposed to flatten it, and nothing in the system knows whether that
happened.

So tripping creates an obligation with a deadline, measured on a clock the tests advance rather
than wait on. It is discharged when the position reaches zero. If the deadline passes with the
position still open, the outcome is UNKNOWN: the same absorbing state an unconfirmed order lands
in, for the same reason.

Walked over the committed marks, against a **10 per cent** limit:

```text
  date        mark    drawdown  breaker   obligation
  2026-01-26    96.1     0.113  TRIPPED   OPEN
  2026-01-29    92.1     0.150  TRIPPED   UNKNOWN
  2026-02-05    97.7     0.099  TRIPPED   UNKNOWN
```

**The last row is the point.** The decline has recovered back under the limit and the obligation
is still UNKNOWN. A window that closed with exposure open is a fact about the past, and closing
the position afterwards does not reach back into it. Without that, a system could trip, miss the
window, flatten late, and report a clean run.

A mutation found that guard was once dead code: deleting it changed nothing, because the function
ended with a catch-all that passed any obligation through unchanged, so the property held by
accident rather than by decision. The match is exhaustive by name now, a state the policy cannot
reach raises rather than being absorbed, and deleting the guard fails the test it protects.

## What is deliberately thin here

**The marks are invented.** 24 dated, unitless numbers written for the demonstration. They are
not an observation of anything, they were not captured from a feed, and this repository has never
had an account anywhere. A test reads the fixture for currency symbols and instrument names,
because a drawdown is a fraction and an amount would be a claim this repository does not make.

The deepest decline in that fixture is **15.04 per cent**, and a test asserts it exceeds the
declared limit, because a series that never crossed it would let the breaker never trip while
every other test still passed and the demonstration printed a run in which nothing happened.

**The venue is simulated** and has no wire format. What is modelled is the shape of the
misbehaviour, which is the part that reaches the state machine.

## What was decided, and what was rejected

Six records under [`docs/adr/`](docs/adr/), because an absence is harder to review than an
addition: nothing in a diff points at the thing that is not there.

| | |
|---|---|
| [0001](docs/adr/0001-unknown-is-absorbing.md) | why an unconfirmed outcome is terminal, and what the transient version costs |
| [0002](docs/adr/0002-no-timing-anywhere.md) | why nothing here sleeps, and why an absent answer is a value rather than an exception |
| [0003](docs/adr/0003-one-row.md) | why the breaker and the position cannot be two rows |
| [0004](docs/adr/0004-crash-consistency-not-exactly-once.md) | what this proves, and the neighbouring property it deliberately does not |
| [0005](docs/adr/0005-a-fixture-not-a-generator.md) | why the marks are written down rather than generated |
| [0006](docs/adr/0006-bought-on-the-argument-not-on-demand.md) | the reach admission, in full |

## Limitations

**Nothing here is production.** No real users, no operational history, no system anyone depends
on. The venue is simulated, the marks are invented, and the control plane has no path to anything
outside this repository.

**No position modelled here was ever real**, and nothing in this repository has ever connected to
anything that could make one real.

**The breaker is bought on the integrity of the argument rather than on demand.** Drawdown, kill
switch, circuit breaker and position limit each reach **zero employers** in the posting register
behind this portfolio. It is here because a breaker without an obligation is a print statement,
and saying so is worth more than pretending somebody asked for it.

**A simulated clock proves nothing about wall clock behaviour.** The tests advance time by hand,
which makes the deadline logic deterministic and says nothing whatsoever about how this would
behave against a real one.

**The four misbehaviours are the four that were thought of.** A fifth exists somewhere and is not
modelled. The state machine is arranged so that adding one is a row in a table and a test that
runs against it automatically, which is the best that can be done about a list that cannot be
complete.

**The crash proof covers one process and one row.** Two processes deciding at once is a different
problem with a different answer, and it is not addressed here.

## Development

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Those are what continuous integration runs, in a workflow shared across this toolset and pinned
to a tag so that a commit elsewhere cannot turn this badge red. The tests that need a container
are deselected from that run by their marker and run in their own job against a real PostgreSQL,
because a skipped test reports as a pass and nobody reads it.

<!-- toolset:start -->

Part of the Q...Z toolset, all of it designing for the failure that does not announce itself:

- [QUACKZ](https://github.com/PNX89/QUACKZ), deflating a backtest that only looks good because
  it was picked out of two hundred.
- [QUOTEZ](https://github.com/PNX89/QUOTEZ), market data an agent can read and cannot act on.
- [QUELLZ](https://github.com/PNX89/QUELLZ), measuring what prompt-injection containment costs
  in utility as well as in attack rate.
- [QUIDZ](https://github.com/PNX89/QUIDZ), refusing the outbound payment that would have gone
  out twice.
- [QUESTZ](https://github.com/PNX89/QUESTZ), stopping a scraper before it writes a CSV from a
  page that changed shape.
- [QUIZZ](https://github.com/PNX89/QUIZZ), answering what a statistic said at the time, and
  refusing when it cannot.
- QUARANTINEZ, this one: treating an outcome the venue never confirmed as terminal rather than
  as a retry.

<!-- toolset:end -->

## Licence

MIT. See [LICENSE](LICENSE).
