"""Out-of-process learner code: hidden tests in the parent, learner code in a child (ADR 0009).

`install(submission)` makes learner modules importable in the parent as proxies of the real
modules, which a child interpreter imports. See `peer` for the protocol and what crosses it, and
`parent` for the child's start-up and failure messages.
"""

from lattice_grader.bridge.parent import (
    DEFAULT_TIMEOUT,
    Bridge,
    LearnerProcessError,
    ProxyModule,
    install,
    installed_roots,
    uninstall,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "Bridge",
    "LearnerProcessError",
    "ProxyModule",
    "install",
    "installed_roots",
    "uninstall",
]
