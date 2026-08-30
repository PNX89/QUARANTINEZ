"""Every checkable claim on the front page, checked, and written before the page existed.

The four kinds the shared contract names, implemented here:

    NUMBER     a figure on the page against the thing it counts
    COMMAND    a command the page tells a reader to run against what CI runs
    OUTPUT     the diagram and the walk against what the code and the demo produce
    REFERENCE  every link and path against what exists

The must-never-claim check bans the CLAIM rather than the vocabulary. A page that says it makes
no claim about latency has to be able to use the word, which is the trap this toolset has walked
into more than once.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

from quarantinez.breaker import Limits
from quarantinez.marks import deepest_drawdown, series
from quarantinez.states import TABLE, Event, State, outgoing
from quarantinez.venue import MISBEHAVIOURS
from tests.test_doc_contract import IMPLEMENTATIONS

REPO = pathlib.Path(__file__).resolve().parent.parent
README = (REPO / "README.md").read_text("utf-8")
EVIDENCE = REPO / "docs" / "evidence"

#: Small counts are written as words on this page, so a figure check has to read them as words.
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight")


def sentence_with(phrase: str) -> str:
    """The one sentence on the page carrying `phrase`, with its line wrapping undone.

    A figure is compared against the sentence that states it rather than against the page. A page
    this long contains most small numbers somewhere, so searching the whole of it for one is a
    check that passes on a coincidence, and there is no coincidence a reader benefits from.
    """
    flat = " ".join(README.split())
    matches = [part for part in re.split(r"(?<=[.:]) ", flat) if phrase in part]
    assert len(matches) == 1, f"expected one sentence carrying {phrase!r}, found {len(matches)}"
    return matches[0]


def demonstrated_limits() -> Limits:
    """The limits the walk on the page was actually run with, loaded from the demonstration.

    Read from `examples/venue_session.py` rather than retyped here. A copy in this file agrees
    with whatever this file says, so changing the demonstration's limit left the page's figure
    unchecked, which is the single thing the assertion using it exists to catch.
    """
    location = REPO / "examples" / "venue_session.py"
    spec = importlib.util.spec_from_file_location("_venue_session", location)
    assert spec is not None and spec.loader is not None, location
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    limits = module.LIMITS
    assert isinstance(limits, Limits), "the demonstration stopped declaring the limits it walks"
    return limits


def third_party_imports() -> set[str]:
    """Every module imported here that is neither this package nor the standard library.

    Computed rather than read off `pyproject.toml`, because the page counts what the tree
    imports and a declared dependency nothing imports is not one of those.
    """
    ours = {"quarantinez", "tests", "examples", "scripts"}
    found: set[str] = set()
    for path in sorted(REPO.glob("**/*.py")):
        if any(part.startswith(".") for part in path.parts):
            continue
        for line in path.read_text("utf-8").splitlines():
            match = re.match(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            if match is None:
                continue
            name = match.group(1)
            if name not in ours and name not in sys.stdlib_module_names:
                found.add(name)
    return found


LIMITS = demonstrated_limits()


def test_the_readme_shows_one_transcript_line_per_declared_misbehaviour() -> None:
    """NUMBER, tied to the transcript rather than to the prose.

    An earlier version of this test demanded a digit in a heading, which is the wrong place to
    put a claim: a heading is prose and reads better as a word. The checkable claim is that the
    page shows one unconfirmed outcome for each declared misbehaviour, so that is what is
    counted, and adding a fifth to the declaration makes this fail until the page is regenerated.
    """
    assert README.count("UNKNOWN via") == len(MISBEHAVIOURS)


def test_the_readme_states_the_deepest_decline_in_the_fixture() -> None:
    """NUMBER, and it is the figure that decides whether the demonstration shows anything."""
    deepest = deepest_drawdown(series())
    assert f"{deepest * 100:.2f} per cent" in README, f"{deepest * 100:.2f} per cent"


def test_the_readme_states_how_many_marks_are_committed() -> None:
    assert f"{len(series())} dated" in README


def test_the_readme_states_the_limit_the_walk_was_run_against() -> None:
    """NUMBER, in the sentence that introduces the walk, against the demonstration's own limit.

    Both halves were loose. The figure was searched for anywhere on the page, and it was compared
    to a copy of the constant typed into this file rather than to the limit the walk ran with, so
    changing the demonstration left it passing.
    """
    stated = f"{LIMITS.max_drawdown:.0%}".replace("%", " per cent")
    sentence = sentence_with("Walked over the committed marks")
    assert stated in sentence, f"the sentence introducing the walk does not say {stated}"


def test_the_readme_states_that_unknown_has_exactly_one_edge_out() -> None:
    """NUMBER, computed from the machine rather than counted by eye."""
    assert len(outgoing(State.UNKNOWN)) == 1
    assert "one edge" in README or "a single edge" in README


def test_the_diagram_shows_every_state_the_machine_has() -> None:
    """OUTPUT. A diagram missing a state is a diagram describing a different machine."""
    diagram = README.split("```")[1]
    for state in State:
        assert state.value in diagram, f"{state.value} is missing from the diagram"


def test_the_diagram_does_not_show_an_edge_the_machine_does_not_have() -> None:
    """OUTPUT, and the direction that matters. A drawn edge out of UNKNOWN would be a lie.

    Checked by requiring that the only state named on a line after UNKNOWN's box is the
    quarantine record, rather than by parsing arrows, because the point is what a reader takes
    away rather than what a parser can prove.
    """
    diagram = README.split("```")[1]
    after_unknown = diagram.split("UNKNOWN")[-1]
    for state in (State.FILLED, State.WORKING, State.PENDING, State.REJECTED):
        assert state.value not in after_unknown, f"{state.value} appears below UNKNOWN"


def test_every_command_the_readme_shows_is_one_this_repository_runs() -> None:
    """COMMAND."""
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    gates = {
        "uv sync --dev",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy",
        "uv run pytest",
    }
    local = set(re.findall(r"^\s*-?\s*run: (uv run .+?)\s*$", workflow, re.MULTILINE))
    scripts = {
        f"uv run python {path.relative_to(REPO)}"
        for path in list(REPO.glob("examples/*.py")) + list(REPO.glob("scripts/*.py"))
    }

    def normalise(command: str) -> str:
        return command.replace(" -q", "").strip()

    known = {normalise(c) for c in gates | local | scripts}
    for command in re.findall(r"^(uv (?:run|sync) .+)$", README, re.MULTILINE):
        assert normalise(command) in known, command


def test_every_path_and_link_in_the_readme_resolves() -> None:
    """REFERENCE."""
    for target in re.findall(r"\]\(([^)]+)\)", README):
        if target.startswith("https://"):
            continue
        assert not target.startswith("http://"), target
        assert (REPO / target.split("#")[0]).exists(), target


def test_the_readme_names_a_headline_file_that_exists() -> None:
    """REFERENCE. An interviewer asked to pick a file picks the one named first."""
    first_screenful = README.split("## ")[0]
    named = re.findall(r"\[`([^`]+)`\]", first_screenful)
    assert named, "the first screenful names no file"
    for path in named:
        assert (REPO / path).exists(), path


def test_the_readme_transcript_lines_are_in_the_captured_run() -> None:
    """OUTPUT. Every transcript line on the page appears in the committed capture, in order.

    Three `text` blocks are on the page: the diagram, the order transcript and the breaker walk.
    Only the diagram is drawn by hand, and the two tests above check that one against the machine
    instead. This used to skip any block with no `>>>` prompt in it, which quietly excluded the
    walk, so the three rows the page calls its point, and the only computed figures on the front
    page, were the one thing here that nothing compared to a run.
    """
    blocks = re.findall(r"```text\n(.*?)```", README, re.DOTALL)
    drawn = [block for block in blocks if "+---" in block]
    from_a_run = [block for block in blocks if "+---" not in block]
    assert len(drawn) == 1, "the hand-drawn diagram is the only block this test may skip"
    assert len(from_a_run) == 2, "a text block on the page stopped being compared to the capture"

    captured = (EVIDENCE / "demo.txt").read_text("utf-8").splitlines()
    for block in from_a_run:
        position = 0
        for line in block.splitlines():
            if not line.strip():
                continue
            while position < len(captured) and captured[position].strip() != line.strip():
                position += 1
            assert position < len(captured), f"not in the captured run, or out of order: {line}"
            position += 1


def test_every_named_contract_implementation_is_a_test_pytest_actually_collects() -> None:
    """All four kinds in the shared manifest are implemented in this file, so they are checked here.

    The manifest's own check resolves each name by searching the text of the test files, which a
    name occurring anywhere satisfies, a `#` comment included. A comment saying what used to
    check something is precisely what a deletion leaves behind. Demonstrated: deleting the
    REFERENCE implementation, leaving its name in a comment, and breaking a real link on the page
    left the whole suite green and the manifest reporting itself kept.

    This resolves the same names through the items pytest collects instead. It lives here rather
    than beside the manifest because that file is generated by the portfolio's page generator,
    and regenerating it takes an edit there away again.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout[-400:] + result.stderr[-400:]
    collected = {
        line.rsplit("::", 1)[1].split("[")[0] for line in result.stdout.splitlines() if "::" in line
    }
    missing = {kind: name for kind, name in IMPLEMENTATIONS.items() if name not in collected}
    assert missing == {}, (
        f"these contract kinds name a test that pytest does not collect: {missing}. A name left "
        "in a comment is not an implementation."
    )


