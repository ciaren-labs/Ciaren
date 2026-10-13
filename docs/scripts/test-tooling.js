import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const docs = fileURLToPath(new URL("..", import.meta.url));
const packageJson = JSON.parse(
  fs.readFileSync(path.join(docs, "package.json"), "utf8"),
);

function runInFixture(script, content, relative = "guide/example.md") {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ciaren-docs-tooling-"));
  try {
    fs.writeFileSync(
      path.join(root, "package.json"),
      JSON.stringify({ scripts: packageJson.scripts }),
    );
    fs.copyFileSync(
      path.join(docs, ".markdownlint.json"),
      path.join(root, ".markdownlint.json"),
    );
    for (const ignored of ["node_modules", ".vitepress", "agent-runs"]) {
      fs.mkdirSync(path.join(root, ignored));
      fs.writeFileSync(
        path.join(root, ignored, "invalid.md"),
        "# Heading\nNo blank line.\n",
      );
    }
    const markdown = path.join(root, relative);
    fs.mkdirSync(path.dirname(markdown), { recursive: true });
    fs.writeFileSync(markdown, content);
    const result = spawnSync(
      process.platform === "win32" ? "npm.cmd" : "npm",
      ["run", script],
      {
        cwd: root,
        shell: process.platform === "win32",
        env: {
          ...process.env,
          PATH: `${path.join(docs, "node_modules", ".bin")}${path.delimiter}${process.env.PATH}`,
        },
        encoding: "utf8",
        timeout: 30000,
      },
    );
    if (result.error) throw result.error;
    return {
      status: result.status,
      output: result.stdout + result.stderr,
      markdown: fs.readFileSync(markdown, "utf8"),
    };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

for (const relative of [
  "example.md",
  "guide/example.md",
  "guide/nested/example.md",
  "recipes/example.md",
]) {
  test(`the lint command detects a Markdown violation in ${relative}`, () => {
    const result = runInFixture(
      "lint",
      "# Heading\nNo blank line after heading.\n",
      relative,
    );
    assert.notEqual(result.status, 0, result.output);
    assert.match(result.output, /MD022/);
  });
}

test("the lint command accepts valid Markdown and ignores dependency/build/run files", () => {
  const result = runInFixture("lint", "# Heading\n\nA valid paragraph.\n");
  assert.equal(result.status, 0, result.output);
});

test("the format command formats a nested Markdown page", () => {
  const result = runInFixture(
    "format",
    "# Heading\n\n-   First\n-    Second\n",
  );
  assert.equal(result.status, 0, result.output);
  assert.equal(result.markdown, "# Heading\n\n- First\n- Second\n");
});
