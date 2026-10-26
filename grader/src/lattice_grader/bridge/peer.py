"""One end of the bridge between the grader (parent) and learner code (child).

The same code runs at both ends. The parent imports it as `lattice_grader.bridge.peer`; the child
is handed this file's source on its command line and runs it as `__main__` (see `run_child`), so
the child never imports `lattice_grader` at all.

**Wire format.** Newline-delimited JSON over a pair of pipes. A request is
``{"q": id, "c": conversation, "op": ..., "t": target, "n": name, "a": [args], "k": {kwargs}}``;
a reply is ``{"r": id, "c": conversation, "v": value}`` or ``{..., "e": error}``; ``{"o": text}``
is learner output. Calls nest: while one end waits for its reply it serves the other end's
requests, so learner code can call back into a test's fake while the test is waiting for learner
code to return.

**Threads.** Each thread's calls, with the calls nested in them, are one *conversation*, named
by the end whose thread began it ("p0" is the parent's main thread, "c3" a learner thread). A
reader thread at each end hands every message to the thread waiting on its conversation, and a
call that begins a new conversation is served by a new thread at the receiving end, so a learner
thread pool's calls reach the tests' fakes at the same time, as they would in one process. The
parent serves at most `MAX_CONVERSATIONS` of the child's threads at once.

**Values.** Plain data crosses by value, rebuilt from exact built-in types (a `str` subclass
arrives as a plain `str`): `None`, `bool`, `int`, `float`, `str`, `bytes`, `list`, exact `tuple`,
`dict`, `set`, `frozenset`, `datetime` values, and frozen dataclasses from `forgeway_kit`
(`Message`, `Completion`, `ToolCall`, ...). Built-in and `forgeway_kit` classes cross by name.
Everything else crosses as a *handle*: the receiver gets a proxy whose attribute reads, calls,
iteration and operators are requests back to the owner. A handle sent back home arrives as the
original object.

**Exceptions.** A builtin or `forgeway_kit` exception is rebuilt as that same class. A learner
exception class arrives in the parent as a mirror class with the learner's name, qualified name
and module, and builtin bases, so ``pytest.raises(StoreError)`` and ``pytest.raises(ValueError)``
both behave as they would in-process. An exception that crosses and comes back arrives as the
original object.

**The guarded end.** The parent's objects are handed to learner code, which is untrusted, so the
parent peer is `guarded`: through a handle the child may call the object, use its read
operators and read its public methods and plain-data attributes, nothing else. Private and
dunder attributes (`__closure__`, `__globals__`, `_responder`), instance attributes and
properties holding functions or objects (`FakeModel.responder`) and attribute writes are
refused, so the test's frames, closures and modules stay out of reach. Item writes apply only to
a store (a mapping or sequence object), `next` only to an iterator, and `with` to nothing.
Handles are random numbers, so the child can name only objects it was given. Every message the
child sends is treated as untrusted input: an exception's private attributes are never set, and
its learner frames arrive in a field of their own, capped.
"""

from __future__ import annotations

import base64
import builtins
import contextlib
import dataclasses
import datetime as _dt
import importlib
import inspect
import json
import operator
import os
import queue
import secrets
import select
import sys
import threading
import time
import traceback
import weakref
from collections.abc import Callable, Iterator, MutableMapping, MutableSequence
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 100
MAX_CONVERSATIONS = 32  # threads of the other end served at once
KIT = "forgeway_kit"
GRADER = "lattice" + "_grader"  # spelt so a grep for the import finds only real imports
READABLE_DUNDERS = frozenset({"__name__", "__qualname__", "__doc__"})
MAX_OUTPUT_CHARS = 100_000  # learner output forwarded in one run; the rest is dropped
OUTPUT_TRUNCATED = (
    f"\n[The grader stopped showing your code's output after {MAX_OUTPUT_CHARS:,} characters.]\n"
)
MAX_FRAMES = 5
MAX_FRAME_CHARS = 500
_SENT_ERRORS_KEPT = 256


class ProtocolError(Exception):
    """The other end sent something that is not a valid bridge message."""


class PeerGone(Exception):  # noqa: N818 - a state, not an error the caller made
    """The other end closed its pipe."""


class PeerTimeout(PeerGone):
    """The other end said nothing within the allowed time."""


class Channel:
    """Newline-delimited JSON messages over a read and a write file descriptor."""

    def __init__(self, read_fd: int, write_fd: int) -> None:
        self._read_fd = read_fd
        self._write_fd = write_fd
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        data = json.dumps(message, separators=(",", ":")).encode() + b"\n"
        view = memoryview(data)
        with self._lock:
            try:
                while view:
                    view = view[os.write(self._write_fd, view) :]
            except (BrokenPipeError, OSError) as exc:
                raise PeerGone("the other end closed its pipe") from exc

    def recv(self, timeout: float | None) -> dict[str, Any]:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            end = self._buffer.find(b"\n")
            if end >= 0:
                line = bytes(self._buffer[:end])
                del self._buffer[: end + 1]
                try:
                    message = json.loads(line)
                except (ValueError, RecursionError) as exc:
                    raise ProtocolError("a message that is not JSON") from exc
                if not isinstance(message, dict):
                    raise ProtocolError("a message that is not a JSON object")
                return message
            if len(self._buffer) > MAX_MESSAGE_BYTES:
                raise ProtocolError("a message larger than the limit")
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PeerTimeout("no message in time")
                ready, _, _ = select.select([self._read_fd], [], [], remaining)
                if not ready:
                    continue
            try:
                chunk = os.read(self._read_fd, 65536)
            except OSError as exc:
                raise PeerGone("the other end closed its pipe") from exc
            if not chunk:
                raise PeerGone("the other end closed its pipe")
            self._buffer += chunk


