import { useState } from "react";
import { useTasks } from "../hooks/useTasks";
import { ConfirmModal } from "./ConfirmModal";

export const TaskList = () => {
  const { tasks, loading, error, deleteTasks, isDeleting } = useTasks();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  if (loading) return <div className="loading">タスク情報を読み込み中...</div>;
  if (error) return <div className="error">エラー: {error.message}</div>;

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(new Set(tasks.map((task) => task.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedIds(newSet);
  };

  const handleDeleteConfirm = () => {
    deleteTasks(Array.from(selectedIds), {
      onSuccess: () => {
        setSelectedIds(new Set());
        setIsDeleteModalOpen(false);
      },
    });
  };

  return (
    <div className="table-container">
      <div className="list-header">
        <h2>タスク一覧</h2>
        <div className="list-actions">
          {selectedIds.size > 0 && (
            <button className="button delete-button" onClick={() => setIsDeleteModalOpen(true)}>
              選択した項目を削除 ({selectedIds.size})
            </button>
          )}
        </div>
      </div>

      {tasks.length === 0 ? (
        <p>タスクデータがありません</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "40px", textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={tasks.length > 0 && selectedIds.size === tasks.length}
                    onChange={handleSelectAll}
                  />
                </th>
                <th>ID</th>
                <th>タスク名</th>
                <th>エラーメッセージ</th>
                <th>制御情報 (args_control)</th>
                <th>キーワード引数 (args_keyword)</th>
                <th>位置引数 (args_positional)</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(task.id)}
                      onChange={(e) => handleSelectOne(task.id, e.target.checked)}
                    />
                  </td>
                  <td>{task.id}</td>
                  <td>{task.task}</td>
                  <td className="error-text">{task.error_message || "-"}</td>
                  <td>
                    <code>{JSON.stringify(task.args_control)}</code>
                  </td>
                  <td>
                    <code>{JSON.stringify(task.args_keyword)}</code>
                  </td>
                  <td>
                    <code>{JSON.stringify(task.args_positional)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleDeleteConfirm}
        title="タスクの削除"
        message={`選択した ${selectedIds.size} 件のタスクを本当に削除しますか？この操作は取り消せません。`}
        isConfirming={isDeleting}
      />
    </div>
  );
};
