import { useEffect, useRef, useState } from "react";
import { apiClient } from "../../../api/client";
import { Modal } from "../../../components/ui/Modal/Modal";
import styles from "./FilePreviewModal.module.css";

const MAX_TEXT_BYTES = 512 * 1024;

type PreviewMode = "loading" | "error" | "image" | "text" | "binary";

interface FilePreviewModalProps {
  objectKey: string | null;
  onClose: () => void;
}

function baseContentType(header: string | null): string {
  if (!header) return "application/octet-stream";
  return header.split(";")[0].trim().toLowerCase();
}

function fileNameFromKey(key: string): string {
  const i = key.lastIndexOf("/");
  return i >= 0 ? key.slice(i + 1) : key;
}

interface FilePreviewInnerProps {
  objectKey: string;
}

function FilePreviewInner({ objectKey }: FilePreviewInnerProps) {
  const [mode, setMode] = useState<PreviewMode>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<string>("application/octet-stream");
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const assignUrl = (blob: Blob) => {
      const url = URL.createObjectURL(blob);
      if (cancelled) {
        URL.revokeObjectURL(url);
        return;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
      objectUrlRef.current = url;
      setObjectUrl(url);
    };

    (async () => {
      const { data, error, response } = await apiClient.GET("/api/files/{key}", {
        params: { path: { key: objectKey } },
        parseAs: "blob",
      });

      if (cancelled) return;

      if (error || !response.ok || !data || !(data instanceof Blob)) {
        setMode("error");
        setErrorMessage(
          error ? String(error) : !response.ok ? `HTTP ${response.status}` : "ファイルを取得できませんでした"
        );
        return;
      }

      const ct = baseContentType(response.headers.get("Content-Type"));

      if (ct.startsWith("image/")) {
        assignUrl(data);
        setContentType(ct);
        setMode("image");
        return;
      }

      const textLike =
        ct.startsWith("text/") || ct === "application/json" || ct === "application/javascript";

      if (textLike && data.size <= MAX_TEXT_BYTES) {
        try {
          const text = await data.text();
          if (cancelled) return;
          setTextContent(text);
          setContentType(ct);
          assignUrl(data);
          setMode("text");
        } catch {
          if (cancelled) return;
          assignUrl(data);
          setContentType(ct);
          setMode("binary");
        }
        return;
      }

      assignUrl(data);
      setContentType(ct);
      setMode("binary");
    })();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [objectKey]);

  return (
    <div className={styles.body}>
      {mode === "loading" && <p className={styles.loading}>読み込み中…</p>}
      {mode === "error" && <p className={styles.error}>{errorMessage ?? "エラーが発生しました"}</p>}
      {mode === "image" && objectUrl && (
        <div className={styles.imageWrap}>
          <img className={styles.image} src={objectUrl} alt={objectKey} />
        </div>
      )}
      {mode === "text" && textContent !== null && (
        <>
          <pre className={styles.pre}>{textContent}</pre>
          {objectUrl && (
            <a className={styles.download} href={objectUrl} download={fileNameFromKey(objectKey)}>
              ダウンロード
            </a>
          )}
        </>
      )}
      {mode === "binary" && (
        <div className={styles.binary}>
          <p>バイナリまたは大きなテキストファイルのため、ここではプレビューできません。</p>
          <p className={styles.meta}>Content-Type: {contentType}</p>
          {objectUrl && (
            <a className={styles.download} href={objectUrl} download={fileNameFromKey(objectKey)}>
              ダウンロード
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export function FilePreviewModal({ objectKey, onClose }: FilePreviewModalProps) {
  const isOpen = objectKey !== null;
  const title = objectKey ? `ファイル: ${fileNameFromKey(objectKey)}` : "ファイル";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="min(920px, 96vw)">
      {objectKey ? <FilePreviewInner key={objectKey} objectKey={objectKey} /> : null}
    </Modal>
  );
}
