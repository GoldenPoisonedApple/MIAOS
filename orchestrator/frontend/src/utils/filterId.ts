export const FILTER_ID_RE = /^[a-zA-Z0-9_-]+$/;

/** ファイル名（拡張子 .png 除く）からフィルタ ID を導出する。不正な場合は null */
export function deriveFilterId(filename: string): string | null {
  const base = filename.replace(/\.png$/i, "");
  return FILTER_ID_RE.test(base) ? base : null;
}

export function isValidFilterId(id: string): boolean {
  return FILTER_ID_RE.test(id);
}
