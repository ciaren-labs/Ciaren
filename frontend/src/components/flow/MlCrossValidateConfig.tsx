import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  cvModels,
  cvStrategiesForTask,
  CV_SCORING,
  CV_STRATEGY_MAP,
  getModelDef,
  type MlTask,
} from "@/lib/mlModels";
import { Field, ColumnMultiSelect, ColumnSelect } from "./configFields";

type Config = Record<string, any>;

interface Props {
  config: Config;
  columns: string[];
  errors: Record<string, string>;
  set: (patch: Record<string, unknown>) => void;
}

/**
 * Config form for the Cross-Validate node: pick a model, a target, a CV strategy
 * (k-fold, stratified, shuffle, time-series, group, repeated, leave-one-out), and
 * which scores to report. Strategy/scoring options follow the model's task.
 */
export function MlCrossValidateConfig({ config, columns, errors, set }: Props) {
  const models = cvModels();
  const modelDef = getModelDef(config.model_type) ?? models[0];
  const task = (modelDef?.task ?? "classification") as MlTask;
  const scoringTask = task === "regression" ? "regression" : "classification";
  const strategies = cvStrategiesForTask(task);
  const strategy = CV_STRATEGY_MAP[config.cv_strategy as string] ?? strategies[0];

  const scoring = (config.scoring as string[]) ?? [];
  const toggleScore = (value: string) =>
    set({ scoring: scoring.includes(value) ? scoring.filter((s) => s !== value) : [...scoring, value] });

  const onModelChange = (value: string) => {
    const newTask = getModelDef(value)?.task;
    const allowed = cvStrategiesForTask(newTask).map((s) => s.value);
    const patch: Record<string, unknown> = { model_type: value, hyperparameters: {}, scoring: [] };
    // A stratified strategy is invalid for regression — fall back to plain k-fold.
    if (!allowed.includes(config.cv_strategy)) patch.cv_strategy = "kfold";
    set(patch);
  };

  return (
    <>
      <Field label="Model" error={errors.model_type} help="The classification or regression model to evaluate.">
        <Select value={modelDef?.value ?? ""} onChange={(e) => onModelChange(e.target.value)}>
          {models.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </Select>
      </Field>

      {modelDef?.requires && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
          Needs the <strong>{modelDef.requires}</strong> library (installed with the <code>ml</code> extra).
        </p>
      )}

      <Field label="Target column" error={errors.target_column} help="The column the model learns to predict.">
        <ColumnSelect value={config.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
      </Field>

      <Field
        label="Feature columns (optional)"
        error={errors.feature_columns}
        hint="Empty = every column except the target"
        help="The inputs the model is trained on."
      >
        <ColumnMultiSelect
          value={config.feature_columns}
          columns={columns.filter((col) => col !== config.target_column)}
          onChange={(v) => set({ feature_columns: v })}
        />
      </Field>

      <Field label="Strategy" error={errors.cv_strategy} help={strategy?.help}>
        <Select value={strategy?.value ?? "kfold"} onChange={(e) => set({ cv_strategy: e.target.value })}>
          {strategies.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
      </Field>

      {!strategy?.noSplits && !strategy?.usesTestSize && (
        <Field label="Folds" error={errors.n_splits} help="How many folds to split the data into.">
          <Input
            type="number"
            min={2}
            value={config.n_splits ?? 5}
            onChange={(e) => set({ n_splits: Number(e.target.value) })}
          />
        </Field>
      )}

      {strategy?.usesTestSize && (
        <>
          <Field label="Splits" error={errors.n_splits} help="How many random train/test splits to evaluate.">
            <Input
              type="number"
              min={2}
              value={config.n_splits ?? 5}
              onChange={(e) => set({ n_splits: Number(e.target.value) })}
            />
          </Field>
          <Field label="Test size" error={errors.test_size} hint="0–1, e.g. 0.2 = 20% held out">
            <Input
              type="number"
              step="0.05"
              value={config.test_size ?? 0.2}
              onChange={(e) => set({ test_size: Number(e.target.value) })}
            />
          </Field>
        </>
      )}

      {strategy?.usesRepeats && (
        <Field label="Repeats" error={errors.n_repeats} help="How many times to repeat k-fold with a fresh shuffle.">
          <Input
            type="number"
            min={1}
            value={config.n_repeats ?? 1}
            onChange={(e) => set({ n_repeats: Number(e.target.value) })}
          />
        </Field>
      )}

      {strategy?.usesGroup && (
        <Field
          label="Group column"
          error={errors.group_column}
          help="Rows sharing a group value stay together in one fold."
        >
          <ColumnSelect
            value={config.group_column ?? ""}
            columns={columns.filter((col) => col !== config.target_column)}
            onChange={(v) => set({ group_column: v })}
          />
        </Field>
      )}

      {strategy?.usesShuffle && (
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={config.shuffle !== false}
            onChange={(e) => set({ shuffle: e.target.checked })}
          />
          Shuffle rows before splitting
        </label>
      )}

      <Field label="Scoring (optional)" hint="Empty = sensible defaults for the task" help="Which scores to report per fold.">
        <div className="flex flex-wrap gap-1.5">
          {CV_SCORING[scoringTask].map((s) => {
            const on = scoring.includes(s.value);
            return (
              <button
                key={s.value}
                type="button"
                onClick={() => toggleScore(s.value)}
                className={
                  "rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all " +
                  (on
                    ? "border-primary bg-primary text-primary-foreground shadow-sm"
                    : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted")
                }
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </Field>

      <Field label="Random seed" error={errors.seed} help="Required — reproduces the same folds every run.">
        <Input type="number" value={config.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
      </Field>
    </>
  );
}
