---
title: Recipes
description: "Short Ciaren recipes for common data tasks: clean text, split columns or rows, choose fallback values, convert Excel to Parquet, remove duplicates, and pivot tables."
search: recipes how to tasks convert excel parquet remove duplicates pivot fill missing values clean text split rows tags coalesce
---

# Recipes

Quick, focused answers to *"how do I do X in Ciaren?"* Each recipe is a single
small task you can build in a minute or two — no long walkthrough. For end-to-end
projects, see the [Examples](/examples/sales-analysis).

## Format conversion

- **[Convert Excel to Parquet](/recipes/convert-excel-to-parquet)** — read `.xlsx`,
  write columnar `.parquet`

## Cleaning

- **[Remove duplicate rows](/recipes/remove-duplicate-rows)** — drop exact or
  key-based duplicates
- **[Fill missing values](/recipes/fill-missing-values)** — mean / median / mode /
  constant / forward-fill
- **[Clean messy text](/recipes/clean-messy-text)** — trim spaces and normalize
  email casing before a join or deduplication
- **[Combine columns with fallback values](/recipes/coalesce-fallback-values)** —
  pick the first non-null value in priority order

## Reshaping

- **[Pivot a table](/recipes/pivot-a-table)** — turn long rows into a wide summary
- **[Split a column](/recipes/split-a-column)** — separate delimited text into
  named columns
- **[One row per tag](/recipes/one-row-per-tag)** — split delimited tags into
  rows while preserving record IDs

## Looking for more?

- Browse the full [Transformations reference](/transformations/overview)
- Try a complete [Example](/examples/sales-analysis)
- Need a node that doesn't exist? [Write a plugin](/plugins/overview)

::: tip Have a recipe to suggest?
Open a [Discussion](https://github.com/ciaren-labs/Ciaren/discussions) — the
recipes that get requested most get written first.
:::
