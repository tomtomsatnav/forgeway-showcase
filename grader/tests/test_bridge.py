"""The bridge runs learner code in a child process: values, handles, reverse calls, exceptions,
generators, timeouts and what the child can no longer reach."""

import datetime as dt
import importlib
import os
import sys
import textwrap
import threading
import time
from collections.abc import Iterator, MutableMapping
from pathlib import Path

import pytest

from forgeway_kit import FakeModel, Message, ToolCall
from lattice_grader import bridge
from lattice_grader.bridge import peer
from lattice_grader.plugin import ReportPlugin

LEARNER = textwrap.dedent(
    """
    import os, sys, threading, time
    from dataclasses import dataclass
    from forgeway_kit import Message

    class Loud(str):
        def __eq__(self, other):
            return True

    class StoreError(ValueError):
        pass

    class Store:
        def __init__(self, embedder):
            self.embedder = embedder
            self.items = []

        def add(self, text):
            self.items.append((text, self.embedder.embed([text])[0]))
            return len(self.items)

        def search(self, k=1):
            if not self.items:
                raise StoreError("the store is empty")
            return [text for text, _ in self.items[:k]]

    @dataclass(frozen=True)
    class Hit:
        id: str
        score: float

    def echo(value):
        return value

    def loud():
        return Loud("anything")

    def hit():
        return Hit("a", 0.5)

    def ask(client, question):
        return client.complete([Message(role="user", content=question)]).text

    def call(fn, *args):
        return fn(*args)

    def catch(fn):
        try:
            fn()
        except Exception as error:
            return f"error: {type(error).__name__}: {error}"

    def countdown(n):
        while n:
            yield n
            n -= 1
        return "lift-off"

    def consume(items):
        return [item * 2 for item in items]

    def boom():
        raise KeyError("missing")

    def spin():
        while True:
            pass

    def leave():
        os._exit(3)

    def chatty():
        print("hello from the child")
        return os.getpid()

    def peek(obj, name):
        return getattr(obj, name)

    def poke(obj):
        obj.patched = True

    def frames():
        return [f.f_code.co_name for f in _walk(sys._getframe())]

    def _walk(frame):
        while frame is not None:
            yield frame
            frame = frame.f_back

    def modules():
        return sorted(m for m in sys.modules if m.startswith(("lattice", "test_")))

    def greeting():
        return GREETING

    def fan_out(fn, n, hang=False):
        from concurrent.futures import ThreadPoolExecutor

        def one(i):
            while hang:
                pass
            return fn(i)

        with ThreadPoolExecutor(max_workers=n) as pool:
            return list(pool.map(one, range(n)))

    GREETING = "hi"

    def chatter():
        while True:
            print(".", end="")
            time.sleep(0.3)

    def shout(n):
        print("x" * n, end="")

    class Slow:
        def __eq__(self, other):
            time.sleep(3600)
            return True

    def reflect(obj):
        # `obj == Slow()` asks the parent, whose fake answers NotImplemented, so Python tries
        # the reflected `Slow.__eq__`, back in this process, which never returns.
        worker = threading.Thread(target=lambda: obj == Slow())
        worker.start()
        worker.join()

    def set_item(obj, key, value):
        obj[key] = value

    def del_item(obj, key):
        del obj[key]

    def enter(obj):
        with obj:
            return "entered"

    def step(obj):
        return next(obj)

    def _peer():
        frame = sys._getframe()
        while frame is not None:
            candidate = frame.f_locals.get("self")
            if type(candidate).__name__ == "Peer":
                return candidate
            frame = frame.f_back
        raise LookupError("no peer")

    def forge_error():
        peer_class = type(_peer())
        real = peer_class._encode_error

        def forged(self, exc):
            data = real(self, exc)
            data["attrs"] = {
                "__class__": {"$builtin": "KeyboardInterrupt"},
                "__cause__": {"$exc": real(self, SystemExit(0))},
                "__learner_frames__": ["  forged.py, line 1, in forged"],
                "note": "kept",
            }
            data["frames"] = [f"  learner_mod.py, line {n}, in f" for n in range(9)] + ["y" * 999]
            return data

        peer_class._encode_error = forged
        raise ValueError("forged")

    def guess(obj, offset):
        # A handle for an object this process was never given, named by its neighbour's number.
        handle = object.__getattribute__(obj, "_bridge_id") + offset
        info = {"k": "obj", "n": "Guess", "q": "Guess", "m": "guess", "call": False}
        return _peer()._proxy(handle, info).secret
    """
)


@pytest.fixture
def learner(tmp_path: Path) -> Iterator[object]:
    (tmp_path / "learner_mod.py").write_text(LEARNER)
    installed = bridge.install(tmp_path, timeout=3)
    try:
        yield importlib.import_module("learner_mod")
    finally:
        bridge.uninstall(installed)


