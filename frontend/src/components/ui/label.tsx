"use client";

import { LabelHTMLAttributes } from "react";

interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  children: React.ReactNode;
}

export function Label({ children, className = "", ...props }: LabelProps) {
  return (
    <label className={`block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5 ${className}`} {...props}>
      {children}
    </label>
  );
}