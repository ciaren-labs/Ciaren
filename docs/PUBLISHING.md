# Publishing to ciaren.com

These docs live here, but they are **also** published at
[ciaren.com/docs](https://ciaren.com/docs). This page is the contract between
what you write here and what readers see there — follow it and your page
publishes cleanly; step outside it and the sync fails loudly (which is better
than shipping broken output).

> **TL;DR** — Write normal Markdown, VitePress containers (`::: tip`), and the
> documented custom components below. Everything else (raw HTML components,
> `<script>`, arbitrary Vue) does **not** publish. Preview locally with
> `npm run dev` for content and structure; the visual styling on ciaren.com is
> intentionally different (see [Visual parity](#visual-parity)).

## How publishing works

- `docs/` here is **VitePress source**. The public site is a **separate
  Next.js project** that pulls this `docs/` tree after a release and transforms
  it into its own MDX + design system. The sync is **one-way and manual** —
  this repo never needs to know the website exists.
- The transform re-renders every page in **ciaren.com's own design system**
  (its typography, colors, light/dark themes). It does **not** reuse VitePress's
  CSS or your `.vue` component styling — it maps each custom component to a
  hand-built React equivalent that matches the site.
- **Security boundary:** the transform **never executes JavaScript** from these
  docs. Custom-component data is passed as validated JSON *strings* that the
  React components parse themselves. That is why the supported surface is a
  fixed catalog, not "any Vue component" — see below.

## Golden rules

1. **Use only the documented components** (next section). A capitalized tag the
   website doesn't recognize **fails the sync**.
2. **No `<script>`, no inline event handlers, no arbitrary raw HTML components.**
   Plain inline HTML that Markdown already allows (`<br>`, `<sub>`, `<kbd>`) is
   fine; capitalized/custom components are not.
3. **Custom-component data must be valid JSON.** A malformed `:nodes='…'` bind
   fails the sync with a clear error rather than rendering broken on the site.
4. **Show example component markup inside code fences.** ```` ```vue ````
   blocks and `` `inline code` `` are treated as literal text, so you can
   document `<FlowPipeline>` usage without the guard flagging it.
5. **Reference assets by root-relative path** (`/screenshots/…`, `/samples/…`).
   Everything under `public/` is mirrored to the site automatically — see
   [Assets](README.md#assets).

## Supported components

All of these already exist as Vue components under
`.vitepress/theme/components/`. Author them exactly as you do today; the props
below are what survives to ciaren.com. Data props use Vue's `:prop='json'` bind
syntax and must contain **valid JSON**.

### Pipeline diagrams

Pipeline **node** objects share a shape:

```json
{ "type": "input", "label": "File Input", "detail": "applicants.csv" }
```

`type` drives the node's color/icon. Recognized values:
`input`, `clean`, `transform`, `output`, `ml`. Anything else renders in a
neutral gray with a default icon — so a typo won't break the build, it just
loses its category color.

**`<FlowPipeline>`** — a linear pipeline.

```vue
<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"applicants.csv"},
  {"type":"clean","label":"Fill Nulls","detail":"income → median"},
  {"type":"ml","label":"Scale Features","detail":"standard: age, income"}
]' :vertical="true" />
```

- `:nodes` — array of node objects (required).
- `:vertical` — `true` stacks the nodes; omit for horizontal.

**`<ForkJoin>`** — two inputs merging through a join.

```vue
<ForkJoin
  :left='[{"type":"transform","label":"Left input","detail":"orders by customer"}]'
  :right='[{"type":"input","label":"Right input","detail":"customers.csv"}]'
  :join='{"label":"Join","detail":"on: customer_id · how: left"}'
  :after='[{"type":"transform","label":"Enriched result","detail":"transactions + name"}]'
/>
```

- `:left`, `:right`, `:after` — arrays of node objects.
- `:join` — a single `{ "label", "detail" }` object.

### Data & parameters

**`<DataTransform>`** — a before/after table view of a transformation.

```vue
<DataTransform
  transform="Full flow"
  :before='{"columns":["name","email","age"],"rows":[["  Ada ","ADA@X.COM",36]]}'
  :after='{"columns":["name","email","age"],"rows":[["Ada","ada@x.com",36]]}'
  :highlight='["age"]'
/>
```

- `transform` — a plain string label (not a bind).
- `:before`, `:after` — `{ "columns": string[], "rows": (string|number|null)[][] }`.
- `:highlight` — optional array of column names to emphasize.

**`<ParamFlow>`** — how parameters resolve (defaults → overrides).

```vue
<ParamFlow
  :params='[{"name":"keep","type":"integer","default":"100","description":"Max rows"}]'
  :nodeExample='{"label":"Limit Rows","field":"Number of rows","ref":"keep"}'
  :overrides='[{"source":"run","label":"Per-run override","value":"highest priority"}]'
/>
```

- `:params` — array of `{ "name", "type", "default", "description" }`.
- `:nodeExample` — `{ "label", "field", "ref" }`; `ref` points at a param name.
- `:overrides` — array of `{ "source", "label", "value" }`; `source` is one of
  `run`, `schedule`, `default`.

### Static diagrams (no props)

These take **no data** — just drop the tag on its own line:

- **`<NodeCategoryGrid />`** — the transformation-category overview grid. Its
  internal links are pointed at the correct `/docs/<version>/…` path
  automatically.
- **`<DomainModel />`** — the projects/runs/schedules domain diagram.
- **`<ScheduleCycle />`** — the schedule lifecycle diagram.
- **`<EditorLayout />`** — the flow-editor anatomy diagram.

## The home page

`index.md` uses VitePress's `layout: home`. Its `hero`, `features`, and the
hand-authored `.ciaren-proof-grid` / `.ciaren-path-grid` / `.ciaren-next-grid`
blocks are all rendered into styled components on ciaren.com. If you add a
**new** `ciaren-*` grid class, the sync fails until the website adds a matching
renderer — coordinate that change with the website repo before merging.

## Visual parity

The website deliberately **re-styles** these docs rather than mirroring
VitePress pixel-for-pixel. So:

- **Content and structure parity is exact** — what you write is what publishes,
  and anything unsupported fails the sync instead of silently degrading.
- **Visual styling is intentionally different** — `npm run dev` shows the
  VitePress rendering; ciaren.com applies its own theme. Don't chase
  pixel-identical output; author for correct content and use the components
  above, and the site handles the look.

## What fails the sync (so you can fix it here first)

The website's transform rejects a page — with a message naming the problem —
when it finds:

- an **unhandled `:::` container** (only `tip`/`info`/`warning`/`danger`/
  `details`/`code-group` are supported);
- a **component tag it doesn't recognize**, or a leftover Vue `:prop=` bind on
  one it can't map;
- an **un-rendered `ciaren-*` home grid**;
- **malformed JSON** in any custom-component bind;
- a **broken internal link or missing asset**.

All of these also fail `npm run build` / `npm run test:links` here, so running
the [local checks](README.md#deployment) before pushing catches them early.

---

Questions about the pipeline itself belong with the website repo; questions
about doc content and standards are in [CONTRIBUTING.md](../CONTRIBUTING.md).
