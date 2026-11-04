"""Run your extract() against a live model, by each route in turn.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from schema_output import Refused, extract

from forgeway_kit import default_client

SCHEMA = {
    "type": "object",
    "properties": {
        "customer": {"type": "string"},
        "order_id": {"type": "integer"},
        "priority": {"type": "string", "enum": ["low", "normal", "urgent"]},
    },
    "required": ["customer", "order_id", "priority"],
    "additionalProperties": False,
}
TEXT = "Hi, Priya Shah here. Order 48213 still has not arrived and I fly out tomorrow!"

for supports in [{"response_format", "tool_choice"}, {"tool_choice"}, set()]:
    try:
        print(
            sorted(supports), extract(default_client(), TEXT, SCHEMA, "ticket", supports=supports)
        )
    except Refused as refused:
        print(sorted(supports), "refused:", refused.text)
    except ValueError as error:
        print(sorted(supports), "invalid:", error)
