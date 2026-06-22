/** 同一オリジンの GET /api/files/{key}（キーは 1 パスセグメントとしてエンコード） */
export function fileApiPath(objectKey: string): string {
  return `/api/files/${encodeURIComponent(objectKey)}`;
}

export function isPngObjectKey(objectKey: string): boolean {
  return /\.png$/i.test(objectKey);
}
