"""An advisory cheat review: the checklist from `docs/authoring.md`, tailored to one exercise.

Each heuristic reads the exercise's files (it never runs them) and is deliberately cheap and
conservative: it would rather miss a problem than cry wolf, so a ✓ means "nothing found", never
"nothing there". Items no heuristic can judge are listed for the author to check by hand.

Known limits:

- Learner functions are names imported from an editable module, attributes of an imported
  editable module, and functions in the test file that call either (wrappers, followed to a fixed
  point). Calls through other objects, `getattr` or `importlib` are not seen.
- *Equality* flags `==`, `!=`, `in` and `not in` in an `assert` whose operand is a learner call,
  or a name bound directly to one in the same function, unless the call is wrapped (`plain(...)`,
  `json.loads(...)`, `float(...)` and other built-in conversions) or the function asserts
  `type(name) is ...`. A value canonicalised later, or reached through a container, is not seen.
- *Expected values* flags a name bound before a test function's first learner call to a literal,
  a display or a call to a lower-case helper, which is then a whole operand of an assert's
  comparison and is never passed to learner code. Answers kept in fixtures, globals, objects or
  closures are not seen.
- *Keyword fakes* reads only responders handed to a `...Model(...)` constructor as a lambda, a
  function or a method of the same file, looking for a string literal tested with `in`,
  `startswith` or `endswith`. Regular expressions are not judged: extracting a seeded token with
  one is the recommended pattern, and matching a keyword with one is not seen.
- *Randomness* flags `random.Random()` with no seed and the module-level `random.*` functions
  (which share an unseeded generator) in a file that never calls `random.seed`.
- *Defaults* reads signatures written in backticks in the brief, ``name(a, b=1)``, and looks for a
  call to `name` that passes fewer positional arguments than the default's position and does not
  name it. Calls with `*args` or `**kwargs` are skipped, and a function the tests never call
  directly (it is reached through a tool call or a fresh process) is not judged. Defaults
  described in prose, and exact boundaries, are not checked.
- *Fresh processes* flags, in a test file that uses `run_fresh`, calls without `path=` and file
  paths written as relative string literals (each child starts in a new, empty directory).
- *Oracles in the test module* flags, in an exercise graded in-process, a function defined at a
  test file's top level whose name is `reference`, `expected` or `oracle`, alone or followed by
  `_...` (a leading underscore too). Learner code in the same process can call it through
  `sys.modules`. Answers computed by other names, by methods (`Built(seed).expected()`) or kept
  as module-level data are not seen.
- *Borrows the grader* looks for a test import of `lattice_grader.*_reference` and a wrong case
  whose files call `import_module` on a name containing `_grader`.

An author who has read a finding and judged it safe marks the flagged line with
`# review-ok: <why>` in a test file, or `<!-- review-ok: <why> -->` in the brief. The finding is
then counted as accepted rather than warned about; the reason must not be empty.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum

from lattice.domain.content import Exercise, Isolation, Tier, WrongCase


class Status(StrEnum):
    OK = "ok"  # the heuristic found nothing
    WARN = "warn"  # the heuristic found something worth a look
    MANUAL = "manual"  # no heuristic: read the tests with this in mind


@dataclass(frozen=True)
class Finding:
    path: str  # relative to the exercise directory, e.g. "tests/test_x.py"
    line: int
    note: str


@dataclass(frozen=True)
class ReviewItem:
    title: str
    status: Status
    summary: str
    findings: tuple[Finding, ...] = field(default=())
    accepted: tuple[Finding, ...] = field(default=())  # marked `review-ok` with a reason


@dataclass(frozen=True)
class ReviewInput:
    """Everything the review reads, as text. Paths are relative to each directory."""

    exercise: Exercise
    tests: Mapping[str, str]
    wrong_cases: tuple[WrongCase, ...]


_CONVERSIONS = {
    "plain",
    "canonical",
    "float",
    "int",
    "str",
    "bool",
    "len",
    "sorted",
    "list",
    "tuple",
    "dict",
    "set",
    "frozenset",
    "repr",
    "type",
    "isinstance",
    "loads",  # json.loads
    "__str__",  # str.__str__
}
_RANDOM_FUNCS = {
    "random",
    "randint",
    "randrange",
    "choice",
    "choices",
    "shuffle",
    "sample",
    "uniform",
    "gauss",
    "randbytes",
    "getrandbits",
}
_SIGNATURE = re.compile(r"`(\w+)\(([^`]*)\)`")
_ACCEPTED = re.compile(r"(?:#|<!--)\s*review-ok:\s*\S")
_ORACLE = re.compile(r"_?(?:reference|expected|oracle)(?:_\w*)?")


def review_exercise(source: ReviewInput) -> list[ReviewItem]:
    """The checklist, in the order `docs/authoring.md` gives it."""
    modules = _learner_modules(source.exercise.editable)
    parsed = {
        f"tests/{path}": tree
        for path, text in sorted(source.tests.items())
        if path.endswith(".py") and (tree := _parse(text)) is not None
    }
    items = [
        _messages(parsed),
        _borrowed(parsed, source.wrong_cases),
        ReviewItem(
            "Surface assertions",
            Status.MANUAL,
            "Assert on the content that reached the model or tool (FakeModel.requests), with "
            "per-call values the learner cannot guess, not on counts or that something was sent.",
        ),
        _keyword_fakes(parsed),
        ReviewItem(
            "Reachable test state",
            Status.MANUAL,
            "Counters, barriers and flags live in closures or test-local objects, never on an "
            "object handed to learner code.",
        ),
        ReviewItem(
            "Untested requirements",
            Status.MANUAL,
            "Every behaviour the brief promises is exercised by a check, so a wrong case for it "
            "fails.",
        ),
        ReviewItem(
            "Unstated rules",
            Status.MANUAL,
            "Every format, case or character set a test enforces is stated in the brief.",
        ),
        _equality(parsed, modules),
        _randomness(parsed),
        _defaults(source.exercise.brief, parsed),
        _expected_first(parsed, modules),
        _oracles(parsed, source.exercise.isolation),
        _fresh(parsed),
    ]
    if source.exercise.tier is Tier.CAPSTONE:
        items.append(_pasted(source.wrong_cases))
    texts = {f"tests/{path}": text for path, text in source.tests.items()}
    texts["brief.md"] = source.exercise.brief
    return [_accept(item, texts) for item in items]


def _accept(item: ReviewItem, texts: Mapping[str, str]) -> ReviewItem:
    """Move findings whose line carries a `review-ok: <why>` comment out of the warnings."""
    if not item.findings:
        return item
    accepted: list[Finding] = []
    open_: list[Finding] = []
    for finding in item.findings:
        lines = texts.get(finding.path, "").splitlines()
        line = lines[finding.line - 1] if 0 < finding.line <= len(lines) else ""
        (accepted if _ACCEPTED.search(line) else open_).append(finding)
    if not accepted:
        return item
    if open_:
        return replace(item, findings=tuple(open_), accepted=tuple(accepted))
    return ReviewItem(
        item.title,
        Status.OK,
        f"{len(accepted)} finding(s) accepted with a review-ok reason",
        accepted=tuple(accepted),
    )


# -- the heuristics ------------------------------------------------------------------------------


def _messages(parsed: Mapping[str, ast.Module]) -> ReviewItem:
    found = [
        Finding(path, node.lineno, "assert without a message")
        for path, tree in parsed.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert) and node.msg is None
    ]
    return _item(
        "Learner-facing messages",
        found,
        "every assert carries a message",
        f"{len(found)} assert(s) have no message; learners see only the message, never the test",
    )


def _borrowed(parsed: Mapping[str, ast.Module], cases: Iterable[WrongCase]) -> ReviewItem:
    title = "Borrowed behaviour"
    imports = [
        Finding(path, node.lineno, f"imports {name}")
        for path, tree in parsed.items()
        for node, name in _imported_modules(tree)
        if name.startswith("lattice_grader.") and "_reference" in name
    ]
    if not imports:
        return ReviewItem(title, Status.OK, "the tests use no lattice_grader.*_reference package")
    borrowing = [
        c.name
        for c in cases
        if any("import_module" in text and "_grader" in text for text in c.files.values())
    ]
    if borrowing:
        return ReviewItem(
            title,
            Status.OK,
            f"the tests use a reference package and wrong case '{borrowing[0]}' borrows it",
        )
    return ReviewItem(
        title,
        Status.WARN,
        "the tests use a reference package but no wrong case borrows it: add borrows-the-grader "
        '(the solution plus importlib.import_module("lattice" + "_grader.<package>"))',
        tuple(imports),
    )


def _keyword_fakes(parsed: Mapping[str, ast.Module]) -> ReviewItem:
    found: list[Finding] = []
    for path, tree in parsed.items():
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        for responder in _responders(tree, functions):
            for node in ast.walk(responder):
                literal = _keyword_test(node)
                if literal is not None and isinstance(node, ast.expr):
                    found.append(
                        Finding(path, node.lineno, f"responder decides by the keyword {literal!r}")
                    )
    return _item(
        "Predictable fakes",
        _unique(found),
        "no responder decides by a keyword",
        "a fake that answers by keyword can be steered without the model: make its answer "
        "arbitrary (a seeded table, a fresh token) and assert the code followed it",
    )


def _equality(parsed: Mapping[str, ast.Module], modules: set[str]) -> ReviewItem:
    found: list[Finding] = []
    for path, tree in parsed.items():
        learner = _LearnerCalls(tree, modules)
        for function in _functions(tree):
            raw = _raw_bindings(function, learner)
            checked = _type_checked(function)
            for node in ast.walk(function):
                if not isinstance(node, ast.Assert):
                    continue
                for operand in _compared_operands(node.test):
                    if isinstance(operand, ast.Call) and learner.is_call(operand):
                        found.append(
                            Finding(path, node.lineno, f"compares {_src(operand)} directly")
                        )
                        continue
                    root = _root_name(operand)
                    if root in raw and root not in checked:
                        found.append(
                            Finding(
                                path,
                                node.lineno,
                                f"compares {root!r} from {raw[root]} without canonicalising",
                            )
                        )
    return _item(
        "Objects that lie about equality",
        _unique(found),
        "learner values are canonicalised before they are compared",
        "turn learner values into plain built-ins (plain(), json.loads(json.dumps(...)), or "
        "type(x) is str) before comparing them",
    )


def _randomness(parsed: Mapping[str, ast.Module]) -> ReviewItem:
    found: list[Finding] = []
    for path, tree in parsed.items():
        seeded = any(
            isinstance(n, ast.Call) and _call_name(n) == "random.seed" for n in ast.walk(tree)
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in ("random.Random", "Random") and not node.args and not node.keywords:
                found.append(Finding(path, node.lineno, "random.Random() without a seed"))
            elif (
                not seeded
                and name is not None
                and name.startswith("random.")
                and name.split(".", 1)[1] in _RANDOM_FUNCS
            ):
                found.append(Finding(path, node.lineno, f"{name}() uses the unseeded generator"))
    return _item(
        "Unseeded randomness",
        found,
        "every generator is seeded",
        "grading must be deterministic: use random.Random(<seed>) and draw from it",
    )


def _defaults(brief: str, parsed: Mapping[str, ast.Module]) -> ReviewItem:
    signatures: list[tuple[int, str, str, int]] = []  # line, function, parameter, position
    for number, line in enumerate(brief.splitlines(), start=1):
        for match in _SIGNATURE.finditer(line):
            params = _split_params(match.group(2))
            for position, param in enumerate(params):
                if "=" in param and not param.startswith("*"):
                    name = param.split("=", 1)[0].strip().split(":", 1)[0].strip()
                    signatures.append((number, match.group(1), name, position))
    if not signatures:
        return ReviewItem(
            "Untested defaults and boundaries",
            Status.OK,
            "the brief gives no defaults in a signature; check boundaries (> versus >=) by hand",
        )
    calls = [
        node
        for tree in parsed.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and not _has_star(node)
    ]
    found: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for number, function, param, position in signatures:
        if (function, param) in seen:
            continue
        seen.add((function, param))
        mine = [c for c in calls if _callee(c) == function]
        if not mine:
            continue  # called some other way (a tool call, a fresh process): cannot tell
        if not any(
            len(c.args) <= position and all(k.arg != param for k in c.keywords) for c in mine
        ):
            found.append(Finding("brief.md", number, f"no test calls {function}() without {param}"))
    return _item(
        "Untested defaults and boundaries",
        found,
        "every default in the brief's signatures is exercised; check boundaries by hand",
        "a default the brief gives must be exercised by a call that leaves it out",
    )


def _expected_first(parsed: Mapping[str, ast.Module], modules: set[str]) -> ReviewItem:
    found: list[Finding] = []
    for path, tree in parsed.items():
        learner = _LearnerCalls(tree, modules)
        for function in _functions(tree):
            if not function.name.startswith("test"):
                continue
            calls = [n for n in ast.walk(function) if isinstance(n, ast.Call) and learner.calls(n)]
            if not calls:
                continue
            first = min(c.lineno for c in calls)
            early = {
                target.id: statement.lineno
                for statement in function.body
                if isinstance(statement, ast.Assign)
                and (statement.end_lineno or statement.lineno) < first
                for target in statement.targets
                if isinstance(target, ast.Name) and _answer_like(statement.value)
            }
            # A name read before the learner call, or by a nested function, feeds the inputs.
            inputs = {
                n.id
                for c in calls
                for arg in [*c.args, *(k.value for k in c.keywords)]
                for n in ast.walk(arg)
                if isinstance(n, ast.Name)
            }
            inputs.update(
                n.id
                for n in ast.walk(function)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.lineno <= first
            )
            inputs.update(
                n.id
                for inner in ast.walk(function)
                if inner is not function
                and isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda)
                for n in ast.walk(inner)
                if isinstance(n, ast.Name)
            )
            for node in ast.walk(function):
                if isinstance(node, ast.Assert) and node.lineno > first:
                    for operand in _compared_operands(node.test):
                        root = _root_name(operand)
                        if root in early and root not in inputs:
                            found.append(
                                Finding(
                                    path,
                                    early[root],
                                    f"{root!r} is worked out before the learner call on line "
                                    f"{first} and compared on line {node.lineno}",
                                )
                            )
    return _item(
        "Expected values in the caller's frame",
        _unique(found),
        "no expected value is built before learner code runs",
        "learner code can read the test's locals: compute expected values in a helper called "
        "after it returns",
    )


def _oracles(parsed: Mapping[str, ast.Module], isolation: Isolation) -> ReviewItem:
    title = "Oracles in the test module"
    if isolation is Isolation.PROCESS:
        return ReviewItem(
            title, Status.OK, "learner code runs in its own process, out of the test module's reach"
        )
    found = [
        Finding(path, node.lineno, f"{node.name}() is defined at module level")
        for path, tree in parsed.items()
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _ORACLE.fullmatch(node.name)
    ]
    return _item(
        title,
        found,
        "no reference_, expected_ or oracle function at a test file's top level",
        "in-process learner code can call a module-level oracle through sys.modules: set "
        "isolation: process, or define it inside the test that uses it",
    )


def _fresh(parsed: Mapping[str, ast.Module]) -> ReviewItem:
    found: list[Finding] = []
    used = False
    for path, tree in parsed.items():
        if not any(
            isinstance(n, ast.Name | ast.Attribute) and _leaf(n) == "run_fresh"
            for n in ast.walk(tree)
        ):
            continue
        used = True
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _callee(node)
            if callee == "run_fresh" and all(k.arg != "path" for k in node.keywords):
                found.append(
                    Finding(
                        path,
                        node.lineno,
                        "run_fresh without path=: the child cannot import the submission",
                    )
                )
            elif callee in ("open", "Path") and node.args:
                arg = node.args[0]
                if (
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and arg.value
                    and not arg.value.startswith("/")
                ):
                    found.append(
                        Finding(
                            path,
                            node.lineno,
                            f"relative path {arg.value!r}: each run_fresh child starts in a "
                            "new, empty directory",
                        )
                    )
    if not used:
        return ReviewItem(
            "In-process persistence",
            Status.MANUAL,
            "no run_fresh: if the brief promises a restart, run each session in a fresh "
            "interpreter, and assert on what the store itself holds",
        )
    return _item(
        "In-process persistence",
        found,
        "run_fresh is given the submission and no relative file paths",
        "run_fresh children import the submission from path= and start in an empty directory: "
        "pass data as JSON arguments, not files beside the test",
    )


def _pasted(cases: Iterable[WrongCase]) -> ReviewItem:
    names = [c.name for c in cases if "pasted" in c.name]
    if names:
        return ReviewItem(
            "Capstone: pasted reference solutions",
            Status.OK,
            f"wrong case '{names[0]}' stitches together earlier reference solutions",
        )
    return ReviewItem(
        "Capstone: pasted reference solutions",
        Status.WARN,
        "add a pasted-solutions wrong case: earlier reference solutions stitched together must "
        "fail the check on the parts working together",
    )


# -- AST helpers ---------------------------------------------------------------------------------


class _LearnerCalls:
    """Which calls in a test file reach learner code, directly or through a local wrapper."""

    def __init__(self, tree: ast.Module, modules: set[str]) -> None:
        self.modules: set[str] = set()  # local names bound to learner modules
        self.functions: set[str] = set()  # local names bound to learner functions
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in modules:
                        self.modules.add(alias.asname or alias.name.split(".", 1)[0])
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
                and node.module.split(".", 1)[0] in modules
            ):
                self.functions.update(a.asname or a.name for a in node.names)
        self.wrappers: set[str] = set()
        functions = list(_functions(tree))
        changed = True
        while changed:
            changed = False
            for function in functions:
                if function.name in self.wrappers or function.name in self.functions:
                    continue
                if any(isinstance(n, ast.Call) and self.calls(n) for n in ast.walk(function)):
                    self.wrappers.add(function.name)
                    changed = True

    def is_call(self, node: ast.Call) -> bool:
        """A direct call to a learner function."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in self.functions
        root = _root_name(func)
        return root in self.modules

    def calls(self, node: ast.Call) -> bool:
        """A call that reaches learner code: direct, or through a wrapper in the test file."""
        return self.is_call(node) or (
            isinstance(node.func, ast.Name) and node.func.id in self.wrappers
        )


