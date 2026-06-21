import { useState } from "react";
import { useFilters } from "../../../hooks/useFilters";
import { Button } from "../../../components/ui/Button/Button";
import { fileApiPath } from "../../../utils/fileApiPath";
import styles from "./FilterManager.module.css";

export const FilterManager = () => {
  const { filters, loading, uploadFilter, isUploading } = useFilters();
  const [filterId, setFilterId] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!filterId.trim() || !file) return;
    uploadFilter(
      { id: filterId.trim(), file },
      {
        onSuccess: () => {
          setFilterId("");
          setFile(null);
        },
      }
    );
  };

  return (
    <section className={styles.section}>
      <h3>フィルタ画像</h3>
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
                  width={32}
                  height={32}
                />
                <span className={styles.filterId}>{f.id}</span>
                <a
                  href={fileApiPath(`filters/${f.id}.png`)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  プレビュー
                </a>
              </li>
            ))
          )}
        </ul>
      )}

      <form onSubmit={handleSubmit} className={styles.uploadForm}>
        <div className={styles.formRow}>
          <label>
            ID
            <input
              type="text"
              value={filterId}
              onChange={(e) => setFilterId(e.target.value)}
              placeholder="circle"
              pattern="[a-zA-Z0-9_-]+"
              required
            />
          </label>
          <label>
            PNG (32×32)
            <input
              type="file"
              accept="image/png"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
        </div>
        <Button type="submit" variant="primary" disabled={isUploading || !file}>
          {isUploading ? "アップロード中..." : "フィルタを追加"}
        </Button>
      </form>
    </section>
  );
};
