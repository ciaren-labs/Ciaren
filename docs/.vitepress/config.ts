import { defineConfig } from 'vitepress'

const gaMeasurementId = process.env.VITEPRESS_GA_ID
const docsOrigin = 'https://ciaren.com/docs'
const socialImage = `${docsOrigin}/Ciaren.png`

// Set by CI to build a pinned version snapshot at /v/<tag>/ instead of the
// root site. DOCS_VERSIONS_JSON is the full list of stable releases that
// have a snapshot, shared across every build in a deploy so the "Versions"
// nav item is identical whether this is the root build or a snapshot build.
const docsBasePath = process.env.DOCS_BASE_PATH || '/'
const stableVersions: string[] = (() => {
  try {
    return JSON.parse(process.env.DOCS_VERSIONS_JSON || '[]')
  } catch {
    return []
  }
})()

function pageUrl(page: string) {
  const path = page
    .replace(/\\/g, '/')
    .replace(/(^|\/)index\.md$/, '$1')
    .replace(/\.md$/, '')
    .replace(/^\/+/, '')

  return path ? `${docsOrigin}/${path}` : `${docsOrigin}/`
}

// Shared sidebar for the developer-facing extensibility docs (plugins + the
// public .flow / manifest schemas). Reused across /plugins/, /specs/, /security/.
// Plugins are a first-class concept in Ciaren, so this sidebar leads with the
// overview (the extension-points map) before the how-to and reference pages.
const extendingSidebar = [
  {
    text: 'Plugins & Extensibility',
    items: [
      { text: 'Overview', link: '/plugins/overview' },
      { text: 'Build Your First Plugin', link: '/plugins/first-plugin' },
      { text: 'Writing a Plugin', link: '/plugins/writing-a-plugin' },
      { text: 'Packaging & Distribution', link: '/plugins/packaging-and-distribution' },
    ],
  },
  {
    text: 'Reference',
    items: [
      { text: 'Plugin API Reference', link: '/plugins/api-reference' },
      { text: '.flow Document Format', link: '/specs/flow-format' },
      { text: 'Plugin Manifest', link: '/specs/plugin-manifest' },
    ],
  },
  {
    text: 'Security & Trust',
    items: [
      { text: 'Plugin Security & Permissions', link: '/security/plugin-security' },
      { text: 'Local-First Trust Model', link: '/security/local-first-trust-model' },
    ],
  },
]

