# Does the judge agree with people? Cohen's kappa

Using a model to grade another model's answers is cheap and fast, but a judge is only worth
using if it agrees with people. The usual check: have people label a sample, have the judge label
the same sample, and measure how often they agree.

Raw agreement misleads. If 90% of answers are good, a judge that says "PASS" every time agrees
with people 90% of the time and tells you nothing. **Cohen's kappa** corrects for the agreement
you would expect by chance, given how often each rater uses each label:

```text
p_o   = (items where the two labels are equal) / n
p_e   = sum over every label k of  (share of rater 1's items labelled k) x (share of rater 2's items labelled k)
kappa = (p_o - p_e) / (1 - p_e)
```

Kappa is 1 for perfect agreement, 0 for no better than chance, and negative for worse than
chance. Many teams ask for 0.6 or more before they let a judge gate a release.

## Your task

Implement four functions in `agreement.py`.

- `cohens_kappa(first, second)`: the formula above, for two lists of labels (any hashable
  values, any number of distinct labels). The sum for `p_e` runs over every label that appears in
  either list. If `p_e` is exactly `1.0` (both raters used one single label throughout), return
  `1.0`. Raise `ValueError` if the lists are empty or of different lengths.
- `parse_verdict(reply)`: take the first whitespace-separated word of the reply, keep only its
  letters, and upper-case it. Return `"PASS"` or `"FAIL"`; anything else (including an empty reply)
  raises `ValueError`. So `"Fail."` and `"pass: it cites the policy"` are fine, and `"PASSING"` is not.
- `judge_labels(client, items, rubric)`: for each item, in order, make one `client.complete` call
  in a fresh conversation whose single `user` message contains both the rubric and the item. Return
  the parsed verdicts.
- `judge_report(client, items, human_labels, rubric, min_kappa=0.6)`: label the items with the
  judge, and return `{"n": ..., "observed": ..., "kappa": ..., "trusted": ...}` where `observed`
  is `p_o` and `trusted` is `True` when `kappa >= min_kappa`.
