# Phase 3 plan

Scope (from the brief): the Knowledge graphs, Memory, Context engineering and Evals & guardrails
branches; boss challenges and capstones. Earlier plans: [Phase 1](docs/plans/phase-1.md) and
[Phase 2](docs/plans/phase-2.md).

On 2026-10-25 the product owner approved Phase 2 and asked for Phases 3 and 4 to be built
without per-phase sign-off, with one review at the end. Each phase still ends with a
verification report. Paid cloud resources are never created without the owner present.

The same rules apply as before:

- Each slice is tested before it is committed.
- Every new branch gets an independent cheat-and-fairness review, and its findings are fixed and
  re-proven.
- The gates stay green.

## Decisions

### Branches

Each branch has about eight or nine exercises, from beginner to advanced, and ends in a
capstone. Topics that duplicated earlier branches were cut, and the freed slots went to topics
practitioners need in 2026 (◆).

- **Knowledge graphs (`knowledge-graphs`), which requires Retrieval:**
  - ontology-guided extraction into typed triples, rejecting triples that violate the schema;
  - an in-memory triple store with pattern queries;
  - entity resolution, with the normalisation rules stated exactly;
  - multi-hop traversal for question answering;
  - guarded text-to-query;
  - community summaries, with the algorithm fixed in the brief and grading on what reaches the
    prompt;
  - hybrid graph and vector retrieval;
  - provenance for every answer edge;
  - temporal edges with validity intervals and invalidation (◆).
- **Memory (`memory`), which requires the starter zone:**
  - rolling summarisation;
  - an episodic store with recency, importance and relevance scoring, where importance is a
    seeded model score;
  - semantic facts with updates and contradictions;
  - a write policy;
  - memory as a tool the agent calls (◆);
  - per-user isolation and deletion on request;
  - decay and forgetting;
  - reflection that consolidates episodes into facts.
- **Context engineering (`context-engineering`), which requires the starter zone:**
  - prompt assembly under a token budget with priorities;
  - structured sections and delimiting;
  - ordering against "lost in the middle";
  - dynamic few-shot selection;
  - a stable cache prefix, graded as byte-identical across requests (◆);
  - just-in-time loading by tool call within a budget, beating a pre-loaded baseline on prompt
    tokens (◆);
  - pruning stale tool results across turns;
  - context provenance and citation.
