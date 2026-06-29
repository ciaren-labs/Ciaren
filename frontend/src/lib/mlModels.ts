// Frontend mirror of the backend model catalog (app/ml/models.py). Drives the
// mlTrain model picker and its hyperparameter controls. Hyperparameters marked
// `advanced` live behind the "Advanced options" modal; the rest show inline.

export type MlTask =
  | "classification"
  | "regression"
  | "clustering"
  | "dimensionality_reduction"
  | "timeseries";

export const ML_TASK_LABELS: Record<MlTask, string> = {
  classification: "Classification",
  regression: "Regression",
  clustering: "Clustering",
  dimensionality_reduction: "Dimensionality reduction",
  timeseries: "Time series",
};

export const SUPERVISED_TASKS = new Set<MlTask>(["classification", "regression", "timeseries"]);

// Each task-scoped train node accepts models from one task family, so its picker
// shows only relevant models. Mirrors TRAIN_NODE_TASKS in app/ml/models.py.
export const TRAIN_NODE_TASKS: Record<string, MlTask> = {
  mlTrainClassifier: "classification",
  mlTrainRegressor: "regression",
  mlTrainClustering: "clustering",
  mlTrainForecaster: "timeseries",
  mlTrainDimReduction: "dimensionality_reduction",
};

export const TRAIN_NODE_TYPES = Object.keys(TRAIN_NODE_TASKS);

/** Models a given train node can pick (empty for tasks with no models yet). */
export function modelsForNodeType(nodeType: string): MlModelDef[] {
  const task = TRAIN_NODE_TASKS[nodeType];
  return task ? ML_MODELS.filter((m) => m.task === task) : ML_MODELS;
}

export type HyperControl = "int" | "float" | "bool" | "select";

export interface HyperParam {
  name: string;
  label: string;
  control: HyperControl;
  default: number | boolean | string;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  help?: string;
  /** Shown only inside the Advanced options modal. */
  advanced?: boolean;
}

export interface MlModelDef {
  value: string;
  label: string;
  task: MlTask;
  /** Optional library beyond scikit-learn the model needs. */
  requires?: "xgboost" | "lightgbm";
  params: HyperParam[];
}

const CLASS_WEIGHT: HyperParam = {
  name: "class_weight",
  label: "Class weight",
  control: "select",
  default: "none",
  options: [
    { value: "none", label: "None" },
    { value: "balanced", label: "Balanced" },
  ],
  help: "Weight classes inversely to their frequency — useful for imbalanced data.",
  advanced: true,
};

// Tree-ensemble hyperparameters shared by the RF / boosting models.
const TREE_PARAMS = (boosting: boolean): HyperParam[] => [
  { name: "n_estimators", label: "Number of trees", control: "int", default: boosting ? 200 : 100, min: 1, help: "More trees = stronger but slower." },
  ...(boosting
    ? [{ name: "learning_rate", label: "Learning rate", control: "float" as const, default: 0.1, min: 0, step: 0.01, help: "Lower = more robust, needs more trees." }]
    : []),
  { name: "max_depth", label: "Max depth", control: "int", default: boosting ? 6 : 0, min: 0, help: "0 = no limit (sklearn). Caps tree size to fight overfitting.", advanced: true },
  { name: "subsample", label: "Row subsample", control: "float", default: 1, min: 0, max: 1, step: 0.05, help: "Fraction of rows sampled per tree.", advanced: true },
];

