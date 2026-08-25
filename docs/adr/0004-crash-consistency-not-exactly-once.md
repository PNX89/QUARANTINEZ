# ADR 0004: A crash consistency proof, and why it is not the other one

**Status:** accepted, 25 August 2026.

## The decision

**This proves a control decision survives the process dying.** It deliberately does not prove
that an effect happens exactly once, which is a different property that a sibling repository in
this toolset proves about a paid call.

Two repositories both killing a process and both writing about durability would be one idea
counted twice, so the difference is stated in both.

| | proves |
|---|---|
| the sibling repository | an effect runs once and is never replayed after a crash |
| this one | a decision reaches the same state whatever instant the process died at |

## How the proof works

The decision is a pure function of what is stored. That is the whole mechanism:

- Killed **after deciding and before writing**, nothing changed. The next start reads the same
  inputs and computes the same decision.
- Killed **after writing**, the work is done.

There is no third place to be, so no interleaving produces a state the next start disagrees with.

## Why the purity test earns its place

It would be easy to read `decide` and conclude it reads nothing else, and easy for that to stop
being true in a later change that nobody connects to a crash test in a different file.

So the coupling is demonstrated rather than described: giving the decision a clock of its own
breaks four tests across two files, both crash tests and the purity test itself. That is why the
purity test is not decorative.

## What was rejected

**Asserting the write is atomic.** It is, trivially, being a single-row update, and asserting it
would be asserting something about PostgreSQL rather than about this design.

**A write-ahead log of intended decisions.** It would let a restart replay an intention rather
than recompute it, which is more machinery for a weaker guarantee: recomputation cannot disagree
with itself, while a replayed intention can disagree with what the current inputs imply.
