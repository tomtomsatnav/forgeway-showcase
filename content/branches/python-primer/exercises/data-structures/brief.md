# Data structures and comprehensions

Almost everything in this course passes through Python's built-in containers: a chat is a list
of messages, a tool's arguments are a dict, and a set of seen ids is, well, a set. If you know
another language, the containers will feel familiar. What may be new is how much work a
comprehension does in one line:

```python
prices = {"tea": 3, "cake": 5, "soup": 7}

cheap = [name for name, price in prices.items() if price < 6]  # a list: ['tea', 'cake']
lengths = {name: len(name) for name in prices}  # a dict
initials = {name[0] for name in prices}  # a set: no repeats
```

`sorted()` takes a `key` function, and a tuple key sorts by its first item, then its second:

```python
sorted(["pear", "fig", "kiwi"], key=lambda word: (len(word), word))  # ['fig', 'kiwi', 'pear']
```

## Your task

A message here is a plain dict such as `{"role": "user", "content": "hello there"}`. Implement
four functions in `transcript.py`:

- `contents_by_role(messages)` returns a dict from each role to the list of that role's
  `content` strings, in the order they appear in `messages`.
- `unique_roles(messages)` returns a list of the roles used, each once, in alphabetical order.
- `long_messages(messages, min_words)` returns the `content` of each message with at least
  `min_words` words, in order. Words are what `str.split()` gives you.
- `top_words(text, n)` returns the `n` most common words in `text` as a list of `(word, count)`
  tuples: the highest count first, and words with the same count in alphabetical order. Words
  are what `text.split()` gives you, and case matters.

None of them should change `messages`.
