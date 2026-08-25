"""Freshness, and whether the evidence still contains the argument.

A capture that ran cleanly and demonstrated nothing would pass a byte comparison. So alongside
the comparison there are checks that the transcript still shows four unconfirmed outcomes, still
shows the window being missed, and still shows the obligation surviving a recovery.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "docs" / "evidence"


def facts() -> dict[str, object]:
    parsed: dict[str, object] = json.loads((EVIDENCE / "facts.json").read_text("utf-8"))
    return parsed


def demo() -> str:
    return (EVIDENCE / "demo.txt").read_text("utf-8")


def test_the_committed_demo_output_is_what_the_demo_prints_today() -> None:
    result = subprocess.run(
        [sys.executable, "examples/venue_session.py"],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert result.stdout == demo(), (
        "the committed evidence no longer matches a live run. Regenerate it with "
        "scripts/capture_evidence.py rather than editing it."
    )


def test_the_recorded_test_total_is_this_suites_real_total() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
    )
    match = re.search(r"^(\d+) tests? collected", result.stdout, re.MULTILINE)
    assert match, result.stdout[-400:]
    assert int(match.group(1)) == facts()["tests"]


def test_the_recorded_python_range_is_the_one_ci_actually_runs() -> None:
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    versions = sorted({v for v in re.findall(r'"(3\.\d+)"', workflow)}, key=lambda v: int(v[2:]))
    assert facts()["python"] == f"{versions[0]} to {versions[-1]}"


def test_the_recorded_release_matches_the_package_version() -> None:
    from quarantinez import __version__

    assert facts()["release"] == f"v{__version__}"


def test_the_transcript_still_shows_four_outcomes_nobody_can_confirm() -> None:
    """The evidence has to contain the argument, not merely be current."""
    text = demo()
    assert text.count("UNKNOWN via") == 4, "the four misbehaviours stopped ending unconfirmed"
    assert "FILLED" in text, "nothing confirms, so the demonstration proves only that it refuses"


def test_each_misbehaviour_is_still_named_separately_in_the_transcript() -> None:
    """A single collapsed timeout would read the same on the page and mean much less."""
    for reason in ("SILENCE", "DOUBLE_ACK", "FOREIGN_ID", "UNASKED_QUANTITY"):
        assert reason in demo(), reason


def test_the_transcript_still_shows_a_window_closing_with_exposure_open() -> None:
    text = demo()
    assert "TRIPPED" in text
    assert "UNKNOWN" in text.split("The breaker")[1], "the breaker section stopped reaching UNKNOWN"


def test_the_transcript_shows_the_obligation_surviving_a_recovery() -> None:
    """The point that makes the obligation more than a flag.

    The last rows of the walk have a drawdown back under the limit, and the obligation is still
    UNKNOWN. If that stopped being visible, the strongest thing on the page would be gone.
    """
    tail = demo().split("The breaker")[1]
    rows = re.findall(r"\s+(\d{4}-\d{2}-\d{2})\s+([\d.]+)\s+([\d.]+)\s+(\w+)\s+(\w+)", tail)
    assert rows, "the walk table is no longer in the transcript"
    _, _, last_drawdown, _, last_obligation = rows[-1]
    assert float(last_drawdown) < 0.10, "the walk no longer ends below the limit"
    assert last_obligation == "UNKNOWN", "a recovered drawdown cleared the obligation"


def test_the_transcript_says_the_numbers_are_invented() -> None:
    """Wherever a figure is rendered, the page says where it came from."""
    assert "invented" in demo()
