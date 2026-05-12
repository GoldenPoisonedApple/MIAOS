import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";

interface DictionaryConfig<TData> {
  key: keyof TData;
  prefix: string;
}

export function useDynamicColumns<TData extends Record<string, unknown>>(
  data: TData[],
  dictionaryConfigs: DictionaryConfig<TData>[]
): { dynamicColumns: ColumnDef<TData>[]; defaultHiddenColumns: Record<string, boolean> } {
  return useMemo(() => {
    const dynamicColumns: ColumnDef<TData>[] = [];
    const defaultHiddenColumns: Record<string, boolean> = {};

    // For memoization to work properly with complex objects, we might want to be careful,
    // but extracting keys from data array directly is fine here.
    dictionaryConfigs.forEach(({ key, prefix }) => {
      const uniqueKeys = new Set<string>();

      // Extract all unique keys from the dictionary property across all rows
      data.forEach((row) => {
        const dict = row[key];
        if (dict && typeof dict === "object" && !Array.isArray(dict)) {
          Object.keys(dict).forEach((k) => uniqueKeys.add(k));
        }
      });

      // Create a column for each unique key
      Array.from(uniqueKeys).forEach((dictKey) => {
        const columnId = `${String(key)}_${dictKey}`;
        
        dynamicColumns.push({
          id: columnId,
          accessorFn: (row: TData) => {
            const dict = row[key] as Record<string, unknown> | undefined | null;
            return dict ? dict[dictKey] : undefined;
          },
          header: `${prefix}: ${dictKey}`,
          cell: ({ getValue }) => {
            const val = getValue();
            if (val === null || val === undefined) return "-";
            if (typeof val === "object") return JSON.stringify(val);
            return String(val);
          },
        });

        // Hide dynamic columns by default to prevent clutter
        defaultHiddenColumns[columnId] = false;
      });
    });

    return { dynamicColumns, defaultHiddenColumns };
  }, [data, dictionaryConfigs]);
}
