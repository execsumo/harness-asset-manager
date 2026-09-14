---
name: HarnessAM
source-of-truth: frontend/src/styles/tokens.css
themes: [dark, light]
typography:
  sans: Geist Variable
  mono: Geist Mono Variable
  scale:
    3xs: 11px
    2xs: 12px
    xs: 13px
    sm: 14px
    md: 15px
    lg: 17px
    xl: 20px
    2xl: 28px
  weights: [400, 500, 600, 700]
  leading: { none: 1, tight: 1.2, snug: 1.35, normal: 1.5, relaxed: 1.65 }
  tracking: { tight: -0.02em, snug: -0.011em, normal: 0, wide: 0.03em, caps: 0.06em }
colors-dark:
  bg: '#0b0c0f'
  surface: '#16171b'
  surface-raised: '#1f2025'
  surface-sunken: '#121317'
  sidebar-bg: '#121317'
  border: '#26272c'
  border-strong: '#3a3b40'
  text: '#e8e6e1'
  text-muted: '#9a958d'
  text-subtle: '#6f6c66'
  accent: '#6aa9d6'
  accent-strong: '#8cc0e4'
  highlight: '#f3c969'
  success: '#6bc2a4'
  warning: '#f3c969'
  danger: '#f08d79'
  star: '#f59e0b'
colors-light:
  bg: '#f8f5ed'
  surface: '#ffffff'
  surface-raised: '#efeadd'
  surface-sunken: '#eae5d7'
  sidebar-bg: '#f2eee5'
  border: '#e3ddcc'
  border-strong: '#c8bfa6'
  text: '#1f1f1c'
  text-muted: '#6b6558'
  text-subtle: '#8d8677'
  accent: '#2f6f9f'
  accent-strong: '#26567d'
  highlight: '#9a5c03'
  success: '#0f6e56'
  warning: '#97620a'
  danger: '#b14828'
  star: '#c27803'
radii: { 2xs: 3px, xs: 6px, sm: 8px, md: 12px, lg: 16px, xl: 20px, pill: 999px }
spacing:
  unit: 4px
  scale: [4, 6, 8, 12, 16, 20, 24, 32, 40, 56]
  sidebar-width: 256px
  page-max-width: 1200px
breakpoints: { sm: 680px, md: 900px, lg: 1100px }
motion:
  fast: 120ms
  medium: 200ms
  ease-out: 'cubic-bezier(0.2, 0.8, 0.2, 1)'
---

## Brand & style

HarnessAM is a local-first control panel for the config sprawl across a
developer's coding agents. It is a dense, read-heavy tool: matrices of
extensions against harnesses, file paths, JSON snapshots, drift reports. The
aesthetic follows from that — **quiet, warm, and legible**, closer to a
well-made reference application than to a dashboard.

Three commitments shape every decision:

- **Warm neutrals, not grey.** Both themes are built on warm greys and creams.
  Text is `#e8e6e1` on dark rather than pure white, and the light theme is
  parchment rather than white. Long sessions staring at config diffs should not
  feel like staring at a spreadsheet.
- **Density with air.** High information density is the point, but rows get
  real padding and sections get real gaps. Structure comes from spacing and
  hairline borders, not from boxes inside boxes.
- **Colour means something.** The palette is mostly neutral so that the few
  saturated things — a drift warning, an accent action, a starred row — are
  unambiguous. Decorative colour is not used.

## Tokens are the contract

`frontend/src/styles/tokens.css` owns every scale value in the app: type,
weight, leading, tracking, colour, radius, spacing, shadow, motion, focus.
Component CSS references tokens and **never hardcodes a raw value**. A literal
`font-size: 0.85rem`, `border-radius: 4px`, or `#f59e0b` in a feature file is a
bug, not a style choice — it is a value that will drift away from the rest of
the app the moment anything changes.

This is the single rule that keeps the system coherent, and it is mechanically
checkable. See `frontend/src/styles/README.md` for the cascade-layer
architecture that enforces where rules may live.

## Typography

**Geist** for the interface, **Geist Mono** for anything the user could paste
into a terminal. Both are self-hosted variable fonts
(`@fontsource-variable/*`, imported in `main.tsx`) — never a CDN, because the
app must render identically with no network.

The scale runs 11 → 28px in eight steps. It is deliberately compressed at the
small end, where this app does most of its work, and jumps at the top so a page
title is unmistakably a page title:

| Token | Size | Used for |
|---|---|---|
| `3xs` | 11px | caps micro-labels, tag pills |
| `2xs` | 12px | counts, badges, table meta |
| `xs` | 13px | secondary text, descriptions |
| `sm` | 14px | dense body, table cells, controls |
| `md` | 15px | body |
| `lg` | 17px | card and section headings |
| `xl` | 20px | detail-sheet titles |
| `2xl` | 28px | page titles |

Rules:

- **Mono is reserved.** File paths, config keys, JSON, and uppercase
  caps-tracked labels. It is a signal that the text is literal, not prose —
  using it decoratively destroys that signal.
- **Tabular numerals everywhere.** Set globally on `body`. Every number in this
  app lives in a table cell, a badge, or a sidebar counter, and none of them
  may reflow as counts change.
- **Tracking follows size.** Display sizes tighten (`--tracking-tight`), body
  sits at `--tracking-snug`, and uppercase labels open up (`--tracking-caps`).
  Uppercase text without added tracking is never acceptable.
- Headings are `--weight-semibold`. `--weight-bold` is for emphasis inside
  running text and badge numerals, not for headings.

