"""`python -S notes_server.py NOTES_FILE`: notes that survive a restart.

NOTES_FILE need not exist yet. What you keep in it, and how, is up to you.
"""

import sys

from mcp_server import McpServer


def build(path):
    """The notes server, keeping its notes in the file at `path`: tools `add_note`,
    `list_notes` and `delete_note`, and one resource per note."""
    return McpServer("notes")


if __name__ == "__main__":
    build(sys.argv[1]).serve(sys.stdin, sys.stdout)
