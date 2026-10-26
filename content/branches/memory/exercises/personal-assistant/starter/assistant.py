from memstore import MemoryStore

from forgeway_kit import ModelClient, Tool

SYSTEM = (
    "You are a personal assistant with a long-term memory that survives between conversations. "
    "Use `recall` to look up what you know about the user before you answer, and `forget` when "
    "the user asks you to remove something. Do not guess what you have not recalled."
)

TOOLS = [
    Tool(
        "recall",
        "Look up what is remembered about the user: matching facts and the most relevant events.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look up"}},
            "required": ["query"],
        },
    ),
    Tool(
        "forget",
        "Permanently delete every memory that mentions the topic, as the user asked.",
        {
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "Text to forget"}},
            "required": ["topic"],
        },
    ),
]


class Assistant:
    """Classifies each turn into memory, answers with memory tools, then reflects."""

    def __init__(
        self,
        model: ModelClient,
        classifier: ModelClient,
        reflector: ModelClient,
        store: MemoryStore,
        reflect_threshold: int = 25,
        max_steps: int = 6,
    ) -> None:
        self.model = model
        self.classifier = classifier
        self.reflector = reflector
        self.store = store
        self.reflect_threshold = reflect_threshold
        self.max_steps = max_steps

    def chat(self, user_id: str, message: str) -> str:
        """One turn: write policy, tool loop, reflection. Returns the model's final text."""
        raise NotImplementedError

    def delete_user(self, user_id: str) -> bool:
        """Forget everything about the user. True if there was anything."""
        raise NotImplementedError
