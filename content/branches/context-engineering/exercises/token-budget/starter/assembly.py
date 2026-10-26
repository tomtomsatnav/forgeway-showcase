# You will need `Message` from forgeway_kit, and `count_tokens` to measure text.
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Section:
    name: str
    text: str
    priority: int
    truncatable: bool = False


def assemble(sections: list[Section], budget: int) -> str:
    """The kept sections' texts, joined with a blank line, in their original order.

    Visit sections from the highest priority down (ties in list order). Keep a whole section if
    it fits; cut a `truncatable` one to the tokens that are left; otherwise skip it.
    """
    raise NotImplementedError("decide what is kept in priority order, output in list order")


def ask(client: ModelClient, sections: list[Section], question: str, budget: int) -> str:
    """Send the assembled sections as the system prompt and `question` as the user message.

    The budget covers both. Raises ValueError if the question alone is over the budget.
    """
    raise NotImplementedError("the question counts towards the budget")