def _kit_class(path: object) -> type:
    """A class from `forgeway_kit` named "module:qualname"; nothing else is ever looked up."""
    if not isinstance(path, str) or ":" not in path:
        raise ProtocolError("a malformed class name")
    module_name, _, qualname = path.partition(":")
    if module_name != KIT and not module_name.startswith(KIT + "."):
        raise ProtocolError("a class from outside forgeway_kit")
    found: Any = importlib.import_module(module_name)
    for part in qualname.split("."):
        if part.startswith("_"):
            raise ProtocolError("a private name")
        found = getattr(found, part)
    if not isinstance(found, type):
        raise ProtocolError("a name that is not a class")
    return found


def _kit_path(cls: type) -> str | None:
    """The "module:qualname" of a public `forgeway_kit` class, or None."""
    module = getattr(cls, "__module__", "")
    if not isinstance(module, str) or not (module == KIT or module.startswith(KIT + ".")):
        return None
    path = f"{module}:{cls.__qualname__}"
    try:
        return path if _kit_class(path) is cls else None
    except (ProtocolError, ImportError, AttributeError):
        return None


def _builtin_name(cls: type) -> str | None:
    return cls.__name__ if getattr(builtins, cls.__name__, None) is cls else None


def _is_kit_value(value: object) -> bool:
    """A frozen `forgeway_kit` dataclass instance: plain data, safe to rebuild at the other end."""
    cls = type(value)
    params = getattr(cls, "__dataclass_params__", None)
    return params is not None and params.frozen and _kit_path(cls) is not None


