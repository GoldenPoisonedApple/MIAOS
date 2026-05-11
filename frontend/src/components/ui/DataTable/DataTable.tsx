import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type VisibilityState,
  type ColumnOrderState,
  type Header,
  type Cell,
} from "@tanstack/react-table";
import { useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
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

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: import("@tanstack/react-table").OnChangeFn<RowSelectionState>;
}

// Draggable Header Cell Component
function DraggableHeader<TData, TValue>({ header }: { header: Header<TData, TValue> }) {
  const { attributes, isDragging, listeners, setNodeRef, transform, transition } = useSortable({
    id: header.column.id,
  });

  const style = {
    opacity: isDragging ? 0.8 : 1,
    position: "relative" as const,
    transform: CSS.Translate.toString(transform), // Translate instead of Transform to keep other styling
    transition,
    whiteSpace: "nowrap" as const,
    width: header.column.getSize(),
    zIndex: isDragging ? 2 : 1,
  };

  // Do not make the select column draggable
  if (header.column.id === "select") {
    return (
      <th key={header.id} colSpan={header.colSpan}>
        {flexRender(header.column.columnDef.header, header.getContext())}
      </th>
    );
  }

  return (
    <th key={header.id} colSpan={header.colSpan} ref={setNodeRef} style={style}>
      <div className={styles.headerContent}>
        <div {...attributes} {...listeners} className={styles.dragHandle}>
          ⋮⋮
        </div>
        {flexRender(header.column.columnDef.header, header.getContext())}
      </div>
    </th>
  );
}

// Draggable Body Cell Component (To follow column order visually)
function SortableCell<TData, TValue>({ cell }: { cell: Cell<TData, TValue> }) {
  const { isDragging, setNodeRef, transform, transition } = useSortable({
    id: cell.column.id,
  });

  const style = {
    opacity: isDragging ? 0.8 : 1,
    position: "relative" as const,
    transform: CSS.Translate.toString(transform),
    transition,
    width: cell.column.getSize(),
    zIndex: isDragging ? 2 : 1,
  };

  if (cell.column.id === "select") {
    return (
      <td key={cell.id}>
        {flexRender(cell.column.columnDef.cell, cell.getContext())}
      </td>
    );
  }

  return (
    <td key={cell.id} ref={setNodeRef} style={style}>
      {flexRender(cell.column.columnDef.cell, cell.getContext())}
    </td>
  );
}


export function DataTable<TData, TValue>({
  columns,
  data,
  rowSelection,
  onRowSelectionChange,
}: DataTableProps<TData, TValue>) {
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  
  // Set initial column order based on the provided columns
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(
    columns.map((c) => c.id as string)
  );

  const table = useReactTable({
    data,
    columns,
    state: {
      rowSelection,
      columnVisibility,
      columnOrder,
    },
    enableRowSelection: true,
    onRowSelectionChange,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnOrderChange: setColumnOrder,
    getCoreRowModel: getCoreRowModel(),
  });

  // Setup DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5, // Start dragging after moving 5px (prevents accidental drag when clicking)
      },
    }),
    useSensor(KeyboardSensor)
  );

  // Handle drag end
  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (active && over && active.id !== over.id) {
      setColumnOrder((columnOrder) => {
        const oldIndex = columnOrder.indexOf(active.id as string);
        const newIndex = columnOrder.indexOf(over.id as string);
        return arrayMove(columnOrder, oldIndex, newIndex); // Reorder the array
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
                    items={columnOrder}
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
                    <SortableContext
                      items={columnOrder}
                      strategy={horizontalListSortingStrategy}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <SortableCell key={cell.id} cell={cell} />
                      ))}
                    </SortableContext>
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
