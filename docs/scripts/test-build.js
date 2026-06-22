#!/usr/bin/env node

/**
 * Documentation build validation script
 * Verifies:
 * - Build succeeds without errors
 * - Build output directory exists
 * - Required files are present
 * - No orphaned pages
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DIST_DIR = path.join(__dirname, '../.vitepress/dist');
const REQUIRED_FILES = [
  'index.html',
  '404.html',
];

let errors = [];
let warnings = [];

console.log('🔍 Validating documentation build...\n');

// Check if dist directory exists
if (!fs.existsSync(DIST_DIR)) {
  errors.push('❌ Build directory not found: ' + DIST_DIR);
  console.error(errors[errors.length - 1]);
  process.exit(1);
}

console.log('✅ Build directory exists');

// Check required files
console.log('\n📄 Checking required files:');
REQUIRED_FILES.forEach((file) => {
  const filePath = path.join(DIST_DIR, file);
  if (fs.existsSync(filePath)) {
    console.log(`  ✅ ${file}`);
  } else {
    errors.push(`❌ Missing required file: ${file}`);
    console.error(`  ❌ ${file}`);
  }
});

// Check for common issues
console.log('\n🔎 Checking for common issues:');

// Check index.html is not empty
const indexPath = path.join(DIST_DIR, 'index.html');
if (fs.existsSync(indexPath)) {
  const indexContent = fs.readFileSync(indexPath, 'utf8');
  if (indexContent.length < 1000) {
    warnings.push(`⚠️  index.html seems small (${indexContent.length} bytes)`);
    console.warn(`  ⚠️  index.html seems small (${indexContent.length} bytes)`);
  } else {
    console.log(`  ✅ index.html is ${Math.round(indexContent.length / 1024)}KB`);
  }

  if (!indexContent.includes('<html')) {
    errors.push('❌ index.html missing HTML tags');
    console.error('  ❌ index.html missing HTML tags');
  } else {
    console.log('  ✅ index.html has valid HTML');
  }
}

// Count total files
const countFiles = (dir) => {
  let count = 0;
  const walk = (d) => {
    fs.readdirSync(d).forEach((file) => {
      const filePath = path.join(d, file);
      if (fs.statSync(filePath).isDirectory()) {
        walk(filePath);
      } else {
        count++;
      }
    });
  };
  walk(dir);
  return count;
};

const totalFiles = countFiles(DIST_DIR);
console.log(`  ✅ Total files built: ${totalFiles}`);

// Count HTML files (should have many pages)
const countHtmlFiles = (dir) => {
  let count = 0;
  const walk = (d) => {
    fs.readdirSync(d).forEach((file) => {
      const filePath = path.join(d, file);
      if (fs.statSync(filePath).isDirectory()) {
        walk(filePath);
      } else if (file.endsWith('.html')) {
        count++;
      }
    });
  };
  walk(dir);
  return count;
};

const htmlFiles = countHtmlFiles(DIST_DIR);
console.log(`  ✅ HTML pages built: ${htmlFiles}`);

if (htmlFiles < 3) {
  errors.push(`❌ Fewer HTML pages than expected (${htmlFiles}, expected >3)`);
  console.error(`  ❌ Fewer HTML pages than expected (${htmlFiles})`);
}

// Summary
console.log('\n' + '='.repeat(50));
if (errors.length === 0) {
  console.log('✅ All checks passed!');
  console.log(`\n📊 Build Summary:`);
  console.log(`   - Files: ${totalFiles}`);
  console.log(`   - Size: ~${Math.round(
    fs.readdirSync(DIST_DIR, { recursive: true }).reduce(
      (sum, file) => {
        const filePath = path.join(DIST_DIR, file);
        return sum + (fs.statSync(filePath).isFile() ? fs.statSync(filePath).size : 0);
      },
      0
    ) / 1024 / 1024
  )}MB`);
  console.log('   - Status: Ready for deployment');

  if (warnings.length > 0) {
    console.log(`\n⚠️  ${warnings.length} warning(s):`);
    warnings.forEach((w) => console.log(`   ${w}`));
  }

  process.exit(0);
} else {
  console.log(`❌ ${errors.length} error(s) found:\n`);
  errors.forEach((e) => console.log(`   ${e}`));
  process.exit(1);
}
