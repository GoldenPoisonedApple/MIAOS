import React from "react";
import styles from "./Badge.module.css";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: "waiting" | "running" | "succeeded" | "failed" | string;
}

export const Badge = ({ status, className = "", ...props }: BadgeProps) => {
  const statusClass = styles[status.toLowerCase()] || styles.default;

  return (
    <span className={`${styles.badge} ${statusClass} ${className}`} {...props}>
      {status}
    </span>
  );
};