def _is_plain(value: object, depth: int = 0) -> bool:
    """True when `value` would cross entirely by value (no handles)."""
    if depth > MAX_DEPTH:
        return False
    if value is None or isinstance(value, bool | int | float | str | bytes):
        return True
    if type(value) is tuple or isinstance(value, list | set | frozenset):
        return all(_is_plain(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            _is_plain(k, depth + 1) and _is_plain(v, depth + 1) for k, v in dict.items(value)
        )
    if isinstance(value, _dt.date | _dt.time | _dt.timedelta):
        return True
    if _is_kit_value(value):
        return all(
            _is_plain(getattr(value, f.name), depth + 1)
            for f in dataclasses.fields(value)  # type: ignore[arg-type]
        )
    return False


def _mirror_str(self: BaseException) -> str:
    message = self.__dict__.get("_bridge_message")
    return message if isinstance(message, str) else BaseException.__str__(self)


_OPS: dict[str, Callable[..., Any]] = {
    "repr": repr,
    "str": str,
    "len": len,
    "iter": iter,
    "next": next,
    "bool": bool,
    "hash": hash,
    "eq": operator.eq,
    "ne": operator.ne,
    "lt": operator.lt,
    "le": operator.le,
    "gt": operator.gt,
    "ge": operator.ge,
    "getitem": operator.getitem,
    "setitem": operator.setitem,
    "delitem": operator.delitem,
    "contains": lambda obj, item: item in obj,
    "enter": lambda obj: obj.__enter__(),
    "exit": lambda obj, *args: obj.__exit__(*args),
    "dir": lambda obj: sorted(dir(obj)),
}

# Operators that change an object or step it on. On the guarded end they apply only to the kinds
# of object a test hands over for that purpose: a store (a mapping or sequence object, as a dict
# or list would arrive as a copy) for item writes, an iterator for `next`. No test object is a
# context manager for learner code.
_GUARDED_OPS: dict[str, tuple[tuple[type, ...], str]] = {
    "setitem": ((MutableMapping, MutableSequence), "assign to items of"),
    "delitem": ((MutableMapping, MutableSequence), "delete items of"),
    "next": ((Iterator,), "call next() on"),
    "enter": ((), "enter"),
    "exit": ((), "exit"),
}


class Peer:
    """One end of the bridge: exports local objects as handles and proxies remote ones.

    `guarded` restricts what the other end may do with this end's objects (see the module
    docstring). `frames_root` is set in the child: exceptions it sends carry the frames of
    learner files under that directory, for the learner-facing message. `timeout` bounds how long
    this end waits for any one message (the parent's guard against learner code that never
    returns); `on_broken` turns a dead or misbehaving channel into the exception callers see.
    """

    def __init__(
        self,
        channel: Channel,
        *,
        guarded: bool,
        frames_root: str | None = None,
        timeout: float | None = None,
        on_output: Callable[[str], None] | None = None,
        on_broken: Callable[[Exception], BaseException] | None = None,
        side: str = "p",
    ) -> None:
        self._channel = channel
        self._guarded = guarded
        self._frames_root = Path(frames_root).resolve() if frames_root else None
        self._timeout = timeout
        self._on_output = on_output
        self._on_broken = on_broken
        self._exports: dict[int, Any] = {}
        self._export_ids: dict[int, int] = {}
        self._next_request = 1
        self._proxies: weakref.WeakValueDictionary[int, Any] = weakref.WeakValueDictionary()
        self._mirrors: dict[Any, type] = {}  # remote class handle or name key -> local class
        self._mirror_handles: dict[type, int] = {}  # local mirror of a remote class -> its handle
        self._sent_errors: dict[int, BaseException] = {}
        self.broken: BaseException | None = None
        self._unreported: BaseException | None = None  # a failure only a serving thread saw
        self._output_left = MAX_OUTPUT_CHARS
        # Conversations: each thread's calls, and the calls nested inside them, are one
        # conversation, named by the end whose thread started it ("p" parent, "c" child).
        self._side = side
        self._lock = threading.RLock()
        self._local = threading.local()
        self._next_conversation = 1
        self._queues: dict[str, queue.SimpleQueue[Any]] = {}
        self._claims: dict[str, int] = {}  # conversation -> local threads waiting on it
        self._serving = 0  # threads serving the other end's conversations right now
        self._working = 0  # threads running this end's code for the other end right now
        self._failure: Exception | None = None
        self._last_message = time.monotonic()
        if side == "c":  # the child's main thread serves the parent's main thread
            self._claims["p0"] = 1
            self._queues["p0"] = queue.SimpleQueue()
        self._reader = threading.Thread(target=self._read, name="bridge-reader", daemon=True)
        self._reader.start()

    # ---- requests -------------------------------------------------------------------------

    def request(
        self,
        op: str,
        target: Any = None,
        *,
        name: str | None = None,
        args: tuple[Any, ...] | list[Any] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if self.broken is not None:
            raise self._break(PeerGone("the channel broke earlier"))
        conversation = self._conversation()
        with self._lock:
            request_id = self._next_request
            self._next_request += 1
        message: dict[str, Any] = {"q": request_id, "c": conversation, "op": op}
        if target is not None:
            message["t"] = self.encode(target)
        if name is not None:
            message["n"] = name
        message["a"] = [self.encode(a) for a in args]
        if kwargs:
            message["k"] = {str(k): self.encode(v) for k, v in kwargs.items()}
        inbox = self._claim(conversation)
        try:
            self._guard_channel(lambda: self._channel.send(message))
            while True:
                reply = self._next(inbox)
                if "r" in reply:
                    if reply["r"] != request_id:
                        raise self._break(
                            ProtocolError("a reply to a request that was not waiting")
                        )
                    if "e" in reply:
                        raise self._decode_error(reply["e"])
                    return self._decode_safely(reply.get("v"))
                self._send_reply(self._serve_working(reply))
        finally:
            self._unclaim(conversation)

    def serve_forever(self) -> None:
        """Answer the parent's main thread until it hangs up (the child's main loop). Calls
        from the parent's other threads are served by threads of their own."""
        self._local.conversation = "p0"
        inbox = self._queues["p0"]  # claimed for good when this peer was made
        while True:
            message = self._next(inbox)
            if "q" not in message:
                raise ProtocolError("expected a request")
            self._send_reply(self._serve_working(message))

    def _conversation(self) -> str:
        conversation = getattr(self._local, "conversation", None)
        if conversation is None:
            if threading.current_thread() is threading.main_thread():
                conversation = f"{self._side}0"
            else:
                with self._lock:
                    conversation = f"{self._side}{self._next_conversation}"
                    self._next_conversation += 1
            self._local.conversation = conversation
        return str(conversation)

    def _claim(self, conversation: str) -> queue.SimpleQueue[Any]:
        with self._lock:
            self._claims[conversation] = self._claims.get(conversation, 0) + 1
            inbox = self._queues.setdefault(conversation, queue.SimpleQueue())
            if self._failure is not None:
                inbox.put(None)
            return inbox

    def _unclaim(self, conversation: str) -> None:
        with self._lock:
            left = self._claims.get(conversation, 0) - 1
            if left > 0:
                self._claims[conversation] = left
            else:
                self._claims.pop(conversation, None)

    def _set_working(self, working: bool) -> bool:
        """Mark this thread as running code for the other end, or not; returns what it was."""
        was = bool(getattr(self._local, "working", False))
        if working != was:
            self._local.working = working
            with self._lock:
                self._working += 1 if working else -1
        return was

    def _serve_working(self, message: dict[str, Any]) -> dict[str, Any]:
        was = self._set_working(True)
        try:
            return self._serve(message)
        finally:
            self._set_working(was)

    def _next(self, inbox: queue.SimpleQueue[Any]) -> dict[str, Any]:
        """The next message of this thread's conversation; silence for `timeout` breaks it.

        Silence means the whole channel: while the other end sends a request or a reply, or a
        thread of this end runs code for it, a conversation that waits on the rest is not stuck.
        A thread that is itself waiting on the other end runs nothing, so two ends waiting on
        each other (a reflected `__eq__` that hangs in learner code) still time out. Learner
        output is not activity: printing in a loop does not hold the limit open."""
        was = self._set_working(False)
        try:
            while True:
                try:
                    message = inbox.get(timeout=self._timeout)
                except queue.Empty:
                    with self._lock:
                        idle = time.monotonic() - self._last_message
                        busy = self._working > 0
                    if busy or (self._timeout is not None and idle < self._timeout):
                        continue
                    raise self._break(PeerTimeout("no message in time")) from None
                if message is None:
                    raise self._break(self._failure or PeerGone("the other end closed its pipe"))
                return message  # type: ignore[no-any-return]
        finally:
            self._set_working(was)

    def _read(self) -> None:
        """The reader thread: hands each message to the thread whose conversation it is."""
        try:
            while True:
                message = self._channel.recv(None)
                if "o" in message and "q" not in message and "r" not in message:
                    self._forward_output(message["o"])
                    continue
                with self._lock:
                    self._last_message = time.monotonic()
                if "q" not in message and "r" not in message:
                    raise ProtocolError("a message of no known kind")
                self._route(message)
        except (ProtocolError, PeerGone) as exc:
            with self._lock:
                self._failure = exc
                for inbox in self._queues.values():
                    inbox.put(None)

    def _forward_output(self, text: object) -> None:
        """Pass learner output on, up to `MAX_OUTPUT_CHARS` in all, then a note that it stopped."""
        if not isinstance(text, str) or self._on_output is None or self._output_left <= 0:
            return
        if len(text) > self._output_left:
            text = text[: self._output_left] + OUTPUT_TRUNCATED
        self._output_left -= len(text)
        self._on_output(text)

    def _route(self, message: dict[str, Any]) -> None:
        conversation = message.get("c")
        if not isinstance(conversation, str) or len(conversation) > 32:
            raise ProtocolError("a message without a conversation")
        with self._lock:
            if self._claims.get(conversation):
                self._queues[conversation].put(message)
                return
            remote = "p" if self._side == "c" else "c"
            if "q" not in message or not conversation.startswith(remote):
                raise ProtocolError("a message for a conversation that is not waiting")
            if self._serving >= MAX_CONVERSATIONS:
                raise ProtocolError("more threads at once than the limit")
            self._serving += 1
            self._claims[conversation] = 1
            self._queues.setdefault(conversation, queue.SimpleQueue())
        threading.Thread(
            target=self._serve_conversation, args=(conversation, message), daemon=True
        ).start()

    def _serve_conversation(self, conversation: str, message: dict[str, Any]) -> None:
        """A thread of this end for one call from a thread of the other end."""
        self._local.conversation = conversation
        try:
            reply = self._serve_working(message)
        except BaseException:  # the channel broke: the threads waiting on it report it
            reply = None
        finally:
            with self._lock:
                self._serving -= 1
            self._unclaim(conversation)
        if reply is not None:  # sent once unclaimed: the next call may then start a new thread
            with contextlib.suppress(BaseException):  # a broken channel: the waiter reports it
                self._send_reply(reply)

    def wait_closed(self, timeout: float) -> None:
        """Wait for the reader thread to see the other end hang up."""
        self._reader.join(timeout)

    def _send_reply(self, reply: dict[str, Any]) -> None:
        self._guard_channel(lambda: self._channel.send(reply))

    def _guard_channel(self, action: Callable[[], Any]) -> Any:
        try:
            return action()
        except (ProtocolError, PeerGone) as exc:
            raise self._break(exc) from None

    def _break(self, exc: Exception) -> BaseException:
        """The failure to raise for a broken channel. The first thread of this end's own
        conversations to see it gets what happened, even when a thread serving the other end
        noticed first (that thread has no one to tell); every later call gets `broken`."""
        with self._lock:
            if self.broken is not None:
                if self._unreported is not None and not self._is_serving_thread():
                    failure, self._unreported = self._unreported, None
                    return failure
                return self.broken
            failure = self._on_broken(exc) if self._on_broken else exc
            if self.broken is None:
                self.broken = failure
            if self._is_serving_thread():
                self._unreported = failure
            return failure

    def _is_serving_thread(self) -> bool:
        conversation = getattr(self._local, "conversation", None)
        return isinstance(conversation, str) and not conversation.startswith(self._side)

    def _decode_safely(self, data: Any) -> Any:
        try:
            return self.decode(data)
        except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
            raise self._break(ProtocolError(f"an unreadable value ({exc})")) from None

    # ---- serving --------------------------------------------------------------------------

    def _serve(self, message: dict[str, Any]) -> dict[str, Any]:
        """Run one request from the other end and return the reply to send."""
        request_id = message.get("q")
        conversation = message.get("c")
        try:
            op = message.get("op")
            raw_target = message.get("t")
            is_ours = isinstance(raw_target, dict) and "$back" in raw_target
            if raw_target is not None and not is_ours:
                raise ProtocolError("a request whose target is not one of this end's objects")
            target = None if raw_target is None else self.decode(raw_target)
            args = [self.decode(a) for a in message.get("a", [])]
            kwargs = {str(k): self.decode(v) for k, v in dict(message.get("k", {})).items()}
            name = message.get("n")
            if name is not None and not isinstance(name, str):
                raise ProtocolError("a non-string name")
        except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
            raise self._break(ProtocolError(f"an unreadable request ({exc})")) from None
        try:
            result = self._dispatch(str(op), target, name, args, kwargs)
            reply: dict[str, Any] = {"r": request_id, "c": conversation, "v": self.encode(result)}
        except (PeerGone, ProtocolError):
            raise
        except BaseException as exc:  # every failure, learner or grader, goes back as a value
            if self.broken is not None:
                raise  # the channel is gone: there is no one to reply to
            reply = {"r": request_id, "c": conversation, "e": self._encode_error(exc)}
        return reply

    def _dispatch(
        self, op: str, target: Any, name: str | None, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:
        if op == "call":
            if not callable(target):
                raise TypeError(f"'{type(target).__name__}' object is not callable")
            return target(*args, **kwargs)
        if op == "getattr" and name is not None:
            return self._getattr(target, name)
        if self._guarded and op in _GUARDED_OPS:
            kinds, verb = _GUARDED_OPS[op]
            if not isinstance(target, kinds):
                kind = type(target).__name__
                raise TypeError(f"your code cannot {verb} a {kind} the tests passed in")
        if op in ("setattr", "delattr") and name is not None:
            if self._guarded:
                raise AttributeError(
                    f"your code cannot change attribute {name!r} of a "
                    f"{type(target).__name__} the tests passed in"
                )
            if op == "setattr":
                setattr(target, name, args[0])
            else:
                delattr(target, name)
            return None
        if op == "import" and name is not None and not self._guarded:
            if args:
                self._forget(args[0])
            return importlib.import_module(name)
        if op in _OPS and target is not None:
            return _OPS[op](target, *args)
        raise ProtocolError(f"an unknown operation {op!r}")

    def _forget(self, names: list[str]) -> None:
        """Drop learner modules, so the next import runs them afresh: the ones named, or
        every module loaded from the submission for "*"."""
        for loaded in list(sys.modules):
            if "*" in names:
                file = getattr(sys.modules[loaded], "__file__", None)
                root = self._frames_root
                if not file or root is None or not Path(file).resolve().is_relative_to(root):
                    continue
            elif loaded.partition(".")[0] not in names:
                continue
            del sys.modules[loaded]
        importlib.invalidate_caches()

    def _getattr(self, obj: Any, name: str) -> Any:
        if not self._guarded:
            return getattr(obj, name)
        denied = AttributeError(
            f"{type(obj).__name__}.{name} is not reachable from your code: objects the tests "
            "pass in expose only their public methods and plain data"
        )
        if name.startswith("_") and name not in READABLE_DUNDERS:
            raise denied
        value = getattr(obj, name)
        if name in READABLE_DUNDERS:
            return value if isinstance(value, str) else None
        if inspect.ismethod(value) and value.__self__ is obj:
            return value
        if _is_plain(value):
            return value  # a property's value too: a property cannot hand out an object
        raise denied

    # ---- encoding -------------------------------------------------------------------------

    def encode(self, value: Any, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise ValueError("a value nested too deeply to send between processes")
        if value is None or value is True or value is False:
            return value
        if isinstance(value, _Proxy) and object.__getattribute__(value, "_bridge_peer") is self:
            return {"$back": object.__getattribute__(value, "_bridge_id")}
        if isinstance(value, type) and value in self._mirror_handles:
            return {"$back": self._mirror_handles[value]}
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, int):
            return int.__int__(value)
        if isinstance(value, float):
            return float.__float__(value)
        if isinstance(value, str):
            return str.__str__(value)
        if isinstance(value, list):
            return [self.encode(v, depth + 1) for v in list.__iter__(value)]
        if type(value) is tuple:
            return {"$tuple": [self.encode(v, depth + 1) for v in value]}
        if isinstance(value, dict):
            return {
                "$dict": [
                    [self.encode(k, depth + 1), self.encode(v, depth + 1)]
                    for k, v in dict.items(value)
                ]
            }
        if isinstance(value, set | frozenset):
            tag = "$frozenset" if isinstance(value, frozenset) else "$set"
            return {tag: [self.encode(v, depth + 1) for v in value]}
        if isinstance(value, bytes | bytearray):
            return {"$bytes": base64.b64encode(bytes(value)).decode()}
        if type(value) is _dt.datetime:
            return {"$datetime": value.isoformat()}
        if type(value) is _dt.date:
            return {"$date": value.isoformat()}
        if type(value) is _dt.timedelta:
            return {"$timedelta": [value.days, value.seconds, value.microseconds]}
        if isinstance(value, BaseException):
            return {"$exc": self._encode_error(value)}
        if isinstance(value, type):
            builtin = _builtin_name(value)
            if builtin:
                return {"$builtin": builtin}
            kit = _kit_path(value)
            if kit:
                return {"$kit": kit}
            if self._guarded and issubclass(value, BaseException):
                return {"$named": self._class_info(value, depth)}
        if _is_kit_value(value):
            return {
                "$kitdc": _kit_path(type(value)),
                "f": {
                    f.name: self.encode(getattr(value, f.name), depth + 1)
                    for f in dataclasses.fields(value)
                },
            }
        return {"$ref": self._export(value), "c": self._describe(value, depth)}

    def _export(self, value: Any) -> int:
        """The handle for `value`: a random number, so the other end can name only the objects
        it was given, never guess one given elsewhere or one prepared for a send that failed."""
        with self._lock:
            handle = self._export_ids.get(id(value))
            if handle is None or self._exports.get(handle) is not value:
                handle = self._new_id(self._exports)
                self._exports[handle] = value
                self._export_ids[id(value)] = handle
            return handle

    @staticmethod
    def _new_id(taken: dict[int, Any]) -> int:
        while True:
            new = secrets.randbits(53)  # an exact number in any JSON reader
            if new and new not in taken:
                return new

    def _class_info(self, cls: type, depth: int) -> dict[str, Any]:
        info: dict[str, Any] = {"n": cls.__name__, "q": cls.__qualname__, "m": cls.__module__}
        if issubclass(cls, BaseException):
            info["b"] = [self.encode(base, depth + 1) for base in cls.__bases__]
        return info

    def _describe(self, value: Any, depth: int) -> dict[str, Any]:
        if isinstance(value, type):
            info = self._class_info(value, depth)
            info["k"] = "excclass" if issubclass(value, BaseException) else "class"
            info["ic"] = any("__call__" in vars(k) for k in value.__mro__ if k is not object)
            return info
        cls = type(value)
        info = {"k": "obj", "n": cls.__name__, "q": cls.__qualname__, "m": cls.__module__}
        info["call"] = callable(value)
        if not self._guarded:  # the parent may see (and isinstance-check) learner classes
            encoded = self.encode(cls, depth + 1)
            if isinstance(encoded, dict) and "$ref" in encoded:
                info["cls"] = encoded
        return info

    def _encode_error(self, exc: BaseException) -> dict[str, Any]:
        frames = self._learner_frames(exc)
        origin = exc.__dict__.get("_bridge_origin") if hasattr(exc, "__dict__") else None
        if isinstance(origin, int):
            return {"back": origin, "frames": frames}
        with self._lock:
            error_id = self._new_id(self._sent_errors)
            self._sent_errors[error_id] = exc
            while len(self._sent_errors) > _SENT_ERRORS_KEPT:
                self._sent_errors.pop(next(iter(self._sent_errors)))
        try:
            args = [self.encode(a) for a in exc.args]
        except Exception:
            args = [self._safe_str(exc)]
        attrs = {}
        for key, item in getattr(exc, "__dict__", {}).items():
            if not key.startswith("_"):
                try:
                    attrs[key] = self.encode(item)
                except Exception:  # noqa: S112 - an attribute that cannot cross is left behind
                    continue
        try:
            kind = self.encode(type(exc))
        except Exception:
            kind = {"$builtin": "Exception"}
        return {
            "type": kind,
            "args": args,
            "msg": self._safe_str(exc),
            "attrs": attrs,
            "id": error_id,
            "frames": frames,
        }

    @staticmethod
    def _safe_str(exc: BaseException) -> str:
        try:
            return str(exc)
        except Exception:
            return type(exc).__name__

    def _learner_frames(self, exc: BaseException) -> list[str]:
        if self._frames_root is None:
            return []
        frames = []
        for frame in traceback.extract_tb(exc.__traceback__):
            try:
                relative = Path(frame.filename).resolve().relative_to(self._frames_root)
            except ValueError:
                continue
            frames.append(f"  {relative.as_posix()}, line {frame.lineno}, in {frame.name}")
        return frames[-5:]

    # ---- decoding -------------------------------------------------------------------------

    def decode(self, data: Any) -> Any:
        if data is None or isinstance(data, bool | int | float | str):
            return data
        if isinstance(data, list):
            return [self.decode(d) for d in data]
        if not isinstance(data, dict) or len(data) not in (1, 2):
            raise ProtocolError("a malformed value")
        if "$tuple" in data:
            return tuple(self.decode(d) for d in data["$tuple"])
        if "$dict" in data:
            return {self.decode(k): self.decode(v) for k, v in data["$dict"]}
        if "$set" in data:
            return {self.decode(d) for d in data["$set"]}
        if "$frozenset" in data:
            return frozenset(self.decode(d) for d in data["$frozenset"])
        if "$bytes" in data:
            return base64.b64decode(data["$bytes"])
        if "$datetime" in data:
            return _dt.datetime.fromisoformat(data["$datetime"])
        if "$date" in data:
            return _dt.date.fromisoformat(data["$date"])
        if "$timedelta" in data:
            days, seconds, micro = data["$timedelta"]
            return _dt.timedelta(days=days, seconds=seconds, microseconds=micro)
        if "$back" in data:
            handle = data["$back"]
            if handle not in self._exports:
                raise ProtocolError("a handle this end never gave out")
            return self._exports[handle]
        if "$ref" in data:
            return self._proxy(data["$ref"], data["c"])
        if "$builtin" in data:
            found = getattr(builtins, str(data["$builtin"]), None)
            if not isinstance(found, type):
                raise ProtocolError("a builtin name that is not a class")
            return found
        if "$kit" in data:
            return _kit_class(data["$kit"])
        if "$kitdc" in data:
            cls = _kit_class(data["$kitdc"])
            params = getattr(cls, "__dataclass_params__", None)
            if params is None or not params.frozen:
                raise ProtocolError("a forgeway_kit class that is not a frozen dataclass")
            return cls(**{str(k): self.decode(v) for k, v in dict(data["f"]).items()})
        if "$named" in data:
            with self._lock:
                return self._mirror_exception(("named", data["$named"]["m"], data["$named"]["q"]),
                                              data["$named"])  # fmt: skip
        if "$exc" in data:
            return self._decode_error(data["$exc"])
        raise ProtocolError("a value of no known kind")

    def _proxy(self, handle: Any, info: dict[str, Any]) -> Any:
        if not isinstance(handle, int) or not isinstance(info, dict):
            raise ProtocolError("a malformed handle")
        with self._lock:  # one proxy, and one mirror class, per handle across threads
            return self._make_proxy(handle, info)

    def _make_proxy(self, handle: int, info: dict[str, Any]) -> Any:
        kind = info.get("k")
        if kind == "excclass":
            return self._mirror_exception(handle, info)
        if kind == "class":
            return self._mirror_class(handle, info)
        existing = self._proxies.get(handle)
        if existing is not None:
            return existing
        cls: type | None = None
        if "cls" in info:
            candidate = self.decode(info["cls"])
            if isinstance(candidate, type) and issubclass(candidate, _Proxy):
                cls = candidate
        if cls is None or (info.get("call") and not issubclass(cls, _CallableProxy)):
            cls = self._generic_class(info, callable_=bool(info.get("call")))
        proxy: Any = object.__new__(cls)
        object.__setattr__(proxy, "_bridge_peer", self)
        object.__setattr__(proxy, "_bridge_id", handle)
        self._proxies[handle] = proxy
        return proxy

    def _names(self, info: dict[str, Any]) -> dict[str, Any]:
        name, qualname, module = info.get("n"), info.get("q"), info.get("m")
        if not all(isinstance(x, str) for x in (name, qualname, module)):
            raise ProtocolError("a class without a name")
        return {"__module__": module, "__qualname__": qualname, "_bridge_name": name}

    def _generic_class(self, info: dict[str, Any], *, callable_: bool) -> type:
        names = self._names(info)
        key = ("generic", names["__module__"], names["__qualname__"], callable_)
        if key not in self._mirrors:
            base = _CallableProxy if callable_ else _Proxy
            self._mirrors[key] = type(names.pop("_bridge_name"), (base,), names)
        return self._mirrors[key]

    def _mirror_class(self, handle: int, info: dict[str, Any]) -> type:
        if handle not in self._mirrors:
            names = self._names(info)
            base = _CallableProxy if info.get("ic") else _Proxy
            cls = _RemoteClass(names.pop("_bridge_name"), (base,), names)
            type.__setattr__(cls, "_bridge_peer", self)
            type.__setattr__(cls, "_bridge_id", handle)
            self._mirrors[handle] = cls
            self._mirror_handles[cls] = handle
        return self._mirrors[handle]

    def _mirror_exception(self, key: Any, info: dict[str, Any]) -> type:
        if key not in self._mirrors:
            names = self._names(info)
            bases = tuple(
                b
                for b in (self.decode(raw) for raw in info.get("b", []))
                if isinstance(b, type) and issubclass(b, BaseException)
            ) or (Exception,)
            if self._guarded and not any(issubclass(b, Exception) for b in bases):
                # Learner code never raises a KeyboardInterrupt or SystemExit look-alike in the
                # parent. A test's own BaseException (a simulated crash) stays one in the
                # child, so learner code's `except Exception` cannot hide it.
                bases = (Exception,)
            names["__str__"] = _mirror_str
            try:
                cls = type(names.pop("_bridge_name"), bases, names)
            except TypeError:
                cls = type(str(info.get("n")), (Exception,), names)
            self._mirrors[key] = cls
            if isinstance(key, int):
                self._mirror_handles[cls] = key
        return self._mirrors[key]

    def _decode_error(self, data: Any) -> BaseException:
        try:
            return self._build_error(data)
        except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._break(ProtocolError(f"an unreadable error ({exc})"))

    def _build_error(self, data: dict[str, Any]) -> BaseException:
        raw_frames = data.get("frames", [])
        if not isinstance(raw_frames, list):
            raise ProtocolError("frames that are not a list")
        frames = [f[:MAX_FRAME_CHARS] for f in raw_frames[-MAX_FRAMES:] if isinstance(f, str)]
        if "back" in data:
            original = self._sent_errors.get(data["back"])
            if original is None:
                raise ProtocolError("an error this end never sent")
            if frames:
                original.__dict__["__learner_frames__"] = frames
            return original
        cls = self.decode(data["type"])
        if not isinstance(cls, type) or not issubclass(cls, BaseException):
            raise ProtocolError("an error whose type is not an exception class")
        args = [self.decode(a) for a in data.get("args", [])]
        message = str(data.get("msg", ""))
        if self._guarded and not issubclass(cls, Exception | SystemExit):
            cls, args = RuntimeError, [f"{cls.__name__}: {message}"]
        exc: BaseException
        try:
            exc = cls(*args)
        except Exception:
            exc = cls.__new__(cls)
            exc.args = tuple(args)
        for key, value in dict(data.get("attrs", {})).items():
            if not isinstance(key, str) or key.startswith("_"):
                continue  # public attributes only: never `__class__`, `__cause__` or frames
            try:
                setattr(exc, key, self.decode(value))
            except (ProtocolError, AttributeError, TypeError):
                continue
        if cls.__str__ is _mirror_str:
            exc.__dict__["_bridge_message"] = message
        if isinstance(data.get("id"), int):
            exc.__dict__["_bridge_origin"] = data["id"]
        if frames:
            exc.__dict__["__learner_frames__"] = frames
        return exc


# ---- proxies ------------------------------------------------------------------------------


def _remote(proxy: Any, op: str, *args: Any, name: str | None = None) -> Any:
    peer: Peer = object.__getattribute__(proxy, "_bridge_peer")
    return peer.request(op, proxy, name=name, args=args)


class _Proxy:
    """An object that lives at the other end of the bridge."""

    _bridge_peer: Peer
    _bridge_id: int

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_bridge_"):
            raise AttributeError(name)
        return _remote(self, "getattr", name=name)

    def __setattr__(self, name: str, value: Any) -> None:
        _remote(self, "setattr", value, name=name)

    def __delattr__(self, name: str) -> None:
        _remote(self, "delattr", name=name)

    def __repr__(self) -> str:
        peer: Peer = object.__getattribute__(self, "_bridge_peer")
        if peer.broken is not None:
            return f"<{type(self).__qualname__} in a process that has stopped>"
        return str(_remote(self, "repr"))

    def __str__(self) -> str:
        return str(_remote(self, "str"))

    def __len__(self) -> int:
        return int(_remote(self, "len"))

    def __iter__(self) -> Any:
        return _remote(self, "iter")

    def __next__(self) -> Any:
        return _remote(self, "next")

    def __bool__(self) -> bool:
        return bool(_remote(self, "bool"))

    def __hash__(self) -> int:
        return int(_remote(self, "hash"))

    def __eq__(self, other: object) -> bool:
        return bool(_remote(self, "eq", other))

    def __ne__(self, other: object) -> bool:
        return bool(_remote(self, "ne", other))

    def __lt__(self, other: object) -> bool:
        return bool(_remote(self, "lt", other))

    def __le__(self, other: object) -> bool:
        return bool(_remote(self, "le", other))

    def __gt__(self, other: object) -> bool:
        return bool(_remote(self, "gt", other))

    def __ge__(self, other: object) -> bool:
        return bool(_remote(self, "ge", other))

    def __getitem__(self, key: Any) -> Any:
        return _remote(self, "getitem", key)

    def __setitem__(self, key: Any, value: Any) -> None:
        _remote(self, "setitem", key, value)

    def __delitem__(self, key: Any) -> None:
        _remote(self, "delitem", key)

    def __contains__(self, item: Any) -> bool:
        return bool(_remote(self, "contains", item))

    def __enter__(self) -> Any:
        return _remote(self, "enter")

    def __exit__(self, *exc_info: Any) -> Any:
        return _remote(self, "exit", *exc_info)

    def __dir__(self) -> list[str]:
        return list(_remote(self, "dir"))


class _CallableProxy(_Proxy):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        peer: Peer = object.__getattribute__(self, "_bridge_peer")
        return peer.request("call", self, args=args, kwargs=kwargs)


class _RemoteClass(type):
    """The metaclass of a mirrored learner class: calling it constructs at the other end."""

    _bridge_peer: Peer
    _bridge_id: int

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if "_bridge_id" not in vars(cls):
            raise TypeError(
                f"{cls.__qualname__} subclasses a class from learner code, which runs in "
                "another process: the bridge cannot construct it"
            )
        return cls._bridge_peer.request("call", cls, args=args, kwargs=kwargs)

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("_bridge_") or "_bridge_id" not in vars(cls):
            raise AttributeError(name)
        return cls._bridge_peer.request("getattr", cls, name=name)


# ---- the child's side ---------------------------------------------------------------------


class _Output:
    """`sys.stdout` in the child: text goes to the parent, which prints it where pytest sees it."""

    encoding = "utf-8"

    def __init__(self, channel: Channel) -> None:
        self._channel = channel

    def write(self, text: str) -> int:
        if text:
            self._channel.send({"o": str(text)})
        return len(text)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


class _RefuseGrader:
    """No code in the child has any business with the grader: nothing there is a test."""

    message = f"{GRADER} is the grader's own code; your solution must not import it."

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        if fullname == GRADER or fullname.startswith(GRADER + "."):
            raise ImportError(self.message, name=fullname)


def run_child(config: dict[str, Any]) -> None:
    """The child's main loop: called with this file's source as `python -c`."""
    read_fd, write_fd = os.dup(0), os.dup(1)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.dup2(2, 1)  # anything written to fd 1 directly goes to stderr, never into the pipe
    os.close(null)
    for name in [m for m in sys.modules if m == GRADER or m.startswith(GRADER + ".")]:
        del sys.modules[name]  # the image's .pth loads the import guard; nothing else stays
    sys.meta_path.insert(0, _RefuseGrader())
    channel = Channel(read_fd, write_fd)
    sys.stdout = _Output(channel)  # type: ignore[assignment,unused-ignore]
    root = str(config["root"])
    sys.path.insert(0, root)
    peer = Peer(channel, guarded=False, frames_root=root, side="c")
    try:
        peer.serve_forever()
    except PeerGone:
        pass
    finally:
        sys.stdout.flush()
    os._exit(0)
