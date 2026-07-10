import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ColumnMultiSelect, ColumnSelect, CsvListInput, Field, OptionalColumnSelect } from "../configFields";
import { MlTrainConfig } from "../MlTrainConfig";
import { MlCrossValidateConfig } from "../MlCrossValidateConfig";
import type { NodeConfigRenderProps } from "./shared";

/** Config fields for the ML node family (train/split/preprocess/predict/evaluate),
 *  or `undefined` if `type` isn't one. */
export function renderMlConfig(
  type: string,
  { c, errors, set, columns }: NodeConfigRenderProps,
): ReactNode | undefined {
  switch (type) {
    case "mlClassifierModel":
    case "mlRegressorModel":
    case "mlTrainClassifier":
    case "mlTrainRegressor":
    case "mlTrainClustering":
    case "mlTrainForecaster":
    case "mlTrainDimReduction":
      return <MlTrainConfig config={c} columns={columns} errors={errors} set={set} nodeType={type} />;

    case "mlCrossValidate":
      return <MlCrossValidateConfig config={c} columns={columns} errors={errors} set={set} />;

    case "trainTestSplit":
      return (
        <>
          <p className="rounded-md bg-muted/60 px-2.5 py-2 text-[11px] leading-snug text-slate-600">
            Two outputs: the top <span className="font-medium">train</span> handle
            feeds your model; the bottom <span className="font-medium">test</span>{" "}
            handle is held out for evaluation.
          </p>
          <Field
            label="Test size"
            error={errors.test_size}
            help="Fraction of rows held out for testing (e.g. 0.2 = 20% test, 80% train)."
          >
            <Input
              type="number"
              min={0.05}
              max={0.95}
              step={0.05}
              value={c.test_size ?? 0.2}
              onChange={(e) => set({ test_size: Number(e.target.value) })}
            />
          </Field>
          <Field
            label="Stratify by (optional)"
            error={errors.stratify_column}
            help="Keep the same class balance in train and test by stratifying on this column. Leave empty for a plain random split."
          >
            <OptionalColumnSelect
              value={c.stratify_column ?? null}
              columns={columns}
              onChange={(v) => set({ stratify_column: v })}
              noneLabel="(no stratification)"
            />
          </Field>
          <Field
            label="Random seed"
            error={errors.seed}
            help="Required: the same seed reproduces the exact same split every run."
          >
            <Input
              type="number"
              value={c.seed ?? 42}
              onChange={(e) => set({ seed: Number(e.target.value) })}
            />
          </Field>
        </>
      );

    case "scaleFeatures":
      return (
        <>
          <Field label="Method" error={errors.method} help="StandardScaler (mean 0, std 1), MinMax (0–1), or Robust (median/IQR, outlier-resistant).">
            <Select value={c.method ?? "standard"} onChange={(e) => set({ method: e.target.value })}>
              <option value="standard">Standard (z-score)</option>
              <option value="minmax">Min-max (0 to 1)</option>
              <option value="robust">Robust (median / IQR)</option>
            </Select>
          </Field>
          <Field label="Columns" error={errors.columns} help="The numeric columns to scale.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
        </>
      );

    case "encodeCategories": {
      const method = (c.method as string) ?? "onehot";
      return (
        <>
          <Field label="Method" error={errors.method} help="One-hot creates a 0/1 column per category; ordinal maps each category to an integer.">
            <Select value={method} onChange={(e) => set({ method: e.target.value })}>
              <option value="onehot">One-hot (dummy columns)</option>
              <option value="ordinal">Ordinal (integer codes)</option>
            </Select>
          </Field>
          <Field label="Columns" error={errors.columns} help="The categorical (text) columns to encode.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          {method === "onehot" && (
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={!!c.drop_first}
                onChange={(e) => set({ drop_first: e.target.checked })}
              />
              Drop the first category (avoids collinearity)
            </label>
          )}
        </>
      );
    }

    case "selectFeatures": {
      const method = (c.method as string) ?? "variance";
      return (
        <>
          <Field label="Method" error={errors.method} help="Variance drops near-constant columns; correlation drops one of each highly-correlated pair; SelectKBest keeps the top features by relevance to a target.">
            <Select value={method} onChange={(e) => set({ method: e.target.value })}>
              <option value="variance">Variance threshold</option>
              <option value="correlation">Correlation filter</option>
              <option value="kbest">Top-K by relevance</option>
            </Select>
          </Field>
          {method !== "kbest" && (
            <Field
              label="Threshold"
              error={errors.threshold}
              help={method === "variance" ? "Drop columns with variance at or below this." : "Drop a column when its absolute correlation with another exceeds this (0–1)."}
            >
              <Input
                type="number"
                step={0.05}
                value={c.threshold ?? (method === "variance" ? 0 : 0.9)}
                onChange={(e) => set({ threshold: Number(e.target.value) })}
              />
            </Field>
          )}
          {method === "kbest" && (
            <>
              <Field label="Target column" error={errors.target_column} help="The column being predicted — relevance is scored against it.">
                <ColumnSelect value={c.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
              </Field>
              <Field label="Keep top K" error={errors.k} help="How many of the best features to keep.">
                <Input type="number" min={1} value={c.k ?? 10} onChange={(e) => set({ k: Number(e.target.value) })} />
              </Field>
            </>
          )}
        </>
      );
    }

    case "reduceDimensions":
      return (
        <>
          <Field label="Components" error={errors.n_components} help="A whole number = how many components to keep; a fraction in (0,1) = keep enough to explain that much variance.">
            <Input
              type="number"
              step={0.05}
              min={0}
              value={c.n_components ?? 2}
              onChange={(e) => set({ n_components: Number(e.target.value) })}
            />
          </Field>
          <Field label="Columns (optional)" error={errors.columns} hint="Empty = all numeric columns" help="The numeric columns to compress into components.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Component prefix" error={errors.prefix} help="New columns are named prefix_1, prefix_2, …">
            <Input value={c.prefix ?? "pc"} onChange={(e) => set({ prefix: e.target.value })} />
          </Field>
          <Field label="Random seed" error={errors.seed} help="Makes the (randomized) solver reproducible.">
            <Input type="number" value={c.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
          </Field>
        </>
      );

    case "mlPredict":
      return (
        <>
          <p className="rounded-md bg-muted/60 px-2.5 py-2 text-[11px] leading-snug text-slate-600">
            Two inputs: connect the <span className="font-medium">data</span> to
            score, and provide a model — either wire the{" "}
            <span className="font-medium">model</span> input from a Train Model
            node, or set a Model URI below.
          </p>
          <Field
            label="Model URI (optional)"
            error={errors.model_uri}
            hint="Leave empty to use the connected model wire"
            help="Reference a registered model by alias (models:/churn@production) or version (models:/churn/1). Otherwise connect mlTrain's model output to the model input."
          >
            <Input
              value={c.model_uri ?? ""}
              placeholder="models:/your-model@production"
              onChange={(e) => set({ model_uri: e.target.value })}
            />
          </Field>
          <Field label="Prediction column" error={errors.output_column} help="Name of the new column holding the model's prediction.">
            <Input value={c.output_column ?? "prediction"} onChange={(e) => set({ output_column: e.target.value })} />
          </Field>
          <Field
            label="Probability columns (optional)"
            error={errors.output_proba_columns}
            hint="One name per class, e.g. proba_0, proba_1"
            help="For classifiers: also output class probabilities under these column names."
          >
            <CsvListInput
              value={c.output_proba_columns}
              onChange={(v) => set({ output_proba_columns: v })}
              placeholder="proba_0, proba_1"
            />
          </Field>
        </>
      );

    case "mlEvaluate": {
      const task = (c.task_type as string) ?? "classification";
      const metricOptions: Record<string, string[]> = {
        classification: ["accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"],
        regression: ["rmse", "mae", "r2", "mape", "residual_std"],
        clustering: ["silhouette", "davies_bouldin"],
      };
      return (
        <>
          <Field label="Task type" error={errors.task_type} help="Pick the kind of model whose predictions you're scoring.">
            <Select value={task} onChange={(e) => set({ task_type: e.target.value })}>
              <option value="classification">Classification</option>
              <option value="regression">Regression</option>
              <option value="clustering">Clustering</option>
            </Select>
          </Field>
          {task !== "clustering" && (
            <Field label="True value column" error={errors.target_column} help="The actual/observed values to compare predictions against.">
              <ColumnSelect value={c.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
            </Field>
          )}
          <Field
            label={task === "clustering" ? "Cluster label column" : "Prediction column"}
            error={errors.prediction_column}
            help="The column holding the model output (from mlPredict)."
          >
            <ColumnSelect value={c.prediction_column ?? "prediction"} columns={columns} onChange={(v) => set({ prediction_column: v })} />
          </Field>
          {task === "classification" && (
            <Field
              label="Probability columns (optional)"
              error={errors.proba_columns}
              hint="Needed for ROC-AUC"
              help="Class-probability columns produced by mlPredict."
            >
              <ColumnMultiSelect value={c.proba_columns} columns={columns} onChange={(v) => set({ proba_columns: v })} />
            </Field>
          )}
          <Field label="Metrics (optional)" error={errors.metrics} hint="Empty = a sensible default set" help="Pick which metrics to compute.">
            <ColumnMultiSelect
              value={c.metrics}
              columns={metricOptions[task] ?? []}
              onChange={(v) => set({ metrics: v })}
            />
          </Field>
        </>
      );
    }

    case "featureImportance":
      return (
        <Field
          label="Show top N (optional)"
          error={errors.top_n}
          hint="Empty = all features"
          help="Limit the output to the N most important features."
        >
          <Input
            type="number"
            min={1}
            value={c.top_n ?? ""}
            placeholder="all"
            onChange={(e) => set({ top_n: e.target.value === "" ? null : Number(e.target.value) })}
          />
        </Field>
      );

    default:
      return undefined;
  }
}
