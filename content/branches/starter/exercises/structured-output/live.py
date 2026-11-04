"""Extract a person from free text with a live model through your extract_person().

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from extract import extract_person

from forgeway_kit import default_client

client = default_client()
for text in [
    "Maria Gonzalez, 34, joined the Lisbon office last spring as a data engineer.",
    "Our oldest volunteer is Ken Tanaka; he turned seventy-one in March.",
]:
    try:
        print(f"{extract_person(client, text)}  <- {text}")
    except ValueError as error:
        print(f"invalid twice ({error})  <- {text}")