export default defineConfig({
  title: 'Ciaren',
  description:
    'Open-source, plugin-first platform for building Data Engineering and Machine Learning workflows visually — and exporting clean, portable pandas/polars Python. Local-first, no lock-in.',
  lang: 'en-US',
  base: docsBasePath,
  srcExclude: ['README.md'],

  head: [
    ['meta', { name: 'theme-color', content: '#7c3aed' }],
    ...(gaMeasurementId
      ? [
          ['script', { async: '', src: `https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}` }],
          [
            'script',
            {},
            `window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', ${JSON.stringify(gaMeasurementId)});`,
          ],
        ]
      : []),
    // Open Graph — controls how links render on GitHub, Reddit, HN, Slack, etc.
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:locale', content: 'en' }],
    ['meta', { property: 'og:site_name', content: 'Ciaren' }],
    ['meta', { property: 'og:title', content: 'Ciaren — Visual Data Engineering & ML, exported to clean Python' }],
    ['meta', {
      property: 'og:description',
      content:
        'Open-source, plugin-first, local-first platform for building Data Engineering and Machine Learning workflows visually — with portable pandas/polars code export.',
    }],
    ['meta', { property: 'og:image', content: socialImage }],
    // Twitter / X card
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'Ciaren — Visual Data Engineering & ML, exported to clean Python' }],
    ['meta', {
      name: 'twitter:description',
      content:
        'Open-source, plugin-first, local-first platform for Data Engineering and Machine Learning workflows. Build visually, export portable Python.',
    }],
    ['meta', { name: 'twitter:image', content: socialImage }],
  ],

  sitemap: {
    hostname: docsOrigin,
  },

  transformHead({ page }) {
    const url = pageUrl(page)

    return [
      ['link', { rel: 'canonical', href: url }],
      ['meta', { property: 'og:url', content: url }],
    ]
  },

  lastUpdated: true,
  cleanUrls: true,

  ignoreDeadLinks: true,

  markdown: {
    lineNumbers: true,
    math: false,
  },

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'Ciaren',

    nav: [
      {
        text: 'Guide',
        link: '/guide/getting-started',
        activeMatch: '/guide/',
      },
      {
        text: 'Transformations',
        link: '/transformations/overview',
        activeMatch: '/transformations/',
      },
      {
        text: 'Machine Learning',
        link: '/guide/ml-quickstart',
        activeMatch: '/(guide/ml-quickstart|transformations/machine-learning)',
      },
      {
        text: 'Plugins',
        link: '/plugins/overview',
        activeMatch: '/(plugins|specs|security)/',
      },
      {
        text: 'Examples',
        link: '/examples/sales-analysis',
        activeMatch: '/examples/',
      },
      {
        text: 'Recipes',
        link: '/recipes/overview',
        activeMatch: '/recipes/',
      },
      {
        text: 'API',
        link: '/api/rest-api',
        activeMatch: '/api/',
      },
      {
        text: 'FAQ',
        link: '/faq',
      },
      // Root-relative nav links get prefixed with *this build's* `base`, so a
      // /v/0.1.0/ snapshot build would turn '/v/0.2.0/' into
      // '/v/0.1.0/v/0.2.0/'. Fully-qualified docsOrigin links sidestep that
      // and resolve the same way from every snapshot.
      ...(stableVersions.length > 0
        ? [
            {
              text: 'Versions',
              items: [
                { text: 'latest', link: `${docsOrigin}/` },
                ...[...stableVersions].reverse().map((v) => ({ text: v, link: `${docsOrigin}/v/${v}/` })),
              ],
            },
          ]
        : []),
      {
        text: '⭐ Star on GitHub',
        link: 'https://github.com/ciaren-labs/Ciaren',
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/getting-started' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Advanced Setup', link: '/guide/advanced-setup' },
            { text: 'Quick Start (5 min)', link: '/guide/quick-start' },
            { text: 'Demo Project & Tutorials', link: '/guide/demo-project' },
            { text: 'Interface Tour', link: '/guide/interface' },
            { text: 'How Ciaren Compares', link: '/guide/comparison' },
          ],
        },
        {
          text: 'Data Engineering',
          items: [
            { text: 'Projects & Runs', link: '/guide/projects-and-runs' },
            { text: 'Database Connections', link: '/guide/connections' },
            { text: 'Engines (polars / pandas)', link: '/guide/engines' },
            { text: 'Flow Parameters', link: '/guide/parameters' },
            { text: 'Scheduling', link: '/guide/scheduling' },
            { text: 'Webhook Trigger', link: '/guide/webhook' },
            { text: 'Python SDK', link: '/guide/sdk' },
            { text: 'CLI Reference', link: '/guide/cli' },
          ],
        },
        {
          text: 'Machine Learning',
          items: [
            { text: 'ML Quick Start', link: '/guide/ml-quickstart' },
            { text: 'ML Nodes Reference', link: '/transformations/machine-learning' },
            { text: 'Visualizations', link: '/guide/visualizations' },
          ],
        },
        {
          text: 'Plugins & Extensibility',
          items: [
            { text: 'Overview', link: '/plugins/overview' },
            { text: 'Build Your First Plugin', link: '/plugins/first-plugin' },
            { text: 'Writing a Plugin', link: '/plugins/writing-a-plugin' },
            { text: 'Plugin API Reference', link: '/plugins/api-reference' },
            { text: 'Packaging & Distribution', link: '/plugins/packaging-and-distribution' },
            { text: 'Plugin Security & Permissions', link: '/security/plugin-security' },
          ],
        },
        {
          text: 'Deployment',
          collapsed: true,
          items: [
            { text: 'Docker', link: '/guide/docker' },
          ],
        },
        {
          text: 'Reference',
          collapsed: true,
          items: [
            { text: 'Design System', link: '/guide/design-system' },
          ],
        },
        {
          text: 'Community',
          collapsed: true,
          items: [
            { text: 'Roadmap', link: '/guide/roadmap' },
            { text: 'How Ciaren Compares', link: '/guide/comparison' },
          ],
        },
        {
          text: 'Help',
          collapsed: true,
          items: [
            { text: 'Troubleshooting', link: '/guide/troubleshooting' },
            { text: 'FAQ', link: '/faq' },
          ],
        },
      ],

      '/transformations/': [
        {
          text: 'Reference',
          items: [{ text: 'All Transformations', link: '/transformations/overview' }],
        },
        {
          text: 'Input & Output',
          items: [
            { text: 'File input (CSV/Excel/Parquet)', link: '/transformations/file-input' },
            { text: 'File output (CSV/Excel/Parquet)', link: '/transformations/file-output' },
            { text: 'SQL input', link: '/transformations/sql-input' },
            { text: 'SQL output', link: '/transformations/sql-output' },
          ],
        },
        {
          text: 'Columns',
          items: [
            { text: 'Drop columns', link: '/transformations/drop-columns' },
            { text: 'Rename columns', link: '/transformations/rename-columns' },
            { text: 'Select columns', link: '/transformations/select-columns' },
            { text: 'Cast types', link: '/transformations/cast-types' },
            { text: 'Combine columns', link: '/transformations/combine-columns' },
            { text: 'Coalesce columns', link: '/transformations/coalesce-columns' },
          ],
        },
        {
          text: 'Nulls',
          items: [
            { text: 'Drop nulls', link: '/transformations/drop-nulls' },
            { text: 'Fill nulls', link: '/transformations/fill-nulls' },
          ],
        },
        {
          text: 'Rows',
          items: [
            { text: 'Filter rows', link: '/transformations/filter-rows' },
            { text: 'Filter by expression', link: '/transformations/filter-expression' },
            { text: 'Sort rows', link: '/transformations/sort-rows' },
            { text: 'Limit rows', link: '/transformations/limit-rows' },
            { text: 'Sample rows', link: '/transformations/sample-rows' },
            { text: 'Remove duplicates', link: '/transformations/remove-duplicates' },
          ],
        },
        {
          text: 'Text',
          collapsed: true,
          items: [
            { text: 'Replace values', link: '/transformations/replace-values' },
            { text: 'String transform', link: '/transformations/string-transform' },
            { text: 'Split column', link: '/transformations/split-column' },
            { text: 'Map values', link: '/transformations/map-values' },
          ],
        },
        {
          text: 'Numeric',
          collapsed: true,
          items: [
            { text: 'Round numbers', link: '/transformations/round-numbers' },
            { text: 'Remove outliers', link: '/transformations/remove-outliers' },
            { text: 'Bin column', link: '/transformations/bin-column' },
          ],
        },
        {
          text: 'Reshape & combine',
          collapsed: true,
          items: [
            { text: 'Calculated column', link: '/transformations/calculated-column' },
            { text: 'Group by + aggregate', link: '/transformations/group-by-aggregate' },
            { text: 'Join', link: '/transformations/join' },
            { text: 'Union / Concat', link: '/transformations/union-concat' },
            { text: 'Pivot', link: '/transformations/pivot' },
            { text: 'Unpivot', link: '/transformations/unpivot' },
            { text: 'Extract date parts', link: '/transformations/extract-date-parts' },
            { text: 'Parse dates', link: '/transformations/parse-dates' },
            { text: 'Split to rows', link: '/transformations/split-to-rows' },
          ],
        },
        {
          text: 'Analytics',
          collapsed: true,
          items: [
            { text: 'Window function', link: '/transformations/window-function' },
            { text: 'Conditional column', link: '/transformations/conditional-column' },
            { text: 'Rolling aggregate', link: '/transformations/rolling-aggregate' },
            { text: 'Row difference', link: '/transformations/row-difference' },
            { text: 'Date difference', link: '/transformations/date-difference' },
          ],
        },
        {
          text: 'Data Quality',
          collapsed: true,
          items: [
            { text: 'Assert not null', link: '/transformations/assert-not-null' },
            { text: 'Assert unique', link: '/transformations/assert-unique' },
            { text: 'Assert value range', link: '/transformations/assert-value-range' },
            { text: 'Assert expression', link: '/transformations/assert-expression' },
            { text: 'Assert row count', link: '/transformations/assert-row-count' },
            { text: 'Assert values in set', link: '/transformations/assert-values-in-set' },
          ],
        },
        {
          text: 'Advanced',
          collapsed: true,
          items: [
            { text: 'Python transform', link: '/transformations/python-transform' },
          ],
        },
        {
          text: 'Machine Learning',
          collapsed: true,
          items: [
            { text: 'ML nodes', link: '/transformations/machine-learning' },
          ],
        },
      ],

      '/examples/': [
        {
          text: 'Data Engineering',
          items: [
            { text: 'Sales Analysis', link: '/examples/sales-analysis' },
            { text: 'Customer Segmentation', link: '/examples/customer-segmentation' },
            { text: 'Time Series', link: '/examples/time-series' },
            { text: 'Data Quality Checks', link: '/examples/data-quality' },
            { text: 'DuckDB Analytics', link: '/examples/duckdb-analytics' },
          ],
        },
        {
          text: 'Machine Learning',
          items: [
            { text: 'Customer Churn Classification', link: '/examples/ml-classification' },
            { text: 'Feature Engineering', link: '/examples/feature-engineering' },
          ],
        },
        {
          text: 'More',
          items: [
            { text: 'Recipes (quick tasks)', link: '/recipes/overview' },
          ],
        },
      ],

      '/recipes/': [
        {
          text: 'Recipes',
          items: [
            { text: 'Overview', link: '/recipes/overview' },
            { text: 'Convert Excel to Parquet', link: '/recipes/convert-excel-to-parquet' },
            { text: 'Remove Duplicate Rows', link: '/recipes/remove-duplicate-rows' },
            { text: 'Fill Missing Values', link: '/recipes/fill-missing-values' },
            { text: 'Pivot a Table', link: '/recipes/pivot-a-table' },
          ],
        },
      ],

      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/rest-api' },
          ],
        },
        {
          text: 'Resources',
          items: [
            { text: 'Projects', link: '/api/projects' },
            { text: 'Datasets', link: '/api/datasets' },
            { text: 'Flows', link: '/api/flows' },
            { text: 'Runs', link: '/api/runs' },
            { text: 'Transformations', link: '/api/transformations' },
            { text: 'Catalog & Plugins', link: '/api/catalog' },
            { text: 'Schedules', link: '/api/schedules' },
            { text: 'Connections', link: '/api/connections' },
          ],
        },
        {
          text: 'Automation',
          items: [
            { text: 'Webhook Trigger', link: '/guide/webhook' },
            { text: 'Python SDK', link: '/guide/sdk' },
          ],
        },
      ],

      '/plugins/': extendingSidebar,
      '/specs/': extendingSidebar,
      '/security/': extendingSidebar,
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/ciaren-labs/Ciaren' },
    ],

    search: {
      provider: 'local',
    },

    editLink: {
      pattern: 'https://github.com/ciaren-labs/Ciaren/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message:
        '<a href="https://github.com/ciaren-labs/Ciaren" target="_blank" rel="noreferrer">GitHub</a> · ' +
        '<a href="https://github.com/ciaren-labs/Ciaren/discussions" target="_blank" rel="noreferrer">Discussions</a> · ' +
        '<a href="https://github.com/ciaren-labs/Ciaren/issues" target="_blank" rel="noreferrer">Issues</a> · ' +
        '<a href="https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer">Contributing</a><br>' +
        'Released under the Apache License 2.0. Created by ' +
        '<a href="https://www.rodrigo-arenas.com/" target="_blank" rel="noreferrer">Rodrigo Arenas</a> ' +
        '(<a href="https://github.com/rodrigo-arenas" target="_blank" rel="noreferrer">GitHub</a>).',
      copyright:
        'Copyright © 2026 <a href="https://www.rodrigo-arenas.com/" target="_blank" rel="noreferrer">Rodrigo Arenas</a>',
    },
  },
})
