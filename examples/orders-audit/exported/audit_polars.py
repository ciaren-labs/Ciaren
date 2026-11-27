import polars as pl

df_orders = pl.read_csv('orders.csv')
df_catalog = pl.read_csv('catalog.csv')
df_1 = df_orders.join(df_catalog, on='sku', how='left', suffix='_y', coalesce=True)
_eager_1 = df_1.to_pandas()
_eager_2 = _eager_1.copy()
_eager_2['ready_to_fulfill'] = _eager_1['catalog_status'].astype(str).isin(['active'])
df_2 = pl.from_pandas(_eager_2)
df_2 = df_2.sort('order_id', nulls_last=True)
df_2.write_csv('audit.csv')
