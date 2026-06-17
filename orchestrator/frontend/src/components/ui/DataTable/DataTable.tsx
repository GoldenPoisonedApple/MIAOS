import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type VisibilityState,
  type ColumnOrderState,
  type Header,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { restrictToHorizontalAxis } from "@dnd-kit/modifiers";
import styles from "./DataTable.module.css";
import { ColumnVisibilityMenu } from "../ColumnVisibilityMenu/ColumnVisibilityMenu";
import { useTablePreferences } from "../../../hooks/useTablePreferences";
import { getColumnId } from "../../../utils/tablePreferences";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: import("@tanstack/react-table").OnChangeFn<RowSelectionState>;
  initialColumnVisibility?: VisibilityState;
  /** 初期ソート（例: 実験一覧の ID 昇順） */
  initialSorting?: SortingState;
  /** 行 ID をデータの識別子に固定（ソート後も選択・削除が正しく動く） */
  getRowId?: (row: TData) => string;
  /** 指定時は表示カラム・列順・ソートを localStorage に永続化 */
  storageKey?: string;
}

// Draggable Header Cell Component
function DraggableHeader<TData, TValue>({ header }: { header: Header<TData, TValue> }) {
  const { attributes, isDragging, listeners, setNodeRef, transform, transition } = useSortable({
    id: header.column.id,
  });

  const style = {
    opacity: isDragging ? 0.8 : 1,
    position: "relative" as const,
    transform: CSS.Translate.toString(transform),
    transition,
    whiteSpace: "nowrap" as const,
    zIndex: isDragging ? 2 : 1,
  };

  // Do not make the select column draggable
  if (header.column.id === "select") {
    return (
      <th key={header.id} colSpan={header.colSpan} className={styles.thSelect}>
        {flexRender(header.column.columnDef.header, header.getContext())}
      </th>
    );
  }

  const { table } = header.getContext();
  const canSort = header.column.getCanSort();
  const sorted = header.column.getIsSorted();

  return (
    <th key={header.id} colSpan={header.colSpan} ref={setNodeRef} style={style} className={styles.th}>
      <div className={styles.headerContent}>
        <div {...attributes} {...listeners} className={styles.dragHandle}>
          ⋮⋮
        </div>
        <div className={styles.headerMain}>
          <span className={styles.headerTitle}>{flexRender(header.column.columnDef.header, header.getContext())}</span>
          {canSort && (
            <span className={styles.sortGroup}>
              <button
                type="button"
                className={sorted === "asc" ? styles.sortBtnActive : styles.sortBtn}
                aria-label="昇順で並べ替え"
                onClick={(e) => {
                  e.stopPropagation();
                  table.setSorting([{ id: header.column.id, desc: false }]);
                }}
              >
                ▲
              </button>
              <button
                type="button"
                className={sorted === "desc" ? styles.sortBtnActive : styles.sortBtn}
                aria-label="降順で並べ替え"
                onClick={(e) => {
                  e.stopPropagation();
                  table.setSorting([{ id: header.column.id, desc: true }]);
                }}
              >
                ▼
              </button>
            </span>
          )}
        </div>
      </div>
    </th>
  );
}

// Removed SortableCell to prevent duplicate useSortable IDs in DndContext.
// Body cells will be naturally reordered by TanStack Table after drag ends.


export function DataTable<TData, TValue>({
  columns,
  data,
  rowSelection,
  onRowSelectionChange,
  initialColumnVisibility = {},
  initialSorting = [],
  getRowId,
  storageKey,
}: DataTableProps<TData, TValue>) {
  const columnIds = useMemo(
    () => columns.map((col) => getColumnId(col)).filter((id): id is string => id !== undefined),
    [columns]
  );

  const preferenceDefaults = useMemo(
    () => ({
      columnVisibility: initialColumnVisibility,
      columnOrder: [] as ColumnOrderState,
      sorting: initialSorting,
    }),
    [initialColumnVisibility, initialSorting]
  );

  const {
    columnVisibility,
    columnOrder,
    sorting,
    onColumnVisibilityChange,
    onColumnOrderChange,
    onSortingChange,
  } = useTablePreferences(storageKey, preferenceDefaults, columnIds);

  const table = useReactTable({
    data,
    columns,
    state: {
      rowSelection,
      columnVisibility,
      columnOrder,
      sorting,
    },
    enableRowSelection: true,
    onRowSelectionChange,
    onColumnVisibilityChange,
    onColumnOrderChange,
    onSortingChange,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: getRowId ? (original) => getRowId(original) : undefined,
  });

  const currentColumnIds = table.getAllLeafColumns().map((c) => c.id);

  // Setup DnD sensors
  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 5, // Start dragging after moving 5px (prevents accidental drag when clicking)
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor)
  );

  // Handle drag end
  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (active && over && active.id !== over.id) {
      onColumnOrderChange(() => {
        const oldIndex = currentColumnIds.indexOf(active.id as string);
        const newIndex = currentColumnIds.indexOf(over.id as string);
        return arrayMove(currentColumnIds, oldIndex, newIndex); // Reorder the array
      });
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <ColumnVisibilityMenu table={table} />
      </div>

      <div className={styles.tableWrapper}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToHorizontalAxis]}
        >
          <table className={styles.dataTable}>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  <SortableContext
                    items={currentColumnIds}
                    strategy={horizontalListSortingStrategy}
                  >
                    {headerGroup.headers.map((header) => (
                      <DraggableHeader key={header.id} header={header} />
                    ))}
                  </SortableContext>
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.length > 0 ? (
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
  <td key={cell.id} style={{ textAlign: cell.column.id === "select" ? "center" : "left" }}>
    {flexRender(cell.column.columnDef.cell, cell.getContext())}
  </td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={columns.length} className={styles.noData}>
                    データがありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DndContext>
      </div>
    </div>
  );
}
