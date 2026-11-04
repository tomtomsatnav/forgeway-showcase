"""Let a live model answer with your tool loop and two small tools.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from tool_loop import run_with_tools

from forgeway_kit import Tool, default_client

STOCK = {"blue mug": 12, "red mug": 0, "teapot": 3}
PRICES = {"blue mug": 8.5, "red mug": 8.5, "teapot": 24.0}
ITEM = {"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]}
TOOLS = [
    Tool("check_stock", "How many of an item are in stock (blue mug, red mug, teapot).", ITEM),
    Tool("get_price", "The price of one item in pounds.", ITEM),
]
REGISTRY = {"check_stock": lambda item: STOCK.get(item, 0), "get_price": lambda item: PRICES[item]}

question = "I want two teapots and a red mug. Is everything in stock, and what would it cost?"
print(run_with_tools(default_client(), question, TOOLS, REGISTRY, max_steps=6))
