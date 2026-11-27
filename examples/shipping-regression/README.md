# Predict shipping cost from orders and two lookup tables

All three CSVs are synthetic. Each of the 80 orders has a customer and a product. Each lookup key is unique. The input covers each customer–product combination once. Distance and weight are known before shipping. The historical shipping charge is the outcome to learn.

| File | Role | Fields used |
| --- | --- | --- |
| [orders.csv](orders.csv) | Main input | `customer_id`, `sku`, target `shipping_cost` |
| [customers.csv](customers.csv) | First lookup | `customer_id`, predictor `distance_km` |
| [catalog.csv](catalog.csv) | Second lookup | `sku`, predictor `weight_kg` |

Upload the files to one project and create a blank flow in that project. Open **Assistant → Build** with ML enabled. Select the files in table order and choose `shipping_cost` as the target. Under **Data shared with provider**, opt in to column names for this turn so the model can distinguish the predictors from the extra numeric columns.

> Join orders to customers and catalog. Predict shipping cost from distance and weight with linear regression. Evaluate on held-out orders.

Review the ten nodes and ten connections. The two inner joins should keep 80 orders. Only the training output of the split feeds the regressor. The test output and fitted model feed Predict. Evaluate compares predictions with the held-out charges. Choose **Apply and save**, then **Run** separately. Select **File Output → Download output** to inspect `mae` and `r2`.

The seeded split sends 64 orders to training and 16 to evaluation. In the reference run, MAE was about 0.27 currency units per order and R² was about 0.997. These values describe this deliberately simple fixture. Identifiers, tenure and shelf life are excluded from the feature list. For related orders or time-dependent outcomes, choose an appropriate split manually.

See the [assistant guide](../../docs/guide/flow-assistant.md#train-a-shipping-cost-model-from-three-csvs) for the privacy boundaries and admission checks.
