import { useState, useMemo } from "react";
import { useExperiments } from "../../hooks/useExperiments";
import { CreateExperimentModal } from "./components/CreateExperimentModal";
import { ConfirmModal } from "../../components/ui/ConfirmModal/ConfirmModal";
import { Button } from "../../components/ui/Button/Button";
import { Badge } from "../../components/ui/Badge/Badge";
import { DataTable } from "../../components/ui/DataTable/DataTable";
import type { ColumnDef } from "@tanstack/react-table";
import type { components } from "../../api/schema";
import styles from "./ExperimentList.module.css";

type Experiment = components["schemas"]["Model"];

export const ExperimentList = () => {
  const { experiments, loading, error, deleteExperiments, createExperiment, isCreating, isDeleting } = useExperiments();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [rowSelection, setRowSelection] = useState({});

  const columns = useMemo<ColumnDef<Experiment>[]>(
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
      { accessorKey: "name", header: "名前" },
      { accessorKey: "method", header: "手法" },
      {
        accessorKey: "status",
        header: "ステータス",
        cell: ({ row }) => <Badge status={row.original.status} />,
      },
      {
        accessorKey: "created_at",
        header: "作成日時",
        cell: ({ row }) => new Date(row.original.created_at).toLocaleString(),
      },
      {
        accessorKey: "completed_at",
        header: "完了日時",
        cell: ({ row }) => (row.original.completed_at ? new Date(row.original.completed_at).toLocaleString() : "-"),
      },
      { accessorKey: "base_experiment_id", header: "ベース実験ID" },
      { accessorKey: "worker_name", header: "ワーカー名" },
      { accessorKey: "error_message", header: "エラーメッセージ" },
      { accessorKey: "global_auc", header: "全体AUC" },
      { accessorKey: "tpr_at_001_fpr", header: "TPR (0.01% FPR)" },
      { accessorKey: "tpr_at_01_fpr", header: "TPR (0.1% FPR)" },
      { accessorKey: "tpr_at_1_fpr", header: "TPR (1% FPR)" },
      { accessorKey: "total_time", header: "実行時間(秒)" },
      { accessorKey: "batch_size", header: "バッチサイズ" },
      { accessorKey: "max_epochs", header: "最大エポック数" },
      { accessorKey: "seed", header: "シード値" },
      { accessorKey: "num_shadow_models", header: "シャドウモデル数" },
      { accessorKey: "shadow_train_size", header: "Shadow Train Size" },
      { accessorKey: "shadow_test_size", header: "Shadow Test Size" },
      { accessorKey: "target_train_size", header: "Target Train Size" },
      { accessorKey: "target_test_size", header: "Target Test Size" },
      {
        accessorKey: "load_attack_model",
        header: "Load Attack Model",
        cell: ({ row }) => (row.original.load_attack_model ? "Yes" : "No"),
      },
      {
        accessorKey: "load_shadow_model",
        header: "Load Shadow Model",
        cell: ({ row }) => (row.original.load_shadow_model ? "Yes" : "No"),
      },
      {
        accessorKey: "load_target_model",
        header: "Load Target Model",
        cell: ({ row }) => (row.original.load_target_model ? "Yes" : "No"),
      },
      { accessorKey: "dataset_json_path", header: "データセットパス" },
      { accessorKey: "execution_log_path", header: "実行ログパス" },
      { accessorKey: "minio_path", header: "MinIOパス" },
      { accessorKey: "notes", header: "備考" },
      {
        accessorKey: "hyperparameters",
        header: "ハイパーパラメータ",
        cell: ({ row }) => <code>{JSON.stringify(row.original.hyperparameters)}</code>,
      },
      {
        accessorKey: "other_files",
        header: "その他のファイル",
        cell: ({ row }) => (row.original.other_files ? <code>{JSON.stringify(row.original.other_files)}</code> : "-"),
      },
      {
        accessorKey: "other_metrics",
        header: "その他のメトリクス",
        cell: ({ row }) => (row.original.other_metrics ? <code>{JSON.stringify(row.original.other_metrics)}</code> : "-"),
      },
    ],
    []
  );

  if (loading) return <div>実験情報を読み込み中...</div>;
  if (error) return <div>エラー: {error.message}</div>;

  const selectedCount = Object.keys(rowSelection).length;
  const selectedIds = Object.keys(rowSelection).map((index) => experiments[Number(index)].id);

  const handleDeleteConfirm = () => {
    deleteExperiments(selectedIds, {
      onSuccess: () => {
        setRowSelection({});
        setIsDeleteModalOpen(false);
      },
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.listHeader}>
        <h2>実験一覧</h2>
        <div className={styles.listActions}>
          {selectedCount > 0 && (
            <Button variant="danger" onClick={() => setIsDeleteModalOpen(true)}>
              選択した項目を削除 ({selectedCount})
            </Button>
          )}
          <Button variant="primary" onClick={() => setIsCreateModalOpen(true)}>
            新しい実験を作成
          </Button>
        </div>
      </div>

      <DataTable
        data={experiments}
        columns={columns}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />

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
        message={`選択した ${selectedCount} 件の実験を本当に削除しますか？この操作は取り消せません。`}
        isConfirming={isDeleting}
      />
    </div>
  );
};
