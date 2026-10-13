// @vitest-environment node

import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import postcss from "postcss";
import { beforeAll, expect, test } from "vitest";

const root = fileURLToPath(new URL("../../", import.meta.url));
const entry = resolve(root, "__react-flow-query_contract__.js").replace(
  /\\/g,
  "/",
);
let bundle: Awaited<ReturnType<typeof build>>;

beforeAll(async () => {
  bundle = await build({
    root,
    configFile: resolve(root, "vite.config.ts"),
    logLevel: "silent",
    plugins: [
      {
        name: "vendor-contract-entry",
        resolveId(id) {
          return id === "ciaren-vendor-contract" ? entry : null;
        },
        load(id) {
          return id === entry
            ? `
          import * as React from 'react';
          import * as ReactDOM from 'react-dom/client';
          import * as Router from 'react-router-dom';
          import * as Flow from '@xyflow/react';
          import * as Query from '@tanstack/react-query';
          import './src/index.css';
          console.log(React, ReactDOM, Router, Flow, Query);
        `
            : null;
        },
      },
    ],
    build: {
      write: false,
      minify: false,
      rolldownOptions: { input: "ciaren-vendor-contract" },
    },
  });
}, 30_000);

test("production config keeps vendor libraries in their named chunks", () => {
  if (Array.isArray(bundle) || !("output" in bundle)) {
    throw new Error("Expected one finite production bundle");
  }
  const chunks = bundle.output.filter((output) => output.type === "chunk");
  const entryChunk = chunks.find((chunk) => chunk.isEntry);
  expect(entryChunk?.moduleIds).toContain(entry);
  expect(["react", "flow", "query"]).not.toContain(entryChunk?.name);
  for (const [name, packages] of [
    ["react", ["react", "react-dom", "react-router-dom"]],
    ["flow", ["@xyflow/react"]],
    ["query", ["@tanstack/react-query"]],
  ] as const) {
    const chunk = chunks.find((candidate) => candidate.name === name);
    expect(chunk, `${name} vendor chunk`).toBeDefined();
    for (const packageName of packages) {
      expect(
        chunk!.moduleIds.some((id) =>
          id.replace(/\\/g, "/").includes(`/node_modules/${packageName}/`),
        ),
        `${packageName} belongs to ${name}`,
      ).toBe(true);
    }
  }
});

test.each([
  ["button:not(:disabled)", "cursor", "pointer"],
  ["[role=button]:not(:disabled)", "cursor", "pointer"],
  [":disabled", "cursor", "default"],
  ["input::placeholder", "color", "#9ca3af"],
  ["textarea::placeholder", "color", "#9ca3af"],
  [".text-slate-500", "color", "#64748b"],
  [".bg-amber-100", "background-color", "#fef3c7"],
])("production CSS retains %s %s", (selector, property, expected) => {
  if (Array.isArray(bundle) || !("output" in bundle)) {
    throw new Error("Expected one finite production bundle");
  }
  const css = bundle.output.find(
    (output) => output.type === "asset" && output.fileName.endsWith(".css"),
  );
  expect(css, "production CSS is bundled with the editor").toBeDefined();
  if (!css || css.type !== "asset") throw new Error("Missing production CSS");
  const stylesheet = postcss.parse(String(css.source));
  const values: Record<string, string> = {};
  stylesheet.walkRules((rule) => {
    if (rule.selectors.some((value) => value.replace(/"/g, "") === selector)) {
      rule.walkDecls((declaration) => {
        values[declaration.prop] = declaration.value;
      });
    }
  });
  expect(values[property]).toBe(expected);
});
