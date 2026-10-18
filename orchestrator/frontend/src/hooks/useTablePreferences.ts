import { useCallback, useEffect, useMemo, useState } from "react";
import type { ColumnOrderState, OnChangeFn, VisibilityState } from "@tanstack/react-table";
import {
  loadTablePreferences,
  mergeTablePreferences,
  saveTablePreferences,
  type TablePreferencesDefaults,
  type TablePreferencesV1,
} from "../utils/tablePreferences";

interface UseTablePreferencesResult {
  columnVisibility: VisibilityState;
  columnOrder: ColumnOrderState;
  onColumnVisibilityChange: OnChangeFn<VisibilityState>;
  onColumnOrderChange: OnChangeFn<ColumnOrderState>;
}

export function useTablePreferences(
  storageKey: string | undefined,
  defaults: TablePreferencesDefaults,
  columnIds: string[]
): UseTablePreferencesResult {
  const [storedPrefs, setStoredPrefs] = useState<TablePreferencesV1>(() =>
    mergeTablePreferences(
      storageKey ? loadTablePreferences(storageKey) : null,
      defaults,
      columnIds
    )
  );

  const prefs = useMemo(
    () => mergeTablePreferences(storedPrefs, defaults, columnIds),
    [storedPrefs, defaults, columnIds]
  );

  // 設定変更を localStorage に保存
  useEffect(() => {
    if (!storageKey) return;
    saveTablePreferences(storageKey, prefs);
  }, [storageKey, prefs]);

  const onColumnVisibilityChange = useCallback<OnChangeFn<VisibilityState>>(
    (updater) => {
      setStoredPrefs((current) => {
        const currentMerged = mergeTablePreferences(current, defaults, columnIds);
        return {
          ...current,
          columnVisibility:
            typeof updater === "function"
              ? updater(currentMerged.columnVisibility)
              : updater,
        };
      });
    },
    [defaults, columnIds]
  );

  const onColumnOrderChange = useCallback<OnChangeFn<ColumnOrderState>>(
    (updater) => {
      setStoredPrefs((current) => {
        const currentMerged = mergeTablePreferences(current, defaults, columnIds);
        return {
          ...current,
          columnOrder:
            typeof updater === "function" ? updater(currentMerged.columnOrder) : updater,
        };
      });
    },
    [defaults, columnIds]
  );

  return {
    columnVisibility: prefs.columnVisibility,
    columnOrder: prefs.columnOrder,
    onColumnVisibilityChange,
    onColumnOrderChange,
  };
}
