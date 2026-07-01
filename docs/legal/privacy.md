---
title: Privacy Policy
description: What data this website and the Ciaren software do and do not collect
search: legal privacy policy analytics cookies telemetry data collection
---

# Privacy Policy

Last updated: **July 1, 2026**

This policy explains what data is collected when you visit this website and
when you use the Ciaren software. The short version: the software collects
nothing, and the website collects only standard hosting logs plus optional
aggregate analytics.

## The Ciaren software

Ciaren is **local-first**. The application:

- runs entirely on your machine — there is no Ciaren-hosted backend it needs to
  talk to;
- sends **no telemetry, usage statistics, or crash reports** to us or anyone
  else;
- requires **no account, registration, or license key** to use the open-source
  core;
- stores your flows, datasets, and settings only where you configure it to
  (your local database and file system).

Your pipelines may of course connect to databases or services **you**
configure; that traffic goes directly from your machine to those services under
their own terms, and never through us.

## This website

### Hosting

This site is a static site served by
[GitHub Pages](https://pages.github.com/). GitHub may log standard request data
(such as IP addresses) to operate the service; see the
[GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement).
We do not have access to those raw logs.

### Analytics (opt-in only)

This site uses **Google Analytics** to understand aggregate traffic (pages
visited, referrers, approximate geography) — but **only if you say yes**. On
your first visit a small banner asks for permission:

- Until you accept, **no analytics script is loaded and no analytics cookies
  are set**. Declining (or ignoring the banner) keeps analytics off.
- Your choice is remembered in your browser's `localStorage` under the key
  `ciaren-analytics-consent`. That value stays on your machine and is not a
  tracking cookie.
- To change your mind later, clear this site's data in your browser (or delete
  that key from `localStorage`) and the banner will ask again.

If you accept, Google Analytics sets cookies and processes your IP address
(with IP anonymization enabled) and browser information under the
[Google Privacy Policy](https://policies.google.com/privacy). We use this data
only in aggregate to improve the documentation; we do not use it to identify
individuals, and we do not sell or share it. The site works fully with
analytics declined or blocked.

### What we do not do

- No accounts, sign-ups, or newsletters.
- No advertising or ad-tech trackers.
- No selling or sharing of personal data.

## Third-party links

This site links to external services (GitHub, PyPI, Google, and others). Once
you leave this site, their privacy policies apply, not this one.

## Data requests

We hold essentially no personal data about visitors ourselves. For data
collected by Google Analytics or GitHub Pages, requests are best directed to
those providers; if you believe we can help with a privacy question or request,
contact us via
[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions) or the
maintainer's [website](https://www.rodrigo-arenas.com/).

## Changes to this policy

We may update this policy as the project evolves (for example, if analytics
tooling changes). The "Last updated" date above reflects the latest revision.
