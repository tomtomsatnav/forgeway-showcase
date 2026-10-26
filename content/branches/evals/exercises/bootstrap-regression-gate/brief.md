# Confidence intervals and a regression gate

You change a prompt and the eval score moves from 0.81 to 0.79. Is the new prompt worse, or did
you just draw a slightly unlucky sample of cases? A single number cannot tell you. An eval score
is an average over a finite set of cases, so it has **sampling error**, and the smaller the set,
the bigger the error.

The **bootstrap** estimates that error without any formulas. Treat your cases as if they were the
whole population: draw a new set of the same size *with replacement*, compute its mean, and repeat
a thousand times. The spread of those means shows how much the score would wobble on a different
sample. The middle 95% of them is a **95% confidence interval**.

```text
scores ──► resample ×1000 ──► sort the means ──► take the 2.5th and 97.5th percentile ──► (low, high)
```

A **regression gate** turns that into a CI-style yes/no: block the change only when you are
confident it made things worse by more than you can tolerate. A noisy two-point dip passes; a clear
five-point drop does not.

The procedure below is fixed exactly, so for a given seed there is one right interval. Your tests
check those exact bounds on small inputs, and also that the interval contains the point estimate,
is repeatable for a seed, narrows as the data grows, widens with confidence, and that the gate
flips exactly where the interval crosses the threshold.

## Your task

Implement two functions in `gate.py`.

`bootstrap_ci(scores, confidence=0.95, resamples=1000, seed=0)` returns `(low, high)` using the
**percentile bootstrap**:

1. Make a private generator, `random.Random(seed)`. Never use the global `random` state.
2. Do `resamples` times: draw one resample with `rng.choices(scores, k=len(scores))` (one call
   per resample, nothing else drawn from `rng`) and record its mean, `sum(resample) / len(scores)`.
3. Sort the means. With `alpha = 1 - confidence`, `low` is the mean at index
   `floor(alpha / 2 * resamples)` and `high` is the mean at index
   `ceil((1 - alpha / 2) * resamples) - 1`. Do not interpolate: each bound is one of the resample
   means.
4. Raise `ValueError` if `scores` is empty, `confidence` is not strictly between 0 and 1, or
   `resamples` is less than 1. Do not modify `scores`.

`regression_gate(baseline, candidate, max_drop=0.02, confidence=0.95, resamples=1000, seed=0)`
compares two runs over the same cases, in the same order. Work on the paired differences
`candidate[i] - baseline[i]`. Return
`{"mean_diff": ..., "low": ..., "high": ..., "passed": ...}`, where `mean_diff` is the mean
difference, `low` and `high` are `bootstrap_ci` of the differences (passing on `confidence`,
`resamples` and `seed`), and `passed` is `False` only when `high < -max_drop`. Raise `ValueError`
for empty lists or lists of different lengths.
