import { useState, useRef, useEffect } from "react";
import type { Table } from "@tanstack/react-table";
import { Button } from "../Button/Button";
import styles from "./ColumnVisibilityMenu.module.css";

interface Props<TData> {
  table: Table<TData>;
}

export function ColumnVisibilityMenu<TData>({ table }: Props<TData>) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className={styles.container} ref={menuRef}>
      <Button variant="outline" onClick={() => setIsOpen(!isOpen)}>
        表示カラム
      </Button>

      {isOpen && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={table.getIsAllColumnsVisible()}
                onChange={table.getToggleAllColumnsVisibilityHandler()}
              />
              すべて表示
            </label>
          </div>
          <div className={styles.columnList}>
            {table.getAllLeafColumns().map((column) => {
              if (column.id === "select" || column.id === "actions") return null;

              return (
                <label key={column.id} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                  />
                  {typeof column.columnDef.header === "string" 
                    ? column.columnDef.header 
                    : column.id}
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
