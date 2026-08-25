# ADR 0005: The marks are a committed fixture, not a generator

**Status:** accepted, 25 August 2026.

## The decision

**Twenty four dated, unitless, invented numbers, written down and committed.** Not generated at
run time and not drawn from any distribution.

## Why not a generator

A generator needs a model of how the numbers move, and a model is a claim. Choosing a random walk
claims the increments are independent; choosing anything with a volatility parameter claims
something about how the number behaves. This repository has nothing to say about any of that, and
a generator would have it saying something by accident.

A committed list claims nothing beyond being the numbers the demonstration uses.

## Why not real data

Because the honest version of that sentence is that this repository has never had an account
anywhere, and any real series would need a licence, a provenance record and a paragraph about
what may be redistributed. It would also invite the reading this repository most needs to avoid,
which is that something here happened.

## The test that matters

Not that the file parses. That a series which never declined past the declared limit would let
the breaker never trip while every other test still passed and the demonstration printed a run in
which nothing happened.

So the deepest decline is asserted to exceed the **declared** limit rather than a hardcoded
number, which means raising the limit without deepening the series fails rather than quietly
emptying the demonstration. Measured on the committed file: 15.04 per cent against a 10 per cent
limit.

A second test reads the file for currency symbols and instrument names, because a drawdown is a
fraction and an amount would be a claim this repository does not make.
