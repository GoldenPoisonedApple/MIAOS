import { useState } from "react";
import { FilterApiError, useFilters } from "../../../hooks/useFilters";
import { Button } from "../../../components/ui/Button/Button";
import { ConfirmModal } from "../../../components/ui/ConfirmModal/ConfirmModal";
import { fileApiPath } from "../../../utils/fileApiPath";
import { deriveFilterId, isValidFilterId } from "../../../utils/filterId";
import styles from "./FilterManager.module.css";

export const FilterManager = () => {
  const { filters, loading, uploadFilter, isUploading, deleteFilter, isDeleting } = useFilters();
  const [file, setFile] = useState<File | null>(null);
  const [filterId, setFilterId] = useState("");
  const [showIdInput, setShowIdInput] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const resetUploadForm = () => {
    setFile(null);
    setFilterId("");
    setShowIdInput(false);
    setUploadError(null);
    setFileInputKey((k) => k + 1);
  };

  const handleFileChange = (selected: File | null) => {
    setFile(selected);
    setUploadError(null);

    if (!selected) {
      setShowIdInput(false);
      setFilterId("");
      return;
    }

    const derived = deriveFilterId(selected.name);
    if (derived === null) {
      setShowIdInput(true);
      setFilterId("");
      return;
    }

    if (filters.some((f) => f.id === derived)) {
      setShowIdInput(true);
      setFilterId(derived);
      return;
    }

    setShowIdInput(false);
    setFilterId(derived);
  };

  const resolveUploadId = (): string | null => {
    if (!file) return null;

    if (showIdInput) {
      const id = filterId.trim();
      return isValidFilterId(id) ? id : null;
    }

    return deriveFilterId(file.name);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = resolveUploadId();
    if (!id || !file) {
      setUploadError("有効なフィルタ ID を指定してください（英数字・`_`・`-` のみ）");
      return;
    }

    setUploadError(null);
    uploadFilter(
      { id, file },
      {
        onSuccess: () => {
          resetUploadForm();
        },
        onError: (err) => {
          if (err instanceof FilterApiError && err.status === 409) {
            setShowIdInput(true);
            setFilterId(id);
            setUploadError("この ID は既に登録されています。別の ID を入力してください。");
            return;
          }
          setUploadError(err instanceof Error ? err.message : "フィルタのアップロードに失敗しました");
        },
      }
    );
  };

  const handleDeleteConfirm = () => {
    if (!deleteTargetId) return;
    deleteFilter(deleteTargetId, {
      onSuccess: () => {
        setDeleteTargetId(null);
      },
      onError: (err) => {
        alert(err instanceof Error ? err.message : "フィルタの削除に失敗しました");
      },
    });
  };

  const uploadId = resolveUploadId();
  const canUpload = Boolean(file && uploadId && !isUploading);

  return (
    <section className={styles.section}>
      {loading ? (
        <p>読み込み中...</p>
      ) : (
        <ul className={styles.filterList}>
          {filters.length === 0 ? (
            <li className={styles.empty}>登録済みフィルタはありません</li>
          ) : (
            filters.map((f) => (
              <li key={f.id} className={styles.filterItem}>
                <img
                  className={styles.thumbnail}
                  src={fileApiPath(`filters/${f.id}.png`)}
                  alt={f.id}
                  width={96}
                  height={96}
                />
                <span className={styles.filterId}>{f.id}</span>
                <div className={styles.itemActions}>
                  <a
                    href={fileApiPath(`filters/${f.id}.png`)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    プレビュー
                  </a>
                  <Button variant="danger" onClick={() => setDeleteTargetId(f.id)}>
                    削除
                  </Button>
                </div>
              </li>
            ))
          )}
        </ul>
      )}

      <form onSubmit={handleSubmit} className={styles.uploadForm}>
        <div className={styles.formRow}>
          <label>
            PNG (32×32)
            <input
              key={fileInputKey}
              type="file"
              accept="image/png"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              required
            />
          </label>
          {showIdInput && (
            <label>
              フィルタ ID
              <input
                type="text"
                value={filterId}
                onChange={(e) => {
                  setFilterId(e.target.value);
                  setUploadError(null);
                }}
                placeholder="circle"
                pattern="[a-zA-Z0-9_-]+"
                required
              />
            </label>
          )}
        </div>
        {showIdInput && !uploadError && (
          <p className={styles.hint}>
            ファイル名から ID を自動設定できないか、既存 ID と衝突しています。別の ID を入力してください。
          </p>
        )}
        {uploadError && <p className={styles.errorMessage}>{uploadError}</p>}
        <Button type="submit" variant="primary" disabled={!canUpload}>
          {isUploading ? "アップロード中..." : "フィルタを追加"}
        </Button>
      </form>

      <ConfirmModal
        isOpen={deleteTargetId !== null}
        onClose={() => setDeleteTargetId(null)}
        onConfirm={handleDeleteConfirm}
        title="フィルタの削除"
        message={`フィルタ「${deleteTargetId ?? ""}」を本当に削除しますか？この操作は取り消せません。`}
        isConfirming={isDeleting}
      />
    </section>
  );
};
