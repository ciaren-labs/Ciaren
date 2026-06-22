#!/usr/bin/env node

/**
 * Check for broken internal links in markdown files
 * Validates that all [text](path) links point to existing files
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DOCS_DIR = path.join(__dirname, '..');
const MARKDOWN_PATTERN = /\[([^\]]+)\]\(([^)]+)\)/g;

let errors = [];
let warnings = [];

console.log('🔗 Checking for broken links...\n');

// Get all markdown files (excluding node_modules and .vitepress)
const getMarkdownFiles = (dir) => {
  const files = [];
  const walk = (d) => {
    fs.readdirSync(d).forEach((file) => {
      const filePath = path.join(d, file);
      const stat = fs.statSync(filePath);

      // Skip node_modules, .vitepress, and hidden directories
      if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
        walk(filePath);
      } else if (file.endsWith('.md') && !filePath.includes('node_modules')) {
        files.push(filePath);
      }
    });
  };
  walk(dir);
  return files;
};

const mdFiles = getMarkdownFiles(DOCS_DIR);
console.log(`Found ${mdFiles.length} markdown files\n`);

// Check each file for broken links
mdFiles.forEach((file) => {
  const relPath = path.relative(DOCS_DIR, file);
  const content = fs.readFileSync(file, 'utf8');
  const matches = content.matchAll(MARKDOWN_PATTERN);

  for (const match of matches) {
    const [, text, link] = match;

    // Skip external links, anchors, and mailto links
    if (
      link.startsWith('http://') ||
      link.startsWith('https://') ||
      link.startsWith('#') ||
      link.startsWith('mailto:') ||
      link.startsWith('tel:')
    ) {
      continue;
    }

    // Handle different link formats
    let targetPath;
    if (link.startsWith('/')) {
      // Absolute path from docs root
      targetPath = path.join(DOCS_DIR, link);
    } else if (link.startsWith('../')) {
      // Relative path
      targetPath = path.normalize(path.join(path.dirname(file), link));
    } else {
      // Relative path without ../
      targetPath = path.normalize(path.join(path.dirname(file), link));
    }

    // Remove query parameters and anchors
    targetPath = targetPath.split('?')[0].split('#')[0];

    // Add .md if not specified
    if (!targetPath.endsWith('.md') && !fs.existsSync(targetPath)) {
      const mdPath = targetPath + '.md';
      if (fs.existsSync(mdPath)) {
        targetPath = mdPath;
      }
    }

    // Check if file exists
    if (!fs.existsSync(targetPath)) {
      const relTarget = path.relative(DOCS_DIR, targetPath);
      errors.push(`${relPath}: Link to "${link}" (${relTarget}) not found`);
    }
  }
});

// Summary
console.log('='.repeat(60));
if (errors.length === 0) {
  console.log('✅ All links are valid!\n');
  process.exit(0);
} else {
  console.log(`❌ Found ${errors.length} broken link(s):\n`);
  errors.forEach((e) => console.log(`   ${e}`));
  process.exit(1);
}
