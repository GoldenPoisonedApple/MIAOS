import React, { useState } from "react";
import { Button } from "../Button/Button";
import styles from "./KeyValueEditor.module.css";

interface KeyValueEditorProps {
  value: Record<string, unknown> | undefined | null;
  onChange: (value: Record<string, unknown>) => void;
  disabled?: boolean;
}

interface Entry {
  id: string;
  key: string;
  value: string;
}

// Function to convert Record to array of entries
const recordToEntries = (record: Record<string, unknown> | undefined | null): Entry[] => {
  if (!record) return [];
  return Object.entries(record).map(([k, v]) => ({
    id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(),
    key: k,
    value: typeof v === "object" ? JSON.stringify(v) : String(v),
  }));
};

// Function to try parsing a string value to appropriate type (number, boolean, or string)
const parseValue = (val: string): unknown => {
  if (val.trim() === "") return "";
  if (val === "true") return true;
  if (val === "false") return false;
  if (!isNaN(Number(val))) return Number(val);
  
  // Try parsing JSON (arrays/objects) if it looks like one
  if ((val.startsWith("{") && val.endsWith("}")) || (val.startsWith("[") && val.endsWith("]"))) {
    try {
      return JSON.parse(val);
    } catch {
      return val;
    }
  }
  
  return val;
};

export const KeyValueEditor: React.FC<KeyValueEditorProps> = ({ value, onChange, disabled }) => {
  const [entries, setEntries] = useState<Entry[]>(recordToEntries(value));

  // Sync internal state to parent when it changes
  const notifyChange = (newEntries: Entry[]) => {
    const newRecord: Record<string, unknown> = {};
    newEntries.forEach((entry) => {
      if (entry.key.trim() !== "") {
        newRecord[entry.key.trim()] = parseValue(entry.value);
      }
    });
    onChange(newRecord);
  };

  const handleAdd = () => {
    const newEntries = [
      ...entries,
      { id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(), key: "", value: "" },
    ];
    setEntries(newEntries);
    notifyChange(newEntries);
  };

  const handleRemove = (idToRemove: string) => {
    const newEntries = entries.filter((entry) => entry.id !== idToRemove);
    setEntries(newEntries);
    notifyChange(newEntries);
  };

  const handleChange = (idToUpdate: string, field: "key" | "value", newValue: string) => {
    const newEntries = entries.map((entry) =>
      entry.id === idToUpdate ? { ...entry, [field]: newValue } : entry
    );
    setEntries(newEntries);
    notifyChange(newEntries);
  };

  return (
    <div className={styles.container}>
      {entries.length === 0 ? (
        <div className={styles.emptyState}>設定されていません</div>
      ) : (
        <div className={styles.list}>
          {entries.map((entry) => (
            <div key={entry.id} className={styles.row}>
              <input
                type="text"
                placeholder="Key"
                value={entry.key}
                onChange={(e) => handleChange(entry.id, "key", e.target.value)}
                disabled={disabled}
                className={styles.input}
              />
              <span className={styles.separator}>:</span>
              <input
                type="text"
                placeholder="Value"
                value={entry.value}
                onChange={(e) => handleChange(entry.id, "value", e.target.value)}
                disabled={disabled}
                className={styles.input}
              />
              <Button
                type="button"
                variant="danger"
                onClick={() => handleRemove(entry.id)}
                disabled={disabled}
                style={{ padding: "4px 8px", fontSize: "12px" }}
              >
                削除
              </Button>
            </div>
          ))}
        </div>
      )}
      <Button
        type="button"
        variant="outline"
        onClick={handleAdd}
        disabled={disabled}
        style={{ marginTop: "8px", alignSelf: "flex-start" }}
      >
        + 新しいパラメータを追加
      </Button>
    </div>
  );
};
