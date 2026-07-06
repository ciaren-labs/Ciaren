# Design System

Ciaren uses a **purple-based, minimalist** visual language. This page is the
single source of truth for colour, type, spacing, motion and component style —
the web app and this documentation site share the same palette.

::: info
This page is the single source of truth for the Ciaren visual language. The
web app (`frontend/`) and this documentation site share the same purple palette.
Token references point at the live implementation in `frontend/src/`.
:::

> For contributors: tokens live in `frontend/src/index.css` as CSS variables and
> are exposed to Tailwind in `frontend/tailwind.config.js`. Never hard-code hex
> values in components — use the semantic token (`bg-primary`, `text-muted-foreground`,
> `border-border`, `bg-brand-50`, …).

## Brand palette (purple)

The brand ramp is a single violet hue stepped from tint to shade. Use `brand-600`
as the canonical brand colour (it is also `--primary`).

| Token | HSL | Use |
| --- | --- | --- |
| `brand-50` | `270 70% 98%` | page tints, hover wash |
| `brand-100` | `269 70% 95%` | subtle fills, chips |
| `brand-200` | `268 72% 90%` | borders on tinted cards, canvas dots |
| `brand-300` | `266 74% 82%` | muted accents |
| `brand-400` | `264 78% 71%` | gradients, secondary accents |
| `brand-500` | `262 83% 62%` | hover state of primary |
| `brand-600` | `262 83% 58%` | **primary / brand** |
| `brand-700` | `263 70% 50%` | pressed primary, links |
| `brand-800` | `263 67% 41%` | headings on tint |
| `brand-900` | `264 60% 33%` | deepest shade |

## Semantic tokens

| Token | Light | Meaning |
| --- | --- | --- |
| `background` | `270 40% 99%` | app background (faint purple white) |
| `foreground` | `265 32% 12%` | primary text |
| `card` | `0 0% 100%` | raised surfaces |
| `primary` | `262 83% 58%` | brand actions, focus ring |
| `secondary` | `270 30% 96%` | secondary buttons / fills |
| `muted` / `muted-foreground` | `270 28% 96%` / `264 12% 46%` | subdued surfaces & text |
| `accent` / `accent-foreground` | `266 85% 96%` / `262 72% 42%` | hover/selected wash |
| `border` | `270 24% 91%` | hairlines |
| `ring` | `262 83% 58%` | focus outline |

### Status colours

| Token | HSL | Use |
| --- | --- | --- |
| `success` | `160 70% 40%` | succeeded runs, valid state |
| `warning` | `38 92% 50%` | drift, outdated version pins |
| `info` | `215 85% 56%` | running / informational |
| `destructive` | `351 75% 53%` | failed runs, delete, errors |

A dark theme is defined under `.dark` (enable via the `class` strategy) using the
same token names, so components need no changes to support it.

## Flow node categories

Nodes stay distinguishable on the canvas while harmonising with the brand. Each
category has a badge / card / ring / text / dot theme in
`frontend/src/lib/nodeVisuals.ts`. There are 9 categories, 72 nodes total (66
transformation nodes, including the 8 chart nodes, plus 6 file/SQL/storage
input-output nodes):

| Category | Hue | Example nodes |
| --- | --- | --- |
| **Inputs** | emerald | File Input, SQL Input, Storage Input |
| **Cleaning** | sky | drop/fill nulls, remove duplicates, filter rows, sort rows |
| **Columns** | indigo | rename, select, drop, split, map values, string transform |
| **Reshape** | violet | group by, join, pivot/unpivot, concat rows |
| **Analytics** | fuchsia | calculated column, window function, bin column, parse dates |
| **Data Quality** | orange | assert not-null/unique/range/expression/row-count |
| **Charts** | rose | bar, line, area, scatter, pie, histogram, box plot, correlation heatmap |
| **Machine Learning** | purple | train/predict/evaluate, feature engineering, cross-validate |
| **Outputs** | amber | File Output, SQL Output, Storage Output |

## Typography

- Family: system UI stack (`ui-sans-serif, system-ui, "Segoe UI", Roboto`).
- Headings: semibold, tight tracking. Page titles `text-xl`/`text-2xl`.
- Body: `text-sm` is the default density; secondary text uses `text-muted-foreground`.
- Numerals/code: monospace only for code export and column/type chips.

## Radius, elevation, spacing

- Radius: `--radius: 0.65rem` (`rounded-lg`/`md`/`sm` derive from it). Cards and
  panels use `rounded-xl`; chips use `rounded-md`.
- Elevation: prefer hairline borders + `shadow-sm`; reserve `shadow-md` for hover
  and floating surfaces (dialogs, dropdowns, drag ghosts).
- Spacing: 4-pt scale. Panel padding `p-4`/`p-5`; gaps `gap-2`/`gap-3`.

## Motion

Small and quick — never distracting. Keyframes in `tailwind.config.js`:

| Class | Duration | Use |
| --- | --- | --- |
| `animate-fade-in` | 180ms | content swaps |
| `animate-fade-in-up` | 220ms | cards/rows entering |
| `animate-slide-in-right` | 200ms | side panels |
| `animate-scale-in` | 140ms | popovers, menus |

Respect `prefers-reduced-motion`; keep transitions ≤ 250ms.

## Gradients

`brand-gradient` (135° `brand-600 → fuchsia`) for hero chrome, and
`brand-text-gradient` for the wordmark. Use sparingly — one hero accent per view.