class Embedder:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[float(len(t))] for t in texts]


# ---- marshalling --------------------------------------------------------------------------


def test_plain_values_cross_as_exact_builtins(learner):
    value = {
        "text": "a",
        "n": 1,
        "x": 1.5,
        "none": None,
        "flag": True,
        "items": [1, (2, 3)],
        1: "int key",
        "set": {1, 2},
        "frozen": frozenset({3}),
        "bytes": b"\x00\xff",
        "when": dt.datetime(2026, 10, 26, 9, 30),
        "day": dt.date(2026, 10, 26),
        "gap": dt.timedelta(hours=2),
    }
    assert learner.echo(value) == value
    assert type(learner.echo((1, 2))) is tuple


def test_a_str_subclass_arrives_as_a_plain_str(learner):
    value = learner.loud()
    assert type(value) is str
    assert value != "something else"


def test_kit_dataclasses_cross_by_value(learner):
    message = learner.echo(Message(role="user", content="hi"))
    assert type(message) is Message and message.content == "hi"
    call = learner.echo(ToolCall("c1", "lookup", {"page": 1}))
    assert call == ToolCall("c1", "lookup", {"page": 1})


# ---- handles ------------------------------------------------------------------------------


def test_learner_classes_are_mirrored_and_their_instances_are_handles(learner):
    embedder = Embedder()
    store = learner.Store(embedder)
    assert isinstance(store, learner.Store)
    assert type(store).__name__ == "Store"
    assert store.add("alpha") == 1
    assert store.add("be") == 2
    assert store.search(k=2) == ["alpha", "be"]
    assert embedder.calls == 2, "the embedder ran in the parent, called back from the child"


def test_attributes_of_learner_objects_read_as_values(learner):
    hit = learner.hit()
    assert type(hit).__name__ == "Hit"
    assert type(hit.id) is str and type(hit.score) is float
    assert hit == learner.hit()


def test_a_handle_sent_home_is_the_original_object(learner):
    embedder = Embedder()
    assert learner.echo(embedder) is embedder
    store = learner.Store(embedder)
    assert learner.echo(store) is store


def test_module_attributes_can_be_monkeypatched(learner, monkeypatch):
    assert learner.greeting() == "hi"
    monkeypatch.setattr(learner, "GREETING", "patched")
    assert learner.greeting() == "patched"
    monkeypatch.undo()
    assert learner.greeting() == "hi"


# ---- reverse calls ------------------------------------------------------------------------


def test_the_fake_model_stays_in_the_parent(learner):
    model = FakeModel(responder=lambda request: f"echo {request.messages[0].content}")
    assert learner.ask(model, "ping") == "echo ping"
    assert model.requests[0].messages[0].content == "ping"


def test_callables_passed_in_are_called_back(learner):
    seen = []
    assert learner.call(lambda x: seen.append(x) or x * 2, 21) == 42
    assert seen == [21]


def test_test_objects_expose_only_methods_and_plain_data(learner):
    model = FakeModel(responder=lambda request: "secret")
    for name in ("responder", "_private", "__globals__", "__wrapped__"):
        with pytest.raises(AttributeError, match="not reachable from your code"):
            learner.peek(model, name)
    # The child's view of the object is a local proxy: its class is not the parent's class.
    assert learner.peek(model, "__class__") is not FakeModel
    assert learner.peek(model, "context_window") == 8000
    with pytest.raises(AttributeError, match="cannot change"):
        learner.poke(model)
    closure = lambda: None  # noqa: E731
    with pytest.raises(AttributeError, match="not reachable"):
        learner.peek(closure, "__closure__")
    assert learner.peek(closure, "__name__") == "<lambda>"


# ---- exceptions ---------------------------------------------------------------------------


def test_learner_exceptions_mirror_their_class(learner):
    with pytest.raises(learner.StoreError, match="the store is empty") as raised:
        learner.Store(Embedder()).search()
    assert type(raised.value).__name__ == "StoreError"
    assert isinstance(raised.value, ValueError)
    assert learner.StoreError is learner.StoreError
    frames = raised.value.__dict__["__learner_frames__"]
    assert any("learner_mod.py" in frame and "search" in frame for frame in frames)


def test_builtin_exceptions_arrive_as_the_builtin(learner):
    with pytest.raises(KeyError) as raised:
        learner.boom()
    assert type(raised.value) is KeyError and raised.value.args == ("missing",)


def test_a_parent_exception_reaches_learner_code_and_returns_as_itself(learner):
    def fails():
        raise RuntimeError("disk full")

    assert learner.catch(fails) == "error: RuntimeError: disk full"
    error = RuntimeError("original")

    def raises():
        raise error

    with pytest.raises(RuntimeError) as raised:
        learner.call(raises)
    assert raised.value is error


