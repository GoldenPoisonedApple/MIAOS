import { FilterManager } from "./components/FilterManager";
import { useFilters } from "../../hooks/useFilters";
import styles from "./FilterList.module.css";

export const FilterList = () => {
  const { error } = useFilters();

  if (error) {
    return <div>エラー: {error.message}</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.listHeader}>
        <h2>フィルタ一覧</h2>
      </div>
      <FilterManager />
    </div>
  );
};
