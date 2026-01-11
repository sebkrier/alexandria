"use client";

import { clsx } from "clsx";
import type { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  color?: string;
  variant?: "solid" | "outline";
  size?: "sm" | "md";
  className?: string;
}

export function Badge({ children, color, variant = "solid", size = "sm", className }: BadgeProps) {
  const baseStyles = "inline-flex items-center font-medium rounded-full";

  const sizes = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-sm",
  };

  const variants = {
    solid: "bg-dark-hover text-dark-text",
    outline: "border border-dark-border text-dark-muted",
  };

  const style = color
    ? { backgroundColor: variant === "solid" ? `${color}20` : "transparent", color, borderColor: color }
    : {};

  return (
    <span className={clsx(baseStyles, sizes[size], variants[variant], className)} style={style}>
      {children}
    </span>
  );
}
