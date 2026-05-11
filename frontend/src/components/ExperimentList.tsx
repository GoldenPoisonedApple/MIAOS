import { useExperiments } from "../hooks/useExperiments";

export const ExperimentList = () => {
  const { experiments, loading, error, deleteExperiment } = useExperiments();

  if (loading) return <div className="loading">実験情報を読み込み中...</div>;
  if (error) return <div className="error">エラー: {error.message}</div>;

  return (
    <div className="table-container">
      <h2>実験一覧</h2>
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
    </div>
  );
};