class Crash(BaseException):
    """A test's simulated crash: not an Exception, so learner code's handlers cannot hide it."""


def test_a_tests_base_exception_passes_through_learner_handlers(learner):
    crash = Crash("killed")

    def dies():
        raise crash

    with pytest.raises(Crash) as raised:
        learner.catch(dies)  # catches Exception, and must not catch this
    assert raised.value is crash


# ---- generators ---------------------------------------------------------------------------


def test_generators_iterate_by_handle(learner):
    countdown = learner.countdown(3)
    assert next(countdown) == 3
    assert list(countdown) == [2, 1]
    with pytest.raises(StopIteration):
        next(countdown)


def test_parent_iterators_are_consumed_by_learner_code(learner):
    assert learner.consume(x for x in range(3)) == [0, 2, 4]


# ---- isolation ----------------------------------------------------------------------------


def test_learner_code_runs_in_another_process(learner):
    assert learner.chatty() != os.getpid()


def test_a_module_dropped_by_the_tests_runs_afresh_in_the_child(tmp_path):
    (tmp_path / "tally.py").write_text(
        "import helper\nSEEN = []\n\n"
        "def add(x):\n    SEEN.append(x)\n    return [len(SEEN), helper.ID]\n"
    )
    (tmp_path / "helper.py").write_text("import itertools\nID = id(itertools.count())\n")
    (tmp_path / "other.py").write_text("VALUE = 1\n")
    installed = bridge.install(tmp_path, timeout=3)
    try:
        importlib.import_module("other")
        tally = importlib.import_module("tally")
        first = tally.add("a")
        assert tally.add("b")[0] == 2
        del sys.modules["tally"]
        again = importlib.import_module("tally").add("c")
        assert again == [1, first[1]], "Only the dropped module runs afresh while tests hold others"
        for name in ("tally", "other"):
            del sys.modules[name]
        fresh = importlib.import_module("tally").add("d")
        assert fresh[0] == 1 and fresh[1] != first[1], "Dropping them all resets every module"
        helper = importlib.import_module("helper")
        assert fresh[1] == helper.ID, "A module the reset loaded again is not reset a second time"
    finally:
        bridge.uninstall(installed)


def test_learner_output_reaches_the_parents_stdout(learner, capsys):
    learner.chatty()
    assert "hello from the child" in capsys.readouterr().out


def test_the_childs_frames_and_modules_hold_no_test_or_grader_code(learner):
    names = learner.frames()
    assert not any(name.startswith("test_") for name in names)
    assert learner.modules() == []
    assert "test_bridge" in sys.modules[__name__].__name__


