---
title: Demo Project & Tutorials
description: The sample datasets and example flows Ciaren ships with, walked through step by step
search: demo project sample data tutorial example flows customers orders products clean join aggregate
---

# Demo Project & Tutorials

Ciaren ships with a built-in **Demo** project so you have something real to
explore the first time you open it. It contains four sample datasets and four
example flows — from a simple linear cleanup to a three-input sales mart — and
every tutorial below walks through a flow **that is already in your Demo
project**. Open the flow, follow along, preview each step, and tweak it.

## Where the demo comes from

The Demo project is created automatically the **first time the server starts**
on a fresh database. You don't run anything — open the app and it's there under
**Projects → Demo** (the emerald one).

The data is generated from a fixed random seed, so **every install gets the
exact same rows**. That's what makes these tutorials reproducible: the numbers
you see are the numbers described here.

::: tip Don't want it?
Skip seeding with `ciaren serve --no-demo`, or set
`CIAREN_SEED_DEMO=false`. Seeding is also idempotent — once the Demo project
exists it's never recreated, so deleting it keeps it gone.
:::

## The sample datasets

All four are CSVs and intentionally **messy** — they have nulls, outliers,
duplicates, inconsistent casing, and dates stored as text — so the example flows
have something realistic to clean.

| Dataset | Rows | Columns | What's messy |
| --------- | ------ | --------- | -------------- |
| `customers.csv` | 60 | `id, name, email, signup_date, country, age` | `signup_date` is **text**; `country` casing is inconsistent (`usa`/`USA`/`Usa`); `age` has nulls and two absurd outliers (199, 0) |
| `orders.csv` | 123 | `order_id, customer_id, order_date, amount, status` | `order_date` is **text**; `amount` has two huge outliers; **3 duplicate rows** |
| `products.csv` | 12 | `product_id, category, price, rating` | `price` has nulls |
| `order_items.csv` | ~one–two per order | `order_id, product_id, quantity, unit_price` | the link table joining orders to products |

::: tip See the mess for yourself
Open any dataset, or drop a **CSV Input** node and hit **Run preview**. Switch
the preview to **Chart → Histogram** on `amount` to *see* the outliers, or to
**Profile** to spot the null counts. (Charts use a sample — see
[Visualizations](./visualizations.md).)
:::

![Flows list showing the Demo project's flows, including Clean Customers, ML flows, and the Full Sales Mart](/screenshots/flows.png)

---

## Tutorial 1 — Clean Customers (linear)

**Flow:** *Clean Customers* · **Goal:** turn the raw customer list into a tidy
table — fill missing ages, normalize country casing, and make the signup date a
real date.

This is the simplest shape: a straight line from input to output.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"CSV Input","detail":"customers.csv"},
    {"type":"clean","label":"Fill Nulls","detail":"age → median"},
    {"type":"clean","label":"String Transform","detail":"country → upper"},
    {"type":"clean","label":"Parse Dates","detail":"signup_date → datetime"},
    {"type":"output","label":"File Output"}
  ]'
/>

1. **CSV Input** → `customers.csv`.
2. **Fill Nulls** — column `age`, strategy **median**. (Some ages are blank;
   median is robust to those 199/0 outliers.)
3. **String Transform** — column `country`, operation **upper**. Now `usa`,
   `USA`, and `Usa` all become `USA`.
4. **Parse Dates** — column `signup_date`, errors **coerce**. Text like
   `2022-06-14` becomes an actual date you can sort and extract parts from.
5. **File Output**.

**Follow along:** select each node and **Run preview** to watch the column
change one step at a time. Select **String Transform** and you'll see `country`
collapse to a handful of clean values.

**Try it:** add a **Group By Aggregate** after step 3 (group by `country`,
count `id`) to see customers per country — proof the casing fix worked.

---

## Tutorial 2 — Order Revenue by Month (dates + aggregation)

**Flow:** *Order Revenue by Month* · **Goal:** total completed revenue per
month, in chronological order.

This adds date-part extraction and grouping.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"CSV Input","detail":"orders.csv"},
    {"type":"clean","label":"Parse Dates","detail":"order_date → datetime"},
    {"type":"clean","label":"Extract Date Parts","detail":"year + month cols"},
    {"type":"clean","label":"Filter Rows","detail":"status = completed"},
    {"type":"transform","label":"Group By","detail":"sum amount by month"},
    {"type":"clean","label":"Sort Rows","detail":"year → month asc"},
    {"type":"output","label":"File Output"}
  ]'
/>

