import type { Column, RowData, Table } from "@tanstack/react-table";

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

/**
 * 列の text-align を決定する。
 * meta.align があれば優先。なければ全行の生値から数値列か推論する。
 */
export function resolveColumnAlign<TData extends RowData>(
  column: Column<TData, unknown>,
  table: Table<TData>
): TableColumnAlign {
  const explicit = column.columnDef.meta?.align;
  if (explicit) return explicit;

  if (column.id === "select") return "center";

  const values = table.getRowModel().rows.map((row) => row.getValue(column.id));
  return inferAlignFromValues(values);
}
