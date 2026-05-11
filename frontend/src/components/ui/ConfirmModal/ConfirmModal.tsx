import React from "react";
import { Modal } from "../Modal/Modal";
import { Button } from "../Button/Button";

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  isConfirming: boolean;
}

export const ConfirmModal = ({ isOpen, onClose, onConfirm, title, message, isConfirming }: ConfirmModalProps) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="400px">
      <p style={{ marginBottom: "24px" }}>{message}</p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", borderTop: "1px solid var(--border)", paddingTop: "24px", marginTop: "24px" }}>
        <Button variant="outline" onClick={onClose} disabled={isConfirming}>
          キャンセル
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={isConfirming}>
          {isConfirming ? "処理中..." : "削除する"}
        </Button>
      </div>
    </Modal>
  );
};
