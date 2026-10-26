"""Grader-side support for the Research agent team project's hidden tests.

Never exported through `forgeway_kit` and never named in a brief. It holds no reference
implementation of what the milestones teach: only `tap`, a stdio relay that records what passes
between a learner's client and a learner's server, so tests can assert on the calls that really
reached a server rather than on what learner code says it sent.
"""

from lattice_grader.project_research_reference.tap import read_log, tap_argv, tool_calls

__all__ = ["read_log", "tap_argv", "tool_calls"]