def test_the_tests_threads_can_call_learner_code(learner):
    results = []
    threads = [
        threading.Thread(target=lambda n=n: results.append(learner.echo(n))) for n in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [0, 1, 2, 3]


def test_learner_threads_call_back_into_the_parent_at_the_same_time(learner):
    meet = threading.Barrier(4, timeout=5)
    seen = []

    def work(n):
        meet.wait()  # passes only if four calls are in the parent at once
        seen.append(threading.current_thread().name)
        return learner.echo(n * 10)  # and each can call back into the child

    assert learner.fan_out(work, 4) == [0, 10, 20, 30]
    assert len(set(seen)) == 4, "Each learner thread is served by a thread of its own."
    assert learner.echo("after") == "after", "The main conversation carries on afterwards."


def test_a_learner_thread_that_hangs_times_out(learner):
    with pytest.raises(bridge.LearnerProcessError, match="did not finish within 3 seconds"):
        learner.fan_out(lambda n: None, 1, hang=True)


def _attempt(fn):
    try:
        fn()
    except Exception as error:
        return error
    return None


# ---- failures -----------------------------------------------------------------------------


def test_a_call_that_never_returns_times_out_with_a_clear_message(learner):
    with pytest.raises(bridge.LearnerProcessError, match="did not finish within 3 seconds"):
        learner.spin()
    with pytest.raises(bridge.LearnerProcessError, match="stopped earlier in this run"):
        learner.greeting()


def test_a_child_that_exits_is_reported(learner):
    with pytest.raises(bridge.LearnerProcessError, match="exited with status 3"):
        learner.leave()


def test_an_import_error_in_learner_code_surfaces_at_import(tmp_path):
    (tmp_path / "broken_mod.py").write_text("raise ValueError('bad module')\n")
    installed = bridge.install(tmp_path, timeout=3)
    try:
        with pytest.raises(ValueError, match="bad module"):
            importlib.import_module("broken_mod")
    finally:
        bridge.uninstall(installed)


def test_a_dead_child_is_not_the_exception_a_test_expected(learner):
    with (
        pytest.raises(bridge.LearnerProcessError, match="exited with status 3"),
        pytest.raises(Exception),  # noqa: B017 - a test that expects any error at all
    ):
        learner.leave()


def test_the_report_shows_a_dead_childs_message_as_written(tmp_path):
    message = "Your code's process exited with status 3 before it returned."
    with pytest.raises(bridge.LearnerProcessError) as raised:
        raise bridge.LearnerProcessError(message)
    assert ReportPlugin({}, tmp_path)._describe(raised) == message


# ---- the silence limit cannot be held open ------------------------------------------------


def test_printing_in_a_loop_does_not_hold_the_time_limit_open(learner, capsys):
    started = time.monotonic()
    with pytest.raises(bridge.LearnerProcessError, match="did not finish within 3 seconds"):
        learner.chatter()
    assert time.monotonic() - started < 8, "Output is not activity: silence is still silence."
    assert "..." in capsys.readouterr().out


def test_a_reflected_comparison_that_hangs_in_learner_code_times_out(learner):
    started = time.monotonic()
    with pytest.raises(bridge.LearnerProcessError, match="did not finish within 3 seconds"):
        learner.reflect(FakeModel())
    assert time.monotonic() - started < 8, "Two ends waiting on each other are not busy."


def test_learner_output_is_cut_off_with_a_note(learner, capsys):
    learner.shout(60_000)
    learner.shout(60_000)
    learner.shout(10)
    out = capsys.readouterr().out
    assert out.count("x") == peer.MAX_OUTPUT_CHARS
    assert out.endswith(peer.OUTPUT_TRUNCATED)


# ---- the guarded end ----------------------------------------------------------------------


class Rows(MutableMapping):
    def __init__(self):
        self.rows = {}

    def __getitem__(self, key):
        return self.rows[key]

    def __setitem__(self, key, value):
        self.rows[key] = value

    def __delitem__(self, key):
        del self.rows[key]

    def __iter__(self):
        return iter(list(self.rows))

    def __len__(self):
        return len(self.rows)


class Writable:
    """Not a store or an iterator, but takes item writes, `next` and `with` all the same."""

    def __init__(self):
        self.touched = []

    def __setitem__(self, key, value):
        self.touched.append(("set", key))

    def __delitem__(self, key):
        self.touched.append(("del", key))

    def __next__(self):
        self.touched.append("next")
        return 1

    def __enter__(self):
        self.touched.append("enter")
        return self

    def __exit__(self, *exc_info):
        self.touched.append("exit")
        return True


def test_learner_code_writes_to_a_store_the_tests_pass_in(learner):
    rows = Rows()
    learner.set_item(rows, "a", "1")
    learner.set_item(rows, "b", "2")
    learner.del_item(rows, "a")
    assert rows.rows == {"b": "2"}
    assert learner.step(iter([1, 2])) == 1


def test_write_operators_on_other_test_objects_are_refused(learner):
    target = Writable()
    with pytest.raises(TypeError, match="cannot assign to items of a Writable"):
        learner.set_item(target, "k", 1)
    with pytest.raises(TypeError, match="cannot delete items of a Writable"):
        learner.del_item(target, "k")
    with pytest.raises(TypeError, match=r"cannot call next\(\) on a Writable"):
        learner.step(target)
    with pytest.raises(TypeError, match="cannot enter a Writable"):
        learner.enter(target)
    assert target.touched == []


class Holder:
    def __init__(self):
        self._hidden = lambda: "secret"

    @property
    def size(self):
        return 3

    @property
    def hidden(self):
        return self._hidden


def test_a_property_hands_out_only_plain_data(learner):
    holder = Holder()
    assert learner.peek(holder, "size") == 3
    with pytest.raises(AttributeError, match="not reachable from your code"):
        learner.peek(holder, "hidden")


def test_a_forged_exception_cannot_set_private_attributes(learner):
    with pytest.raises(ValueError, match="forged") as raised:
        learner.forge_error()
    error = raised.value
    assert type(error) is ValueError, "The child never sets __class__."
    assert error.__cause__ is None
    assert error.note == "kept", "Public attributes still cross."
    frames = error.__dict__["__learner_frames__"]
    assert len(frames) == peer.MAX_FRAMES
    assert "forged.py" not in frames[0]
    assert all(len(frame) <= peer.MAX_FRAME_CHARS for frame in frames)


class Secret:
    def __init__(self):
        self.secret = "the expected answer"


def test_handles_cannot_be_guessed(learner):
    learner.echo(Secret())  # the parent hands out a handle for it
    with pytest.raises(bridge.LearnerProcessError, match="never gave out"):
        learner.guess(Embedder(), -1)
