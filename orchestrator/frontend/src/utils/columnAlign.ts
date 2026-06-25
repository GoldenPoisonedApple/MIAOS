import type { Column, ColumnDef, RowData, Table } from "@tanstack/react-table";
import { getColumnId } from "./tablePreferences";

export type TableColumnAlign = "left" | "right" | "center";

/** セル値が数値列として右寄せ対象か（null / undefined は推論時に無視） */
export function isNumericCellValue(value: unknown): boolean {
  return typeof value === "number" && !Number.isNaN(value);
}

/** 非 null 値がすべて数値なら right、それ以外は left */
export function inferAlignFromValues(values: unknown[]): TableColumnAlign {
  const meaningful = values.filter((v) => v !== null && v !== undefined);
  if (meaningful.length === 0) return "left";
  return meaningful.every(isNumericCellValue) ? "right" : "left";
}

function resolveColumnAlignForColumn<TData extends RowData>(
  column: Column<TData, unknown>,
  rows: ReturnType<Table<TData>["getRowModel"]>["rows"]
): TableColumnAlign {
  const explicit = column.columnDef.meta?.align;
  if (explicit) return explicit;

  if (column.id === "select") return "center";

  const values = rows.map((row) => row.getValue(column.id));
  return inferAlignFromValues(values);
}

function getCellValue<TData extends RowData>(
  row: TData,
  columnDef: ColumnDef<TData, unknown>,
  rowIndex: number
): unknown {
  if ("accessorFn" in columnDef && typeof columnDef.accessorFn === "function") {
    return columnDef.accessorFn(row, rowIndex);
  }
  if ("accessorKey" in columnDef && typeof columnDef.accessorKey === "string") {
    return row[columnDef.accessorKey as keyof TData];
  }
  return undefined;
}

/**
 * 全列の text-align を 1 回の走査でまとめて決定する（セル単位呼び出しの O(rows²) を避ける）。
 */
export function buildColumnAlignMapFromData<TData extends RowData>(
  data: TData[],
  columns: ColumnDef<TData, unknown>[]
): Record<string, TableColumnAlign> {
  const result: Record<string, TableColumnAlign> = {};

  for (const columnDef of columns) {
    const id = getColumnId(columnDef);
    if (!id) continue;

    const explicit = columnDef.meta?.align;
    if (explicit) {
      result[id] = explicit;
      continue;
    }
    if (id === "select") {
      result[id] = "center";
      continue;
    }

    const values = data.map((row, index) => getCellValue(row, columnDef, index));
    result[id] = inferAlignFromValues(values);
  }

  return result;
}

/**
 * 全列の text-align を 1 回の走査でまとめて決定する（セル単位呼び出しの O(rows²) を避ける）。
 */
export function buildColumnAlignMap<TData extends RowData>(
  table: Table<TData>
): Record<string, TableColumnAlign> {
  const rows = table.getRowModel().rows;
  const result: Record<string, TableColumnAlign> = {};

  for (const column of table.getAllLeafColumns()) {
    result[column.id] = resolveColumnAlignForColumn(column, rows);
  }

  return result;
}

/**
 * 列の text-align を決定する。
 * meta.align があれば優先。なければ全行の生値から数値列か推論する。
 */
export function resolveColumnAlign<TData extends RowData>(
  column: Column<TData, unknown>,
  table: Table<TData>
): TableColumnAlign {
  return resolveColumnAlignForColumn(column, table.getRowModel().rows);
}
