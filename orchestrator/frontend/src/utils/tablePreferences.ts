import type {
  ColumnOrderState,
  SortingState,
  VisibilityState,
} from "@tanstack/react-table";

export interface TablePreferencesV1 {
  version: 1;
  columnVisibility: VisibilityState;
  columnOrder: ColumnOrderState;
  sorting: SortingState;
}

export interface TablePreferencesDefaults {
  columnVisibility: VisibilityState;
  columnOrder: ColumnOrderState;
  sorting: SortingState;
}

const STORAGE_PREFIX = "app:table-preferences:v1:";

export function buildStorageKey(storageKey: string): string {
  return `${STORAGE_PREFIX}${storageKey}`;
}

function isSortingState(value: unknown): value is SortingState {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        item &&
        typeof item === "object" &&
        typeof (item as { id?: unknown }).id === "string" &&
        typeof (item as { desc?: unknown }).desc === "boolean"
    )
  );
}

function isVisibilityState(value: unknown): value is VisibilityState {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === "boolean")
  );
}

function isColumnOrderState(value: unknown): value is ColumnOrderState {
  return Array.isArray(value) && value.every((id) => typeof id === "string");
}

function parseTablePreferences(raw: string): TablePreferencesV1 | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      (parsed as { version?: unknown }).version === 1 &&
      isVisibilityState((parsed as TablePreferencesV1).columnVisibility) &&
      isColumnOrderState((parsed as TablePreferencesV1).columnOrder) &&
      isSortingState((parsed as TablePreferencesV1).sorting)
    ) {
      return parsed as TablePreferencesV1;
    }
  } catch {
    // 破損データは無視
  }
  return null;
}

export function loadTablePreferences(storageKey: string): TablePreferencesV1 | null {
  try {
    const raw = localStorage.getItem(buildStorageKey(storageKey));
    if (!raw) return null;
    return parseTablePreferences(raw);
  } catch {
    return null;
  }
}

export function saveTablePreferences(storageKey: string, prefs: TablePreferencesV1): void {
  try {
    localStorage.setItem(buildStorageKey(storageKey), JSON.stringify(prefs));
  } catch {
    // quota 超過・プライベートブラウズ等は握りつぶす
  }
}

function mergeColumnVisibility(
  saved: VisibilityState,
  defaults: VisibilityState,
  columnIds: string[]
): VisibilityState {
  const result: VisibilityState = {};
  for (const id of columnIds) {
    if (id in saved) {
      result[id] = saved[id];
    } else if (id in defaults) {
      result[id] = defaults[id];
    }
  }
  return result;
}

function mergeColumnOrder(saved: ColumnOrderState, columnIds: string[]): ColumnOrderState {
  const currentSet = new Set(columnIds);
  const filtered = saved.filter((id) => currentSet.has(id));
  const savedSet = new Set(filtered);
  const appended = columnIds.filter((id) => !savedSet.has(id));
  return [...filtered, ...appended];
}

function mergeSorting(
  saved: SortingState,
  defaults: SortingState,
  columnIds: string[]
): SortingState {
  const columnIdSet = new Set(columnIds);
  const valid = saved.filter((s) => columnIdSet.has(s.id));
  return valid.length > 0 ? valid : defaults;
}

export function mergeTablePreferences(
  saved: TablePreferencesV1 | null,
  defaults: TablePreferencesDefaults,
  columnIds: string[]
): TablePreferencesV1 {
  if (!saved) {
    return {
      version: 1,
      columnVisibility: mergeColumnVisibility({}, defaults.columnVisibility, columnIds),
      columnOrder: mergeColumnOrder(defaults.columnOrder, columnIds),
      sorting: mergeSorting(defaults.sorting, defaults.sorting, columnIds),
    };
  }

  return {
    version: 1,
    columnVisibility: mergeColumnVisibility(
      saved.columnVisibility,
      defaults.columnVisibility,
      columnIds
    ),
    columnOrder: mergeColumnOrder(saved.columnOrder, columnIds),
    sorting: mergeSorting(saved.sorting, defaults.sorting, columnIds),
  };
}

export function getColumnId<TData, TValue>(col: import("@tanstack/react-table").ColumnDef<TData, TValue>): string | undefined {
  if (col.id) return col.id;
  if ("accessorKey" in col && typeof col.accessorKey === "string") {
    return col.accessorKey;
  }
  return undefined;
}
