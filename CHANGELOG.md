# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `durable_control.write` commits. A psycopg connection is not autocommit by default, so the
  UPDATE used to sit in an open transaction that a kill discarded, and the crash proof held only
  because the crash child passed `autocommit=True`. The child now connects with no flags, so the
  proof is made on the connection an ordinary caller makes.
- `durable_control.step` advances the stored peak, as `marks.running_peak` already did for the
  in-memory walk. The peak was frozen at whatever `start` inserted, so a decline from any high
  reached afterwards was measured from the opening level and could not trip the breaker: a fall
  of 20 per cent off a new high read as 4 per cent against a 10 per cent limit.
- `venue.classify` has four branches that no venue could reach, so each could return the wrong
  event with the suite green. Four ordinary behaviours now reach them: a refusal on submission, a
  refusal in answer to a status query, an acknowledgement that says the order is still held, and
  a submission nobody acknowledged. They are not misbehaviours and are not in `MISBEHAVIOURS`.
- The README's dependency count. It said one third-party package and named the driver; three are
  imported anywhere in the tree, and the page now counts and names them.

### Changed

- `docs/STATE_MACHINE.md` is written by `scripts/capture_evidence.py`, which is what its own
  header had claimed since it was committed. `tests/test_states.py` now requires the committed
  table to equal `render_table()` exactly, so the document and the machine cannot disagree.

## [0.1.0] - 2026-08-26

### Added

- The state machine, as data rather than as a method per state, with UNKNOWN absorbing: one edge
  out, to a quarantine record, requiring a person's name. Proved by a transitive closure
  computation rather than by a list of edges.
- A simulated venue with four named misbehaviours: accepts then goes quiet, acknowledges twice
  with two identifiers, answers about an identifier nobody sent, and fills a quantity nobody
  asked for. No timing anywhere, and the absence of an answer is a value rather than an exception.
- A control plane that submits once and asks once, with no retry and no polling, counted rather
  than asserted about the source.
- A drawdown breaker whose trip creates an obligation with a deadline on an injected clock. A
  window that closes with the position open is UNKNOWN, and flattening afterwards does not
  un-miss it.
- The breaker state and the position as one row in PostgreSQL, with a crash proof that kills the
  process on both sides of the write and requires the identical row.
- Twenty four dated, unitless, invented marks, with a test that they contain a decline crossing
  the declared limit.
- Six decision records, including the one admitting that nobody asked for the breaker.
