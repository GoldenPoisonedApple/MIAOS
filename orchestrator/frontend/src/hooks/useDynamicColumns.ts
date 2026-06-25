import { useMemo } from "react";
import type { ReactNode } from "react";
import type { ColumnDef } from "@tanstack/react-table";

export interface DictionaryCellRenderContext<TData extends Record<string, unknown>> {
  row: TData;
  sourceKey: keyof TData;
  dictKey: string;
  value: unknown;
}

export interface DictionaryConfig<TData extends Record<string, unknown>> {
  key: keyof TData;
  prefix: string;
  renderCell?: (ctx: DictionaryCellRenderContext<TData>) => ReactNode;
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
    dictionaryConfigs.forEach(({ key, prefix, renderCell }) => {
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
          meta: renderCell ? { align: "left" } : undefined,
          sortingFn: (rowA, rowB, columnId) => {
            const a = rowA.getValue(columnId);
            const b = rowB.getValue(columnId);
            const str = (v: unknown) =>
              v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
            return str(a).localeCompare(str(b), undefined, { numeric: true });
          },
          cell: ({ row, getValue }) => {
            const val = getValue();
            if (renderCell) {
              return renderCell({ row: row.original, sourceKey: key, dictKey, value: val });
            }
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
