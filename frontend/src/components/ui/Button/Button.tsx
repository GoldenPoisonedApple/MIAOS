import React from "react";
import styles from "./Button.module.css";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "danger" | "secondary" | "outline";
}

export const Button = ({ variant = "primary", className = "", children, ...props }: ButtonProps) => {
  const variantClass = styles[variant] || styles.primary;

  return (
    <button className={`${styles.button} ${variantClass} ${className}`} {...props}>
      {children}
    </button>
  );
};
