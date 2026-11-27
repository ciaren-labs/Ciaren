---
title: Recipes
description: "Short Ciaren recipes for common data tasks: clean text, split columns or rows, choose fallback values, filter rows by two conditions, convert Excel to Parquet, remove duplicates, and pivot tables."
search: recipes how to tasks convert excel parquet remove duplicates pivot fill missing values clean text split rows tags coalesce filter paid orders conditions
---

# Recipes

Each recipe solves one small task in a few nodes. It includes sample data, the
exact node settings, the expected result, a way to check it, and the
exported pandas and Polars code. For end-to-end projects, see the
[Examples](/examples/sales-analysis).

## Format conversion

- [Convert Excel to Parquet](/recipes/convert-excel-to-parquet): import one
  sheet of an `.xlsx` workbook and write a typed `.parquet` file.

## Cleaning

- [Remove duplicate rows](/recipes/remove-duplicate-rows): keep one row per
  email, and sort first to choose which one survives.
- [Fill missing values](/recipes/fill-missing-values): fill a numeric column
  with its median and a text column with a constant.
- [Clean messy text](/recipes/clean-messy-text): trim spaces and lowercase
  emails so the same address matches in a join.
- [Combine columns with fallback values](/recipes/coalesce-fallback-values):
  take the first value that is not null, in priority order.

## Filtering

- [Filter paid orders](/recipes/filter-paid-orders): keep paid orders of 100
  or more with one two-condition expression.

## Reshaping

- [Pivot a table](/recipes/pivot-a-table): turn one row per sale into one row
  per region and one column per month.
- [Split a column](/recipes/split-a-column): split `EU|Paris` into `region`
  and `city` columns.
- [One row per tag](/recipes/one-row-per-tag): split `news;sports` into one row
  per tag and keep the record ID.

## Looking for more?

- Browse the full [Transformations reference](/transformations/overview).
- Try a complete [Example](/examples/sales-analysis).
- Need a node that does not exist? [Write a plugin](/plugins/overview).

::: tip Have a recipe to suggest?
Open a [Discussion](https://github.com/ciaren-labs/Ciaren/discussions) and
describe the task with a small, made-up sample.
:::
