# Fixed-size chunking

Retrieval systems rarely index whole documents. A 40-page handbook embedded as one vector is a
blurry average of everything in it, and pasting it into a prompt wastes context. So you cut
documents into **chunks** and index those instead.

The simplest strategy is fixed-size chunking: take `size` characters at a time. A fact that
straddles a boundary would be cut in half, so neighbouring chunks **overlap** by a few characters.

```python
chunk("abcdefghij", size=4, overlap=1)
# ['abcd', 'defg', 'ghij']
```

Each chunk starts `size - overlap` characters after the previous one, and the last chunk ends
exactly at the end of the text. In production this is your baseline: cheap, predictable, and
the thing every smarter strategy has to beat.

## Your task

Implement `chunk(text, size, overlap=0)` in `chunker.py`:

- return a list of strings, each at most `size` characters;
- consecutive chunks overlap by exactly `overlap` characters;
- an empty text gives `[]`, and a text no longer than `size` gives `[text]`;
- raise `ValueError` if `size < 1`, `overlap < 0` or `overlap >= size`.
