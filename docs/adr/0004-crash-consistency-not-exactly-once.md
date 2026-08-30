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

**The second bullet is a claim about a commit, and the commit is `write`'s own.** A psycopg
connection is not autocommit by default, so an UPDATE on its own leaves the decision inside an
open transaction that a kill discards: the process would be killed after writing and the work
would not be done, which is precisely the third place this argument says does not exist. Until it
was fixed the whole proof rested on one flag in the crash child rather than on anything in the
module, and a caller who connected the ordinary way silently lost every decision. The connection
in the crash child now carries no flags for that reason, so the demonstration is made on the
connection an ordinary caller makes.

## Why the purity test earns its place

It would be easy to read `decide` and conclude it reads nothing else, and easy for that to stop
being true in a later change that nobody connects to a crash test in a different file.

So the coupling is demonstrated rather than described: giving the decision a clock of its own
breaks both crash tests, the committed demonstration output, and the tests that say it reads
nothing but its arguments. An environment variable or a global of its own breaks only those last
tests, because a crash child inherits its parent's environment and a recomputation after the kill
therefore agrees by construction. That is why they are not decorative.

## What was rejected

**Asserting the write is atomic.** It is, trivially, being a single-row update, and asserting it
would be asserting something about PostgreSQL rather than about this design.

**A write-ahead log of intended decisions.** It would let a restart replay an intention rather
than recompute it, which is more machinery for a weaker guarantee: recomputation cannot disagree
with itself, while a replayed intention can disagree with what the current inputs imply.
