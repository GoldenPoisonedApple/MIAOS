import { useTasks } from "../hooks/useTasks";

export const TaskList = () => {
  const { tasks, loading, error, deleteTask } = useTasks();

  if (loading) return <div className="loading">タスク情報を読み込み中...</div>;
  if (error) return <div className="error">エラー: {error.message}</div>;

  return (
    <div className="table-container">
      <h2>タスク一覧</h2>
      {tasks.length === 0 ? (
        <p>タスクデータがありません</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>タスク名</th>
                <th>エラーメッセージ</th>
                <th>アクション</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>{task.id}</td>
                  <td>{task.task}</td>
                  <td className="error-text">{task.error_message || "-"}</td>
                  <td>
                    <button
                      onClick={() => {
                        if (window.confirm(`タスク ID:${task.id} を本当に削除しますか？`)) {
                          deleteTask(task.id);
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
