# ADR 0003: The breaker and the position are one row

**Status:** accepted, 25 August 2026.

## The decision

**One row holds the breaker state, the obligation, the deadline and the position.** Not two
tables kept in step, and not a flag beside a number.

## Why

Two rows can disagree. A control plane that believes the breaker is tripped while the position
row says flat is a control plane that will act on one of them, and which one it acts on is an
accident of which query ran first.

The usual defence is a transaction spanning both writes, which is correct and which still leaves
two rows that a later change, a repair script or a migration can move independently. One row
cannot disagree with itself.

## How it is checked

Against the schema rather than against the code. `tests/test_durable_control.py` reads
`information_schema` and requires that the control columns live together and that the public
schema holds exactly one table. Splitting them into two tables later fails that test rather than
passing quietly because the code happened to keep them in step.

## What this costs

It does not scale to many accounts with different lifecycles, and it says nothing about two
processes deciding at once, which is a different problem with a different answer. Both are in the
README's limitations rather than left for a reader to notice.
