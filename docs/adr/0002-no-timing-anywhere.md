# ADR 0002: No timing anywhere, and an absence that is a value

**Status:** accepted, 25 August 2026.

## Two decisions that turn out to be one

**Nothing in this repository sleeps, waits, or measures elapsed wall-clock time.** A venue that
stops answering is modelled as a definite absence of an answer rather than as a wait, and a
deadline is measured on a clock the tests advance by hand.

**The absence of an answer is a value rather than an exception.**

## Why no timing

Three reasons, and the third is the one that matters most here.

A test that waits for a deadline is slow when it passes and flaky when it does not, which is the
ordinary argument and would be enough on its own.

A simulated wait proves nothing about a real one. Sleeping for sixty units in a test and then
asserting a deadline fired demonstrates that the arithmetic works, which is what advancing a
counter demonstrates at no cost.

And a repository that measured anything in seconds would be making a claim about how fast it is,
which is a claim it is not in a position to make and has no way to support. This one deliberately
prints no timing figure anywhere.

## Why the absence is a value

`NoAnswer` is a value in the reply type rather than a raised exception, and the type checker
requires it to be handled at every call site.

An exception would be caught somewhere. Whatever catches it will, sooner or later, turn it into a
retry, because that is what almost every exception handler around a network call does. That
retry is the exact behaviour this repository exists to argue against, and building the failure
mode into the type would mean arguing against it in prose while inviting it in code.

## What was rejected

**A timeout event that covers all four misbehaviours.** It would be simpler and it collapses the
question somebody actually asks afterwards, which is which of them happened. The difference
between silence and a contradictory acknowledgement is the interesting part, so the four stay
distinguishable and each has its own named scenario.
