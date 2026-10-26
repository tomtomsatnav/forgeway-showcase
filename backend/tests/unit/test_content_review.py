"""The cheat-review heuristics on small fixture exercises: each must fire on the pattern it
names and stay quiet on the house-style alternative."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from lattice.application.content_review import ReviewInput, ReviewItem, Status, review_exercise
from lattice.cli import app
from lattice.domain.content import Exercise, Isolation, Tier, WrongCase
from lattice.infrastructure.content_loader import load_catalogue
from tests.content_factory import write_branch, write_exercise


@pytest.fixture(scope="module")
def exercise(tmp_path_factory: pytest.TempPathFactory) -> Exercise:
    root: Path = tmp_path_factory.mktemp("content")
    write_branch(root, "starter")
    write_exercise(root, "starter", "adder")
    return load_catalogue(root).sources["starter.adder"].exercise


def _review(
    exercise: Exercise,
    test: str,
    *,
    brief: str = "",
    wrong: tuple[WrongCase, ...] = (),
    tier: str = "beginner",
    isolation: str = "inprocess",
) -> dict[str, ReviewItem]:
    ex = exercise.model_copy(
        update={"brief": brief, "tier": Tier(tier), "isolation": Isolation(isolation)}
    )
    items = review_exercise(ReviewInput(ex, {"test_add.py": test}, wrong))
    return {item.title: item for item in items}


def _status(items: dict[str, ReviewItem], title: str) -> Status:
    return items[title].status


HEADER = "import json\nimport random\n\nfrom solution_mod import add\n\n\n"
PLAIN = "def plain(value):\n    return json.loads(json.dumps(value))\n\n\n"


def test_asserts_without_a_message_are_flagged(exercise: Exercise):
    flagged = _review(exercise, HEADER + "def test_it():\n    assert add(1, 2)\n")
    item = flagged["Learner-facing messages"]
    assert item.status is Status.WARN
    assert [(f.path, f.line) for f in item.findings] == [("tests/test_add.py", 8)]
    fine = _review(exercise, HEADER + "def test_it():\n    assert add(1, 2), 'add should work'\n")
    assert _status(fine, "Learner-facing messages") is Status.OK


@pytest.mark.parametrize(
    "body",
    [
        "    got = add(1, 2)\n    assert got == 3, 'm'\n",
        "    assert add(1, 2) == 3, 'm'\n",
        "    got = add(1, 2)\n    assert got['total'] in (3, 4), 'm'\n",
    ],
)
def test_raw_learner_values_in_comparisons_are_flagged(exercise: Exercise, body: str):
    items = _review(exercise, HEADER + "def test_it():\n" + body)
    assert _status(items, "Objects that lie about equality") is Status.WARN


@pytest.mark.parametrize(
    "body",
    [
        "    got = plain(add(1, 2))\n    assert got == 3, 'm'\n",
        "    got = add(1, 2)\n    assert type(got) is int, 'm'\n    assert got == 3, 'm'\n",
        "    assert float(add(1, 2)) == 3, 'm'\n",
        "    got = add(1, 2)\n    assert got > 2, 'm'\n",
    ],
)
def test_canonicalised_or_type_checked_values_are_not_flagged(exercise: Exercise, body: str):
    items = _review(exercise, HEADER + PLAIN + "def test_it():\n" + body)
    assert _status(items, "Objects that lie about equality") is Status.OK


def test_wrapped_learner_calls_count_as_canonicalised(exercise: Exercise):
    test = (
        HEADER
        + PLAIN
        + (
            "def total(*args):\n    return plain(add(*args))\n\n\n"
            "def test_it():\n    got = total(1, 2)\n    assert got == 3, 'm'\n"
        )
    )
    assert _status(_review(exercise, test), "Objects that lie about equality") is Status.OK


def test_an_answer_built_before_the_learner_call_is_flagged(exercise: Exercise):
    test = (
        HEADER
        + PLAIN
        + (
            "def test_it():\n"
            "    want = [3, 7]\n"
            "    got = plain([add(1, 2), add(3, 4)])\n"
            "    assert got == want, 'm'\n"
        )
    )
    item = _review(exercise, test)["Expected values in the caller's frame"]
    assert item.status is Status.WARN
    assert item.findings[0].line == 12


@pytest.mark.parametrize(
    "body",
    [
        # Worked out after the learner call returns.
        "    got = plain(add(1, 2))\n    want = expected(1, 2)\n    assert got == want, 'm'\n",
        # An input handed to learner code, not an answer.
        "    pair = [1, 2]\n    got = plain(add(*pair))\n    assert got != pair, 'm'\n",
        # A fake or world object, built by a constructor.
        "    world = World(3)\n    got = plain(add(1, 2))\n    assert got == world.total, 'm'\n",
        # Read before the call: it feeds the inputs.
        "    seed = 4\n    rng = random.Random(seed)\n    got = plain(add(rng.random(), 1))\n"
        "    assert got != seed, 'm'\n",
    ],
)
def test_inputs_and_late_answers_are_not_flagged(exercise: Exercise, body: str):
    items = _review(exercise, HEADER + PLAIN + "def test_it():\n" + body)
    assert _status(items, "Expected values in the caller's frame") is Status.OK


def test_keyword_responders_are_flagged_and_seeded_tables_are_not(exercise: Exercise):
    keyword = HEADER + (
        "def answer(request):\n"
        "    if 'refund' in request.messages[-1].content:\n"
        "        return 'yes'\n"
        "    return 'no'\n\n\n"
        "def test_it():\n    model = FakeModel(responder=answer)\n"
        "    assert add(model, 1), 'm'\n"
    )
    item = _review(exercise, keyword)["Predictable fakes"]
    assert item.status is Status.WARN and item.findings[0].line == 8
    inline = HEADER + "MODEL = FakeModel(lambda r: 'A' if r.system.startswith('Judge') else 'B')\n"
    assert _status(_review(exercise, inline), "Predictable fakes") is Status.WARN
    table = HEADER + (
        "TABLE = {}\n\n\n"
        "def test_it():\n    model = FakeModel(responder=lambda r: TABLE[token(r)])\n"
        "    assert add(model, 1), 'm'\n"
    )
    assert _status(_review(exercise, table), "Predictable fakes") is Status.OK


@pytest.mark.parametrize(
    ("line", "status"),
    [
        ("RNG = random.Random()\n", Status.WARN),
        ("VALUE = random.choice([1, 2])\n", Status.WARN),
        ("random.seed(1)\nVALUE = random.choice([1, 2])\n", Status.OK),
        ("RNG = random.Random(7)\n", Status.OK),
    ],
)
def test_unseeded_generators_are_flagged(exercise: Exercise, line: str, status: Status):
    assert _status(_review(exercise, HEADER + line), "Unseeded randomness") is status


def test_brief_defaults_need_a_call_that_leaves_them_out(exercise: Exercise):
    brief = "Write `add(a, b=1, *, scale=(1, 2))` in `solution_mod.py`.\n"
    passes_both = HEADER + "def test_it():\n    assert add(1, 2, scale=3) == 3, 'm'\n"
    item = _review(exercise, passes_both, brief=brief)["Untested defaults and boundaries"]
    assert item.status is Status.WARN
    assert sorted(f.note for f in item.findings) == [
        "no test calls add() without b",
        "no test calls add() without scale",
    ]
    omits = HEADER + "def test_it():\n    assert add(1) == 2, 'm'\n"
    items = _review(exercise, omits, brief=brief)
    assert _status(items, "Untested defaults and boundaries") is Status.OK
    never_called = HEADER + "def test_it():\n    assert True, 'm'\n"
    items = _review(exercise, never_called, brief=brief)
    assert _status(items, "Untested defaults and boundaries") is Status.OK


def test_run_fresh_without_a_path_or_with_relative_files_is_flagged(exercise: Exercise):
    fresh = HEADER + (
        "from lattice_grader.isolation import run_fresh\n\n\n"
        "def session():\n"
        "    import solution_mod\n"
        "    return open('store.json').read()\n\n\n"
        "def test_it(tmp_path):\n    assert run_fresh(session), 'm'\n"
    )
    item = _review(exercise, fresh)["In-process persistence"]
    assert item.status is Status.WARN
    assert len(item.findings) == 2
    good = HEADER + (
        "from lattice_grader.isolation import run_fresh\n\n\n"
        "def session(data):\n    import solution_mod\n    return data\n\n\n"
        "def test_it(tmp_path):\n    assert run_fresh(session, {}, path=[DIR]), 'm'\n"
    )
    assert _status(_review(exercise, good), "In-process persistence") is Status.OK
    assert _status(_review(exercise, HEADER), "In-process persistence") is Status.MANUAL


def test_a_reference_package_needs_a_borrows_the_grader_case(exercise: Exercise):
    test = HEADER + "from lattice_grader.evals_reference import cohens_kappa\n"
    item = _review(exercise, test)["Borrowed behaviour"]
    assert item.status is Status.WARN and item.findings[0].line == 7
    borrow = WrongCase(
        name="borrows-the-grader",
        fails="adds",
        files={
            "solution_mod.py": "import importlib\n"
            'ref = importlib.import_module("lattice" + "_grader.evals_reference")\n'
        },
    )
    items = _review(exercise, test, wrong=(borrow,))
    assert _status(items, "Borrowed behaviour") is Status.OK
    assert _status(_review(exercise, HEADER), "Borrowed behaviour") is Status.OK


def test_capstones_need_a_pasted_solutions_case(exercise: Exercise):
    assert "Capstone: pasted reference solutions" not in _review(exercise, HEADER)
    items = _review(exercise, HEADER, tier="capstone")
    assert _status(items, "Capstone: pasted reference solutions") is Status.WARN
    pasted = WrongCase(name="pasted-solutions", fails="adds", files={})
    items = _review(exercise, HEADER, tier="capstone", wrong=(pasted,))
    assert _status(items, "Capstone: pasted reference solutions") is Status.OK


def test_unparseable_tests_are_skipped(exercise: Exercise):
    items = _review(exercise, "def broken(:\n")
    assert all(i.status is not Status.WARN for i in items.values())


def test_a_review_ok_comment_with_a_reason_accepts_a_finding(exercise: Exercise):
    body = "def test_it():\n    assert add(1, 2)  # review-ok: a sanity check on the fixture\n"
    item = _review(exercise, HEADER + body)["Learner-facing messages"]
    assert item.status is Status.OK
    assert [(f.path, f.line) for f in item.accepted] == [("tests/test_add.py", 8)]

    bare = "def test_it():\n    assert add(1, 2)  # review-ok:\n    assert add(2, 2)\n"
    item = _review(exercise, HEADER + bare)["Learner-facing messages"]
    assert item.status is Status.WARN
    assert [f.line for f in item.findings] == [8, 9]


def test_a_review_ok_comment_in_the_brief_accepts_a_default(exercise: Exercise):
    test = HEADER + "def test_it():\n    assert add(1, 2) == 3, 'm'\n"
    brief = "Write `add(a, b=1)`. <!-- review-ok: b is reached through a tool call -->\n"
    item = _review(exercise, test, brief=brief)["Untested defaults and boundaries"]
    assert item.status is Status.OK
    assert [f.path for f in item.accepted] == ["brief.md"]


ORACLES = "Oracles in the test module"


@pytest.mark.parametrize("name", ["reference_ci", "expected", "expected_messages", "_oracle"])
def test_a_module_level_oracle_in_an_in_process_test_is_flagged(exercise: Exercise, name: str):
    test = HEADER + f"def {name}(a, b):\n    return a + b\n\n\ndef test_it():\n    pass\n"
    item = _review(exercise, test)[ORACLES]
    assert item.status is Status.WARN
    assert [(f.path, f.line) for f in item.findings] == [("tests/test_add.py", 7)]


@pytest.mark.parametrize(
    "test",
    [
        # nested in the test that uses it: not reachable as an attribute of the module
        "def test_it():\n    def expected(a, b):\n        return a + b\n",
        # names that only start like an oracle
        "def expectation(a):\n    return a\n\n\ndef referenced(a):\n    return a\n",
    ],
)
def test_nested_or_differently_named_helpers_are_not_flagged(exercise: Exercise, test: str):
    assert _status(_review(exercise, HEADER + test), ORACLES) is Status.OK


def test_an_oracle_is_fine_when_learner_code_runs_in_its_own_process(exercise: Exercise):
    test = HEADER + "def reference(a, b):\n    return a + b\n"
    assert _status(_review(exercise, test, isolation="process"), ORACLES) is Status.OK
    accepted = HEADER + "def reference(a):  # review-ok: needs inputs no learner sees\n    pass\n"
    item = _review(exercise, accepted)[ORACLES]
    assert item.status is Status.OK and len(item.accepted) == 1


def test_the_cli_reviews_every_exercise_when_no_id_is_given(tmp_path: Path):
    write_branch(tmp_path, "starter")
    test = (
        "from solution_mod import add\n\n\n"
        "def test_adds():\n    assert float(add(2, 2)) == 4, 'add(2, 2) should be 4'\n"
    )
    oracle = "def expected(a, b):\n    return a + b\n\n\n"
    for slug, head in (("clean", ""), ("leaky", oracle)):
        ex_dir = write_exercise(tmp_path, "starter", slug)
        (ex_dir / "tests/test_add.py").write_text(head + test)

    result = CliRunner().invoke(app, ["content", "review", "--content-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "starter.leaky" in result.output and "starter.clean" not in result.output
    assert "tests/test_add.py:1  expected() is defined at module level" in result.output
    assert "2 exercise(s) reviewed, 1 with item(s) to look at" in result.output
