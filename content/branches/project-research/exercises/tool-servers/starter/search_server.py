"""`python -S search_server.py CORPUS`: search and fetch over a JSON list of documents.

CORPUS is a JSON file holding a list of `{"id", "title", "date", "text"}` documents.
"""

import json
import sys
from pathlib import Path

from mcp_server import McpServer


def build(corpus):
    """The search server for `corpus`: tools `search` and `fetch`, and one resource per
    document."""
    return McpServer("search")


if __name__ == "__main__":
    corpus = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    build(corpus).serve(sys.stdin, sys.stdout)
