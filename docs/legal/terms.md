---
title: Terms of Use
description: Terms of use for the Ciaren website and disclaimers for the software
search: legal terms of use disclaimer warranty liability license
---

# Terms of Use

Last updated: **July 1, 2026**

These terms cover your use of this website (the Ciaren documentation site) and
restate, in plain language, the legal terms under which the Ciaren software is
made available. By using this site or the software you agree to them.

## The software is licensed, not sold

Ciaren is open-core software:

- **Ciaren Core** is licensed under the
  [GNU AGPL-3.0-only](https://github.com/ciaren-labs/Ciaren/blob/main/LICENSE).
- The **public Plugin API** (`backend/app/plugin_api/`) is licensed under
  [Apache-2.0](https://github.com/ciaren-labs/Ciaren/blob/main/LICENSES/Apache-2.0.txt).
- Plugins built by third parties are governed by whatever license their authors
  choose. Official premium plugins or hosted services, if and when offered, may
  come with their own separate terms.

Your rights and obligations for the software come from those licenses, not from
this page. If anything here conflicts with the license texts, the license texts
win.

## No warranty

The software is provided **"as is", without warranty of any kind**, express or
implied, including but not limited to the warranties of merchantability,
fitness for a particular purpose, and non-infringement. This is stated in the
license itself (AGPL-3.0 sections 15–16, Apache-2.0 sections 7–8); it applies
to every copy of Ciaren you download, build, or run.

## No security or reliability promises

Ciaren is **alpha software** and makes **no promises about security,
availability, data integrity, or fitness for production use**. In particular:

- Ciaren has **not** undergone an independent third-party security audit.
- Ciaren executes code and SQL that you (or plugins you install) provide, with
  the privileges of the local process. See the
  [local-first trust model](/security/local-first-trust-model) for what is and
  is not a security boundary.
- There is no encryption at rest and no authentication by default; the
  supported deployment model is local-first or behind access controls **you**
  operate.
- APIs, file formats, and generated code may change between releases without
  notice.

You are responsible for reviewing, testing, and securing any deployment of
Ciaren, for the pipelines you build with it, and for the data you process
through it. Nothing on this site — including documentation, examples, and
security pages — is a certification, guarantee, or professional advice of any
kind.

## Limitation of liability

To the maximum extent permitted by applicable law, the authors, maintainers,
and contributors of Ciaren shall not be liable for any claim, damages, or other
liability — including any direct, indirect, incidental, special, exemplary, or
consequential damages, loss of data, loss of profits, or business interruption
— arising from the use of this website or the software, even if advised of the
possibility of such damage.

## Website content

Documentation on this site is provided for general information and may be
incomplete, outdated, or contain errors. Code samples are offered under the
same license as the part of Ciaren they document unless stated otherwise. We
may change or remove any content at any time.

This site links to third-party sites and services (GitHub, PyPI, and others).
We do not control them and are not responsible for their content or terms.

## Trademarks

"Ciaren" and the Ciaren logo are subject to the project's
[trademark policy](https://github.com/ciaren-labs/Ciaren/blob/main/TRADEMARKS.md)
and
[brand guidelines](https://github.com/ciaren-labs/Ciaren/blob/main/BRAND_GUIDELINES.md).
The open-source licenses above do not grant trademark rights.

## Changes to these terms

We may update these terms from time to time. The "Last updated" date above
reflects the latest revision; continued use of the site after a change means
you accept the revised terms.

## Contact

Questions about these terms can be raised via
[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions) or the
maintainer's [website](https://www.rodrigo-arenas.com/). Security issues should
follow the
[security policy](https://github.com/ciaren-labs/Ciaren/blob/main/SECURITY.md)
instead.