export const ML_MODELS: MlModelDef[] = [
  // ----- Classification -----
  {
    value: "logistic_regression",
    label: "Logistic Regression",
    task: "classification",
    params: [
      { name: "C", label: "Regularization (C)", control: "float", default: 1.0, min: 0, step: 0.1, help: "Smaller = stronger regularization." },
      { name: "max_iter", label: "Max iterations", control: "int", default: 1000, min: 1, advanced: true },
      CLASS_WEIGHT,
    ],
  },
  {
    value: "random_forest_classifier",
    label: "Random Forest",
    task: "classification",
    params: [...TREE_PARAMS(false), CLASS_WEIGHT],
  },
  {
    value: "xgboost_classifier",
    label: "XGBoost",
    task: "classification",
    requires: "xgboost",
    params: TREE_PARAMS(true),
  },
  {
    value: "lightgbm_classifier",
    label: "LightGBM",
    task: "classification",
    requires: "lightgbm",
    params: TREE_PARAMS(true),
  },
  {
    value: "svm_classifier",
    label: "Support Vector Machine",
    task: "classification",
    params: [
      { name: "C", label: "Regularization (C)", control: "float", default: 1.0, min: 0, step: 0.1 },
      { name: "kernel", label: "Kernel", control: "select", default: "rbf", options: [
        { value: "rbf", label: "RBF" }, { value: "linear", label: "Linear" }, { value: "poly", label: "Polynomial" },
      ], advanced: true },
      CLASS_WEIGHT,
    ],
  },
  {
    value: "knn_classifier",
    label: "K-Nearest Neighbors",
    task: "classification",
    params: [
      { name: "n_neighbors", label: "Neighbors (k)", control: "int", default: 5, min: 1 },
      { name: "weights", label: "Weighting", control: "select", default: "uniform", options: [
        { value: "uniform", label: "Uniform" }, { value: "distance", label: "By distance" },
      ], advanced: true },
    ],
  },
  // ----- Regression -----
  { value: "linear_regression", label: "Linear Regression", task: "regression", params: [] },
  {
    value: "ridge", label: "Ridge Regression", task: "regression",
    params: [{ name: "alpha", label: "Regularization (alpha)", control: "float", default: 1.0, min: 0, step: 0.1 }],
  },
  {
    value: "lasso", label: "Lasso Regression", task: "regression",
    params: [{ name: "alpha", label: "Regularization (alpha)", control: "float", default: 1.0, min: 0, step: 0.1 }],
  },
  { value: "random_forest_regressor", label: "Random Forest", task: "regression", params: TREE_PARAMS(false) },
  {
    value: "svr", label: "Support Vector Regression", task: "regression",
    params: [
      { name: "C", label: "Regularization (C)", control: "float", default: 1.0, min: 0, step: 0.1 },
      { name: "kernel", label: "Kernel", control: "select", default: "rbf", options: [
        { value: "rbf", label: "RBF" }, { value: "linear", label: "Linear" }, { value: "poly", label: "Polynomial" },
      ], advanced: true },
    ],
  },
  { value: "xgboost_regressor", label: "XGBoost", task: "regression", requires: "xgboost", params: TREE_PARAMS(true) },
  { value: "lightgbm_regressor", label: "LightGBM", task: "regression", requires: "lightgbm", params: TREE_PARAMS(true) },
  // ----- Clustering -----
  {
    value: "kmeans", label: "K-Means", task: "clustering",
    params: [
      { name: "n_clusters", label: "Number of clusters", control: "int", default: 8, min: 2 },
      { name: "n_init", label: "Initializations", control: "int", default: 10, min: 1, advanced: true },
    ],
  },
  {
    value: "dbscan", label: "DBSCAN", task: "clustering",
    params: [
      { name: "eps", label: "Neighborhood size (eps)", control: "float", default: 0.5, min: 0, step: 0.1 },
      { name: "min_samples", label: "Min samples", control: "int", default: 5, min: 1 },
    ],
  },
  {
    value: "agglomerative", label: "Agglomerative", task: "clustering",
    params: [
      { name: "n_clusters", label: "Number of clusters", control: "int", default: 2, min: 2 },
      { name: "linkage", label: "Linkage", control: "select", default: "ward", options: [
        { value: "ward", label: "Ward" }, { value: "complete", label: "Complete" },
        { value: "average", label: "Average" }, { value: "single", label: "Single" },
      ], advanced: true },
    ],
  },
  // ----- Dimensionality reduction -----
  {
    value: "pca_fit", label: "PCA (fit)", task: "dimensionality_reduction",
    params: [{ name: "n_components", label: "Components", control: "int", default: 2, min: 1 }],
  },
];

export const ML_MODEL_MAP: Record<string, MlModelDef> = Object.fromEntries(
  ML_MODELS.map((m) => [m.value, m]),
);

export const ML_MODEL_VALUES = ML_MODELS.map((m) => m.value) as [string, ...string[]];

export function getModelDef(value: string): MlModelDef | undefined {
  return ML_MODEL_MAP[value];
}

export function isSupervisedModel(value: string): boolean {
  const def = ML_MODEL_MAP[value];
  return def ? SUPERVISED_TASKS.has(def.task) : false;
}

