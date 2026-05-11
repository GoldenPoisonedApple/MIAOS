import { useState } from "react";
import { useExperiments } from "../hooks/useExperiments";
import { CreateExperimentModal } from "./CreateExperimentModal";

export const ExperimentList = () => {
  const { experiments, loading, error, deleteExperiment, createExperiment, isCreating } = useExperiments();
  const [isModalOpen, setIsModalOpen] = useState(false);

  if (loading) return <div className="loading">実験情報を読み込み中...</div>;
  if (error) return <div className="error">エラー: {error.message}</div>;

  return (
    <div className="table-container">
      <div className="list-header">
        <h2>実験一覧</h2>
        <button className="button create-button" onClick={() => setIsModalOpen(true)}>
          新しい実験を作成
        </button>
      </div>
      
      {experiments.length === 0 ? (
        <p>実験データがありません</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
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
                <th>アクション</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id}>
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
                  <td>
                    <button
                      onClick={() => {
                        if (window.confirm(`実験 ID:${exp.id} を本当に削除しますか？`)) {
                          deleteExperiment(exp.id);
                        }
                      }}
                      className="button delete-button"
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateExperimentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={createExperiment}
        isCreating={isCreating}
      />
    </div>
  );
};
