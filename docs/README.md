# Ciaren Documentation

User-facing documentation for Ciaren — built with VitePress and deployed to GitHub Pages.

## Quick Start

### Local Development

```bash
npm install
npm run dev
```

Visit `http://localhost:5173`

### Build

```bash
npm run build
```

Output is in `.vitepress/dist/`

### Lint Markdown

```bash
npm run lint
```

## Structure

```
├── index.md                           # Homepage
├── guide/                             # Product docs (projects/runs, interface,
│   ├── getting-started.md             # connections, scheduling, webhook, SDK,
│   ├── installation.md                # engines, advanced setup, etc.)
│   ├── quick-start.md
│   ├── interface.md
│   ├── projects-and-runs.md
│   ├── connections.md
│   ├── parameters.md
│   ├── scheduling.md
│   ├── webhook.md
│   ├── sdk.md
│   ├── engines.md
│   ├── design-system.md
│   ├── visualizations.md
│   ├── ml-quickstart.md
│   ├── docker.md
│   ├── advanced-setup.md
│   ├── demo-project.md
│   ├── comparison.md
│   ├── roadmap.md
│   ├── cli.md
│   └── troubleshooting.md
├── transformations/                   # Flat — one file per node, no subfolders
│   ├── overview.md
│   ├── filter-rows.md
│   ├── join.md
│   └── ...                            # (49 node pages total)
├── examples/
│   ├── sales-analysis.md
│   ├── customer-segmentation.md
│   ├── time-series.md
│   ├── data-quality.md
│   ├── feature-engineering.md
│   ├── ml-classification.md
│   └── duckdb-analytics.md
├── recipes/
│   ├── overview.md
│   ├── convert-excel-to-parquet.md
│   ├── fill-missing-values.md
│   ├── pivot-a-table.md
│   └── remove-duplicate-rows.md
├── api/
│   ├── rest-api.md
│   ├── catalog.md
│   ├── connections.md
│   ├── datasets.md
│   ├── flows.md
│   ├── projects.md
│   ├── runs.md
│   ├── schedules.md
│   └── transformations.md
├── plugins/
│   ├── overview.md
│   ├── first-plugin.md
│   ├── writing-a-plugin.md
│   ├── api-reference.md
│   ├── connector-plugins.md
│   ├── ml-model-plugins.md
│   ├── advanced-plugin-sklearn.md
│   ├── managing-plugins.md
│   ├── packaging-and-distribution.md
│   └── cli-reference.md
├── security/
│   ├── local-first-trust-model.md
│   └── plugin-security.md
├── specs/
│   ├── flow-format.md
│   └── plugin-manifest.md
├── legal/
│   ├── privacy.md
│   └── terms.md
├── faq.md
└── .vitepress/
    ├── config.ts              # VitePress configuration
    └── theme/
        ├── index.ts
        ├── components/
        └── styles/
```

Static assets (images, sample files, favicon) live in `public/` at the docs
root, not under `.vitepress/` — see [Assets](#assets) below.

## Writing Documentation

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution standards.

### Front Matter

Every page needs:

```yaml
---
title: Page Title
description: Brief description for search
search: keyword1 keyword2
---
```

### Navigation

Update `.vitepress/config.ts` to add pages to the sidebar.

### Code Examples

```markdown
:::info
Informational note
:::

:::warning
Important warning
:::

\`\`\`python
# Python code example
df = df.drop(columns=['col1'])
\`\`\`
```

## Adding Content

### New Page

1. Create `.md` file in appropriate folder
2. Add front matter (title, description)
3. Write content
4. Update `.vitepress/config.ts` sidebar (if needed)
5. Test: `npm run dev`

### New Transformation

Create file in `transformations/` (flat, no subfolders):

```markdown
---
title: Transformation Name
description: What it does
---

# [Transformation Name]

## Use Cases

## How It Works

## Configuration

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|

## Examples

## Tips

## See Also
```

### New Example

Create file in `examples/`:

```markdown
---
title: Example Name
description: What this example shows
---

# [Example Name]

## Overview

## Step-by-Step

## Download Sample Data

## Generated Python Code

\`\`\`python
# Exported code here
\`\`\`
```

## Deployment

This repo does not deploy the docs site. `docs-deploy.yml` only lints and
validates `docs/**` as a PR/push gate:

1. **Lint** — `npm run lint` (markdownlint).
2. **Build & test** — `npm run build`, then the build output is validated and
   checked for broken internal links (`npm run test:links`).

`ciaren.com/docs` is published elsewhere, pulled from `docs/` here manually
after cutting a release. There is no GitHub Pages
deploy and no automatic sync in either direction.

Run the same checks locally before pushing:

```bash
npm ci
npm run lint
npm run build
npm run test:links
```

## Assets

Store images and files in `public/` (the docs root, not `.vitepress/`):

```
public/
├── logo.svg
├── favicon.ico / favicon.svg
├── screenshots/
│   ├── your-screenshot.png
│   └── ...
└── samples/
    ├── sales.csv
    ├── customers.xlsx
    └── ...
```

Reference in markdown:

```markdown
![Alt text](/screenshots/your-screenshot.png)
[Download sample](/samples/sales.csv)
```

## Search

VitePress includes local search. No external service needed.

Search is built at build time from page titles, descriptions, and content.

## Style Guide

- **Tone:** Friendly, clear, beginner-friendly
- **Active voice:** "You can rename columns" not "Columns can be renamed"
- **Examples first:** Show before explaining
- **Avoid jargon:** Explain technical terms
- **Links:** Link related pages

## Performance

- No external fonts (uses system fonts)
- Syntax highlighting at build time
- No JavaScript animations
- ~40KB gzipped total

## Questions?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for complete contribution standards.

---

**Last Updated:** 2026-07-03
