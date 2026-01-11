"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { clsx } from "clsx";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-dark-text mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={id}
          className={clsx(
            "w-full px-3 py-2 bg-dark-surface border rounded-lg text-dark-text placeholder-dark-muted",
            "focus:outline-none focus:ring-2 focus:ring-article-blue focus:border-transparent",
            "transition-colors",
            error ? "border-article-red" : "border-dark-border",
            className
          )}
          {...props}
        />
        {error && <p className="mt-1.5 text-sm text-article-red">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";
