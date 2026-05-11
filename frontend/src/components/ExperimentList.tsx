import { useState } from "react";
import { useExperiments } from "../hooks/useExperiments";
import { CreateExperimentModal } from "./CreateExperimentModal";
import { ConfirmModal } from "./ConfirmModal";

export const ExperimentList = () => {
  const { experiments, loading, error, deleteExperiments, createExperiment, isCreating, isDeleting } = useExperiments();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  if (loading) return <div className="loading">実験情報を読み込み中...</div>;
  if (error) return <div className="error">エラー: {error.message}</div>;

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(new Set(experiments.map((exp) => exp.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: number, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedIds(newSet);
  };

  const handleDeleteConfirm = () => {
    deleteExperiments(Array.from(selectedIds), {
      onSuccess: () => {
        setSelectedIds(new Set());
        setIsDeleteModalOpen(false);
      },
    });
  };

  return (
    <div className="table-container">
      <div className="list-header">
        <h2>実験一覧</h2>
        <div className="list-actions">
          {selectedIds.size > 0 && (
            <button className="button delete-button" onClick={() => setIsDeleteModalOpen(true)}>
              選択した項目を削除 ({selectedIds.size})
            </button>
          )}
          <button className="button create-button" onClick={() => setIsCreateModalOpen(true)}>
            新しい実験を作成
          </button>
        </div>
      </div>

      {experiments.length === 0 ? (
        <p>実験データがありません</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "40px", textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={experiments.length > 0 && selectedIds.size === experiments.length}
                    onChange={handleSelectAll}
                  />
                </th>
                <th>ID</th>
                <th>名前</th>
                <th>手法</th>
                <th>ステータス</th>
                <th>作成日時</th>
                <th>完了日時</th>
                <th>ベース実験ID</th>
                <th>ワーカー名</th>
                <th>エラーメッセージ</th>
                <th>全体AUC</th>
                <th>TPR (0.01% FPR)</th>
                <th>TPR (0.1% FPR)</th>
                <th>TPR (1% FPR)</th>
                <th>実行時間(秒)</th>
                <th>バッチサイズ</th>
                <th>最大エポック数</th>
                <th>シード値</th>
                <th>シャドウモデル数</th>
                <th>Shadow Train Size</th>
                <th>Shadow Test Size</th>
                <th>Target Train Size</th>
                <th>Target Test Size</th>
                <th>Load Attack Model</th>
                <th>Load Shadow Model</th>
                <th>Load Target Model</th>
                <th>データセットパス</th>
                <th>実行ログパス</th>
                <th>MinIOパス</th>
                <th>備考</th>
                <th>ハイパーパラメータ</th>
                <th>その他のファイル</th>
                <th>その他のメトリクス</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id}>
                  <td style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(exp.id)}
                      onChange={(e) => handleSelectOne(exp.id, e.target.checked)}
                    />
                  </td>
                  <td>{exp.id}</td>
                  <td>{exp.name}</td>
                  <td>{exp.method}</td>
                  <td>
                    <span className={`status-badge status-${exp.status.toLowerCase()}`}>
                      {exp.status}
                    </span>
                  </td>
                  <td>{new Date(exp.created_at).toLocaleString()}</td>
                  <td>{exp.completed_at ? new Date(exp.completed_at).toLocaleString() : "-"}</td>
                  <td>{exp.base_experiment_id ?? "-"}</td>
                  <td>{exp.worker_name || "-"}</td>
                  <td className="error-text">{exp.error_message || "-"}</td>
                  <td>{exp.global_auc ?? "-"}</td>
                  <td>{exp.tpr_at_001_fpr ?? "-"}</td>
                  <td>{exp.tpr_at_01_fpr ?? "-"}</td>
                  <td>{exp.tpr_at_1_fpr ?? "-"}</td>
                  <td>{exp.total_time ?? "-"}</td>
                  <td>{exp.batch_size}</td>
                  <td>{exp.max_epochs}</td>
                  <td>{exp.seed}</td>
                  <td>{exp.num_shadow_models}</td>
                  <td>{exp.shadow_train_size}</td>
                  <td>{exp.shadow_test_size}</td>
                  <td>{exp.target_train_size}</td>
                  <td>{exp.target_test_size}</td>
                  <td>{exp.load_attack_model ? "Yes" : "No"}</td>
                  <td>{exp.load_shadow_model ? "Yes" : "No"}</td>
                  <td>{exp.load_target_model ? "Yes" : "No"}</td>
                  <td>{exp.dataset_json_path || "-"}</td>
                  <td>{exp.execution_log_path || "-"}</td>
                  <td>{exp.minio_path || "-"}</td>
                  <td>{exp.notes || "-"}</td>
                  <td>
                    <code>{JSON.stringify(exp.hyperparameters)}</code>
                  </td>
                  <td>
                    {exp.other_files ? <code>{JSON.stringify(exp.other_files)}</code> : "-"}
                  </td>
                  <td>
                    {exp.other_metrics ? <code>{JSON.stringify(exp.other_metrics)}</code> : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateExperimentModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={createExperiment}
        isCreating={isCreating}
      />

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleDeleteConfirm}
        title="実験の削除"
        message={`選択した ${selectedIds.size} 件の実験を本当に削除しますか？この操作は取り消せません。`}
        isConfirming={isDeleting}
      />
    </div>
  );
};
