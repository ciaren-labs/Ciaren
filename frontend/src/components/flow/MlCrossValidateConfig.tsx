import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { CV_SCORING, CV_STRATEGIES, CV_STRATEGY_MAP } from "@/lib/mlModels";
import { Field, ColumnSelect } from "./configFields";

type Config = Record<string, any>;

interface Props {
  config: Config;
  columns: string[];
  errors: Record<string, string>;
  set: (patch: Record<string, unknown>) => void;
}

/**
 * Config form for the Cross-Validate node: choose a CV strategy and scores.
 * The estimator, target, features, and preprocessing come from the connected
 * Train node's model handle.
 */
export function MlCrossValidateConfig({ config, columns, errors, set }: Props) {
  const strategy = CV_STRATEGY_MAP[config.cv_strategy as string] ?? CV_STRATEGIES[0];

  const scoring = (config.scoring as string[]) ?? [];
  const toggleScore = (value: string) =>
    set({ scoring: scoring.includes(value) ? scoring.filter((s) => s !== value) : [...scoring, value] });

  return (
    <>
      <p className="rounded-md border border-sky-200 bg-sky-50 px-2 py-1.5 text-[11px] text-sky-800">
        Connect a Train Classifier or Train Regressor node to the <strong>model</strong> input. Target, features,
        hyperparameters, and preprocessing are inherited from that model.
      </p>

      <Field label="Strategy" error={errors.cv_strategy} help={strategy?.help}>
        <Select value={strategy?.value ?? "kfold"} onChange={(e) => set({ cv_strategy: e.target.value })}>
          {CV_STRATEGIES.map((s) => (
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

      <Field
        label="Scoring (optional)"
        hint="Empty = sensible defaults for the connected model"
        help="Only choose metrics that match the connected classifier or regressor."
      >
        {(["classification", "regression"] as const).map((group) => (
          <div key={group} className="mb-2 last:mb-0">
            <p className="mb-1 text-[11px] font-medium uppercase text-slate-500">{group}</p>
            <div className="flex flex-wrap gap-1.5">
              {CV_SCORING[group].map((s) => {
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
          </div>
        ))}
      </Field>

      <Field label="Random seed" error={errors.seed} help="Required — reproduces the same folds every run.">
        <Input type="number" value={config.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
      </Field>
    </>
  );
}
