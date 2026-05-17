import { useState, useMemo } from "react";
import { useTasks } from "../../hooks/useTasks";
import { useDynamicColumns } from "../../hooks/useDynamicColumns";
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

  const { dynamicColumns, defaultHiddenColumns } = useDynamicColumns<Task>(tasks, [
    { key: "args_control", prefix: "Ctrl" },
    { key: "args_keyword", prefix: "Kwarg" },
    { key: "args_positional", prefix: "Arg" },
  ]);

  const columns = useMemo<ColumnDef<Task>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
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
			{ accessorKey: "experiment_id", header: "実験ID" },
      { accessorKey: "task", header: "タスク名" },
      { accessorKey: "error_message", header: "エラーメッセージ" },
      ...dynamicColumns,
    ],
    [dynamicColumns]
  );

  if (loading) return <div>タスク情報を読み込み中...</div>;
  if (error) return <div>エラー: {error.message}</div>;

  const selectedRowIds = Object.entries(rowSelection)
    .filter(([, selected]) => selected)
    .map(([id]) => id);
  const selectedCount = selectedRowIds.length;
  const selectedIds = selectedRowIds;

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
        initialColumnVisibility={{
          ...defaultHiddenColumns,
        }}
        getRowId={(row) => row.id}
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
