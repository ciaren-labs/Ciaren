#!/usr/bin/env node

/**
 * Regenerates docs/guide/changelog.md from the repo-root CHANGELOG.md, so the
 * docs site and the GitHub-rendered changelog never drift — the root file
 * stays the single source of truth. Runs automatically before `dev`/`build`.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SOURCE = path.join(__dirname, '../../CHANGELOG.md');
const TARGET = path.join(__dirname, '../guide/changelog.md');

const FRONTMATTER = `---
title: Changelog
description: Notable changes to Ciaren, release by release
search: changelog release notes history version
---

`;

const source = fs.readFileSync(SOURCE, 'utf8');

// Drop the source's own "# Changelog" H1 — the frontmatter title covers it,
// and VitePress pages conventionally start with frontmatter, not a duplicate H1.
const body = source.replace(/^# Changelog\n+/, '');

const note = `> This page mirrors the [\`CHANGELOG.md\`](https://github.com/ciaren-labs/Ciaren/blob/main/CHANGELOG.md) at the root of the repository.\n\n`;

fs.writeFileSync(TARGET, FRONTMATTER + note + body);

console.log(`Synced ${path.relative(process.cwd(), SOURCE)} -> ${path.relative(process.cwd(), TARGET)}`);
