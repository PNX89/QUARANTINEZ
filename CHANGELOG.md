# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
