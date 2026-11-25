import pandas as pd

df_orders = pd.read_csv('orders.csv')
df_catalog = pd.read_csv('catalog.csv')
df_1 = df_orders.merge(df_catalog, on='sku', how='left')
df_1 = df_1.copy()
df_1['ready_to_fulfill'] = df_1['catalog_status'].astype(str).isin(['active'])
df_1 = df_1.sort_values('order_id')
df_1.to_csv('audit.csv', index=False)