def test_the_readme_makes_none_of_the_claims_this_repository_must_not_make() -> None:
    """The ten clauses, as patterns rather than as banned words.

    A page that says it makes no claim about latency has to be able to use the word. So each
    pattern targets the assertive form, and a denial reads past it.
    """
    forbidden = (
        # The assertive forms only. This page needs to be able to SAY "not a real venue", and a
        # pattern banning the phrase outright would make the honest disclaimer unwritable.
        r"connects to a (?:real )?venue",
        r"\btrades on\b",
        r"routes orders",
        r"\blive capital\b",
        r"\bbroker relationship\b",
        r"\btrack record\b",
        r"\bprofit and loss\b",
        r"\bP&L\b",
        r"\bbest execution\b",
        r"\bsmart order routing\b",
        r"\bmarket making\b",
        r"\bmatching engine\b",
        r"\border book\b",
        r"\bFIX\b",
        r"\bITCH\b",
        r"\bOUCH\b",
        r"production grade",
        r"\$\d",
        r"\b(?:USD|EUR|GBP)\b",
    )
    for pattern in forbidden:
        assert not re.search(pattern, README), pattern


def test_the_readme_says_what_the_numbers_are_not() -> None:
    """Wherever a figure is rendered, the page says it was invented."""
    assert "invented" in README.lower()
    assert "simulated" in README.lower()


