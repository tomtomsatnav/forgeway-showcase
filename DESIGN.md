# Design system

Forgeway has one structure and two skins. Every screen is built from shared components that
read **semantic tokens**; a theme supplies the tokens, a vocabulary and, in a few named
places, an alternative layout. Toggling the mode swaps the skin, never the information.

Two independent switches:

- **Mode** — `professional` or `rpg`. What the product feels like.
- **Colour scheme** — `system`, `light` or `dark`. How bright it is.

That gives four palettes, all checked for WCAG 2.2 AA (see [Contrast](#contrast)).

## Identity

### Professional — "the engineering notebook"

Calm, credible, quietly expensive. The reference is a well-typeset technical book, not a SaaS
dashboard. Warm paper, black ink, one deep green accent used sparingly. Structure comes from
hairline rules and typographic hierarchy, not boxes and shadows. Briefs are set in a reading
serif because people learn by reading them; everything operational is set in a sans.

### RPG — "the cartographer's atlas"

Rich and atmospheric without being costume. The reference is an illuminated map: parchment and
sepia ink with a vermilion wax-seal accent by day; verdigris night with gold leaf by dark.
Branches are regions on a hand-drawn map, exercises are waypoints along a route, a level-up is
a seal being pressed. Ornament is reserved for moments that matter (zone headers, completion,
levels); the working surfaces — the editor and the results — stay as legible as in
professional mode.

### Things we never do

Purple-to-blue gradients. Glassmorphism. Emoji as icons. Grids of identical rounded cards with
a drop shadow and an icon in the corner. Uniform 16px everywhere. Gratuitous motion. Dark mode
as an inverted afterthought.

## Tokens

All colours are referenced by role. Components never use raw hex values or Tailwind's palette.

| Token | Role |
| --- | --- |
| `--surface-base` | Page background |
| `--surface-raised` | Panels, editor chrome, popovers |
| `--surface-sunken` | Wells: code output, inputs |
| `--text-primary` / `--text-secondary` / `--text-muted` | Text hierarchy |
| `--border-subtle` / `--border-strong` | Hairlines / control outlines (≥ 3:1) |
| `--accent` / `--accent-strong` / `--accent-soft` / `--text-on-accent` | Primary action, emphasis, tint |
| `--success` / `--danger` / `--warning` (+ `-soft`) | Check results and notices |
| `--tier-beginner` / `--tier-intermediate` / `--tier-advanced` / `--tier-capstone` | Tier markers; the capstone's has its own hue (blue) so it never reads as a graded tier |
| `--focus-ring` | Keyboard focus outline |
| `--font-display` / `--font-ui` / `--font-reading` / `--font-mono` | Typefaces |
| `--radius-control` / `--radius-panel` | Corner radii |
| `--shadow-raised` | The one elevation shadow |

### Palettes

| Role | Pro light | Pro dark | RPG light | RPG dark |
| --- | --- | --- | --- | --- |
| surface-base | `#F6F4EF` paper | `#131513` graphite | `#EFE4CB` parchment | `#0E1615` verdigris night |
| surface-raised | `#FFFFFF` | `#1C1F1C` | `#F7EFDC` | `#16211F` |
| surface-sunken | `#EDEAE3` | `#0E100E` | `#E5D7B8` | `#0A1110` |
| text-primary | `#1B1C1A` ink | `#E9E6DE` | `#2A1F14` sepia | `#EDE3CC` |
| text-muted | `#5E605A` | `#A3A59C` | `#6B5A44` | `#B3A88F` |
| border-strong | `#84867E` | `#70736B` | `#897453` | `#766C57` |
| accent | `#1D5C4B` deep green | `#6FC2A6` | `#8E2A21` vermilion seal | `#D9A546` gold leaf |
| text-on-accent | `#FFFFFF` | `#0E1B16` | `#FBF3E2` | `#1A1206` |
| success | `#2F6B3A` | `#8FD19B` | `#386429` | `#9CCB7E` |
| danger | `#A3352B` | `#F08A7E` | `#8E2A21` | `#EE8366` |
| warning | `#8A5A12` | `#E7B566` | `#7A5410` | `#E8B85C` |
| tier-capstone | `#1F4F86` | `#8FBDF0` | `#2F4A7C` | `#9DB9EE` |

### Contrast

Measured with the WCAG 2.x relative-luminance formula (`scripts/contrast.py`):

| Pair | Pro light | Pro dark | RPG light | RPG dark |
| --- | --- | --- | --- | --- |
| text-primary / base | 15.6 | 14.7 | 12.7 | 14.4 |
| text-muted / base | 5.8 | 7.4 | 5.2 | 7.8 |
| accent / base | 7.1 | 8.7 | 6.6 | 8.2 |
| text-on-accent / accent | 7.8 | 8.4 | 7.6 | 8.3 |
| success / base | 5.8 | 10.3 | 5.5 | 9.8 |
| danger / base | 6.2 | 7.6 | 6.6 | 7.1 |
| tier-capstone / base | 7.6 | 9.4 | 7.0 | 9.3 |
| tier-capstone / worst of base, raised, sunken | 6.9 | 8.5 | 6.2 | 8.3 |
| border-strong / base | 3.4 | 3.8 | 3.5 | 3.5 |
| border-strong / worst of base, raised, sunken | 3.1 | 3.4 | 3.1 | 3.2 |

Every text pair clears 4.5:1, the capstone tier token on all three surfaces included (`scripts/contrast.py` fails below 4.5:1); control boundaries clear 3:1. State is never conveyed by colour
alone: passed and failed checks also carry an icon and a word.

## Typography

| Role | Professional | RPG |
| --- | --- | --- |
| Display (page and branch titles) | Instrument Sans 600 | Alegreya SC 700 |
| UI (labels, buttons, navigation) | Instrument Sans | Alegreya Sans |
| Reading (exercise briefs) | Source Serif 4 | Alegreya |
| Code | JetBrains Mono | JetBrains Mono |

Fonts load from Google Fonts with `display=swap` and system fallbacks.

Scale (ratio 1.25, base 16px): `xs 12` · `sm 14` · `base 16` · `lg 20` · `xl 25` · `2xl 31` ·
`3xl 39` · `4xl 49`. Briefs use `lg` at 1.6 line height with a 68-character measure. Labels for
tiers and statuses use small caps tracking (`0.06em`) at `xs`. Numerals in XP and progress use
tabular figures.

## Space and layout

A 4px base unit; components use the steps 4, 8, 12, 16, 24, 32, 48, 64. Vertical rhythm on
reading pages is 24px. Layout is a single column up to 640px, a list-and-detail split from
1024px, and the exercise workspace becomes brief | editor | results from 1280px (brief and
editor stacked with a results drawer below that). Content never exceeds 1200px except the
workspace, which uses the full viewport width; on its route the header drops its 1200px column so
its content sits on the workspace's gutters. From 1280px the workspace fills the viewport below
the header, so the page itself never scrolls: the brief, the editor and the results each scroll
on their own. In the three-column layout two splitters
(WAI-ARIA window splitter: drag, arrow keys, Home/End; 24px hit area on a hairline rule with a small grip, both drawn in `--border-strong` so they clear 3:1, and an accent hover state) let
the learner resize the brief and results columns, each kept above a usable minimum; sizes are
remembered per viewer in local storage. The stacked layout has no splitters.

The header is one row. Below 640px it holds the brand, a compact level (the XP figures kept for
screen readers) and a **Menu** button; the navigation links, both toggles and sign out sit in a
disclosure it opens (`aria-expanded`, focus moves to the first link, Escape closes it and
returns focus to the button). From 640px they are all inline.

Radii are small and consistent: `--radius-control` 6px (pro) / 3px (RPG); `--radius-panel`
10px (pro) / 4px (RPG, with a 1px inner rule for an engraved edge). One shadow, used only for
things that float (popovers, the level-up dialog).

## Components

Shared, token-driven; every one is keyboard operable with a visible focus ring
(`2px solid var(--focus-ring)` with a 2px offset).

- **Button** — `primary` (accent fill), `secondary` (strong border), `quiet` (text only).
  44px minimum touch target. Loading state keeps the label width and shows a spinner.
- **TierMark** — the tier as a small-caps label plus a glyph: one, two or three stacked bars
  (pro) or a single, double or triple diamond sigil (RPG). A capstone has its own mark, in
  `--tier-capstone`: three bars inside a frame labelled "Capstone" (pro), or a crenellated tower
  with a gate labelled "Boss" (RPG).
- **StatusMark** — locked / available / passed, as icon + word.
- **ProgressRule** — a thin bar with tabular numbers; XP and branch completion.
- **CheckResult** — title, pass or fail mark, learner-facing message in a sunken well (the
  explanation in the UI font; only code-like parts, such as fenced or indented blocks and
  Expected/Got values, in monospace), the learner's own printed output in a collapsible section.
- **HintReveal** — reveals hints one at a time behind a confirm step that states the cost
  ("Revealing a hint forfeits the +20% no-hint bonus").
- **CodeEditor** — CodeMirror 6 with a theme generated from the tokens; tabs for multiple
  editable files. Edits Python as VS Code does: four-space indentation that follows `:` and
  steps back after `return`/`pass`/`break`/`continue`/`raise` and on `else:`/`elif`/`except`/
  `finally:`; pasted code re-indented to where it lands; auto-closed brackets and quotes; indent
  guides; completion of keywords, builtins, local names and the `forgeway_kit` API, with hovers
  giving a kit symbol's signature and summary; VS Code's bindings for comment, find and replace,
  multiple cursors, folding, moving and duplicating lines. The kit data is generated from the
  package (`uv run python scripts/kit_api.py`; a grader test fails when it drifts). Tooltips,
  the completion list and the search panel use the tokens; the selection is a translucent accent
  wash so it shows on the active line. A *Keyboard shortcuts* disclosure under the editor lists
  the bindings in the mode's words.
- **Toggle** — the mode and colour-scheme switches, as labelled segmented controls.
- **Carried files** — when a milestone opens on the learner's own files from an earlier one
  (`files_source: "carried"`), a note above the editor names that exercise and offers *Start from
  the provided code instead*, behind a confirm step that says the earlier pass is kept. Confirming
  replaces the editor's files with the starter for good. The note stays for the visit.
- **Reference solution** — a disclosure beneath the hints on a passed exercise: each file in a
  read-only block, then the notes. Before the talent that covers it, a one-line hint names that
  talent instead, worded from the problem's `talents` field in the mode's own word. It is not
  requested until the exercise is passed.
- **Profile lists** — specialisations (classes) and badges are ruled lists, never boxed grids: a
  glyph and a word for each state. Earned badges come first; the rest fold under a disclosure
  ("12 more to earn"). The time zone sits in a Settings section at the end.
- **Certificates** — a section on the profile (`#certificates`), one card per certificate: track,
  issue date, exercise count, credential ID, an editable recipient name (1 to 60 characters), a
  Private / Public segmented control that says what publishing exposes, and, only when public,
  *View certificate*, *Copy link* (polite live-region confirmation; a selected read-only field if
  the clipboard is refused), *Add to LinkedIn profile*, *Share on LinkedIn* and a thumbnail of the
  PNG. A learner without Pro sees the Pro mark and a waitlist link beside the control before trying
  to publish. The certificate itself stays professional in both modes; only the heading and the
  announcement take flavour. When the certificate was issued for a track with a capstone
  (`includes_capstone`), the exercise count reads "10, including its capstone project" and the
  announcement ends "including its capstone project". Earning one is announced wherever progression news is (both
  completion moments and the results panel) with a link to the section.

### Layout slots (where the modes legitimately differ)

| Slot | Professional | RPG |
| --- | --- | --- |
| `BranchOverview` | A syllabus: numbered, ruled list per branch with tier marks and a progress rule, beside a sticky track index on desktop. Only the tracks in progress (or, when none is, the next one to take) open with their exercises listed; the rest fold to their header with a "Show 10 exercises" button, and following a track in the index opens it. A capstone row sits between two heavy rules in `--tier-capstone`, headed "Capstone project", with its own mark. A project branch (`kind: project`) is labelled "Guided project" in place of its track number | A world atlas: one SVG map with the starter zone at the centre and a road to every other zone, laid out from data; locked zones under fog behind dashed roads. A road leaves each zone its destination requires: a zone that requires a non-hub zone (Knowledge graphs requires Retrieval) lies beyond that zone and is reached from it, otherwise from the hub. A project is an expedition: its island has a second, dashed outer coast and sits on an outer ring, past every other zone in the direction of the zones it requires (below them on a phone), with a road from each of them. Its region is headed "Expedition". Selecting a zone (`?zone=` search param) shows its region, exercises as waypoints on a route. A capstone is the route's last waypoint, drawn as a lair: a larger crenellated tower in a double ring, headed "Boss challenge", with the boss's name, the real title and its state (Sealed, Awaiting, Defeated) as a padlock, an open dot or a tick and a word. A list of zone links beneath the map (hub first, then each ring zone followed by the zones beyond it, expeditions last and labelled so), a ruled list rather than cards, is the keyboard and screen-reader path. The map is cropped to what is drawn; roads never run under an island they do not serve (a road threads the water between islands when no single curve will do); island names wrap onto up to three lines and are never cut short. A zone's small labels (Expedition, Pro, the real title, the quest count) share one line above its title |
| `CompletionMoment` | An inline confirmation strip: "Passed · +60 XP · Level 2"; for a capstone, "Capstone complete · +350 XP · Level 5" | A modal seal: the level number pressed into wax, XP counting up, newly opened waypoints listed. For a capstone the boss's tower is pressed into the wax and the dialog reads "Boss defeated", the boss's name, its `defeat` line and the real title. Same single press-in and count-up, so reduced motion applies unchanged |
| `PageHeader` | Title and a one-line summary on a hairline. A capstone adds a "Capstone project" label with its mark above the title and a note that it draws on the whole track | Title in display small caps between ornamental rules. A capstone shows the boss's name as the title, its epithet and lore, then the real exercise title, under a "Boss challenge" label |
| `TalentTree` | The competency matrix: an accessible table (skill, requirements with reasons, state, action button) with a point counter and a respec behind a confirm step | A constellation on parchment or night: nodes and links in layers, general talents above the class's own; on a phone the layers run down, from 768px they run left to right. State is a glyph (tick, ringed dot, padlock) and a word, never colour alone. The same competency table sits beneath it as the accessible equivalent and the only place talents are taken, so keyboard and screen-reader use is identical in both modes |

Both slots receive identical props (the completion moment also lists any badge won, certificate earned, talent points gained and the streak). Adding a theme means providing tokens, a lexicon and
(optionally) slot renderers.

## Vocabulary

A typed lexicon per mode. Keys are domain concepts; values may be functions for plurals and
interpolation so counts read naturally ("1 quest", "3 quests").

| Key | Professional | RPG |
| --- | --- | --- |
| branch | track | zone |
| exercise | exercise | quest |
| capstone | capstone project | boss challenge |
| level | level | level |
| hint | hint | scroll of insight |
| attempt.submit | Run checks | Attempt the quest |
| status.locked | Locked | Shrouded |
| status.passed | Completed | Conquered |
| backToWorld / worldMapTitle | Back to all tracks / All tracks | Back to the world / The known world |
| profile | Profile | Character sheet |
| specialisation (path) | specialisation: Generalist, Retrieval specialist, Integration specialist, Systems specialist | class: Wayfarer, Loremaster, Artificer, Conductor (names from the flavour) |
| talent / talent point | competency / competency point | talent / talent point |
| talent states | Acquired / Available / Locked | Learned / Ready to learn / Sealed |
| allocate / deallocate / respec | Acquire / Release / Reset competencies | Learn / Unlearn / Respec talents |
| talentTree | Competency matrix | Talent tree |
| badge | achievement ("Earned 3 Oct 2026") | badge ("Won 3 Oct 2026") |
| streak | "3-day streak" | "Learning streak: 3 days" |
| referenceSolution | Reference solution | Master's copy |
| referenceLocked | "A competency unlocks reference solutions for this track. Acquire X to unlock it." | "A talent unlocks master's copies for this zone. Learn X to unlock it." |
| certificatesHeading | Certificates | Seals of completion |
| certificatesNone | "No certificates yet. Complete a track to earn its certificate." | "No seals yet. Complete a zone to earn its certificate." |
| certificateEarned | "Certificate earned: Retrieval track" | "The seal is set. Certificate earned: Retrieval track" |
| certificatesLink | View your certificates | See your seals of completion |
| tier.capstone | Capstone | Boss |
| capstoneLabel | Capstone project | Boss challenge |
| capstoneNote | This project draws on the whole track. | The guardian of this zone draws on every quest you have conquered here. |
| capstoneState | Locked / Available / Completed | Sealed / Awaiting / Defeated |
| capstoneStrip | "Capstone complete · +350 XP · Level 5" | "Boss defeated · +350 XP · Level 5" |
| capstoneCompletionTitle | Capstone complete | Boss defeated |
| certificateIncludesCapstone | including its capstone project | including its capstone project |
| projectLabel | Guided project | Expedition |
| carriedNote | "Continuing from your work on Hybrid retrieval." | "You carry your work from Hybrid retrieval into this quest." |
| carriedReset | Start from the provided code instead | Start from the provided code instead |
| carriedResetAction / carriedKeep | Use the provided code / Keep my code | Set it down / Keep my work |

## Motion

Motion explains change; it never decorates or blocks.

- Durations: `fast 120ms` (hover, press), `base 200ms` (panels, drawers), `celebrate 900ms`
  (level-up). Easing `cubic-bezier(0.2, 0.7, 0.2, 1)`.
- Check results stagger in at 40ms intervals so a list of results reads as a sequence.
- The RPG level-up seal presses in (scale 1.15 → 1 with a shadow settle), XP counts up and
  the ring of the next level fills. Input remains live underneath; Escape or a click closes it.
- `prefers-reduced-motion: reduce` replaces every transform and count-up with an instant state
  change or a short opacity fade. Nothing loops.

## Accessibility checklist

WCAG 2.2 AA throughout: semantic landmarks and headings; every control reachable and operable
by keyboard in a logical order; visible focus that is never obscured (2.4.11); targets of at
least 24×24px (2.5.8), 44px for primary actions; results announced through a polite live
region; the editor keeps standard keyboard behaviour and offers a documented way to move focus
out (Escape then Tab, which works even while the completion list or search panel is open, as
Tab otherwise indents); the RPG map has an equivalent accessible list; colour is never the only
signal; text resizes to 200% without loss.