1. **CSV Input** → `orders.csv`.
2. **Parse Dates** — column `order_date` (it's text).
3. **Extract Date Parts** — column `order_date`, parts **year**, **month**.
   This adds `order_date_year` and `order_date_month` columns.
4. **Filter Rows** — keep `status == completed`.
5. **Group By Aggregate** — group by `order_date_year`, `order_date_month`;
   aggregate `amount` with **sum**.
6. **Sort Rows** — by `order_date_year`, `order_date_month` ascending.
7. **File Output**.

**Follow along:** preview after **Extract Date Parts** to see the new
year/month columns, then after **Group By Aggregate** to see one row per month.

**Try it:** select **Group By Aggregate**, open **Chart → Bar**, set category =
`order_date_month` and value = `amount` to see the monthly revenue shape.

---

## Tutorial 3 — Customer Orders Join (two inputs)

**Flow:** *Customer Orders Join* · **Goal:** clean customers and orders
*independently*, then join them and compute a discounted amount.

This is the first branched flow: two inputs, each with its own cleaning chain,
meeting at a **Join**.

<ForkJoin
  :left='[
    {"type":"input","label":"CSV Input","detail":"customers.csv"},
    {"type":"clean","label":"Fill Nulls","detail":"age → median"},
    {"type":"clean","label":"String Transform","detail":"country → upper"}
  ]'
  :right='[
    {"type":"input","label":"CSV Input","detail":"orders.csv"},
    {"type":"clean","label":"Remove Duplicates"},
    {"type":"clean","label":"Remove Outliers","detail":"IQR drop"}
  ]'
  :join='{"label":"Join","detail":"on customer_id — inner"}'
  :after='[
    {"type":"transform","label":"Calculated Column","detail":"net_amount = amount × 0.9"},
    {"type":"output","label":"File Output"}
  ]'
/>

![Customer Orders Join canvas — two input branches meeting at a join node, followed by calculatedColumn and csvOutput](/screenshots/editor-node-selected.png)

### Customer branch

1. **CSV Input** → `customers.csv`.
2. **Fill Nulls** — `age`, median.
3. **String Transform** — `country`, upper.

### Orders branch

1. **CSV Input** → `orders.csv`.
2. **Remove Duplicates** — keep **first** (drops those 3 dupe rows).
3. **Remove Outliers** — column `amount`, method **IQR**, action **drop**
   (removes the 99999.99 / 88888.88 rows).

### Join & finalize

1. **Join** — left input = customers, right input = orders; `left_on = id`,
   `right_on = customer_id`, how **inner**.
2. **Calculated Column** — `net_amount = amount * 0.9`.
3. **File Output**.

**Follow along:** preview the **Remove Outliers** node — the row count drops as
the outliers leave. Preview the **Join** to see customer columns sitting next to
their orders.

**Why two branches?** Each side needs different cleaning. Independent branches
keep that logic readable, and the Join's **left**/**right** handles make the
join direction explicit.

---

## Tutorial 4 — Full Sales Mart (three inputs)

**Flow:** *Full Sales Mart* · **Goal:** build a per-category revenue table from
three datasets, then label each category by revenue tier.

This is the most complex flow — three inputs and two chained joins.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"order_items.csv","detail":"Calculated Column: line_total"},
    {"type":"input","label":"products.csv","detail":"Fill Nulls: price → mean"},
    {"type":"transform","label":"Join","detail":"items + products on product_id"},
    {"type":"input","label":"orders.csv","detail":"Remove Duplicates"},
    {"type":"transform","label":"Join","detail":"+ orders on order_id"},
    {"type":"transform","label":"Group By","detail":"sum line_total by category"},
    {"type":"transform","label":"Conditional Column","detail":"revenue_tier label"},
    {"type":"output","label":"File Output"}
  ]'
  :vertical="true"
/>

### Order items branch

1. **CSV Input** → `order_items.csv`.
2. **Calculated Column** — `line_total = quantity * unit_price`.

### Products branch

1. **CSV Input** → `products.csv`.
2. **Fill Nulls** — `price`, strategy **mean**.

### First join

1. **Join** — items (left) + products (right) on `product_id`, how **left**.

### Orders branch

1. **CSV Input** → `orders.csv`.
2. **Remove Duplicates** — keep first.

### Second join + aggregate + label

1. **Join** — (items+products) (left) + orders (right) on `order_id`, how
   **left**.
2. **Group By Aggregate** — group by `category`; `line_total` **sum**,
   `order_id` **count**.
3. **Conditional Column** — `revenue_tier`: `line_total >= 5000` → **high**,
   `>= 1000` → **medium**, else **low**.
4. **File Output**.

**Follow along:** preview each **Join** to watch the table widen as columns from
the next dataset attach. Preview **Group By Aggregate** for the final
one-row-per-category result, then **Conditional Column** to see the tier label
appear.

**Try it:** on **Group By Aggregate**, open **Chart → Bar** (category =
`category`, value = `line_total`) to compare categories at a glance.

## Next steps

- See every node these flows use in the [Transformations reference](../transformations/overview.md).
- Run a flow and read the [exported Python code](./engines.md#code-export-pandas-polars-and-lazy-polars)
  it generates — the demo flows make for readable, educational examples.
- Build your own: [Quick Start (5 min)](./quick-start.md).
