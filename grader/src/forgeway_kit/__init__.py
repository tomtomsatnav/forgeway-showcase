"""The learner toolkit: the small, stable API that exercise code is written against.

Learner code imports from here and never from the grader. In the sandbox the active model
client is a deterministic fake; in live mode the same call returns a real, proxied client.
"""

from forgeway_kit.embeddings import Embedder, HashingEmbedder, cosine_similarity
from forgeway_kit.errors import InvalidRequestError, ModelError, RateLimitError, ServerError
from forgeway_kit.llm import (
    Completion,
    FakeModel,
    Message,
    ModelClient,
    Tool,
    ToolCall,
    Usage,
    default_client,
    use_client,
)
from forgeway_kit.tokens import count_tokens, tokenize

__all__ = [
    "Completion",
    "Embedder",
    "FakeModel",
    "HashingEmbedder",
    "InvalidRequestError",
    "Message",
    "ModelClient",
    "ModelError",
    "RateLimitError",
    "ServerError",
    "Tool",
    "ToolCall",
    "Usage",
    "cosine_similarity",
    "count_tokens",
    "default_client",
    "tokenize",
    "use_client",
]