- **Evals & guardrails (`evals`), which requires the starter zone:**
  - an eval harness with exact, fuzzy and set metrics;
  - LLM-as-judge against a position-biased fake, so only a swap-and-aggregate implementation
    is stable (◆);
  - judge agreement with human labels (Cohen's kappa);
  - bootstrap confidence intervals and regression gates, graded by property (◆);
  - agent trajectory evals over recorded tool-call sequences (◆);
  - input guardrails (PII redaction);
  - output guardrails (schema and policy);
  - jailbreak and injection detection, where the fake is the classifier and blocked text must
    never reach the main model;
  - a red-team suite runner.

**Grading rules for every branch (◆)**

- **Frozen toolkit.** `lattice_kit` does not change in Phase 3. Helpers live in starter files, or
  on the grader side in `lattice_grader.<branch>_reference`.
- **Arbitrary fakes.** Every model-dependent check uses a fake whose answers cannot be predicted
  from the input: seeded entities, scores and labels. The check then asserts the code followed
  that answer.
- **Statistics.** These are graded by property, or the brief fixes the exact procedure (seed,
  resample count, method).
- **Lessons from Phase 2.** Authors follow docs/authoring.md, including its "Lessons from cheat
  reviews".

### Guided projects (added at the product owner's request, 2026-10-25)

Two end-of-curriculum projects tie the branches together into something a learner can show.

- **Projects are branches.** Each is a branch that `requires` the branches it draws on, so it
  unlocks once those are complete:
  - **Support copilot** (`project-copilot`) requires Retrieval, Memory, Context engineering and
    Evals. Milestones:
    - ingest and hybrid retrieval;
    - per-user memory;
    - context assembly;
    - guardrails;
    - an eval suite with a release gate (the capstone).
  - **Research agent team** (`project-research`) requires Protocols, Orchestration, Knowledge
    graphs and Evals. Milestones:
    - MCP tool servers;
    - a knowledge graph built from research;
    - a durable multi-agent workflow;
    - trajectory evals and red-teaming (the capstone).
- **Milestones build one codebase.** A milestone's `exercise.yaml` may say
  `carry_from: <exercise id>`. The workspace then opens with the learner's own files from their
  latest passing attempt of that exercise, falling back to the starter. Each milestone's starter is
  the previous milestone's reference solution, so grading stays self-contained and deterministic.
- **The last milestone is the project's capstone**, so every capstone rule applies. Finishing a
  project earns its own certificate.
- **Presentation.** Professional mode calls it a "Guided project". RPG calls it an "Expedition",
  with its own region on the world atlas reached by roads from every zone it requires.
- **Real models.** Each project's final brief links to a "run it against a real model" guide.
  Live-model support arrives in Phase 4.

### Progression content

Each new branch gets the same set as before:

- a path or class:

  | Branch | RPG class | Professional name |
  | --- | --- | --- |
  | Knowledge graphs | Surveyor (◆, so as not to clash with the atlas metaphor) | Knowledge engineer |
  | Memory | Chronicler | Memory engineer |
  | Context engineering | Weaver | Context engineer |
  | Evals & guardrails | Arbiter | Evaluation engineer |

- a talent subtree of about six nodes, gated on its exercises, with one
  `reference_solutions` effect;
- a completion badge;
- RPG zone flavour, with quest titles and a boss.

### Not doing

- A stateless (2026-07-28) MCP exercise. The 2025-11-25 brief notes that the newer revision drops
  the handshake.
- Deployment. It stays in Phase 4.

## Checklist

### 0. Housekeeping
- [x] Phase 2 plan archived to `docs/plans/phase-2.md`
- [x] Plan reviewed independently; changes marked ◆
- [x] CI shards `lattice content test` by branch (◆)

### 1. Capstone and boss engine
- [x] Backend:
  - capstone validation in `PrerequisiteGraph` (◆);
  - capstone ordering;
  - the `capstones_passed` badge criterion;
  - `includes_capstone` on certificates (migration, page and image);
  - boss flavour (`bosses:` keyed by exercise id), validated against capstone exercises;
  - `LearnerFacts.capstones_passed`;
  - old-certificate rendering;
  - ADR 0007;
  - the capstone section in docs/authoring.md;
  - correcting the "advanced tier bonus" claim in ARCHITECTURE §6;
  - tests.
- [x] Frontend:
  - capstone tier mark (both modes);
  - RPG lair waypoint and "boss defeated" completion variant;
  - professional capstone framing;
  - world-atlas routes from `requires`;
  - the lair in the accessible list;
  - a `--tier-capstone` token in all four palettes, with contrast checked (◆);
  - lexicon, Vitest and e2e.

### 2. Branches (each: exercises, solutions, wrong cases, capstone, RPG flavour)
- [x] Knowledge graphs
- [x] Memory
- [x] Context engineering
- [x] Evals & guardrails

### 3. Capstones for existing branches
- [x] Retrieval
- [x] Protocols & tools
- [x] Orchestration

### 3b. Guided projects
- [x] Engine:
  - `carry_from` (validation, workspace prefill from the learner's passing files, a reset to the
    starter);
  - atlas roads from every required zone;
  - project framing in both modes;
  - lexicon;
  - tests.
- [x] Support copilot content
- [x] Research agent team content
- [x] Badges for completing each project; RPG flavour and bosses

### 4. Reviews (◆ per branch, as each lands)
- [x] Knowledge graphs
- [x] Memory
- [x] Context engineering
- [x] Evals & guardrails
- [x] The three retro-fitted capstones
- [x] Both guided projects

### 5. Progression content
- [x] Paths, talents, badges and flavour for the four new branches; `capstones_passed` badges

### 5b. Phase review (product owner's rule, 2026-10-25)
- [x] Fable reviews everything built in Phase 3; findings fixed by Opus agents before the
      verification report. From this point on, Opus does all agent work.

### 5c. Rename sweep (product owner's request, 2026-10-25)
- [x] Once everything else is finished: a cheap-model agent searches the whole repo for
      remaining user-facing "Lattice"/"lattice" that should now read "Forgeway"/"forgeway"
      (the product was renamed; internal package names stay `lattice` by decision)

### 5d. Between Phase 3 and Phase 4 (product owner's decision, 2026-10-26)
- [x] Rename the learner toolkit `lattice_kit` → `forgeway_kit` (toolkit, every brief, starter,
      solution and wrong case, docs), then a full content test. Learners import it, so its
      name is user-facing; the grader and backend packages keep their internal names.

### 6. End to end and release
- [x] Playwright: a capstone in both modes (lair, boss-defeated moment, capstone framing); atlas
      routes; axe in all four palettes
- [x] Every exercise attempted with correct and wrong solutions (content test, CI)
- [x] Clean checkout → `docker compose up` → smoke and e2e; CI green
- [x] README, ARCHITECTURE and Phase 3 verification report (screenshots deferred to the end of
      Phase 4, at the product owner's request)

## Progress log

- 2026-10-25 — Phase 3 plan drafted and reviewed independently; all twelve recommendations
  accepted.
- 2026-10-26 — Fable's end-of-phase review: five MUST findings fixed at the root (import guard,
  fresh-interpreter restarts, answer keys out of reach, brief/test agreement, badge count) plus
  CI coverage of carried files and docs. Product renamed to Forgeway; learner toolkit renamed to
  forgeway_kit. One final content run: 553/553. Phase 3 complete
  ([report](docs/phase-3-verification.md)).
