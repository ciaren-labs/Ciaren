import polars as pl
import pandas as pd

df_orders = pl.scan_csv('orders.csv')
df_catalog = pl.scan_csv('catalog.csv')
df_1 = df_orders.join(df_catalog, on='sku', how='left', suffix='_y', coalesce=True)
_eager_1 = df_1.collect().to_pandas()
_eager_2 = _eager_1.copy()
_eager_2['ready_to_fulfill'] = _eager_1['catalog_status'].astype(str).isin(['active'])
df_2 = pl.from_pandas(_eager_2).lazy()
df_2 = df_2.sort('order_id', nulls_last=True)
df_2.collect().write_csv('audit.csv')
