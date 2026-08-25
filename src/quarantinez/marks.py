"""The committed marks, and a blunt statement of what they are not.

INVENTED, DATED, AND COMMITTED. These numbers were made up for the demonstration. They are not a
market observation, they were not captured from any feed, and this repository has never had a
venue account, a broker relationship or exchange membership. The README repeats that wherever a
figure is rendered, because a plausible looking series with dates beside it is exactly the thing
a reader assumes came from somewhere.

UNITLESS. A drawdown is a decline from a peak expressed as a fraction, which needs an index and
not an amount. There is no currency anywhere in this repository.

WHY A FIXTURE AND NOT A GENERATOR. A generator would need a model of how the numbers move, and a
model is a claim. A committed list of numbers somebody wrote down claims nothing beyond being
the numbers the demonstration uses.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class Mark:
    """One dated observation of the invented index."""

    date: str
    mark: float


@lru_cache(maxsize=1)
def series() -> tuple[Mark, ...]:
    text = (resources.files("quarantinez.data") / "marks.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    return tuple(Mark(date=row["date"], mark=float(row["mark"])) for row in rows)


def running_peak(marks: tuple[Mark, ...]) -> tuple[float, ...]:
    """The highest mark seen so far at each point, which is what a drawdown is measured from."""
    peaks: list[float] = []
    highest = float("-inf")
    for entry in marks:
        highest = max(highest, entry.mark)
        peaks.append(highest)
    return tuple(peaks)


def deepest_drawdown(marks: tuple[Mark, ...]) -> float:
    """The worst decline from a running peak anywhere in the series."""
    worst = 0.0
    for peak, entry in zip(running_peak(marks), marks, strict=True):
        worst = max(worst, (peak - entry.mark) / peak)
    return worst
