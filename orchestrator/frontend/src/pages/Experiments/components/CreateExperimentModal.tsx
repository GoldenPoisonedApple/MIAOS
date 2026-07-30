import { useState } from "react";
import type { CreateExperimentRequest } from "../../../hooks/useExperiments";
import type { components } from "../../../api/schema";
import { useFilters } from "../../../hooks/useFilters";
import { Modal } from "../../../components/ui/Modal/Modal";
import { Button } from "../../../components/ui/Button/Button";
import { KeyValueEditor } from "../../../components/ui/KeyValueEditor/KeyValueEditor";
import {
  type ApplySplit,
  type ExperimentFormData,
  type ExperimentFormState,
  getDefaultFormState,
  getFormStateFromExperiment,
} from "../../../utils/experimentForm";
import styles from "./CreateExperimentModal.module.css";

const WATERMARK_SPLITS = [
  { key: "target_train", label: "Target Train" },
  { key: "target_test", label: "Target Test" },
  { key: "shadow_train", label: "Shadow Train" },
  { key: "shadow_test", label: "Shadow Test" },
] as const;

type WatermarkConfig = components["schemas"]["WatermarkConfig"];
type Experiment = components["schemas"]["Model"];

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (req: CreateExperimentRequest) => Promise<void>;
  isCreating: boolean;
  sourceExperiment?: Experiment | null;
}

interface FormProps {
  initialState: ExperimentFormState;
  onClose: () => void;
  onSubmit: (req: CreateExperimentRequest) => Promise<void>;
  isCreating: boolean;
}

