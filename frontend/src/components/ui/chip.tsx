"use client";

import type { ButtonHTMLAttributes } from "react";

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

/**
 * Pill toggle chip for filters (work modes, cities). Active state is brand navy.
 */
export function Chip({ active = false, className = "", children, ...props }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`
        inline-flex items-center rounded-full px-3.5 py-1.5 text-xs font-medium border
        transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1
        ${
          active
            ? "bg-indigo-700 text-white border-indigo-700 shadow-sm"
            : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:bg-transparent dark:text-slate-300 dark:hover:bg-slate-800"
        }
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}
