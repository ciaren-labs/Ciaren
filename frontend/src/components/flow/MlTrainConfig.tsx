import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Settings2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { mlApi } from "@/lib/api";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  getModelDef,
  isSupervisedModel,
  modelsForNodeType,
  TRAIN_NODE_TASKS,
  type HyperParam,
} from "@/lib/mlModels";
import { Field, ColumnMultiSelect, ColumnSelect } from "./configFields";

type Config = Record<string, any>;

interface Props {
  config: Config;
  columns: string[];
  errors: Record<string, string>;
  set: (patch: Record<string, unknown>) => void;
  /** The train node type, e.g. "mlTrainClassifier" — scopes the model picker. */
  nodeType: string;
}

/** One hyperparameter control (int / float / bool / select). */
function HyperControl({
  param,
  value,
  onChange,
}: {
  param: HyperParam;
  value: unknown;
  onChange: (v: number | boolean | string) => void;
}) {
  if (param.control === "bool") {
    return (
      <label className="flex items-center gap-2 text-xs text-slate-600">
        <input type="checkbox" checked={Boolean(value ?? param.default)} onChange={(e) => onChange(e.target.checked)} />
        {param.label}
      </label>
    );
  }
  if (param.control === "select") {
    return (
      <Field label={param.label} help={param.help}>
        <Select value={String(value ?? param.default)} onChange={(e) => onChange(e.target.value)}>
          {param.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>
    );
  }
  // int / float
  return (
    <Field label={param.label} help={param.help}>
      <Input
        type="number"
        min={param.min}
        max={param.max}
        step={param.step ?? (param.control === "int" ? 1 : "any")}
        value={(value ?? param.default) as number}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
  );
}

const NUMERIC_STRATEGIES = [
  { value: "standard_scaler", label: "Standardize (z-score)" },
  { value: "minmax_scaler", label: "Min-max (0–1)" },
  { value: "robust_scaler", label: "Robust (median / IQR)" },
];
const IMPUTE_NUMERIC = [
  { value: "median", label: "Median" },
  { value: "mean", label: "Mean" },
  { value: "most_frequent", label: "Most frequent" },
];
const IMPUTE_CATEGORICAL = [
  { value: "most_frequent", label: "Most frequent" },
  { value: "constant", label: "Constant ('missing')" },
];

export function MlTrainConfig({ config, columns, errors, set, nodeType }: Props) {
  const [open, setOpen] = useState(false);
  const { data: catalog = [] } = useQuery({
    queryKey: ["ml", "model-catalog"],
    queryFn: mlApi.modelCatalog,
    staleTime: 60_000,
  });
  const availability = new Map(catalog.map((m) => [m.model_type, m]));
  const models = modelsForNodeType(nodeType);
  const task = TRAIN_NODE_TASKS[nodeType];
  const modelDef = getModelDef(config.model_type) ?? models[0];
  const selectedAvailability = modelDef ? availability.get(modelDef.value) : undefined;
  // No models for this task yet (e.g. the Train Forecaster scaffold).
  const noModels = models.length === 0;
  const supervised = modelDef ? isSupervisedModel(modelDef.value) : task === "timeseries";
  const isTimeseries = task === "timeseries";
  const hp = (config.hyperparameters ?? {}) as Record<string, unknown>;
  const setHp = (name: string, v: number | boolean | string) =>
    set({ hyperparameters: { ...hp, [name]: v } });

  const pre = (config.preprocessing ?? {}) as Record<string, unknown>;
  const setPre = (patch: Record<string, unknown>) => set({ preprocessing: { ...pre, ...patch } });

  const basicParams = (modelDef?.params ?? []).filter((p) => !p.advanced);

  if (noModels) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        Time-series forecasting models are coming soon. This node is defined but not
        runnable yet.
      </p>
    );
  }

  return (
    <>
      <Field label="Model" error={errors.model_type} help="Pick an algorithm for this task.">
        <Select
          value={modelDef?.value ?? ""}
          // Switching models clears stale hyperparameters from the old model.
          onChange={(e) => set({ model_type: e.target.value, hyperparameters: {} })}
        >
          {models.map((m) => (
            <option key={m.value} value={m.value} disabled={availability.get(m.value)?.available === false}>
              {m.label}
              {availability.get(m.value)?.available === false ? " (not installed)" : ""}
            </option>
          ))}
        </Select>
      </Field>

      {selectedAvailability?.available === false ? (
        <p
          className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800"
          title={selectedAvailability.warning ?? "Required dependency was not found."}
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Required dependency not installed for {modelDef?.label}.</span>
        </p>
      ) : modelDef?.requires ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
          Needs the <strong>{modelDef.requires}</strong> library (installed with the <code>ml</code> extra).
        </p>
      ) : null}

      {isTimeseries && (
        <Field label="Time column" error={errors.time_column} help="The column that orders rows in time.">
          <ColumnSelect value={config.time_column ?? ""} columns={columns} onChange={(v) => set({ time_column: v })} />
        </Field>
      )}

      {supervised && (
        <Field label="Target column" error={errors.target_column} help="The column the model learns to predict.">
          <ColumnSelect value={config.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
        </Field>
      )}

      <Field
        label={supervised ? "Feature columns (optional)" : "Columns to use (optional)"}
        error={errors.feature_columns}
        hint={supervised ? "Empty = every column except the target" : "Empty = all columns"}
        help="The inputs the model is trained on."
      >
        <ColumnMultiSelect
          value={config.feature_columns}
          columns={columns.filter((col) => col !== config.target_column)}
          onChange={(v) => set({ feature_columns: v })}
        />
      </Field>

      {basicParams.map((p) => (
        <HyperControl key={p.name} param={p} value={hp[p.name]} onChange={(v) => setHp(p.name, v)} />
      ))}

      <Field label="Random seed" error={errors.seed} help="Required — reproduces the same model every run.">
        <Input type="number" value={config.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
      </Field>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <button
            type="button"
            className="mt-1 flex items-center justify-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:bg-muted"
          >
            <Settings2 className="h-3.5 w-3.5" />
            Advanced options
          </button>
        </DialogTrigger>
        <DialogContent className="max-h-[85vh] max-w-md overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Advanced options — {modelDef?.label}</DialogTitle>
            <DialogDescription>
              Fine-tune hyperparameters, cross-validation, and preprocessing. Defaults are sensible — only change what you need.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <section className="flex flex-col gap-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hyperparameters</h4>
              {(modelDef?.params ?? []).length === 0 ? (
                <p className="text-xs text-muted-foreground">This model has no tunable hyperparameters.</p>
              ) : (
                (modelDef?.params ?? []).map((p) => (
                  <HyperControl key={p.name} param={p} value={hp[p.name]} onChange={(v) => setHp(p.name, v)} />
                ))
              )}
            </section>

            {supervised && (
              <section className="flex flex-col gap-3 border-t border-border pt-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cross-validation</h4>
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={Boolean(config.cross_validate)}
                    onChange={(e) => set({ cross_validate: e.target.checked })}
                  />
                  Run k-fold cross-validation
                </label>
                {config.cross_validate && (
                  <Field label="Folds" error={errors.cv_folds} help="How many folds to split the training data into.">
                    <Input
                      type="number"
                      min={2}
                      value={config.cv_folds ?? 5}
                      onChange={(e) => set({ cv_folds: Number(e.target.value) })}
                    />
                  </Field>
                )}
              </section>
            )}

            <section className="flex flex-col gap-3 border-t border-border pt-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Preprocessing</h4>
              <p className="text-[11px] text-muted-foreground">
                Bundled into the model so the same steps run at predict time. Leave empty to infer from column types.
              </p>
              <Field label="Numeric columns" help="Columns to impute + scale.">
                <ColumnMultiSelect
                  value={pre.numeric_columns as string[] | undefined}
                  columns={columns}
                  onChange={(v) => setPre({ numeric_columns: v })}
                />
              </Field>
              <Field label="Scaling">
                <Select
                  value={(pre.numeric_strategy as string) ?? "standard_scaler"}
                  onChange={(e) => setPre({ numeric_strategy: e.target.value })}
                >
                  {NUMERIC_STRATEGIES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Impute numeric with">
                <Select
                  value={(pre.impute_numeric as string) ?? "median"}
                  onChange={(e) => setPre({ impute_numeric: e.target.value })}
                >
                  {IMPUTE_NUMERIC.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Categorical columns" help="Columns to impute + one-hot encode.">
                <ColumnMultiSelect
                  value={pre.categorical_columns as string[] | undefined}
                  columns={columns}
                  onChange={(v) => setPre({ categorical_columns: v })}
                />
              </Field>
              <Field label="Impute categorical with">
                <Select
                  value={(pre.impute_categorical as string) ?? "most_frequent"}
                  onChange={(e) => setPre({ impute_categorical: e.target.value })}
                >
                  {IMPUTE_CATEGORICAL.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </Select>
              </Field>
            </section>

            <section className="flex flex-col gap-3 border-t border-border pt-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tracking</h4>
              <Field label="MLflow experiment (optional)" help="Group these runs under a named experiment. Defaults to 'flowframe'.">
                <Input
                  value={config.mlflow_experiment ?? ""}
                  placeholder="flowframe"
                  onChange={(e) => set({ mlflow_experiment: e.target.value })}
                />
              </Field>
            </section>
          </div>

          <DialogClose asChild>
            <button
              type="button"
              className="mt-2 self-end rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            >
              Done
            </button>
          </DialogClose>
        </DialogContent>
      </Dialog>
    </>
  );
}
