"use client";

import clsx from "clsx";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
  children: React.ReactNode;
}

export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "px-4 py-2 rounded-lg text-sm font-semibold uppercase tracking-wide transition-smooth",
        variant === "primary" &&
          "bg-accent-primary text-bg-primary hover:opacity-90 hover:shadow-neon",
        variant === "secondary" &&
          "bg-bg-hover hover:bg-bg-tertiary border border-border text-text-primary",
        variant === "danger" &&
          "bg-accent-danger text-white hover:opacity-90 hover:shadow-danger",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

