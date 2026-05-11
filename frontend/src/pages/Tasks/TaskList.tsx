import { useState, useMemo } from "react";
import { useTasks } from "../../hooks/useTasks";
import { ConfirmModal } from "../../components/ui/ConfirmModal/ConfirmModal";
import { Button } from "../../components/ui/Button/Button";
import { DataTable } from "../../components/ui/DataTable/DataTable";
import type { ColumnDef } from "@tanstack/react-table";
import type { components } from "../../api/schema";
import styles from "./TaskList.module.css";

type Task = components["schemas"]["Task"];

export const TaskList = () => {
  const { tasks, loading, error, deleteTasks, isDeleting } = useTasks();
  const [rowSelection, setRowSelection] = useState({});
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const columns = useMemo<ColumnDef<Task>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <input
            type="checkbox"
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
          />
        ),
      },
      { accessorKey: "id", header: "ID" },
      { accessorKey: "task", header: "タスク名" },
      { accessorKey: "error_message", header: "エラーメッセージ" },
      {
        accessorKey: "args_control",
        header: "制御情報 (args_control)",
        cell: ({ row }) => <code>{JSON.stringify(row.original.args_control)}</code>,
      },
      {
        accessorKey: "args_keyword",
        header: "キーワード引数 (args_keyword)",
        cell: ({ row }) => <code>{JSON.stringify(row.original.args_keyword)}</code>,
      },
      {
        accessorKey: "args_positional",
        header: "位置引数 (args_positional)",
        cell: ({ row }) => <code>{JSON.stringify(row.original.args_positional)}</code>,
      },
    ],
    []
  );

  if (loading) return <div>タスク情報を読み込み中...</div>;
  if (error) return <div>エラー: {error.message}</div>;

  const selectedCount = Object.keys(rowSelection).length;
  const selectedIds = Object.keys(rowSelection).map((index) => tasks[Number(index)].id);

  const handleDeleteConfirm = () => {
    deleteTasks(selectedIds, {
      onSuccess: () => {
        setRowSelection({});
        setIsDeleteModalOpen(false);
      },
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.listHeader}>
        <h2>タスク一覧</h2>
        <div className={styles.listActions}>
          {selectedCount > 0 && (
            <Button variant="danger" onClick={() => setIsDeleteModalOpen(true)}>
              選択した項目を削除 ({selectedCount})
            </Button>
          )}
        </div>
      </div>

      <DataTable
        data={tasks}
        columns={columns}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleDeleteConfirm}
        title="タスクの削除"
        message={`選択した ${selectedCount} 件のタスクを本当に削除しますか？この操作は取り消せません。`}
        isConfirming={isDeleting}
      />
    </div>
  );
};
