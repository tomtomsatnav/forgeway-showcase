# ADR 0004: Theme system

Status: Accepted
Date: 2026-10-25

## Context

Forgeway has two presentation modes. RPG mode uses zones, quests, bosses and classes. Professional
mode uses tracks, exercises, capstone projects and certificates. Both show the same content and
progression. Colour scheme (light or dark) is a separate choice from mode.

Adding or changing a theme must not touch exercise, content or grading code. The domain therefore
has to be written in theme-agnostic terms, and each theme has to supply its vocabulary, visuals
and layout as data plus a small amount of rendering code.

## Decision

**Theme-agnostic domain.** The domain says `Branch`, `Exercise`, `Tier`, `Capstone`, `Path` and
`Milestone`. It never says "quest", "zone" or "boss". The mapping to RPG and professional
terms is in the architecture overview.

**A theme pack has three parts.**

1. **Tokens.** `tokens.css` defines semantic CSS variables such as `--surface-raised` and
   `--accent-progress`, each with a light and a dark value. Tailwind references semantic tokens
   only, never raw colours. Contrast is checked against WCAG AA for each token pair in both schemes.
2. **Lexicon.** `lexicon.ts` is a typed dictionary of user-facing strings. Pluralisation and
   interpolation are supported. The type system requires every theme to define every key, so a
   missing string is a compile error.
3. **Layout slots.** A small, explicit set of places where structure legitimately differs.
   Examples: the branch overview is a zone map in RPG mode and a track list in professional mode.
   Completion is a level-up moment in RPG mode and a quiet confirmation in professional mode. Each
   slot takes the same data and props and has a different renderer.

**Flavour data is content.** RPG flavour (zone names, boss lore, class titles) lives in
`content/themes/rpg/`, keyed by domain ids. The professional vocabulary is the lexicon of the
professional theme pack.

**Independent toggles.** Mode (RPG or professional) and colour scheme (light or dark) are separate
settings. Both are stored on the learner profile and persist per learner.

## Consequences

Positive:

- Content authoring, grading and progression code is unchanged by theme work.
- The typed lexicon catches missing or misspelt strings at build time.
- Semantic tokens let light and dark variants be checked mechanically.
- Two modes share one component tree wherever structure is the same, which keeps the layouts
  consistent in behaviour.

Negative:

- Layout slots are real duplication. Each new slot needs two renderers and tests for both.
- Discipline is needed to keep components on semantic tokens. A lint rule should reject raw colours
  in component code.
- Lexicon keys grow with the product. Keys should be grouped by screen to stay manageable.
- Flavour files depend on domain ids. Renaming an id in content requires a matching change in each
  theme's flavour data. CI should fail on dangling references.
- "A small set of slots" is a judgement. If more slots are needed, that is a sign the theme
  boundary is being drawn in the wrong place, and this ADR should be revisited.

## Alternatives considered

- **Separate component trees per theme.** Rejected. The two trees would drift apart, and every
  shared fix would need doing twice.
- **CSS-only theming.** Rejected. It cannot change structure, and it leaves copy hard-coded in
  components.
- **Theme-specific copy in a CMS.** Rejected. Content lives in git and is reviewed in pull requests
  (see ARCHITECTURE section 9).
- **A general-purpose i18n library.** Considered and not adopted. The need is limited to typed keys,
  pluralisation and interpolation, and a small typed dictionary covers that without a runtime
  dependency.
- **A single theme with a skin toggle.** Rejected. Skins cannot express the layout differences the
  two modes need.
