import "@tanstack/react-table";
import type { TableColumnAlign } from "../utils/columnAlign";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    align?: TableColumnAlign;
  }
}
