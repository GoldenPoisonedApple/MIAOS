import type { components } from "../api/schema";
import type { CreateExperimentRequest } from "../hooks/useExperiments";

type Experiment = components["schemas"]["Model"];

export type ApplySplit = "target_train" | "target_test" | "shadow_train" | "shadow_test";

export type ExperimentFormData = Omit<CreateExperimentRequest, "watermark">;

export type WatermarkFormState = {
  filterId: string;
  seedOffset: number;
  applyFractions: Record<ApplySplit, string>;
  showTestSplits: boolean;
};

export type ExperimentFormState = {
  formData: ExperimentFormData;
  watermark: WatermarkFormState;
};

const APPLY_SPLITS: ApplySplit[] = ["target_train", "target_test", "shadow_train", "shadow_test"];

const defaultApplyFractions = (): Record<ApplySplit, string> => ({
  target_train: "1",
  target_test: "",
  shadow_train: "",
  shadow_test: "",
});

const defaultWatermarkState = (): WatermarkFormState => ({
  filterId: "",
  seedOffset: 0,
  applyFractions: defaultApplyFractions(),
  showTestSplits: false,
});

export const getDefaultDateName = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}_${String(d.getHours()).padStart(2, "0")}-${String(d.getMinutes()).padStart(2, "0")}-${String(d.getSeconds()).padStart(2, "0")}`;
};

export const getDefaultFormState = (): ExperimentFormState => ({
  formData: {
    name: getDefaultDateName(),
    method: "OfflineLira",
    base_experiment_id: null,
    notes: null,
    seed: 42,
    batch_size: 256,
    max_epochs: 200,
    num_shadow_models: 100,
    shadow_train_size: 10520,
    shadow_test_size: 10520,
    target_train_size: 10520,
    target_test_size: 10520,
    load_attack_model: false,
    load_shadow_model: false,
    load_target_model: false,
    hyperparameters: {} as Record<string, never>,
  },
  watermark: defaultWatermarkState(),
});

const watermarkToFormState = (watermark: Experiment["watermark"]): WatermarkFormState => {
  if (!watermark?.enabled || !watermark.filter_id) {
    return defaultWatermarkState();
  }

  const applyFractions = defaultApplyFractions();
  for (const key of APPLY_SPLITS) {
    const value = watermark.apply?.[key];
    applyFractions[key] = value != null && value > 0 ? String(value) : "";
  }

  const hasTestSplits =
    applyFractions.target_test.trim() !== "" || applyFractions.shadow_test.trim() !== "";

  return {
    filterId: watermark.filter_id,
    seedOffset: watermark.seed_offset ?? 0,
    applyFractions,
    showTestSplits: hasTestSplits,
  };
};

export const getFormStateFromExperiment = (source: Experiment): ExperimentFormState => ({
  formData: {
    name: source.name,
    method: source.method,
    base_experiment_id: source.base_experiment_id ?? null,
    notes: source.notes ?? null,
    seed: source.seed,
    batch_size: source.batch_size,
    max_epochs: source.max_epochs,
    num_shadow_models: source.num_shadow_models,
    shadow_train_size: source.shadow_train_size,
    shadow_test_size: source.shadow_test_size,
    target_train_size: source.target_train_size,
    target_test_size: source.target_test_size,
    load_attack_model: source.load_attack_model,
    load_shadow_model: source.load_shadow_model,
    load_target_model: source.load_target_model,
    hyperparameters: structuredClone(source.hyperparameters ?? {}) as Record<string, never>,
  },
  watermark: watermarkToFormState(source.watermark),
});