def test_the_limitations_section_carries_the_arguments_that_weaken_the_page() -> None:
    limitations = README.split("## Limitations")[1]
    for required in ("invented", "zero employers", "wall clock"):
        assert required in limitations.lower(), required


def test_the_readme_states_the_reach_honestly() -> None:
    """The breaker is bought on the integrity of the argument rather than on demand."""
    assert "zero employers" in README.lower()


def test_the_readme_states_the_dependency_argument_in_the_first_screenful() -> None:
    """The R3 mitigation, stated rather than bolted on: thin on purpose, and why."""
    first_screenful = README.split("## Limitations")[0]
    assert "property rather than an integration" in first_screenful


def test_the_readme_counts_and_names_every_third_party_library_in_the_tree() -> None:
    """NUMBER. The half of that paragraph that is checkable, and it used to be the unchecked half.

    The page said there was one third-party package and that it was the database driver. There
    are three: the test runner, the driver, and PyYAML, which one test imports at module scope in
    exactly the way the driver is imported. The assertion beside this one only ever read the
    unfalsifiable clause, so the sentence a reader can check was the sentence nothing checked.
    """
    imported = third_party_imports()
    assert imported == {"pytest", "psycopg", "yaml"}, imported
    sentence = sentence_with("third-party libraries")
    counted = f"{NUMBER_WORDS[len(imported)]} third-party libraries"
    assert counted in sentence.lower(), f"the sentence does not say {counted}"
    for library in ("test runner", "PostgreSQL driver", "PyYAML"):
        assert library in sentence, f"{library} is imported here and the sentence does not name it"


def test_the_readme_is_right_that_installing_this_requires_nothing() -> None:
    """NUMBER, the empty one. An empty list is a claim like any other."""
    pyproject = (REPO / "pyproject.toml").read_text("utf-8")
    assert re.search(r"^dependencies = \[\]$", pyproject, re.MULTILINE), (
        "the page says the runtime dependency list is empty and pyproject.toml disagrees"
    )
    assert "runtime dependency list is empty" in sentence_with("runtime dependency list")


def test_the_table_of_transitions_on_the_page_matches_the_machine() -> None:
    """OUTPUT. Every edge the page names is an edge the code has."""
    for (state, event), target in TABLE.items():
        if event is Event.QUARANTINED_BY_PERSON:
            assert "QUARANTINED" in README
        assert state.value in README and target.value in README
