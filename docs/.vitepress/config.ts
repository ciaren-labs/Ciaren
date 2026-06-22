import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'FlowFrame',
  description: 'Visual ETL builder — Simple, local-first data pipelines on polars or pandas',
  lang: 'en-US',

  head: [
    ['meta', { name: 'theme-color', content: '#7c3aed' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:locale', content: 'en' }],
  ],

  lastUpdated: true,
  cleanUrls: true,

  ignoreDeadLinks: true,

  markdown: {
    lineNumbers: true,
    math: false,
  },

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'FlowFrame',

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
        text: 'Examples',
        link: '/examples/sales-analysis',
        activeMatch: '/examples/',
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
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/getting-started' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick Start (5 min)', link: '/guide/quick-start' },
            { text: 'Interface Tour', link: '/guide/interface' },
          ],
        },
        {
          text: 'Features',
          items: [
            { text: 'Projects & Runs', link: '/guide/projects-and-runs' },
            { text: 'Engines (polars / pandas)', link: '/guide/engines' },
            { text: 'Scheduling', link: '/guide/scheduling' },
            { text: 'CLI Reference', link: '/guide/cli' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'Design System', link: '/guide/design-system' },
          ],
        },
        {
          text: 'Help',
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
      ],

      '/examples/': [
        {
          text: 'Real-World Examples',
          items: [
            { text: 'Sales Analysis', link: '/examples/sales-analysis' },
            { text: 'Customer Segmentation', link: '/examples/customer-segmentation' },
            { text: 'Time Series', link: '/examples/time-series' },
            { text: 'Data Quality Checks', link: '/examples/data-quality' },
          ],
        },
      ],

      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'REST API', link: '/api/rest-api' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/rodrigo-arenas/FlowFrame' },
    ],

    search: {
      provider: 'local',
    },

    editLink: {
      pattern: 'https://github.com/rodrigo-arenas/FlowFrame/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the Apache License 2.0.',
      copyright: 'Copyright © 2026 Rodrigo Arenas',
    },
  },
})