export function modelsByTask(): { task: MlTask; models: MlModelDef[] }[] {
  return (Object.keys(ML_TASK_LABELS) as MlTask[])
    .map((task) => ({ task, models: ML_MODELS.filter((m) => m.task === task) }))
    .filter((g) => g.models.length > 0);
}

// --- Cross-validation (mlCrossValidate) -------------------------------------
// Mirrors CV_STRATEGIES in app/engine/transformations/ml/cross_validation.py.

export interface CvStrategyDef {
  value: string;
  label: string;
  help: string;
  /** Only offered for this task (classification-only for stratified strategies). */
  classificationOnly?: boolean;
  /** Uses test_size rather than a fold count. */
  usesTestSize?: boolean;
  /** Uses n_repeats (repeated k-fold). */
  usesRepeats?: boolean;
  /** Needs a group column (group k-fold). */
  usesGroup?: boolean;
  /** Has no configurable split count (leave-one-out). */
  noSplits?: boolean;
  /** Offers the shuffle toggle (plain / stratified k-fold). */
  usesShuffle?: boolean;
}

export const CV_STRATEGIES: CvStrategyDef[] = [
  { value: "kfold", label: "K-Fold", help: "Split rows into k equal folds; each is held out once.", usesShuffle: true },
  {
    value: "stratified_kfold",
    label: "Stratified K-Fold",
    help: "K-Fold that preserves the class balance in every fold.",
    classificationOnly: true,
    usesShuffle: true,
  },
  { value: "shuffle_split", label: "Shuffle Split", help: "Random train/test splits repeated k times.", usesTestSize: true },
  {
    value: "stratified_shuffle_split",
    label: "Stratified Shuffle Split",
    help: "Shuffle Split that preserves class balance.",
    classificationOnly: true,
    usesTestSize: true,
  },
  {
    value: "group_kfold",
    label: "Group K-Fold",
    help: "Keeps all rows of a group within a single fold (no leakage across groups).",
    usesGroup: true,
  },
  {
    value: "time_series_split",
    label: "Time Series Split",
    help: "Expanding-window splits that respect time order (train on past, test on future).",
  },
  {
    value: "repeated_kfold",
    label: "Repeated K-Fold",
    help: "K-Fold repeated several times with different shuffles.",
    usesRepeats: true,
  },
  { value: "leave_one_out", label: "Leave-One-Out", help: "Each row is its own test fold. Use only on small data.", noSplits: true },
];

export const CV_STRATEGY_MAP: Record<string, CvStrategyDef> = Object.fromEntries(
  CV_STRATEGIES.map((s) => [s.value, s]),
);
export const CV_STRATEGY_VALUES = CV_STRATEGIES.map((s) => s.value) as [string, ...string[]];

/** CV strategies a given model task can use (stratified ⇒ classification only). */
export function cvStrategiesForTask(task: MlTask | undefined): CvStrategyDef[] {
  if (task === "classification") return CV_STRATEGIES;
  return CV_STRATEGIES.filter((s) => !s.classificationOnly);
}

// Scoring metrics per task. Mirrors _SCORING in the backend node; neg_* metrics
// are negated + renamed in the report (the label drops the "lower is better" sign).
export const CV_SCORING: Record<"classification" | "regression", { value: string; label: string }[]> = {
  classification: [
    { value: "accuracy", label: "Accuracy" },
    { value: "balanced_accuracy", label: "Balanced accuracy" },
    { value: "f1_weighted", label: "F1 (weighted)" },
    { value: "f1_macro", label: "F1 (macro)" },
    { value: "precision_weighted", label: "Precision (weighted)" },
    { value: "recall_weighted", label: "Recall (weighted)" },
    { value: "roc_auc", label: "ROC AUC" },
  ],
  regression: [
    { value: "r2", label: "R²" },
    { value: "neg_root_mean_squared_error", label: "RMSE" },
    { value: "neg_mean_absolute_error", label: "MAE" },
    { value: "neg_mean_squared_error", label: "MSE" },
    { value: "neg_mean_absolute_percentage_error", label: "MAPE" },
  ],
};

export const CV_SCORING_VALUES = [
  ...CV_SCORING.classification.map((s) => s.value),
  ...CV_SCORING.regression.map((s) => s.value),
];

/** Cross-validation supports supervised classification & regression models only. */
export function cvModels(): MlModelDef[] {
  return ML_MODELS.filter((m) => m.task === "classification" || m.task === "regression");
}
