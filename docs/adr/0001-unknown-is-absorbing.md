# ADR 0001: UNKNOWN is absorbing, not transient

**Status:** accepted, 25 August 2026.

## The decision

**An outcome the venue never confirmed is terminal.** No retry escapes it, no deadline collapses
it into rejected, and no reconciliation pass decides it was filled after all. There is exactly
one edge out, it goes to a quarantine record, and it requires a person's name.

## The alternative, and what it costs

Almost every control plane treats this state as transient. Retry, poll, and if the venue
eventually answers, resolve it. That is not wrong, and it works most of the time, which is the
problem: it works until the venue never answers, and then the state has to become something.

Whatever it becomes is a guess made by a program about a position somebody holds. The two
available guesses are both bad in different ways. Deciding it failed means a second order goes
out on the assumption the first did not land. Deciding it filled means the arithmetic afterwards
is about a position that may not exist.

A third option is to keep retrying forever, which is the same as the first option with a delay,
because every retry loop has a limit and reaching it produces a decision nobody wrote down.

## How the claim is checked

Not by a list of edges somebody read carefully. `tests/test_states.py` computes the transitive
closure from UNKNOWN and requires it to be exactly two states. An edge added anywhere that
eventually lets an unconfirmed outcome become a confirmed one fails that test however many hops
away it sits, which was verified by adding one two hops away and watching it fail.

Two more tests are parametrised over the event enum rather than over a list written by hand, so
an event added later is tested against UNKNOWN the moment it exists rather than when somebody
remembers.

## What this costs, honestly

Somebody has to look at every quarantined position. That is the point rather than a drawback:
the alternative is a program deciding, and a program deciding is exactly what produced the
guess. But it does mean this design assumes there is a person, and a system with nobody watching
would accumulate quarantine records nobody reads. That is stated in the README rather than
discovered.
