# Episodic recall

An agent that has lived through hundreds of events cannot replay them all. **Episodic memory**
stores events as they happen and, when something is needed, brings back only the few that matter
now. "Matters" is not one thing. The scheme from the *Generative Agents* paper (Park et al., 2023)
scores each episode on three axes and adds them up:

- **Recency**: recent things are easier to recall. It decays smoothly with time.
- **Importance**: breaking a leg matters more than eating toast. Nobody can compute this from
  keywords, so you ask a model to rate each episode when it is stored.
- **Relevance**: how close the episode is to what you are asking about now.

```text
recall("travel plans")
  "booked flights to Oslo"       recency 0.97  importance 0.7  relevance 0.41   total 2.08
  "had toast for breakfast"      recency 0.99  importance 0.1  relevance 0.00   total 1.09
```

Time is the other trap. If the store reads the wall clock, a test (or a replay of yesterday's
conversation) cannot control it. So the store takes a `clock` function, and every age comes from
that.

## Your task

Implement `EpisodicStore` in `episodic.py`. `scorer` is a model client, `clock()` returns the
current time in seconds, and `embedder` turns text into vectors. `embedder` is optional: use
the one you are given, and `HashingEmbedder()` only when it is `None`.

- `add(text)` stores an `Episode` and returns it. Ids count up from 1. `created_at` is `clock()` at
  that moment. Ask `scorer` once, with a single `user` message that is exactly the text, how
  important the episode is on a scale of 1 to 10 (say so in the system prompt). `importance` is
  the **first run of ASCII digits (`0-9`)** in the reply as an integer, clamped to 1 to 10. A
  reply with no such digits means 5. A minus sign is not a digit (`-3` gives 3), and nor are digits
  from other scripts, such as `٧` or `８`.
- `recall(query, k=3)` returns up to `k` episodes, best first. It never calls the scorer. An
  episode's score is the sum of three numbers:
  - recency: `0.5 ** (age_hours / 24)`, where age is `clock() - created_at` in seconds divided by
    3600, and an age below zero counts as zero;
  - importance: the episode's importance divided by 10;
  - relevance: the cosine similarity between the embeddings of the query and the text, or 0 if it
    is negative.
- Episodes with equal scores are returned newest (highest id) first. `k` of 0 returns an empty
  list, and a `k` larger than the store returns every episode.