def _split_params(text: str) -> list[str]:
    """Split a signature's parameters on top-level commas: `a, b=(1, 2)` is two."""
    params: list[str] = []
    depth, current = 0, ""
    for char in text:
        depth += char in "([{"
        depth -= char in ")]}"
        if char == "," and depth == 0:
            params.append(current.strip())
            current = ""
        else:
            current += char
    params.append(current.strip())
    return [p for p in params if p]


def _learner_modules(editable: Iterable[str]) -> set[str]:
    return {path.split("/", 1)[0].removesuffix(".py") for path in editable if path.endswith(".py")}


def _parse(text: str) -> ast.Module | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _functions(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _imported_modules(tree: ast.Module) -> Iterator[tuple[ast.stmt, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node, node.module
            for alias in node.names:
                yield node, f"{node.module}.{alias.name}"


def _raw_bindings(function: ast.AST, learner: _LearnerCalls) -> dict[str, str]:
    """Names bound directly to an unwrapped learner call, with the call's source."""
    raw: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if not learner.is_call(node.value):
                continue
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        raw[name.id] = _src(node.value.func) + "(...)"
    return raw


def _type_checked(function: ast.AST) -> set[str]:
    """Names the function asserts the exact type of: `type(name) is ...`."""
    checked: set[str] = set()
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "type"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            checked.add(node.args[0].id)
    return checked


def _compared_operands(test: ast.expr) -> Iterator[ast.expr]:
    """Operands of ==, !=, in and not in comparisons in an assert's test (not its message),
    skipping anything already inside a call such as plain(...)."""
    stack: list[ast.AST] = [test]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Compare):
            if any(isinstance(op, ast.Eq | ast.NotEq | ast.In | ast.NotIn) for op in node.ops):
                yield node.left
                yield from node.comparators
        elif isinstance(node, ast.BoolOp):
            stack.extend(node.values)
        elif isinstance(node, ast.UnaryOp):
            stack.append(node.operand)


def _root_name(node: ast.AST) -> str | None:
    """`x` for `x`, `x.a`, `x["k"]` and `x.a[0].b`; None for anything else."""
    while isinstance(node, ast.Attribute | ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _answer_like(value: ast.expr) -> bool:
    """A literal, a display, a comprehension or a call to a lower-case helper: something that
    could hold an answer, as opposed to a fake or a world object (a capitalised constructor)."""
    if isinstance(value, ast.Constant | ast.JoinedStr):
        return True
    if isinstance(
        value,
        ast.List | ast.Tuple | ast.Dict | ast.Set | ast.ListComp | ast.DictComp | ast.SetComp,
    ):
        return True
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value.func.id[:1].islower() and value.func.id not in _CONVERSIONS
    return False


def _responders(
    tree: ast.Module, functions: Mapping[str, ast.FunctionDef | ast.AsyncFunctionDef]
) -> Iterator[ast.AST]:
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and (_leaf(node.func) or "").endswith("Model")):
            continue
        given = [*node.args[:1], *(k.value for k in node.keywords if k.arg == "responder")]
        for value in given:
            if isinstance(value, ast.Lambda):
                yield value
            elif isinstance(value, ast.Name | ast.Attribute):
                name = _leaf(value)
                if name is not None and name in functions:
                    yield functions[name]


def _keyword_test(node: ast.AST) -> str | None:
    """The string literal a node tests for, if it is a keyword test."""
    if (
        isinstance(node, ast.Compare)
        and any(isinstance(op, ast.In) for op in node.ops)
        and isinstance(node.left, ast.Constant)
        and isinstance(node.left.value, str)
    ):
        return node.left.value
    if isinstance(node, ast.Call) and node.args:
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return None
        name = _call_name(node) or ""
        if name.split(".")[-1] in ("startswith", "endswith"):
            return arg.value
    return None


def _call_name(node: ast.Call) -> str | None:
    parts: list[str] = []
    func: ast.AST = node.func
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return ".".join(reversed(parts)) if parts else None


def _callee(node: ast.Call) -> str | None:
    return _leaf(node.func)


def _leaf(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _has_star(node: ast.Call) -> bool:
    return any(isinstance(a, ast.Starred) for a in node.args) or any(
        k.arg is None for k in node.keywords
    )


def _src(node: ast.AST) -> str:
    text = ast.unparse(node)
    return text if len(text) <= 60 else text[:57] + "..."


def _unique(found: list[Finding]) -> list[Finding]:
    return list(dict.fromkeys(found))


def _item(title: str, found: list[Finding], ok: str, warn: str) -> ReviewItem:
    if not found:
        return ReviewItem(title, Status.OK, ok)
    return ReviewItem(title, Status.WARN, warn, tuple(found))
