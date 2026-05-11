interface Props {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  isConfirming: boolean;
}

export const ConfirmModal = ({ isOpen, onClose, onConfirm, title, message, isConfirming }: Props) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "400px" }}>
        <h2>{title}</h2>
        <p style={{ marginBottom: "24px" }}>{message}</p>

        <div className="modal-actions">
          <button type="button" onClick={onClose} className="button cancel-button" disabled={isConfirming}>
            キャンセル
          </button>
          <button type="button" onClick={onConfirm} className="button delete-button" disabled={isConfirming} style={{ padding: "8px 16px" }}>
            {isConfirming ? "処理中..." : "削除する"}
          </button>
        </div>
      </div>
    </div>
  );
};
