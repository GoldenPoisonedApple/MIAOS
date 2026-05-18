/** 同一オリジンの GET /api/files/{key}（キーは 1 パスセグメントとしてエンコード） */
export function fileApiPath(objectKey: string): string {
  return `/api/files/${encodeURIComponent(objectKey)}`;
}
