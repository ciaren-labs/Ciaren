# Publishing to ciaren.com

These docs live here, but they are **also** published at
[ciaren.com/docs](https://ciaren.com/docs/latest). This page is the contract between
what you write here and what readers see there — follow it and your page
publishes cleanly; step outside it and the sync fails loudly (which is better
than shipping broken output).

Write normal Markdown, VitePress containers (`::: tip`), and the documented
custom components below. Scripts and arbitrary Vue components do not publish.
Preview with `npm run dev`, then check the imported website rendering before
publishing changes to navigation, components or styles.

## How publishing works

- `docs/` here is **VitePress source**. The public site is a **separate
  Next.js project** that imports this tree and transforms it into MDX. The sync
  is **one-way and manual**: change content here, commit it, then import that
  Git ref in the website repository. Do not edit generated website docs.
- The website maps custom Vue components to React equivalents. It has separate
  CSS, so changes to typography, colors, light/dark themes or component layouts
  require checks in both renderers to preserve the shared Ciaren identity.
- From the website repository, import the source and validate it:

  ```powershell
  pnpm sync:docs --repo=https://github.com/ciaren-labs/Ciaren.git --ref=main --strict
  pnpm check
  ```

  Use a release tag instead of `main` for a release import. `latest` follows the
  selected source ref; published version snapshots stay frozen. Without a
  configured source, a normal sync uses the committed website content, so use
  `--strict` when fresh source is required.
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
   Asset directories under `public/` are mirrored automatically. Put doc assets
   in those directories; loose root files such as site icons are not copied.
   See [Assets](README.md#assets).

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

## Navigation and page order

The website imports the navigation and sidebar definitions from
`.vitepress/config.ts` into a generated `_nav.json`. Top navigation, section
groups, labels, collapsed state and previous/next order therefore come from
the same source. The website opens the group containing the current page and
drops sidebar links to pages absent from that version.
Use section groups with direct page links: the current import supports two
sidebar levels, not nested subgroups.

- **Page titles** come from `title` frontmatter or the first `# Heading`.
- **Older snapshots without `_nav.json`** use folder groups and `_meta.json`
  ordering as a fallback. Keep `docs/_meta.json` current for new folders.
- **Body links** can use relative Markdown filenames or root-relative doc
  paths. The website resolves known pages to clean URLs within their version;
  external links and file downloads retain their original destination.
- **URL moves require website redirects.** The website has explicit redirects
  for historical documentation URLs, but does not infer arbitrary renames.
  Coordinate a redirect in its deployment configuration when moving a page;
  regroup pages through navigation when a move is unnecessary.

List each page **once** in the VitePress sidebars, so each topic keeps one
home in both renderings.

## Visual parity

Both renderers should feel like the same documentation: the same text,
navigation, examples, diagrams and Ciaren visual identity. The website's MDX
transform adapts syntax and components; it does not introduce a second copy
of the content to maintain.

For content changes, import the committed source and check links and examples.
For visual changes, compare both renderers in light and dark themes at desktop
and mobile widths. Check heading hierarchy, code blocks, tables, callouts and
custom diagrams. Shared source alone does not prove visual equivalence: the
Vue and React implementations and their CSS must be verified together.

## What fails the sync (so you can fix it here first)

The website's transform rejects a page — with a message naming the problem —
when it finds:

- an **unhandled `:::` container** (only `tip`/`info`/`warning`/`danger`/
  `details`/`code-group` are supported);
- a **component tag it doesn't recognize**, or a leftover Vue `:prop=` bind on
  one it can't map;
- an **un-rendered `ciaren-*` home grid**;
- **malformed JSON** in any custom-component bind.

The website sync checks supported syntax and components. Its `pnpm check`
validates the exported rendering and links. Here, `npm test` checks Markdown,
the VitePress build and source links. Run both repositories' checks; a green
VitePress build alone does not prove that the MDX import is supported.

VitePress 1.6 uses a scoped Vite 6.4 override in `package.json` to avoid the
unpatched Vite 5 dependency chain. This deliberately exceeds VitePress's
declared Vite range. When changing it, run `npm ci`, `npm audit --audit-level=high`
and `npm test`, then check direct and client-side navigation, search, theme
switching and custom Vue components in a browser. Vite 8 is not a drop-in
replacement for VitePress 1's generated lean page chunks.

---

Questions about the pipeline itself belong with the website repo; questions
about doc content and standards are in [CONTRIBUTING.md](../CONTRIBUTING.md).