const CreateExperimentForm = ({ initialState, onClose, onSubmit, isCreating }: FormProps) => {
  const { filters, loading: filtersLoading } = useFilters();

  const [formData, setFormData] = useState<ExperimentFormData>(initialState.formData);
  const [filterId, setFilterId] = useState(initialState.watermark.filterId);
  const [seedOffset, setSeedOffset] = useState(initialState.watermark.seedOffset);
  const [applyFractions, setApplyFractions] = useState<Record<ApplySplit, string>>(
    initialState.watermark.applyFractions
  );
  const [showTestSplits, setShowTestSplits] = useState(initialState.watermark.showTestSplits);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;

    setFormData((prev) => {
      if (type === "checkbox") {
        return { ...prev, [name]: (e.target as HTMLInputElement).checked };
      }
      if (type === "number") {
        return { ...prev, [name]: value === "" ? 0 : Number(value) };
      }
      return { ...prev, [name]: value };
    });
  };

  const buildWatermark = (): WatermarkConfig | null => {
    if (!filterId) {
      return null;
    }

    const apply: Record<string, number> = {};
    for (const { key } of WATERMARK_SPLITS) {
      const raw = applyFractions[key].trim();
      if (!raw) continue;
      const fraction = Number(raw);
      if (fraction > 0) {
        apply[key] = fraction;
      }
    }

    return {
      enabled: true,
      filter_id: filterId,
      apply,
      seed_offset: seedOffset,
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      ...formData,
      hyperparameters: formData.hyperparameters as Record<string, never>,
      watermark: buildWatermark(),
    });
    onClose();
  };

  return (
    <form onSubmit={handleSubmit} className={styles.modalForm}>
        <div className={styles.formGroup}>
          <label>実験名</label>
          <input type="text" name="name" value={formData.name} onChange={handleChange} required />
        </div>

        <div className={styles.formGroup}>
          <label>手法 (Method)</label>
          <select name="method" value={formData.method} onChange={handleChange}>
            <option value="OfflineLira">OfflineLira</option>
            <option value="OnlineLira">OnlineLira</option>
            <option value="Shokri">Shokri</option>
						<option value="LfMia">LfMia</option>
          </select>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>バッチサイズ</label>
            <input type="number" name="batch_size" value={formData.batch_size} onChange={handleChange} required />
          </div>
          <div className={styles.formGroup}>
            <label>最大エポック数</label>
            <input type="number" name="max_epochs" value={formData.max_epochs} onChange={handleChange} required />
          </div>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>シード値</label>
            <input type="number" name="seed" value={formData.seed} onChange={handleChange} required />
          </div>
          <div className={styles.formGroup}>
            <label>シャドウモデル数</label>
            <input type="number" name="num_shadow_models" value={formData.num_shadow_models} onChange={handleChange} required />
          </div>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Shadow Train Size</label>
            <input type="number" name="shadow_train_size" value={formData.shadow_train_size} onChange={handleChange} required />
          </div>
          <div className={styles.formGroup}>
            <label>Shadow Test Size</label>
            <input type="number" name="shadow_test_size" value={formData.shadow_test_size} onChange={handleChange} required />
          </div>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Target Train Size</label>
            <input type="number" name="target_train_size" value={formData.target_train_size} onChange={handleChange} required />
          </div>
          <div className={styles.formGroup}>
            <label>Target Test Size</label>
            <input type="number" name="target_test_size" value={formData.target_test_size} onChange={handleChange} required />
          </div>
        </div>

        <div className={styles.formGroup}>
          <label>ベース実験ID (任意)</label>
          <input
            type="number"
            name="base_experiment_id"
            value={formData.base_experiment_id || ""}
            onChange={(e) => setFormData((prev) => ({ ...prev, base_experiment_id: e.target.value ? Number(e.target.value) : null }))}
          />
        </div>

        <div className={styles.formCheckboxGroup}>
          <label>
            <input type="checkbox" name="load_attack_model" checked={formData.load_attack_model} onChange={handleChange} />
            Load Attack Model
          </label>
          <label>
            <input type="checkbox" name="load_shadow_model" checked={formData.load_shadow_model} onChange={handleChange} />
            Load Shadow Model
          </label>
          <label>
            <input type="checkbox" name="load_target_model" checked={formData.load_target_model} onChange={handleChange} />
            Load Target Model
          </label>
        </div>

        <fieldset className={styles.watermarkFieldset}>
          <legend>透かし（フィルタ）</legend>
          <div className={styles.formGroup}>
            <label>フィルタ</label>
            <select value={filterId} onChange={(e) => setFilterId(e.target.value)} disabled={filtersLoading}>
              <option value="">なし</option>
              {filters.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.id}
                </option>
              ))}
            </select>
          </div>
          {filterId && (
            <>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label>Target Train 付与割合 (0–1)</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={applyFractions.target_train}
                    onChange={(e) =>
                      setApplyFractions((prev) => ({ ...prev, target_train: e.target.value }))
                    }
                  />
                </div>
                <div className={styles.formGroup}>
                  <label>Shadow Train 付与割合 (0–1)</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={applyFractions.shadow_train}
                    onChange={(e) =>
                      setApplyFractions((prev) => ({ ...prev, shadow_train: e.target.value }))
                    }
                  />
                </div>
              </div>
              <button
                type="button"
                className={styles.toggleTestSplits}
                onClick={() => setShowTestSplits((v) => !v)}
              >
                {showTestSplits ? "テスト分割を隠す" : "テスト分割を表示"}
              </button>
              {showTestSplits && (
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label>Target Test 付与割合 (0–1)</label>
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={applyFractions.target_test}
                      onChange={(e) =>
                        setApplyFractions((prev) => ({ ...prev, target_test: e.target.value }))
                      }
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label>Shadow Test 付与割合 (0–1)</label>
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={applyFractions.shadow_test}
                      onChange={(e) =>
                        setApplyFractions((prev) => ({ ...prev, shadow_test: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}
              <div className={styles.formGroup}>
                <label>seed_offset</label>
                <input
                  type="number"
                  value={seedOffset}
                  onChange={(e) => setSeedOffset(Number(e.target.value))}
                />
              </div>
            </>
          )}
        </fieldset>

        <div className={styles.formGroup}>
          <label>Hyperparameters（その他）</label>
          <KeyValueEditor
            value={formData.hyperparameters}
            onChange={(val) => setFormData((prev) => ({ ...prev, hyperparameters: val as Record<string, never> }))}
          />
        </div>

        <div className={styles.formGroup}>
          <label>備考 (Notes)</label>
          <textarea
            name="notes"
            value={formData.notes || ""}
            onChange={(e) => setFormData((prev) => ({ ...prev, notes: e.target.value || null }))}
            rows={3}
          />
        </div>

        <div className={styles.modalActions}>
          <Button variant="outline" type="button" onClick={onClose} disabled={isCreating}>
            キャンセル
          </Button>
          <Button variant="primary" type="submit" disabled={isCreating}>
            {isCreating ? "作成中..." : "作成する"}
          </Button>
        </div>
      </form>
  );
};

export const CreateExperimentModal = ({
  isOpen,
  onClose,
  onSubmit,
  isCreating,
  sourceExperiment = null,
}: Props) => {
  if (!isOpen) {
    return null;
  }

  const initialState = sourceExperiment
    ? getFormStateFromExperiment(sourceExperiment)
    : getDefaultFormState();

  const modalTitle = sourceExperiment
    ? `実験を作成（#${sourceExperiment.id} から流用）`
    : "新しい実験を作成";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle}>
      <CreateExperimentForm
        key={sourceExperiment?.id ?? "new"}
        initialState={initialState}
        onClose={onClose}
        onSubmit={onSubmit}
        isCreating={isCreating}
      />
    </Modal>
  );
};