## Colour & themes

Both themes are first-class. `data-theme` is written to `<html>` by the
bootstrap script in `frontend/index.html` **before first paint** and kept in
sync by `lib/theme.tsx`, so the palettes key off that attribute alone. There is
no `prefers-color-scheme` fallback in CSS and none should be added — a second
mechanism is a second thing to keep in step.

**Dark** is a near-black `#0b0c0f` page with warm parchment text. **Light** is
a cream `#f8f5ed` page with white cards.

**The accent is blue in both themes, and the brand amber is not the accent.**
This is the load-bearing decision in the palette, and it is counter-intuitive
enough to be worth defending. HarnessAM exists to surface drift, review queues,
and starred items — all of which are amber. Making the primary action amber too
would put "Capture all" in direct visual competition with "4 Drifted" on the
same screen. So the roles are split:

| Hue | Means |
|---|---|
| Blue | interactive — primary actions, focus, links, coverage counts |
| Amber | attention — warnings, drift, review queues, starred rows, the logo mark |
| Green | healthy, in sync |
| Red | destructive |

The brand amber is not diminished by this; it still carries the logo, the star,
selection highlight, and every warning. It simply is not also the button
colour.

Each theme tunes its own hex values for contrast against its own surfaces —
nothing is shared across themes except intent. `--color-accent-strong` is the
hover step and is *brighter* than `accent` on dark, *darker* on light, so it
always reads as more emphatic against whatever is behind it.

Every foreground colour here clears WCAG AA (4.5:1) as text on both the page
and a card, and `--color-star` clears the 3:1 floor for a UI glyph. That is a
constraint, not an observation: the light accent used to be amber at 4.28:1 on
white and 3.93:1 on cream, which failed. If you retune a colour, check it —
`--color-star` and the light accent have the least headroom.

## Elevation & depth

Four surface steps, in both themes: `sunken` → `bg` → `surface` → `raised`.
Depth comes from these tonal steps plus 1px borders; shadows
(`--shadow-sm/md/panel/lift`) are reserved for things that genuinely float —
dialogs, popovers, the bulk-action bar.

`--color-surface-raised` is the fill for hover, active, and chip states, which
means it carries a hard constraint: **it must stay visible against the page,
the sidebar, and a white card at the same time.** In light mode that forces a
warm tint rather than white. If `raised` ever equals `surface`, every hover
state inside a card silently disappears.

`--color-overlay-subtle` / `--color-overlay-sheen` are neutral washes derived
from the theme's own text colour, for skeletons and hairlines. Use them instead
of a white or black `rgba()`, which only works in one theme.

## Shape

Radii scale with the element: `2xs` (3px) for controls under ~16px, `sm` for
buttons and inputs, `md` for inline panels and notes, `lg` for cards and
dialogs, `pill` for action pills and chips.

The `2xs` step exists for a reason — at 14px, a 6px radius reads as a circle,
and a circular checkbox reads as a radio button. Check small controls visually
rather than assuming the next step down is fine.

## Layout & spacing

A 4px baseline with a ten-step scale. Prefer the named steps over arithmetic:
reaching for `--space-7` (24px) instead of `calc(var(--space-4) * 2)` keeps the
rhythm legible to the next reader.

The shell is a fixed 256px sidebar plus a fluid main pane capped at 1200px.
Pages are built from shared primitives rather than per-feature layout:

- `.page-shell` — the column, gap, and max width
- `.page-chrome` — sticky header + filters, with a fade masking rows scrolling
  underneath
- `.page-header` — title, subtitle, and right-aligned actions
- `.matrix-table` — the shared extension × harness matrix
- `.empty-panel` — empty and no-results states

A new screen should compose these, not reimplement them. If a page needs
spacing the primitives do not give it, that is usually a sign the primitive
should change.

## Components

**Buttons.** `.action-pill` is the universal interactive language — ghost pill,
`--md` and `--lg` size modifiers, `--accent` for a page's primary action,
`--danger` for destructive triggers. The solid `.btn` family
(`btn-primary` / `btn-secondary` / `btn-ghost` / `btn-static`) is reserved for
confirmation footers where a binary Cancel | Confirm should carry more weight.
Do not introduce a third button style.

**Status.** `.ui-status-badge` is the uppercase mono badge for state
(`success` / `warning` / `neutral` / `muted`). `.card-status-pill` is its
ghost-pill cousin, for when a status sits in a row of action pills and should
match their shape.

**Notes.** `.detail-note` (`DetailNote`) is the in-body highlight surface for a
caveat, a drift report, or a destructive-cleanup offer, with `warning` /
`danger` / `info` tones and optional title and actions.

**Focus.** One ring, `--focus-ring`, on every interactive element — a crisp 1px
accent edge plus a soft halo, so it stays legible on the page background, on a
card, and on a raised fill alike. `--focus-ring-danger` mirrors it for
destructive controls. Never `outline: none` without replacing the ring.

**Harness marks.** Real brand logos, rendered at their true colours.
Monochrome source marks are normalised per theme in
`styles/components/harness.css`; everything else is left alone. Do not recolour
a vendor's mark to fit the palette. Unavailable or unmanaged states are
expressed with `grayscale()` and opacity, never by substituting a colour.

## Motion

Two durations — `--duration-fast` (120ms) for colour and background changes,
`--duration-medium` (200ms) for movement — and one curve, `--ease-out`. Motion
acknowledges input; it does not perform. Anything that animates position must
respect `prefers-reduced-motion`.
